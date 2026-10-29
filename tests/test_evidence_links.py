import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, db
from backend.apps.rag import embeddings, service, routes
from backend.apps.rag.evidence_links import attach_links, links_requested
from backend.apps.telegram_search.links import telegram_permalink
from backend.apps.telegram_search.parser import parse, rag_message_chunks


class LinkUnitTests(unittest.TestCase):
    def test_permalink_accepts_only_explicit_message_addresses(self):
        for url in ['https://t.me/example_chat/42', 'https://t.me/c/123/42', 'https://t.me/example_chat/9/42']:
            self.assertEqual(telegram_permalink(url), url)
        for url in ['https://t.me/example_chat', 'https://t.me/+invite', 'javascript:alert(1)',
                    'https://evil.invalid/example_chat/42', 'https://t.me@evil.invalid/example_chat/42',
                    'https://t.me/example_chat/42?secret=x', 'https://t.me:443/example_chat/42',
                    'https://t.me/example_chat/0']:
            self.assertIsNone(telegram_permalink(url))

    def test_links_opt_in_and_no_fabricated_chat_mapping(self):
        self.assertTrue(links_requested('Найди ollama и сгенерируй ссылки'))
        self.assertFalse(links_requested('Найди ollama без ссылок'))
        candidates = [{'chunk_id': 1, 'chunk_metadata': {'format': 'telegram_html', 'message_id': 'message42'}}]
        evidence = [{'chunk_id': 1}]
        self.assertFalse(attach_links(evidence, candidates=candidates, query='ollama', profile_id=7, session_id=None))
        self.assertNotIn('links', evidence[0])
        self.assertTrue(attach_links(evidence, candidates=candidates, query='дай ссылки', profile_id=7, session_id='s?&'))
        self.assertEqual(evidence[0]['links'][0]['kind'], 'local_evidence')
        self.assertNotIn('t.me', evidence[0]['links'][0]['url'])
        self.assertTrue(evidence[0]['telegram_link_unavailable'])
        candidates[0]['chunk_metadata']['message_url'] = 'https://t.me/example_chat/42'
        attach_links(evidence, candidates=candidates, query='дай ссылки', profile_id=7, session_id=None)
        self.assertEqual(evidence[0]['links'][0]['url'], 'https://t.me/example_chat/42')

    def test_only_own_date_link_becomes_provenance(self):
        html = '''<div class="page_header"><div class="name">Example</div></div><div class="history">
<div class="message default" id="message1"><a class="date" href="https://t.me/example_chat/42" title="1 January 2026, 10:20:30"></a><div class="text">Text <a href="https://t.me/other_chat/99">other</a></div></div></div>'''
        parsed = parse(html.encode())
        self.assertEqual(parsed['messages'][0]['message_url'], 'https://t.me/example_chat/42')
        self.assertEqual(rag_message_chunks(parsed, lambda text: [text])[0][1]['message_url'], 'https://t.me/example_chat/42')
        no_own = parse(html.replace('href="https://t.me/example_chat/42"', '').encode())
        self.assertIsNone(no_own['messages'][0]['message_url'])


class LocalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for target, name, value in [(db, 'DB_PATH', Path(self.tmp.name)/'synthetic.sqlite'),
                                    (config, 'RAG_SOURCE_DIR', Path(self.tmp.name)/'sources')]:
            patcher = patch.object(target, name, value); patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch.object(service, '_embedding_provider', return_value=embeddings.LocalHashEmbeddingProvider())
        patcher.start(); self.addCleanup(patcher.stop)
        db.init_db(); self.profile = db.ensure_default_profile()
        (service.source_dir(self.profile)/'evidence.md').write_text('quartz <script>alert(1)</script>')
        service.ingest_sources(self.profile)
        self.chunk = db.list_rag_chunks(self.profile)[0]['chunk_id']
        app = FastAPI(); app.include_router(routes.router)
        self.client = TestClient(app); self.addCleanup(self.client.close)

    def test_local_viewer_is_inert_and_profile_scoped(self):
        response = self.client.get(f'/rag/evidence/{self.chunk}', params={'profile_id': self.profile})
        self.assertEqual(response.status_code, 200)
        self.assertIn('&lt;script&gt;', response.text)
        self.assertNotIn('<script>', response.text)
        self.assertIn("default-src 'none'", response.headers['content-security-policy'])
        self.assertEqual(response.headers['cache-control'], 'no-store')
        other = db.create_profile('Other')['id']
        self.assertEqual(self.client.get(f'/rag/evidence/{self.chunk}', params={'profile_id': other}).status_code, 404)
        session = db.create_session(other, 'Other', '')
        self.assertEqual(self.client.get(f'/rag/evidence/{self.chunk}', params={'profile_id': self.profile, 'session_id': session['id']}).status_code, 404)
