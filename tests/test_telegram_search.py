import unittest
from backend.apps.telegram_search.parser import parse, bundle

HTML = b'''<div class="page_header"><div class="name">Example</div></div><div class="history">
<div class="message service"><div class="body">1 January 2026</div></div>
<div class="message default" id="message1"><div class="from_name">Alice</div><div class="date" title="1 January 2026, 10:20:30">edited 10:20</div><div class="text">Hello<br>world<script>evil()</script><a href="https://example.invalid">link</a></div></div>
<div class="message joined" id="message2"><div class="date" title="1 January 2026, 10:21:00"></div><div class="text">Second</div></div></div>'''

class ParserTests(unittest.TestCase):
    def test_structure_and_inert_html(self):
        result = parse(HTML)
        self.assertEqual(len(result['messages']), 3)
        message = result['messages'][1]
        self.assertEqual(message['timestamp'], '2026-01-01T10:20:30')
        self.assertIn('Hello\nworld', message['text'])
        self.assertNotIn('evil', message['text'])
        self.assertEqual(result['messages'][2]['author'], 'Alice')

    def test_unknown_and_duplicate(self):
        with self.assertRaises(ValueError): parse(b'<html>other</html>')
        with self.assertRaises(ValueError): parse(HTML.replace(b'message2', b'message1'))
        result = bundle([('a.html', HTML), ('b.html', HTML)])
        self.assertEqual(result['duplicates'], 2)

    def test_invalid_date_warns(self):
        result = parse(HTML.replace(b'1 January 2026, 10:21:00', b'invalid'))
        self.assertEqual(len(result['warnings']), 1)

class RagIntegrationTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from app import db
        from backend.apps.rag import service, embeddings
        self.db, self.service = db, service
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = db.DB_PATH
        self.old_root = service.config.RAG_SOURCE_DIR
        db.DB_PATH = Path(self.tmp.name)/'db.sqlite'
        service.config.RAG_SOURCE_DIR = Path(self.tmp.name)/'sources'
        db.init_db(); self.profile = db.ensure_default_profile()
        self.patch = patch.object(service, '_embedding_provider', return_value=embeddings.LocalHashEmbeddingProvider())
        self.patch.start()
        self.path = service.source_dir(self.profile)/'messages.html'
        self.path.write_bytes(HTML)

    def tearDown(self):
        self.patch.stop(); self.db.DB_PATH = self.old_db
        self.service.config.RAG_SOURCE_DIR = self.old_root; self.tmp.cleanup()

    def test_ingest_search_provenance_delete(self):
        r = self.service.ingest_sources(self.profile)
        self.assertEqual(r['indexed'], 1, r)
        chunks = self.db.list_rag_chunks(self.profile)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[1]['chunk_metadata']['author'], 'Alice')
        result = self.service.search(self.profile, 'Hello world')
        self.assertTrue(result)
        self.assertIn('Message ID: message1', result[0]['content'])
        self.assertEqual(self.service.search(self.profile, 'Hello world 2026-02-01'), [])
        self.assertTrue(self.service.search(self.profile, 'Hello world 01.01.2026'))
        other = self.db.create_profile('Other')['id']
        self.assertFalse(self.service.search(other, 'Hello world'))
        self.assertEqual(self.service.ingest_sources(self.profile)['skipped'], 1)
        self.service.delete_file(self.profile, 'messages.html')
        self.assertFalse(self.db.list_rag_chunks(self.profile))

    def test_date_bounds_and_long_messages(self):
        from backend.apps.telegram_search.parser import date_bounds, rag_message_chunks
        self.assertEqual(date_bounds('за июль 2026'), ('2026-07-01', '2026-07-31'))
        self.assertEqual(date_bounds('02.01.2026\n01.01.2026'), ('2026-01-02','2026-01-02'))
        with self.assertRaises(ValueError): date_bounds('31.02.2026')
        parsed = parse(HTML.replace(b'Second', b'x ' * 3000))
        parts = rag_message_chunks(parsed, self.service._chunk_text)
        self.assertGreater(len(parts), 3)
        self.assertTrue(all('Date:' in t and 'Message ID:' in t for t, _ in parts))

    def test_remote_provider_rejected_before_embedding(self):
        from dataclasses import replace
        from unittest.mock import patch
        from fastapi import HTTPException
        settings = replace(self.service.config.SETTINGS, base_url='https://example.invalid/v1')
        with patch.object(self.service.config, 'SETTINGS', settings):
            with self.assertRaises(HTTPException): self.service.ingest_sources(self.profile)

    def test_conversational_followups(self):
        from backend.apps.chat.routes import compose_rag_query
        topic = 'Найди сообщения про Hello world'
        for followup in ['За какие даты?', 'Теперь за июль 2026', 'Только 01.01.2026', 'Ключевые слова Hello']:
            query = compose_rag_query(followup, [topic])
            self.assertIn(topic, query)
            self.assertTrue(query.startswith(followup))

    def test_upload_validation_and_numeric_timestamp(self):
        from io import BytesIO
        from fastapi import UploadFile
        result = self.service.save_uploaded_files(self.profile, [
            UploadFile(filename='bad.html', file=BytesIO(b'<html>wrong</html>')),
            UploadFile(filename='good.html', file=BytesIO(HTML))])
        self.assertEqual(len(result['saved']), 1)
        self.assertEqual(len(result['errors']), 1)
        parsed = parse(HTML.replace(b'1 January 2026, 10:20:30', b'01.01.2026 10:20:30 UTC+03:00'))
        self.assertEqual(parsed['messages'][1]['timestamp'], '2026-01-01T10:20:30')
        self.assertIn('UTC+03:00', parsed['messages'][1]['raw_date'])

    def test_remote_reindex_rejected(self):
        from dataclasses import replace
        from unittest.mock import Mock
        from fastapi import HTTPException
        from backend.apps.rag.embeddings import LocalHashEmbeddingProvider
        self.service.ingest_sources(self.profile)
        remote = Mock()
        remote.descriptor = replace(LocalHashEmbeddingProvider().descriptor, provider='ollama')
        with self.assertRaises(HTTPException):
            self.service.reindex_embeddings(self.profile, provider=remote)
        remote.embed.assert_not_called()

    def test_open_date_intervals(self):
        from backend.apps.telegram_search.parser import date_bounds
        self.assertEqual(date_bounds('после 01.01.2026'), ('2026-01-02', '9999-12-31'))
        self.assertEqual(date_bounds('до 02.01.2026'), ('0001-01-01', '2026-01-02'))
        self.assertEqual(date_bounds('начиная с 01.01.2026'), ('2026-01-01', '9999-12-31'))
        self.assertEqual(date_bounds('раньше 02.01.2026'), ('0001-01-01', '2026-01-01'))
        self.service.ingest_sources(self.profile)
        self.assertFalse(self.service.search(self.profile, 'Hello world после 01.01.2026'))
        self.assertTrue(self.service.search(self.profile, 'Hello world до 02.01.2026'))

    def test_locality_guard_precedes_model_routing(self):
        from dataclasses import replace
        from unittest.mock import patch
        from fastapi import HTTPException
        from app.schemas import ChatRequest
        from backend.apps.chat.routes import _prepare_chat_request
        self.service.ingest_sources(self.profile)
        session = self.db.create_session(self.profile, 'guard', 'qwen2.5:3b')
        settings = replace(self.service.config.SETTINGS, base_url='https://example.invalid/v1')
        with patch.object(self.service.config, 'SETTINGS', settings), patch.object(self.db, 'effective_settings') as effective:
            with self.assertRaises(HTTPException) as error:
                _prepare_chat_request(ChatRequest(profile_id=self.profile, session_id=session['id'], query='Hello', model='qwen2.5:3b'))
            self.assertEqual(error.exception.status_code, 409)
            effective.assert_not_called()

    def test_explicit_message_id_excludes_distractors(self):
        self.service.ingest_sources(self.profile)
        for query in ['Что написано в message1?', 'Текст сообщения 1', 'ID: 1']:
            result = self.service.search(self.profile, query)
            self.assertTrue(result)
            self.assertTrue(all(m['metadata']['message_id'] == 'message1' for m in result))
        self.assertFalse(self.service.search(self.profile, 'Текст message999999'))
        self.assertTrue(self.service.search(self.profile, 'Сообщения 01.01.2026'))
        self.assertTrue(self.service.search(self.profile, 'Сообщения 2026-01-01'))

    def test_negated_date_bounds_and_source_collisions(self):
        from backend.apps.telegram_search.parser import date_bounds
        self.assertEqual(date_bounds('не раньше 02.01.2026'), ('2026-01-02', '9999-12-31'))
        self.assertEqual(date_bounds('не позже 02.01.2026'), ('0001-01-01', '2026-01-02'))
        (self.path.parent/'other.html').write_bytes(HTML.replace(b'Hello', b'Other'))
        self.service.ingest_sources(self.profile)
        result = self.service.search(self.profile, 'Текст message1 из other.html')
        self.assertTrue(result)
        self.assertTrue(all(m['source_id']=='other.html' for m in result))
        result = self.service.search(self.profile, 'Текст message1 из messages.html')
        self.assertTrue(all(m['source_id']=='messages.html' for m in result))
        self.assertFalse(self.service.search(self.profile, 'Hello не раньше 02.01.2026'))

    def test_stream_upload_without_markdown_size_limits(self):
        from io import BytesIO
        from unittest.mock import patch
        from fastapi import UploadFile
        with patch.object(self.service, 'MAX_FILE_BYTES', 5), patch.object(self.service, 'MAX_UPLOAD_TOTAL_BYTES', 5):
            result = self.service.save_uploaded_files(self.profile, [UploadFile(filename='large.html', file=BytesIO(HTML))])
        self.assertFalse(result['errors'])
        self.assertEqual((self.path.parent/'large.html').read_bytes(), HTML)
        from contextlib import closing
        with closing(self.db._connect()) as conn:
            names = [row['name'] for row in conn.execute('PRAGMA index_list(document_embeddings)')]
        self.assertIn('idx_document_embeddings_chunk_model', names)

    def test_fragmented_utf8_stream(self):
        from io import BytesIO
        from backend.apps.telegram_search.parser import parse_stream
        class Fragmented(BytesIO):
            def read(self, size):
                return super().read(min(size, 1))
        raw = HTML.replace(b'Second', 'Привет'.encode())
        result = parse_stream(Fragmented(raw))
        self.assertEqual(result['messages'][2]['text'], 'Привет')

    def test_exact_quote_bypasses_top_k_and_keeps_full_text(self):
        self.path.write_bytes(HTML.replace(b'Hello', b'long_factual_marker ' * 1000))
        self.service.ingest_sources(self.profile)
        text = parse(self.path.read_bytes())['messages'][1]['text']
        reply = self.service.exact_telegram_quote(self.profile, 'Полный текст message1 из messages.html дословно')
        self.assertIn(text, reply)
        self.assertIsNone(self.service.exact_telegram_quote(self.profile, 'Объясни содержание message1'))
        self.assertIn('не найдено', self.service.exact_telegram_quote(self.profile, 'Полный текст message999'))

    def test_hashtag_spelling_normalization(self):
        self.path.write_bytes(HTML.replace(b'Hello', b'#BuildNotes Hello'))
        self.service.ingest_sources(self.profile)
        for query in ['хэштег Build Notes, Hello', '#build_notes Hello', '#BuildNotes Hello']:
            result = self.service.search(self.profile, query)
            self.assertTrue(result)
            self.assertTrue(all(m['metadata']['message_id']=='message1' for m in result))
        self.assertFalse(self.service.search(self.profile, 'хэштег Unknown Tag, Hello'))

    def test_tagged_technical_word_lookup(self):
        self.path.write_bytes(HTML.replace(b'Hello', b'#BuildNotes alpha_tool Hello').replace(b'Second', b'#BuildNotes beta_tool Second'))
        self.service.ingest_sources(self.profile)
        result = self.service.search(self.profile, '#BuildNotes сообщения про alpha_tool, какой стек и дата')
        self.assertTrue(result)
        self.assertTrue(all(m['metadata']['message_id']=='message1' for m in result))
