from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import config, db
from backend.apps.chat import knowledge_search_tasks as search_tasks, routes
from backend.apps.rag import embeddings, service as rag


class KnowledgeSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = patch.object(config, "SETTINGS", replace(config.SETTINGS, base_url="http://127.0.0.1:11434"))
        self.database = patch.object(db, "DB_PATH", Path(self.tmp.name) / "synthetic.sqlite")
        self.sources = patch.object(config, "RAG_SOURCE_DIR", Path(self.tmp.name) / "sources")
        self.provider = patch.object(rag, "_embedding_provider", return_value=embeddings.LocalHashEmbeddingProvider())
        for item in (self.settings, self.database, self.sources, self.provider):
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(self.tmp.cleanup)
        db.init_db()
        self.profile = db.ensure_default_profile()
        self.session = db.create_session(self.profile, "Synthetic", "")
        app = FastAPI()
        app.include_router(routes.router)
        self.client = TestClient(app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)
        self.addCleanup(search_tasks.reset)

    def search(self, query="quartz", **kwargs):
        return self.client.post("/chat/knowledge-search", json={
            "profile_id": self.profile, "session_id": self.session["id"], "query": query, **kwargs,
        })

    def index_markdown(self, text="Synthetic quartz evidence."):
        (rag.source_dir(self.profile) / "synthetic.md").write_text(text)
        rag.ingest_sources(self.profile)

    def test_deterministic_evidence_persists_without_any_generation_or_embedding(self):
        self.index_markdown("Synthetic quartz evidence.\nLiteral [LOCALGPT_DATA_ENVELOPE marker.")
        with patch.object(routes, "_prepare_chat_request") as prepare, \
             patch.object(routes.chat_service, "chat_completion_result") as complete, \
             patch.object(routes.chat_tasks, "start_chat_task") as task, \
             patch.object(rag, "_embed_texts") as embed:
            response = self.search()
        self.assertEqual(response.status_code, 200, response.text)
        for forbidden in (prepare, complete, task, embed):
            forbidden.assert_not_called()
        result = response.json()
        self.assertEqual(result["status"], "matches")
        self.assertIn("Synthetic quartz evidence.", result["reply"])
        self.assertIn("synthetic.md", result["reply"])
        self.assertIn("chunk ID:", result["reply"])
        self.assertNotIn("Автор:", result["reply"])
        self.assertNotIn("Дата:", result["reply"])
        self.assertFalse(result["limits"]["exhaustive"])
        messages = db.get_messages(self.session["id"])
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[-1]["model"], "knowledge_search")
        self.assertEqual(messages[-1]["content"], result["reply"])

    def test_empty_index_and_no_matches_are_distinct_successes(self):
        self.assertEqual(self.search().json()["status"], "empty_index")
        self.index_markdown()
        result = self.search("absenttermzzzz")
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["status"], "no_matches")
        self.assertEqual(result.json()["results"], [])

    def test_telegram_metadata_and_literal_fences_survive(self):
        html = '''<div class="page_header"><div class="name">Synthetic</div></div><div class="history"><div class="message default" id="message41"><div class="from_name">Synthetic Author</div><div class="date" title="01.01.2026 10:20:30 UTC+03:00"></div><div class="text">quartz ``` evidence</div></div></div>'''
        (rag.source_dir(self.profile) / "synthetic.html").write_text(html)
        rag.ingest_sources(self.profile)
        result = self.search("quartz 2026-01-01").json()
        self.assertEqual(result["status"], "matches")
        self.assertIn("message41", result["reply"])
        self.assertIn("Synthetic Author", result["reply"])
        self.assertIn("2026-01-01T10:20:30", result["reply"])
        self.assertIn("UTC+03:00", result["reply"])
        self.assertIn("````text", result["reply"])
        self.assertEqual(self.search("quartz 2026-02-01").json()["status"], "no_matches")

    def test_profile_ownership_is_checked_before_retrieval_or_persistence(self):
        other = db.create_profile("Synthetic Other")["id"]
        with patch.object(routes.knowledge_search, "search") as search:
            response = self.search(profile_id=other)
        self.assertEqual(response.status_code, 404)
        search.assert_not_called()
        self.assertEqual(db.get_messages(self.session["id"]), [])
        self.index_markdown()
        other_session = db.create_session(other, "Other", "")
        response = self.search(profile_id=other, session_id=other_session["id"])
        self.assertEqual(response.json()["status"], "empty_index")

    def test_session_owned_context_is_visible_only_in_its_session(self):
        message = db.add_message(self.session["id"], "user", "Synthetic quartz context")
        rag.index_chat_context(profile_id=self.profile, session_id=self.session["id"],
                               message_id=message["id"], title="Synthetic", text="quartz sessiononly")
        self.assertEqual(self.search("sessiononly").json()["status"], "matches")
        other = db.create_session(self.profile, "Other session", "")
        self.assertEqual(self.search("sessiononly", session_id=other["id"]).json()["status"], "empty_index")
        response = self.search("sessiononly", session_id=None)
        self.assertEqual(response.json()["status"], "empty_index")
        self.assertNotEqual(response.json()["session_id"], self.session["id"])

    def test_remote_provider_is_rejected_before_retrieval_or_external_calls(self):
        remote = Mock()
        remote.descriptor = replace(embeddings.LocalHashEmbeddingProvider().descriptor, provider="ollama")
        with patch.object(rag, "_embedding_provider", return_value=remote), \
             patch.object(rag, "search_with_diagnostics") as retrieve:
            response = self.search()
        self.assertEqual(response.status_code, 409, response.text)
        remote.embed.assert_not_called()
        retrieve.assert_not_called()
        self.assertEqual(db.get_messages(self.session["id"]), [])

    def test_retrieval_error_is_not_no_matches_and_does_not_write_history(self):
        with patch.object(rag, "search_with_diagnostics", side_effect=HTTPException(503, "synthetic retrieval failure")), \
             patch.object(routes, "_prepare_chat_request") as fallback:
            response = self.search()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("no_matches", response.text)
        fallback.assert_not_called()
        self.assertEqual(db.get_messages(self.session["id"]), [])

    def test_query_and_result_limits_are_enforced(self):
        for value in ("", " ", "x" * 4001):
            self.assertEqual(self.search(value).status_code, 422)
        self.assertEqual(self.search(top_k=21).status_code, 422)
        self.index_markdown(("quartz evidence " * 2000))
        result = self.search(top_k=1).json()
        self.assertLessEqual(len(result["results"]), 1)
        self.assertLessEqual(sum(len(r["content"]) for r in result["results"]), 16000)

    def test_planner_expands_synonyms_but_evidence_is_verbatim_and_links_opt_in(self):
        import json
        from backend.apps.chat.services import knowledge_search as smart
        self.index_markdown("Synthetic battery evidence.")
        plan = json.dumps({"topics": [{"topic": "аккумулятор", "keywords": [], "variants": ["battery"]}], "dates": None})
        with patch.object(smart, "_planner_completion", return_value=plan) as planner:
            result = self.search("аккумулятор", model_name="qwen3:4b").json()
        planner.assert_called_once()
        self.assertEqual(result["planner"]["status"], "ready")
        self.assertEqual(result["status"], "matches")
        self.assertIn("Synthetic battery evidence.", result["reply"])
        self.assertFalse(result["links_requested"])
        self.assertEqual(result["semantic"]["status"], "not_configured")
        with patch.object(smart, "_planner_completion", return_value=plan):
            linked = self.search("аккумулятор и добавь ссылки", model_name="qwen3:4b").json()
        self.assertEqual(linked["results"][0]["links"][0]["kind"], "local_evidence")

    def test_invalid_planner_degrades_explicitly_without_answer_generation(self):
        from backend.apps.chat.services import knowledge_search as smart
        self.index_markdown()
        for value in ["not JSON", '{"topics":[],"answer":"fabricated"}', '{"topics":[{"topic":"https://evil.invalid"}]}']:
            with self.subTest(value=value), patch.object(smart, "_planner_completion", return_value=value):
                result = self.search("quartz", model_name="qwen3:4b").json()
            self.assertEqual(result["status"], "matches")
            self.assertEqual(result["planner"]["status"], "unavailable")
            self.assertNotIn("fabricated", result["reply"])

    def test_original_date_id_and_source_constraints_survive_expansion(self):
        import json
        from backend.apps.chat.services import knowledge_search as smart
        html = '<div class="page_header"><div class="name">Synthetic</div></div><div class="history">'
        for mid, day in [(1, '01'), (2, '02')]:
            html += f'<div class="message default" id="message{mid}"><div class="date" title="{day}.01.2026 10:20:30 UTC+03:00"></div><div class="text">battery</div></div>'
        (rag.source_dir(self.profile) / 'synthetic.html').write_text(html+'</div>')
        rag.ingest_sources(self.profile)
        plan = json.dumps({"topics": [{"topic": "battery"}], "dates": {"start": "2020-01-01", "end": "2020-01-02", "source_text": "invented"}})
        with patch.object(smart, "_planner_completion", return_value=plan):
            result = self.search("аккумулятор message1 synthetic.html 2026-01-01", model_name="qwen3:4b").json()
        self.assertEqual(result['status'], 'matches')
        self.assertIsNone(result['search_plan']['dates'])
        self.assertTrue(all(r['provenance']['message_id'] == 'message1' for r in result['results']))

    def test_local_semantic_vectors_find_evidence_without_word_overlap(self):
        from backend.apps.chat.services import knowledge_search as smart
        provider = embeddings.OllamaEmbeddingProvider(base_url='http://127.0.0.1:11434', model='synthetic-embed', version='v1', dimensions=2)
        self.index_markdown('quartz source text')
        with patch.object(rag, '_embedding_provider', return_value=provider), \
             patch.object(provider, 'embed', side_effect=lambda texts, **kwargs: [[1.0, 0.0] for _ in texts]) as embed:
            rag.reindex_embeddings(self.profile, provider=provider)
            embed.reset_mock()
            response = self.search('непохожее', model_name='')
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
        self.assertEqual(result['status'], 'matches')
        self.assertEqual(result['semantic']['status'], 'ready')
        self.assertEqual(result['limits']['strategy'], 'hybrid_v2')
        self.assertTrue(provider.local_only)
        embed.assert_called()
        self.assertIn('quartz source text', result['reply'])

    def test_remote_endpoint_and_redirects_are_blocked_before_planning(self):
        from backend.apps.chat.services import knowledge_search as smart
        self.index_markdown()
        with patch.object(config, 'SETTINGS', replace(config.SETTINGS, base_url='https://external.invalid')), \
             patch.object(smart, '_planner_completion') as planner:
            self.assertEqual(self.search('quartz', model_name='qwen3:4b').status_code, 409)
            planner.assert_not_called()
        handler = embeddings._RejectRedirects()
        with self.assertRaises(embeddings.EmbeddingProviderError):
            handler.redirect_request(None, None, 302, 'redirect', {}, 'https://external.invalid')
        for url in ['https://external.invalid', 'http://localhost@external.invalid', 'ftp://127.0.0.1', 'http://127.0.0.1?token=x']:
            self.assertFalse(embeddings.is_loopback_endpoint(url))

    def test_structured_qwen_planner_disables_native_reasoning(self):
        import io, json
        from backend.apps.chat.services import knowledge_search as smart
        response = {"message": {"content": '{"topics":[{"topic":"synthetic"}]}'}, "done": True, "done_reason": "stop"}
        with patch.object(embeddings, "open_local_request", return_value=io.BytesIO(json.dumps(response).encode())) as transport:
            smart._planner_completion("qwen3:4b", "synthetic query")
        sent = json.loads(transport.call_args.args[0].data)
        self.assertIs(sent["think"], False)
        self.assertEqual(sent["format"], smart.SearchPlan.model_json_schema())

    def test_planner_failure_reports_safe_specific_reason(self):
        from backend.apps.chat.services import knowledge_search as smart
        for error, reason in [(ValueError("planner_response_incomplete"), "planner_response_incomplete"),
                              (TimeoutError("private transport text"), "timeout")]:
            with patch.object(smart, "_planner_completion", side_effect=error):
                _, diagnostic, warnings = smart._plan("private synthetic query", "qwen3:4b")
            self.assertEqual(diagnostic["reason"], reason)
            self.assertNotIn("private", str(diagnostic) + str(warnings))

    def test_native_planner_response_shape_and_budget_are_validated(self):
        import io
        import json
        from backend.apps.chat.services import knowledge_search as smart
        for payload in [[], {'message': []}, {'message': {'content': 'x'}, 'done_reason': 'length'}, {'message': {'content': 1}}]:
            with self.subTest(payload=payload), patch.object(embeddings, 'open_local_request', return_value=io.BytesIO(json.dumps(payload).encode())):
                with self.assertRaises(ValueError):
                    smart._planner_completion('synthetic', 'question')

    def test_indexed_own_permalink_survives_retrieval_metadata_shape(self):
        html = '<div class="page_header"><div class="name">Synthetic</div></div><div class="history"><div class="message default" id="message7"><a class="date" title="01.01.2026 10:20:30 UTC+03:00" href="https://t.me/example_chat/42"></a><div class="text">quartz</div></div></div>'
        (rag.source_dir(self.profile)/'permalink.html').write_text(html)
        rag.ingest_sources(self.profile)
        result = self.search('quartz и добавь ссылки').json()
        self.assertEqual(result['results'][0]['links'][0]['url'], 'https://t.me/example_chat/42')
        self.assertIn('[Открыть сообщение в Telegram]', result['reply'])

    def test_planner_receives_only_current_query_not_corpus_or_history(self):
        import io
        import json
        from backend.apps.chat.services import knowledge_search as smart
        self.index_markdown('PRIVATE_SYNTHETIC_CORPUS quartz')
        db.add_message(self.session['id'], 'user', 'PRIVATE_SYNTHETIC_HISTORY')
        plan = json.dumps({'topics':[{'topic':'quartz'}]})
        response = io.BytesIO(json.dumps({'message': {'content': plan}, 'done': True}).encode())
        with patch.object(embeddings, 'open_local_request', return_value=response) as transport:
            self.assertEqual(self.search('quartz', model_name='qwen3:4b').status_code, 200)
        payload = json.loads(transport.call_args.args[0].data)
        self.assertEqual([item['role'] for item in payload['messages']], ['system', 'user'])
        self.assertIn('quartz', payload['messages'][-1]['content'])
        self.assertNotIn('PRIVATE_SYNTHETIC', str(payload))

    def test_search_has_no_automatic_elapsed_deadline(self):
        from backend.apps.chat.services import knowledge_search as smart
        self.index_markdown()
        # The removed global stopwatch must not decide when retrieval stops.
        with patch.object(smart, 'monotonic', side_effect=[0, 100], create=True) as elapsed:
            response = self.search()
        self.assertEqual(response.status_code, 200, response.text)
        elapsed.assert_not_called()
        self.assertEqual(len(db.get_messages(self.session['id'])), 2)

    def start_search(self, **kwargs):
        return self.client.post('/chat/knowledge-search/tasks', json={
            'profile_id': self.profile, 'session_id': self.session['id'], 'query': 'quartz', **kwargs,
        })

    def task_scope(self, **kwargs):
        return {'profile_id': self.profile, 'session_id': self.session['id'], **kwargs}

    def join_search(self, task_id):
        search_tasks._TASKS[task_id]['thread'].join(timeout=3)
        self.assertFalse(search_tasks._TASKS[task_id]['thread'].is_alive())

    def test_async_search_completes_and_persists_the_existing_result_format(self):
        self.index_markdown()
        with patch.object(routes.knowledge_search, '_planner_completion') as planner, \
             patch.object(rag, '_embed_texts') as embed, \
             patch.object(routes.chat_service, 'chat_completion_result') as generate:
            response = self.start_search()
            self.assertEqual(response.status_code, 202, response.text)
            task_id = response.json()['task_id']
            self.join_search(task_id)
        for forbidden in (planner, embed, generate):
            forbidden.assert_not_called()
        task = self.client.get(f'/chat/knowledge-search/tasks/{task_id}', params=self.task_scope()).json()
        self.assertEqual(task['state'], 'completed')
        self.assertEqual(task['result']['status'], 'matches')
        messages = db.get_messages(self.session['id'])
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[-1]['content'], task['result']['reply'])
        cancelled = self.client.post(f'/chat/knowledge-search/tasks/{task_id}/cancel', params=self.task_scope()).json()
        self.assertEqual(cancelled['state'], 'completed')
        self.assertEqual(cancelled['result'], task['result'])

    def test_async_scope_is_required_for_status_and_cancel(self):
        response = self.start_search()
        task_id = response.json()['task_id']
        self.join_search(task_id)
        other_profile = db.create_profile('Synthetic Other')['id']
        other_session = db.create_session(self.profile, 'Synthetic Other', '')['id']
        for scope in [self.task_scope(profile_id=other_profile), self.task_scope(session_id=other_session),
                      {'profile_id': self.profile}]:
            with self.subTest(scope=scope):
                self.assertEqual(self.client.get(f'/chat/knowledge-search/tasks/{task_id}', params=scope).status_code, 404)
                self.assertEqual(self.client.post(f'/chat/knowledge-search/tasks/{task_id}/cancel', params=scope).status_code, 404)
        with patch.object(routes.knowledge_search, 'search') as retrieve:
            invalid = self.start_search(profile_id=other_profile)
        self.assertEqual(invalid.status_code, 404)
        retrieve.assert_not_called()

    def test_cancel_during_planner_stops_before_retrieval_without_history(self):
        import json
        self.index_markdown()
        entered, release = threading.Event(), threading.Event()
        def planner(*args):
            entered.set()
            self.assertTrue(release.wait(3))
            return json.dumps({'topics': [{'topic': 'quartz', 'variants': ['crystal']}]})
        try:
            with patch.object(routes.knowledge_search, '_planner_completion', side_effect=planner), \
                 patch.object(rag, 'search_with_diagnostics') as retrieve:
                response = self.start_search(model_name='synthetic')
                self.assertTrue(entered.wait(3))
                task_id = response.json()['task_id']
                cancelled = self.client.post(f'/chat/knowledge-search/tasks/{task_id}/cancel', params=self.task_scope())
                self.assertEqual(cancelled.json()['state'], 'cancelled')
                release.set()
                self.join_search(task_id)
            retrieve.assert_not_called()
            self.assertEqual(db.get_messages(self.session['id']), [])
        finally:
            release.set()

    def test_cancel_during_retrieval_stops_remaining_expansions_and_late_persistence(self):
        import json
        self.index_markdown()
        entered, release = threading.Event(), threading.Event()
        def retrieve(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(3))
            return {'results': []}
        try:
            with patch.object(routes.knowledge_search, '_planner_completion', return_value=json.dumps({
                'topics': [{'topic': 'quartz', 'variants': ['crystal', 'stone']}],
            })), patch.object(rag, 'search_with_diagnostics', side_effect=retrieve) as retrieval_call:
                response = self.start_search(model_name='synthetic')
                self.assertTrue(entered.wait(3))
                task_id = response.json()['task_id']
                self.client.post(f'/chat/knowledge-search/tasks/{task_id}/cancel', params=self.task_scope())
                release.set()
                self.join_search(task_id)
            self.assertEqual(retrieval_call.call_count, 1)
            self.assertEqual(db.get_messages(self.session['id']), [])
            self.assertIsNone(search_tasks.get(task_id, **self.task_scope())['result'])
        finally:
            release.set()

    def test_cancelled_native_call_keeps_capacity_until_worker_exits(self):
        entered, release = threading.Event(), threading.Event()
        def retrieve(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(3))
            return {'reply': 'Synthetic late result'}
        try:
            with patch.object(search_tasks, 'MAX_ACTIVE_PER_PROFILE', 1), \
                 patch.object(routes.knowledge_search, 'search', side_effect=retrieve):
                response = self.start_search()
                task_id = response.json()['task_id']
                self.assertTrue(entered.wait(3))
                self.client.post(f'/chat/knowledge-search/tasks/{task_id}/cancel', params=self.task_scope())
                self.assertEqual(self.start_search().status_code, 429)
                release.set()
                self.join_search(task_id)
                next_response = self.start_search()
                self.assertEqual(next_response.status_code, 202)
                self.join_search(next_response.json()['task_id'])
            self.assertEqual(len(db.get_messages(self.session['id'])), 2)
        finally:
            release.set()

    def test_async_errors_are_explicit_and_leave_history_untouched(self):
        with patch.object(routes.knowledge_search, 'search', side_effect=HTTPException(503, {
            'code': 'knowledge_search_embedding_unavailable', 'message': 'Synthetic provider failure',
        })):
            response = self.start_search()
            task_id = response.json()['task_id']
            self.join_search(task_id)
        task = self.client.get(f'/chat/knowledge-search/tasks/{task_id}', params=self.task_scope()).json()
        self.assertEqual(task['state'], 'failed')
        self.assertEqual(task['error']['status_code'], 503)
        self.assertEqual(task['error']['detail']['code'], 'knowledge_search_embedding_unavailable')
        self.assertIsNone(task['result'])
        self.assertEqual(db.get_messages(self.session['id']), [])

    def test_async_revalidates_deleted_session_before_persistence(self):
        entered, release = threading.Event(), threading.Event()
        def retrieve(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(3))
            return {'reply': 'Synthetic evidence'}
        try:
            with patch.object(routes.knowledge_search, 'search', side_effect=retrieve):
                response = self.start_search()
                task_id = response.json()['task_id']
                self.assertTrue(entered.wait(3))
                db.delete_session(self.session['id'])
                release.set()
                self.join_search(task_id)
            task = search_tasks.get(task_id, **self.task_scope())
            self.assertEqual(task['state'], 'failed')
            self.assertEqual(task['error']['status_code'], 404)
            self.assertIsNone(task['result'])
        finally:
            release.set()

    def test_async_new_session_uses_original_null_scope_and_only_creates_chat_on_success(self):
        response = self.start_search(session_id=None)
        task_id = response.json()['task_id']
        self.join_search(task_id)
        task = self.client.get(f'/chat/knowledge-search/tasks/{task_id}', params={'profile_id': self.profile}).json()
        self.assertEqual(task['state'], 'completed')
        self.assertIsNone(task['session_id'])
        self.assertTrue(task['result']['session_id'])
        self.assertNotEqual(task['result']['session_id'], self.session['id'])
        self.assertEqual(len(db.get_messages(task['result']['session_id'])), 2)

    def test_request_local_corpus_is_reused_only_with_matching_scope_and_provider(self):
        import json
        self.index_markdown()
        with patch.object(rag, '_current_generation_chunks', wraps=rag._current_generation_chunks) as load, \
             patch.object(routes.knowledge_search, '_planner_completion', return_value=json.dumps({
                 'topics': [{'topic': 'quartz', 'variants': ['crystal', 'stone']}],
             })):
            self.assertEqual(self.search(model_name='synthetic').status_code, 200)
            self.assertEqual(load.call_count, 1)
            self.assertEqual(self.search(model_name='synthetic').status_code, 200)
            self.assertEqual(load.call_count, 2)
        provider = embeddings.LocalHashEmbeddingProvider()
        corpus = rag.prepare_search_corpus(self.profile, provider, session_id=self.session['id'])
        for overrides in [{'profile_id': self.profile + 1}, {'session_id': None}, {
            'embedding_provider': Mock(descriptor=replace(provider.descriptor, storage_key='synthetic/other')),
        }]:
            kwargs = {'profile_id': self.profile, 'session_id': self.session['id'], 'embedding_provider': provider, **overrides}
            with self.assertRaisesRegex(ValueError, 'scope_mismatch'):
                rag.search_with_diagnostics(query='quartz', prepared_corpus=corpus, **kwargs)
        self.assertEqual(self.start_search(prepared_corpus={'profile_id': self.profile}).status_code, 422)

    def test_lexical_corpus_cache_preserves_ranking_and_original_filter(self):
        self.index_markdown('Synthetic quartz evidence.\nSecond crystal sentence.')
        provider = embeddings.LocalHashEmbeddingProvider()
        corpus = rag.prepare_search_corpus(self.profile, provider, session_id=self.session['id'])
        kwargs = {'profile_id': self.profile, 'session_id': self.session['id'], 'embedding_provider': provider,
                  'strategy': 'lexical_v1', 'filter_query': 'quartz'}
        for query in ['quartz', 'crystal', 'absenttermzzzz']:
            uncached = rag.search_with_diagnostics(query=query, **kwargs)
            cached = rag.search_with_diagnostics(query=query, prepared_corpus=corpus, **kwargs)
            self.assertEqual(cached, uncached)
        self.assertEqual(len(corpus.lexical_cache), len(corpus.chunks))


if __name__ == "__main__":
    unittest.main()
