import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app import config, db
from app.schemas import ChatRequest
from app.services import models as model_service
from backend.apps.asr import pipeline
from backend.apps.chat.routes import _ensure_chat_model_available, _prepare_chat_request, start_chat_task
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

    def test_rag_ingest_and_prompt_context(self):
        config.RAG_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
        (config.RAG_SOURCE_DIR / "project.md").write_text(
            "Alpha project deadline is Friday. The owner is Speaker_1.",
            encoding="utf-8",
        )
        db.update_profile_preferences(self.profile_id, {"settings": {"rag_enabled": True}})

        ingest = rag_service.ingest_sources(self.profile_id)
        prepared = _prepare_chat_request(
            ChatRequest(query="What is Alpha project deadline?", profile_id=self.profile_id, model_name="qwen2.5:3b")
        )

        self.assertEqual(ingest["indexed"], 1)
        self.assertEqual(ingest["stats"]["documents"], 1)
        self.assertTrue(prepared["rag_chunks"])
        contents = [item["content"] for item in prepared["messages"]]
        rag_index = next(idx for idx, item in enumerate(contents) if "Relevant RAG context" in item)
        query_index = len(contents) - 1
        self.assertLess(rag_index, query_index)
        self.assertIn("Alpha project deadline", contents[rag_index])

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
        self.assertIn("clean phrase", summary_payload)
        self.assertNotIn("raw noise phrase raw noise phrase", summary_payload)

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
