import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import config, db
from app.routes import profiles as profile_routes
from app.schemas import ChatRequest, ProfileCreate, ProfileUpdate
from app.services import models as model_service
from backend.apps.asr import pipeline
from backend.apps.chat.routes import _ensure_chat_model_available, _prepare_chat_request, start_chat_task
from backend.apps.chat.service import sanitize_reply
from backend.apps.rag import service as rag_service


class LocalGPTPipelineMemoryTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.tmpdir.name) / "localgpt-test.db"
        self.original_rag_source_dir = config.RAG_SOURCE_DIR
        config.RAG_SOURCE_DIR = Path(self.tmpdir.name) / "rag_sources"
        db.init_db()
        self.profile_id = db.ensure_default_profile()

    def tearDown(self):
        config.RAG_SOURCE_DIR = self.original_rag_source_dir
        self.tmpdir.cleanup()

    def test_model_list_does_not_auto_pull_when_empty(self):
        with (
            patch.object(model_service, "_list_local_models", return_value=[]),
            patch.object(model_service, "_pull_statuses", return_value=[]),
            patch.object(model_service, "start_model_pull") as start_pull,
        ):
            data = model_service.list_models()

        self.assertEqual(data["installed"], [])
        self.assertEqual(data["downloads"], [])
        start_pull.assert_not_called()

    def test_asr_studio_default_model_is_large_v3_turbo(self):
        profile = db.get_profile(self.profile_id)

        self.assertEqual(profile["preferences"]["asr"]["studio_model"], "large-v3-turbo")
        self.assertEqual(profile["preferences"]["chat"]["dictation_model"], config.SETTINGS.whisper_default_model)

    def test_default_pipeline_uses_current_catalog_and_token_budget(self):
        expected = {
            "cleaner": ("qwen2.5:3b-instruct", 6000),
            "segmenter": ("qwen2.5:3b-instruct", 6000),
            "speaker_resolver": ("qwen2.5:7b-instruct", 4000),
            "structurer": ("qwen3:8b", 3500),
            "summary": ("mistral-nemo:12b", 3000),
        }

        for stage, (model, max_tokens) in expected.items():
            with self.subTest(stage=stage):
                self.assertEqual(config.DEFAULT_PIPELINE[stage]["model"], model)
                self.assertEqual(config.DEFAULT_PIPELINE[stage]["max_tokens"], max_tokens)

    def test_profile_create_and_update_accept_system_prompt(self):
        profile = profile_routes.create_profile(
            ProfileCreate(name="  Work  ", description="  Client work  ", system_prompt="  Use profile context.  ")
        )

        self.assertEqual(profile["name"], "Work")
        self.assertEqual(profile["description"], "Client work")
        self.assertEqual(profile["preferences"]["chat"]["system_prompt"], "Use profile context.")

        updated = profile_routes.update_profile(
            profile["id"],
            ProfileUpdate(description="  Updated description  ", system_prompt="  Updated prompt  "),
        )

        self.assertEqual(updated["description"], "Updated description")
        self.assertEqual(updated["preferences"]["chat"]["system_prompt"], "Updated prompt")

    def test_chat_model_missing_is_readable(self):
        with patch.object(model_service, "is_model_installed", return_value=False):
            with self.assertRaises(HTTPException) as ctx:
                _ensure_chat_model_available("qwen2.5:3b")

        self.assertEqual(ctx.exception.status_code, 424)
        self.assertEqual(ctx.exception.detail["code"], "chat_model_missing")

    def test_chat_task_model_missing_is_not_wrapped(self):
        req = ChatRequest(query="hello", profile_id=self.profile_id, model_name="qwen2.5:3b")
        with patch.object(model_service, "is_model_installed", return_value=False):
            with self.assertRaises(HTTPException) as ctx:
                start_chat_task(req)

        self.assertEqual(ctx.exception.status_code, 424)
        self.assertEqual(ctx.exception.detail["code"], "chat_model_missing")

    def test_chat_task_without_model_is_rejected_before_session_created(self):
        req = ChatRequest(query="hello", profile_id=self.profile_id)

        with self.assertRaises(HTTPException) as ctx:
            start_chat_task(req)

        self.assertEqual(ctx.exception.status_code, 424)
        self.assertEqual(ctx.exception.detail["code"], "chat_model_not_selected")
        self.assertEqual(db.list_sessions(self.profile_id), [])

    def test_database_cleanup_removes_orphans_but_keeps_asr_history_and_manual_rag(self):
        session = db.create_session(self.profile_id, "Cleanup test", "qwen2.5:3b")
        chat_transcript = db.create_transcript(
            profile_id=self.profile_id,
            session_id=session["id"],
            name="Chat transcript",
            content="chat audio context",
        )
        db.create_pipeline_run(
            transcript_id=int(chat_transcript["id"]),
            profile_id=self.profile_id,
            session_id=session["id"],
            preset="balanced",
            action="full",
            raw_transcript="chat audio context",
            cleaned_transcript="chat audio context",
            segments=[],
            speaker_mapping=[],
            speaker_overrides={},
            structured_json=None,
            summary=None,
            stage_timings={},
            warnings=[],
            used_settings={},
        )
        orphan_doc = db.create_source_document(
            profile_id=self.profile_id,
            session_id=session["id"],
            source_type="asr_transcript",
            source_id="chat-audio",
            title="Chat audio",
            content="context",
            metadata={},
        )
        orphan_chunk = db.create_document_chunk(
            document_id=int(orphan_doc["id"]),
            profile_id=self.profile_id,
            session_id=session["id"],
            chunk_index=0,
            content="context",
            metadata={},
        )
        db.create_document_embedding(
            chunk_id=orphan_chunk,
            profile_id=self.profile_id,
            embedding_model="local-hash-v1",
            embedding=[0.1, 0.2],
            metadata={},
        )
        db.create_session_summary(
            profile_id=self.profile_id,
            session_id=None,
            source_type="chat",
            source_id="old-chat",
            summary="orphan summary",
            structured_json=None,
        )
        asr_transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="ASR Studio transcript",
            content="standalone ASR history",
            labels={"origin": "asr_tool"},
        )
        db.create_session_summary(
            profile_id=self.profile_id,
            session_id=None,
            source_type="asr",
            source_id=str(asr_transcript["id"]),
            summary="ASR summary",
            structured_json=None,
        )
        manual_doc = db.create_source_document(
            profile_id=self.profile_id,
            session_id=None,
            source_type="manual_file",
            source_id="manual.md",
            title="manual.md",
            content=None,
            metadata={},
        )

        db.delete_session(session["id"])
        result = db.cleanup_database_garbage(vacuum=False)

        self.assertGreaterEqual(result["deleted"]["transcripts"], 1)
        self.assertGreaterEqual(result["deleted"]["transcript_pipeline_runs"], 1)
        self.assertGreaterEqual(result["deleted"]["session_summaries"], 1)
        self.assertGreaterEqual(result["deleted"]["source_documents"], 1)
        self.assertGreaterEqual(result["deleted"]["document_chunks"], 1)
        self.assertGreaterEqual(result["deleted"]["document_embeddings"], 1)
        self.assertIsNone(db.get_transcript(chat_transcript["id"]))
        self.assertIsNotNone(db.get_transcript(asr_transcript["id"]))
        documents = db.list_source_documents(self.profile_id)
        self.assertTrue(any(item["id"] == manual_doc["id"] for item in documents))
        self.assertFalse(any(item["id"] == orphan_doc["id"] for item in documents))

    def test_database_reset_recreates_default_profile(self):
        db.create_profile("Work", None, None)
        session = db.create_session(self.profile_id, "Reset test", "qwen2.5:3b")
        db.add_message(session["id"], "user", "hello")
        db.create_transcript(profile_id=self.profile_id, session_id=session["id"], name="Transcript", content="text")
        db.create_source_document(
            profile_id=self.profile_id,
            session_id=None,
            source_type="manual_file",
            source_id="manual.md",
            title="manual.md",
            content=None,
            metadata={},
        )

        result = db.reset_database(vacuum=False)
        profiles = db.list_profiles()

        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["name"], "Default")
        self.assertEqual(result["default_profile_id"], profiles[0]["id"])
        self.assertEqual(db.list_sessions(profiles[0]["id"]), [])
        self.assertEqual(db.rag_stats()["documents"], 0)

    def test_prompt_uses_summary_memory_before_short_history(self):
        session = db.create_session(self.profile_id, "Memory test", "qwen2.5:3b")
        for idx in range(4):
            db.add_message(session["id"], "user", f"old user {idx}")
            db.add_message(session["id"], "assistant", f"old assistant {idx}")
        db.create_session_summary(
            profile_id=self.profile_id,
            session_id=session["id"],
            source_type="chat",
            source_id="chat:test",
            summary="User prefers concise answers.",
            structured_json=None,
        )

        prepared = _prepare_chat_request(ChatRequest(query="continue", session_id=session["id"], model_name="qwen2.5:3b"))
        contents = [item["content"] for item in prepared["messages"]]
        summary_index = next(idx for idx, item in enumerate(contents) if "Summary memory" in item)
        history_index = next(idx for idx, item in enumerate(prepared["messages"]) if item["role"] == "user" and item["content"].startswith("old user"))

        self.assertLess(summary_index, history_index)
        self.assertLessEqual(len([item for item in prepared["messages"] if item["role"] in {"user", "assistant"}]), 14)

    def test_profile_system_prompt_is_added_to_prompt(self):
        db.update_profile_preferences(self.profile_id, {"chat": {"system_prompt": "Отвечай только по базе профиля."}})

        prepared = _prepare_chat_request(
            ChatRequest(query="hello", profile_id=self.profile_id, model_name="qwen2.5:3b")
        )
        contents = [item["content"] for item in prepared["messages"]]

        self.assertTrue(any("Профильный system prompt" in item for item in contents))
        self.assertTrue(any("Отвечай только по базе профиля." in item for item in contents))

    def test_language_policy_follows_last_user_message(self):
        prepared = _prepare_chat_request(
            ChatRequest(query="do you speak english?", profile_id=self.profile_id, model_name="qwen2.5:3b")
        )
        contents = [item["content"] for item in prepared["messages"]]

        self.assertFalse(any("ТОЛЬКО на русском" in item for item in contents))
        self.assertTrue(any("языке последнего сообщения пользователя" in item.lower() for item in contents))

    def test_response_formatting_guardrail_is_global(self):
        prepared = _prepare_chat_request(
            ChatRequest(query="проверь расчет 23730 + 11960", profile_id=self.profile_id, model_name="qwen2.5:3b")
        )
        contents = [item["content"] for item in prepared["messages"]]

        self.assertTrue(any("Не используй LaTeX" in item for item in contents))
        self.assertTrue(any("35,690 ₽" in item and "35 690 ₽" in item for item in contents))

    def test_sanitize_reply_normalizes_latex_currency_format(self):
        raw = r"Итого: \[ 23,730 \, \text{₽} + 11,960 \, \text{₽} = 35,690 \, \text{₽} \]"

        cleaned = sanitize_reply(raw)

        self.assertNotIn(r"\[", cleaned)
        self.assertNotIn(r"\text", cleaned)
        self.assertIn("23 730 ₽ + 11 960 ₽ = 35 690 ₽", cleaned)

    def test_rag_ingest_and_prompt_context(self):
        source_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        (source_dir / "project.md").write_text(
            "Alpha project deadline is Friday. The owner is Speaker_1.",
            encoding="utf-8",
        )
        db.update_profile_preferences(self.profile_id, {"settings": {"rag_enabled": True}})

        ingest = rag_service.ingest_sources(self.profile_id)
        prepared = _prepare_chat_request(
            ChatRequest(query="What is Alpha project deadline?", profile_id=self.profile_id, model_name="qwen2.5:3b")
        )

        self.assertEqual(ingest["indexed"], 2)
        self.assertIn("project.json", ingest["generated_json"])
        self.assertEqual(ingest["stats"]["documents"], 2)
        self.assertTrue(prepared["rag_chunks"])
        contents = [item["content"] for item in prepared["messages"]]
        rag_index = next(idx for idx, item in enumerate(contents) if "Relevant RAG context" in item)
        query_index = len(contents) - 1
        self.assertLess(rag_index, query_index)
        self.assertIn("Alpha project deadline", contents[rag_index])
        self.assertIn("JSON chunks are source of truth", contents[rag_index])
        self.assertEqual(prepared["effective_settings"]["rag_enabled_effective"], True)
        self.assertGreater(prepared["effective_settings"]["rag_chunks_used"], 0)

    def test_rag_search_uses_recent_user_history_for_short_followup(self):
        source_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        (source_dir / "interests.md").write_text(
            "Интересы пользователя: гитара, PUBG Mobile, футбол и наведение порядка в CRM-процессах.",
            encoding="utf-8",
        )
        db.update_profile_preferences(self.profile_id, {"settings": {"rag_enabled": True}})
        rag_service.ingest_sources(self.profile_id)
        session = db.create_session(self.profile_id, "RAG followup", "qwen2.5:3b")
        db.add_message(session["id"], "user", "На основании моих интересов что можешь предложить?")
        db.add_message(session["id"], "assistant", "Уточню интересы.")

        prepared = _prepare_chat_request(
            ChatRequest(query="для этого есть rag", session_id=session["id"], model_name="qwen2.5:3b")
        )
        contents = [item["content"] for item in prepared["messages"]]
        rag_block = next(item for item in contents if "Relevant RAG context" in item)

        self.assertIn("PUBG Mobile", rag_block)

    def test_force_reindex_regenerates_only_auto_json(self):
        source_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        md_path = source_dir / "plain.md"
        md_path.write_text("Первичная заметка.", encoding="utf-8")
        generated = rag_service.ensure_structured_json_files(self.profile_id)
        self.assertEqual(generated, ["plain.json"])

        md_path.write_text("Обновленная заметка с гитарой.", encoding="utf-8")
        generated_again = rag_service.ensure_structured_json_files(self.profile_id, force=True)
        self.assertEqual(generated_again, ["plain.json"])
        self.assertIn("гитарой", (source_dir / "plain.json").read_text(encoding="utf-8"))

        manual_json = source_dir / "manual.json"
        manual_json.write_text('{"generated_by":"human","facts":[{"text":"do not overwrite"}]}', encoding="utf-8")
        (source_dir / "manual.md").write_text("Авто не должен перезаписать ручной JSON.", encoding="utf-8")
        rag_service.ensure_structured_json_files(self.profile_id, force=True)
        self.assertIn("do not overwrite", manual_json.read_text(encoding="utf-8"))

    def test_rag_delete_file_removes_file_and_auto_companion(self):
        source_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        md_path = source_dir / "delete-me.md"
        md_path.write_text("Удаляемая заметка.", encoding="utf-8")
        rag_service.ingest_sources(self.profile_id, force=True)
        self.assertTrue((source_dir / "delete-me.json").exists())
        self.assertGreater(db.rag_stats(self.profile_id)["documents"], 0)

        result = rag_service.delete_file(self.profile_id, "delete-me.md")

        self.assertIn("delete-me.md", result["deleted"])
        self.assertIn("delete-me.json", result["deleted"])
        self.assertFalse(md_path.exists())
        self.assertFalse((source_dir / "delete-me.json").exists())
        self.assertEqual(db.rag_stats(self.profile_id)["documents"], 0)

    def test_rag_files_are_scoped_per_profile(self):
        first_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        second = db.create_profile("Work", None, None)
        second_dir = rag_service.ensure_profile_source_dir(second["id"])
        (first_dir / "one.md").write_text("Only alpha_unique_profile_fact.", encoding="utf-8")
        (second_dir / "two.md").write_text("Only beta_unique_profile_fact.", encoding="utf-8")

        first_ingest = rag_service.ingest_sources(self.profile_id)
        second_ingest = rag_service.ingest_sources(second["id"])

        self.assertEqual(first_ingest["stats"]["documents"], 2)
        self.assertEqual(second_ingest["stats"]["documents"], 2)
        self.assertTrue(rag_service.search(self.profile_id, "alpha_unique_profile_fact", top_k=3))
        results = rag_service.search(self.profile_id, "beta_unique_profile_fact", top_k=3)
        self.assertFalse(any("beta_unique_profile_fact" in item["content"] for item in results))

    def test_pipeline_summary_uses_cleaned_text_and_sanitizes_speakers(self):
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="raw noise phrase raw noise phrase",
            labels={"origin": "asr_tool"},
        )
        responses = [
            "clean phrase",
            '[{"segment_id": 1, "text": "clean phrase"}]',
            '[{"segment_id": 1, "speaker": "Alice", "confidence": 0.95, "text": "clean phrase"}]',
            '{"topic": "demo", "tasks": [], "decisions": [], "risks": [], "open_questions": []}',
            "## Краткое резюме\nclean summary",
        ]

        with (
            patch.object(pipeline.model_service, "is_model_installed", return_value=True),
            patch.object(
                pipeline.ChatService,
                "chat_completion",
                autospec=True,
                side_effect=lambda self, model, messages, *, settings: responses.pop(0),
            ) as chat_mock,
        ):
            run = pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="balanced", action="full")

        self.assertEqual(run["cleaned_transcript"], "clean phrase")
        self.assertEqual(run["speaker_mapping"][0]["speaker"], "Unknown speaker")
        self.assertIn("clean summary", run["summary"])
        summary_messages = chat_mock.call_args_list[-1].args[2]
        summary_payload = summary_messages[-1]["content"]
        first_stage_settings = chat_mock.call_args_list[0].kwargs["settings"]
        self.assertEqual(first_stage_settings["ollama_num_gpu"], 0)
        self.assertEqual(first_stage_settings["ollama_keep_alive_effective"], "0")
        self.assertIn("clean phrase", summary_payload)
        self.assertNotIn("raw noise phrase raw noise phrase", summary_payload)
        saved_transcript = db.get_transcript(transcript["id"])
        self.assertEqual(saved_transcript["latest_pipeline_run_id"], run["id"])
        self.assertIn("clean summary", saved_transcript["summary"])
        self.assertEqual(saved_transcript["structured_json"]["topic"], "demo")
        self.assertTrue(saved_transcript["name"])

    def test_pipeline_tasks_are_normalized_for_transcript_record(self):
        transcript = db.create_transcript(profile_id=self.profile_id, name="Call", content="raw call")
        responses = [
            "clean call",
            '[{"segment_id": 1, "text": "clean call"}]',
            '{"theme": "Website pricing", "summary": "Нужно уточнить цены.", "tasks": [{"title": "Уточнить источник цены", "details": "В разговоре неясно, откуда берется старая цена.", "owner": "не указано", "status": "open"}], "solutions": ["Провести диагностику"], "responsible": "Unknown speaker", "schedules": "not specified"}',
        ]

        with (
            patch.object(pipeline.model_service, "is_model_installed", return_value=True),
            patch.object(
                pipeline.ChatService,
                "chat_completion",
                autospec=True,
                side_effect=lambda self, model, messages, *, settings: responses.pop(0),
            ),
        ):
            run = pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="balanced", action="tasks")

        task = run["structured_json"]["tasks"][0]
        self.assertEqual(task["task"], "Уточнить источник цены")
        self.assertIn("старая цена", task["context"])
        saved_transcript = db.get_transcript(transcript["id"])
        self.assertEqual(saved_transcript["summary"], "Нужно уточнить цены.")
        self.assertEqual(saved_transcript["structured_json"]["tasks"][0]["task"], "Уточнить источник цены")

    def test_speaker_overrides_are_saved_and_summary_regenerates(self):
        transcript = db.create_transcript(profile_id=self.profile_id, name="Call", content="hello")
        run = db.create_pipeline_run(
            transcript_id=transcript["id"],
            profile_id=self.profile_id,
            session_id=None,
            preset="balanced",
            action="full",
            raw_transcript="hello",
            cleaned_transcript="hello",
            segments=[{"segment_id": 1, "text": "hello"}],
            speaker_mapping=[{"segment_id": 1, "speaker": "Unknown speaker", "confidence": 0.0, "text": "hello"}],
            speaker_overrides={},
            structured_json={"topic": "demo"},
            summary="old",
            stage_timings={},
            warnings=[],
            used_settings=config.DEFAULT_SETTINGS,
        )

        updated = pipeline.update_speakers(run["id"], {"1": "Alice"})
        self.assertEqual(updated["speaker_overrides"]["1"], "Alice")
        self.assertEqual(updated["speaker_mapping"][0]["speaker"], "Alice")
        self.assertTrue(updated["speaker_mapping"][0]["manual_override"])

        with (
            patch.object(pipeline.model_service, "is_model_installed", return_value=True),
            patch.object(pipeline.ChatService, "chat_completion", autospec=True, return_value="## Краткое резюме\nnew"),
        ):
            regenerated = pipeline.regenerate_summary(run["id"], save_memory=False)

        self.assertIn("new", regenerated["summary"])


if __name__ == "__main__":
    unittest.main()
