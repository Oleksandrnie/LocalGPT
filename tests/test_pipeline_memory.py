import json
import sqlite3
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import config, db
from app.routes import profiles as profile_routes
from app.schemas import (
    AsrPreferencesUpdate,
    ChatRequest,
    ModelSettingsRequest,
    ModelSettingsReset,
    ProfileCreate,
    ProfilePreferencesUpdate,
    ProfileUpdate,
)
from app.services import models as model_service
from backend.apps.chat import routes as chat_routes
from backend.apps.asr import pipeline
from backend.apps.asr.transcripts import router as transcripts_router
from backend.apps.chat import tasks as chat_tasks
from backend.apps.chat.routes import _ensure_chat_model_available, _prepare_chat_request, _sse_event, router as chat_router, start_chat_task
from backend.apps.chat.service import response_language_instruction, sanitize_reply
from backend.apps.chat.services import ollama_runtime
from backend.apps.rag import routes as rag_routes
from backend.apps.rag import service as rag_service


class LocalGPTPipelineMemoryTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.tmpdir.name) / "localgpt-test.db"
        self.original_rag_source_dir = config.RAG_SOURCE_DIR
        self.original_asr_diagnostics_dir = config.ASR_DIAGNOSTICS_DIR
        config.RAG_SOURCE_DIR = Path(self.tmpdir.name) / "rag_sources"
        config.ASR_DIAGNOSTICS_DIR = Path(self.tmpdir.name) / "asr_diagnostics"
        db.init_db()
        self.profile_id = db.ensure_default_profile()

    def tearDown(self):
        with chat_tasks._LOCK:
            chat_tasks._TASKS.clear()
        config.RAG_SOURCE_DIR = self.original_rag_source_dir
        config.ASR_DIAGNOSTICS_DIR = self.original_asr_diagnostics_dir
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
        self.assertEqual(profile["preferences"]["asr"]["analysis_language"], "auto")
        self.assertEqual(profile["preferences"]["chat"]["dictation_model"], config.SETTINGS.whisper_default_model)

    def test_default_pipeline_uses_current_catalog_and_token_budget(self):
        expected = {
            "cleaner": (False, "qwen2.5:7b-instruct", 0, 6000),
            "segmenter": (False, "qwen2.5:7b-instruct", 0.05, 6000),
            "speaker_resolver": (False, "qwen2.5:7b-instruct", 0, 3000),
            "structurer": (True, "qwen3:8b", 0.05, 6000),
            "summary": (True, "qwen3:8b", 0.05, 7000),
        }

        for stage, (enabled, model, temperature, max_tokens) in expected.items():
            with self.subTest(stage=stage):
                self.assertEqual(config.DEFAULT_PIPELINE[stage]["enabled"], enabled)
                self.assertEqual(config.DEFAULT_PIPELINE[stage]["model"], model)
                self.assertEqual(config.DEFAULT_PIPELINE[stage]["temperature"], temperature)
                self.assertEqual(config.DEFAULT_PIPELINE[stage]["max_tokens"], max_tokens)

    def test_asr_pipeline_gpu_setting_defaults_to_configured_pipeline_value(self):
        self.assertEqual(pipeline._pipeline_num_gpu({}), config.SETTINGS.ollama_pipeline_num_gpu)
        self.assertIsNone(pipeline._pipeline_num_gpu({"pipeline_num_gpu": "auto"}))
        self.assertEqual(pipeline._pipeline_num_gpu({"pipeline_num_gpu": 0}), 0)

    def test_asr_pipeline_stop_terminates_stuck_ollama_runner(self):
        with patch.object(
            pipeline.ollama_runtime,
            "force_unload_models",
            return_value={
                "unloaded_models": ["qwen3:8b"],
                "unload_failed": [],
                "stuck_models": ["qwen3:8b"],
                "terminated_runner_pids": [12345],
                "terminate_failed_pids": [],
            },
        ) as force_unload:
            result = pipeline.request_pipeline_stop()

        self.assertTrue(result["pipeline_stop_requested"])
        self.assertIn("qwen3:8b", result["active_models"])
        self.assertEqual(result["stuck_models"], ["qwen3:8b"])
        self.assertEqual(result["terminated_runner_pids"], [12345])
        force_unload.assert_called_once()
        self.assertTrue(force_unload.call_args.kwargs["terminate_stuck_runners"])

    def test_legacy_profile_pipeline_summary_default_migrates_to_qwen3(self):
        old_summary_default = {
            "enabled": True,
            "model": "mistral-nemo:12b",
            "temperature": 0.1,
            "max_tokens": 8000,
        }
        db.update_profile_preferences(
            self.profile_id,
            {"settings": {"pipeline": {"summary": old_summary_default}}},
        )
        conn = db._connect()
        try:
            conn.execute("DELETE FROM app_settings WHERE key = ?", ("migration_asr_pipeline_summary_default_qwen3",))
            db._migrate_asr_pipeline_summary_default_qwen3(conn)
            conn.commit()
        finally:
            conn.close()

        profile = db.get_profile(self.profile_id)
        summary_cfg = profile["preferences"]["settings"]["pipeline"]["summary"]

        self.assertEqual(summary_cfg["model"], "qwen3:8b")
        self.assertEqual(summary_cfg["max_tokens"], 7000)

    def test_custom_pipeline_settings_override_updated_defaults(self):
        db.upsert_model_settings(
            self.profile_id,
            "qwen2.5:7b-instruct",
            pipeline={"cleaner": {"model": "qwen2.5:3b-instruct", "temperature": 0.2, "max_tokens": 1234}},
        )

        settings = db.effective_settings(self.profile_id, "qwen2.5:7b-instruct", config.DEFAULT_SETTINGS)
        pipeline_settings = settings["effective"]["pipeline"]

        self.assertEqual(pipeline_settings["cleaner"]["model"], "qwen2.5:3b-instruct")
        self.assertEqual(pipeline_settings["cleaner"]["max_tokens"], 1234)
        self.assertEqual(pipeline_settings["segmenter"]["model"], "qwen2.5:7b-instruct")
        self.assertFalse(pipeline_settings["segmenter"]["enabled"])
        self.assertEqual(pipeline_settings["segmenter"]["max_tokens"], 6000)

    def test_asr_pipeline_reset_uses_current_defaults_over_stale_profile_pipeline(self):
        stale_pipeline = deepcopy(config.DEFAULT_PIPELINE)
        stale_pipeline["cleaner"] = {
            "enabled": True,
            "model": "qwen2.5:7b-instruct",
            "temperature": 0.2,
            "max_tokens": 9000,
        }
        stale_pipeline["segmenter"] = {
            "enabled": True,
            "model": "qwen2.5:7b-instruct",
            "temperature": 0.2,
            "max_tokens": 8000,
        }
        stale_pipeline["speaker_resolver"] = {
            "enabled": True,
            "model": "qwen2.5:7b-instruct",
            "temperature": 0.2,
            "max_tokens": 4000,
        }
        db.update_profile_preferences(self.profile_id, {"settings": {"pipeline": stale_pipeline}})

        result = profile_routes.reset_model_settings(
            ModelSettingsReset(profile_id=self.profile_id, model_name=pipeline.ASR_PIPELINE_SETTINGS_MODEL_ID)
        )
        effective_pipeline = result["effective"]["pipeline"]

        self.assertEqual(result["effective"]["ollama_think"], "off")
        self.assertEqual(effective_pipeline["cleaner"], config.DEFAULT_PIPELINE["cleaner"])
        self.assertEqual(effective_pipeline["segmenter"], config.DEFAULT_PIPELINE["segmenter"])
        self.assertEqual(effective_pipeline["speaker_resolver"], config.DEFAULT_PIPELINE["speaker_resolver"])
        self.assertEqual(effective_pipeline["structurer"], config.DEFAULT_PIPELINE["structurer"])
        self.assertEqual(effective_pipeline["summary"], config.DEFAULT_PIPELINE["summary"])

    def test_model_settings_validate_and_round_trip_token_budgets(self):
        result = profile_routes.save_model_settings(
            ModelSettingsRequest(
                profile_id=self.profile_id,
                model_name="qwen3:8b",
                output_tokens=900,
                thinking_tokens=1800,
                ollama_think="on",
            )
        )

        self.assertEqual(result["effective"]["output_tokens"], 900)
        self.assertEqual(result["effective"]["thinking_tokens"], 1800)
        self.assertEqual(result["effective"]["max_tokens"], 900)
        with self.assertRaises(HTTPException) as ctx:
            profile_routes.save_model_settings(
                ModelSettingsRequest(
                    profile_id=self.profile_id,
                    model_name="qwen3:8b",
                    output_tokens=0,
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail["code"], "invalid_output_tokens")

    def test_asr_analysis_actions_map_to_generic_stages(self):
        pipeline_cfg = deepcopy(config.DEFAULT_PIPELINE)

        self.assertFalse(pipeline._stage_enabled("cleaner", "summary", "balanced", pipeline_cfg))
        self.assertTrue(pipeline._stage_enabled("summary", "summary", "balanced", pipeline_cfg))

        self.assertFalse(pipeline._stage_enabled("cleaner", "smart_summary", "balanced", pipeline_cfg))
        self.assertFalse(pipeline._stage_enabled("speaker_resolver", "smart_summary", "balanced", pipeline_cfg))
        self.assertTrue(pipeline._stage_enabled("structurer", "smart_summary", "balanced", pipeline_cfg))
        self.assertTrue(pipeline._stage_enabled("summary", "smart_summary", "balanced", pipeline_cfg))

        self.assertFalse(pipeline._stage_enabled("cleaner", "full", "balanced", pipeline_cfg))
        self.assertFalse(pipeline._stage_enabled("segmenter", "full", "balanced", pipeline_cfg))
        self.assertFalse(pipeline._stage_enabled("speaker_resolver", "full", "balanced", pipeline_cfg))
        self.assertTrue(pipeline._stage_enabled("structurer", "full", "balanced", pipeline_cfg))
        self.assertTrue(pipeline._stage_enabled("summary", "full", "balanced", pipeline_cfg))

        pipeline_cfg["structurer"]["enabled"] = False
        pipeline_cfg["summary"]["enabled"] = False
        self.assertFalse(pipeline._stage_enabled("structurer", "smart_summary", "balanced", pipeline_cfg))
        self.assertFalse(pipeline._stage_enabled("summary", "smart_summary", "balanced", pipeline_cfg))

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

    def test_profile_preferences_persist_streaming_enabled(self):
        profile = db.get_profile(self.profile_id)
        self.assertTrue(profile["preferences"]["settings"]["streaming_enabled"])

        updated = profile_routes.update_profile_preferences(
            self.profile_id,
            ProfilePreferencesUpdate(settings={"streaming_enabled": False}),
        )
        settings = db.effective_settings(self.profile_id, "qwen2.5:7b-instruct", config.DEFAULT_SETTINGS)

        self.assertFalse(updated["preferences"]["settings"]["streaming_enabled"])
        self.assertFalse(settings["effective"]["streaming_enabled"])
        self.assertFalse(settings["overrides"]["streaming_enabled"])

        updated = profile_routes.update_profile_preferences(
            self.profile_id,
            ProfilePreferencesUpdate(settings={"streaming_enabled": True}),
        )
        settings = db.effective_settings(self.profile_id, "qwen2.5:7b-instruct", config.DEFAULT_SETTINGS)

        self.assertTrue(updated["preferences"]["settings"]["streaming_enabled"])
        self.assertTrue(settings["effective"]["streaming_enabled"])
        self.assertTrue(settings["overrides"]["streaming_enabled"])

    def test_chat_model_missing_is_readable(self):
        with patch.object(model_service, "is_model_installed", return_value=False):
            with self.assertRaises(HTTPException) as ctx:
                _ensure_chat_model_available("qwen2.5:3b")

        self.assertEqual(ctx.exception.status_code, 424)
        self.assertEqual(ctx.exception.detail["code"], "chat_model_missing")

    def test_chat_task_model_missing_creates_failed_assistant_message(self):
        req = ChatRequest(query="hello", profile_id=self.profile_id, model_name="qwen2.5:3b")
        with patch.object(model_service, "is_model_installed", return_value=False):
            task = start_chat_task(req)

        self.assertEqual(task["state"], "failed")
        self.assertEqual(task["error_code"], "chat_model_missing")
        self.assertIsNotNone(task["user_message_id"])
        self.assertIsNotNone(task["assistant_message_id"])

        messages = db.get_messages(task["session_id"])
        self.assertEqual([item["role"] for item in messages], ["user", "assistant"])
        self.assertEqual(messages[0]["content"], "hello")
        self.assertEqual(messages[0]["status"], "completed")
        self.assertEqual(messages[1]["status"], "failed")
        self.assertEqual(messages[1]["error"], "Модель не загружена. Загрузите модель и повторите отправку.")
        self.assertEqual(messages[1]["task_id"], task["id"])

    def test_chat_task_without_model_is_rejected_before_session_created(self):
        req = ChatRequest(query="hello", profile_id=self.profile_id)

        with self.assertRaises(HTTPException) as ctx:
            start_chat_task(req)

        self.assertEqual(ctx.exception.status_code, 424)
        self.assertEqual(ctx.exception.detail["code"], "chat_model_not_selected")
        self.assertEqual(db.list_sessions(self.profile_id), [])

    def test_chat_task_creates_persistent_user_and_assistant_before_worker(self):
        req = ChatRequest(query="hello", profile_id=self.profile_id, model_name="qwen2.5:7b-instruct")

        def fake_start_chat_task(**kwargs):
            return {
                "id": "ct_fake",
                "task_id": "ct_fake",
                "state": "generating",
                "session_id": kwargs["session_id"],
                "conversation_id": kwargs["session_id"],
                "profile_id": kwargs["profile_id"],
                "model_name": kwargs["model_name"],
                "role": kwargs["role"],
                "user_message_id": kwargs["user_message_id"],
                "assistant_message_id": kwargs["assistant_message_id"],
                "message": "Chat generation started.",
                "error_code": None,
                "pid": 123,
                "used_settings": kwargs["used_settings"],
                "router_notice": kwargs["router_notice"],
                "result": None,
                "stream": bool(kwargs.get("stream")),
                "streaming_enabled": bool(kwargs.get("stream")),
            }

        with (
            patch.object(model_service, "is_model_installed", return_value=True),
            patch("backend.apps.chat.routes.chat_tasks.start_chat_task", side_effect=fake_start_chat_task) as task_mock,
        ):
            task = start_chat_task(req)

        self.assertEqual(task["state"], "generating")
        self.assertEqual(task["task_id"], "ct_fake")
        self.assertIsNotNone(task["user_message_id"])
        self.assertIsNotNone(task["assistant_message_id"])
        self.assertFalse(task["stream"])
        self.assertFalse(task["streaming_enabled"])
        task_mock.assert_called_once()
        self.assertFalse(task_mock.call_args.kwargs["stream"])
        self.assertFalse(task_mock.call_args.kwargs["used_settings"]["streaming_enabled"])

        messages = db.get_messages(task["session_id"])
        self.assertEqual([item["role"] for item in messages], ["user", "assistant"])
        self.assertEqual(messages[0]["id"], task["user_message_id"])
        self.assertEqual(messages[0]["content"], "hello")
        self.assertEqual(messages[0]["status"], "completed")
        self.assertEqual(messages[1]["id"], task["assistant_message_id"])
        self.assertEqual(messages[1]["content"], "")
        self.assertEqual(messages[1]["status"], "generating")
        self.assertEqual(messages[1]["model"], "qwen2.5:7b-instruct")

    def test_chat_task_stream_true_is_passed_to_worker(self):
        req = ChatRequest(query="hello", profile_id=self.profile_id, model_name="qwen2.5:7b-instruct", stream=True)

        def fake_start_chat_task(**kwargs):
            return {
                "id": "ct_stream_true",
                "task_id": "ct_stream_true",
                "state": "generating",
                "session_id": kwargs["session_id"],
                "conversation_id": kwargs["session_id"],
                "profile_id": kwargs["profile_id"],
                "model_name": kwargs["model_name"],
                "role": kwargs["role"],
                "user_message_id": kwargs["user_message_id"],
                "assistant_message_id": kwargs["assistant_message_id"],
                "message": "Chat generation started.",
                "error_code": None,
                "pid": 123,
                "used_settings": kwargs["used_settings"],
                "router_notice": kwargs["router_notice"],
                "result": None,
                "stream": bool(kwargs.get("stream")),
                "streaming_enabled": bool(kwargs.get("stream")),
            }

        with (
            patch.object(model_service, "is_model_installed", return_value=True),
            patch("backend.apps.chat.routes.chat_tasks.start_chat_task", side_effect=fake_start_chat_task) as task_mock,
        ):
            task = start_chat_task(req)

        self.assertTrue(task["stream"])
        self.assertTrue(task["streaming_enabled"])
        task_mock.assert_called_once()
        self.assertTrue(task_mock.call_args.kwargs["stream"])
        self.assertTrue(task_mock.call_args.kwargs["used_settings"]["streaming_enabled"])
        self.assertEqual(db.get_message(task["assistant_message_id"])["status"], "generating")

    def test_sse_event_formats_utf8_json(self):
        event = _sse_event("status", {"status": "generating", "message": "Привет"})

        self.assertEqual(event, 'event: status\ndata: {"status":"generating","message":"Привет"}\n\n')

    def test_chat_task_events_returns_model_and_done_events(self):
        session = db.create_session(self.profile_id, "SSE lifecycle", "qwen2.5:7b-instruct")
        user_message = db.add_message(session["id"], "user", "hello")
        assistant_message = db.create_assistant_message(
            session["id"],
            model="qwen2.5:7b-instruct",
        )
        task = chat_tasks.create_completed_task(
            session_id=session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5:7b-instruct",
            role="chat",
            used_settings={},
            reply="Привет, готово.",
            user_message_id=user_message["id"],
            assistant_message_id=assistant_message["id"],
        )

        app = FastAPI()
        app.include_router(chat_router)
        client = TestClient(app)

        with client.stream("GET", f"/chat/tasks/{task['id']}/events") as response:
            self.assertEqual(response.status_code, 200)
            body = "".join(response.iter_text())

        self.assertIn("event: model_selected\n", body)
        self.assertIn('"model":"qwen2.5:7b-instruct"', body)
        self.assertIn("event: done\n", body)
        self.assertIn('"status":"completed"', body)

    def test_reasoning_endpoint_restores_only_profile_owned_assistant_reasoning(self):
        session = db.create_session(self.profile_id, "Reasoning API", "qwen3:4b")
        assistant = db.add_message(
            session["id"],
            "assistant",
            "Финальный ответ",
            reasoning="Сохранённое рассуждение",
        )
        other_profile = db.create_profile("Other", None, None)
        app = FastAPI()
        app.include_router(chat_router)
        client = TestClient(app)

        response = client.get(
            f"/chat/messages/{assistant['id']}/reasoning",
            params={"profile_id": self.profile_id},
        )
        forbidden = client.get(
            f"/chat/messages/{assistant['id']}/reasoning",
            params={"profile_id": other_profile["id"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reasoning"], "Сохранённое рассуждение")
        self.assertEqual(forbidden.status_code, 403)

    def test_non_streaming_worker_uses_full_response_and_updates_assistant_message(self):
        session = db.create_session(self.profile_id, "Non-streaming fallback", "qwen2.5:7b-instruct")
        assistant_message = db.create_assistant_message(
            session["id"],
            model="qwen2.5:7b-instruct",
            task_id="ct_non_streaming",
        )
        result_path = Path(self.tmpdir.name) / "non-streaming.result.json"
        error_path = Path(self.tmpdir.name) / "non-streaming.error.json"
        delta_path = Path(self.tmpdir.name) / "non-streaming.deltas.jsonl"
        status_path = Path(self.tmpdir.name) / "non-streaming.status.json"

        with (
            patch(
                "backend.apps.chat.tasks.ChatService.chat_completion_result",
                return_value=ollama_runtime.ChatCompletionResult(
                    content="Полный ответ",
                    reasoning="Нестриминговое рассуждение",
                    done_reason="stop",
                ),
            ) as full_response,
            patch("backend.apps.chat.tasks.ChatService.chat_completion_stream_events") as stream_response,
        ):
            chat_tasks._chat_worker(
                "qwen2.5:7b-instruct",
                [{"role": "user", "content": "hello"}],
                {"streaming_enabled": False},
                session["id"],
                self.profile_id,
                assistant_message["id"],
                False,
                str(delta_path),
                str(status_path),
                str(result_path),
                str(error_path),
            )

        full_response.assert_called_once()
        stream_response.assert_not_called()
        self.assertFalse(delta_path.exists())
        self.assertFalse(status_path.exists())
        self.assertFalse(error_path.exists())
        self.assertEqual(json.loads(result_path.read_text(encoding="utf-8"))["reply"], "Полный ответ")

        updated_message = db.get_message(assistant_message["id"])
        self.assertEqual(updated_message["status"], "completed")
        self.assertEqual(updated_message["content"], "Полный ответ")
        self.assertEqual(updated_message["reasoning"], "Нестриминговое рассуждение")
        self.assertFalse(updated_message["is_partial"])
        self.assertIsNone(updated_message["error"])

    def test_streaming_worker_separates_reasoning_from_final_deltas(self):
        session = db.create_session(self.profile_id, "Reasoning stream", "qwen3:4b")
        assistant_message = db.create_assistant_message(session["id"], model="qwen3:4b")
        result_path = Path(self.tmpdir.name) / "reasoning.result.json"
        error_path = Path(self.tmpdir.name) / "reasoning.error.json"
        delta_path = Path(self.tmpdir.name) / "reasoning.deltas.jsonl"
        status_path = Path(self.tmpdir.name) / "reasoning.status.json"

        events = iter(
            [
                ollama_runtime.ChatStreamEvent(reasoning="internal "),
                ollama_runtime.ChatStreamEvent(reasoning="trace"),
                ollama_runtime.ChatStreamEvent(content="Финальный "),
                ollama_runtime.ChatStreamEvent(content="ответ"),
                ollama_runtime.ChatStreamEvent(done=True, done_reason="stop", eval_count=12),
            ]
        )
        with patch(
            "backend.apps.chat.tasks.ChatService.chat_completion_stream_events",
            return_value=events,
        ):
            chat_tasks._chat_worker(
                "qwen3:4b",
                [{"role": "user", "content": "hello"}],
                {"streaming_enabled": True, "ollama_think": "on"},
                session["id"],
                self.profile_id,
                assistant_message["id"],
                True,
                str(delta_path),
                str(status_path),
                str(result_path),
                str(error_path),
            )

        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(result["reply"], "Финальный ответ")
        self.assertEqual(result["reasoning"], "internal trace")
        self.assertEqual(result["done_reason"], "stop")
        self.assertEqual(result["eval_count"], 12)
        delta_text = delta_path.read_text(encoding="utf-8")
        self.assertIn("Финальный ", delta_text)
        self.assertIn("ответ", delta_text)
        self.assertNotIn("internal", delta_text)
        persisted = db.get_message(assistant_message["id"])
        self.assertEqual(persisted["content"], "Финальный ответ")
        self.assertEqual(persisted["reasoning"], "internal trace")
        history_message = db.get_messages(session["id"])[0]
        self.assertTrue(history_message["has_reasoning"])
        self.assertNotIn("reasoning", history_message)
        self.assertFalse(error_path.exists())

    def test_reasoning_only_length_exhaustion_fails_worker(self):
        session = db.create_session(self.profile_id, "Reasoning exhausted", "qwen3:4b")
        assistant_message = db.create_assistant_message(session["id"], model="qwen3:4b")
        result_path = Path(self.tmpdir.name) / "exhausted.result.json"
        error_path = Path(self.tmpdir.name) / "exhausted.error.json"
        delta_path = Path(self.tmpdir.name) / "exhausted.deltas.jsonl"
        status_path = Path(self.tmpdir.name) / "exhausted.status.json"

        events = iter(
            [
                ollama_runtime.ChatStreamEvent(reasoning="unfinished reasoning"),
                ollama_runtime.ChatStreamEvent(done=True, done_reason="length", eval_count=64),
            ]
        )
        with patch(
            "backend.apps.chat.tasks.ChatService.chat_completion_stream_events",
            return_value=events,
        ):
            chat_tasks._chat_worker(
                "qwen3:4b",
                [{"role": "user", "content": "hello"}],
                {"streaming_enabled": True, "ollama_think": "on"},
                session["id"],
                self.profile_id,
                assistant_message["id"],
                True,
                str(delta_path),
                str(status_path),
                str(result_path),
                str(error_path),
            )

        error = json.loads(error_path.read_text(encoding="utf-8"))
        self.assertEqual(error["code"], "chat_final_answer_incomplete")
        self.assertIn("Thinking budget exhausted", error["message"])
        self.assertFalse(result_path.exists())
        updated = db.get_message(assistant_message["id"])
        self.assertEqual(updated["status"], "failed")
        self.assertEqual(updated["content"], "")

    def test_chat_task_events_streams_delta_events_from_task_artifact(self):
        session = db.create_session(self.profile_id, "SSE delta", "qwen2.5:7b-instruct")
        delta_path = Path(self.tmpdir.name) / "task.deltas.jsonl"
        task_id = "ct_delta_test"
        chat_tasks._append_delta_jsonl(delta_path, 1, "При")
        chat_tasks._append_delta_jsonl(delta_path, 2, "вет")
        with chat_tasks._LOCK:
            chat_tasks._TASKS[task_id] = {
                "id": task_id,
                "state": "completed",
                "created_at": "2026-05-06T10:00:00Z",
                "updated_at": "2026-05-06T10:00:01Z",
                "session_id": session["id"],
                "profile_id": self.profile_id,
                "model_name": "qwen2.5:7b-instruct",
                "role": "chat",
                "assistant_message_id": 42,
                "message": "Chat generation completed.",
                "error_code": None,
                "used_settings": {},
                "result": {"reply": "Привет"},
                "delta_path": str(delta_path),
                "stream": True,
            }

        app = FastAPI()
        app.include_router(chat_router)
        client = TestClient(app)

        with client.stream("GET", f"/chat/tasks/{task_id}/events") as response:
            self.assertEqual(response.status_code, 200)
            body = "".join(response.iter_text())

        self.assertIn("event: delta\n", body)
        self.assertIn('"sequence":1', body)
        self.assertIn('"text":"При"', body)
        self.assertIn('"sequence":2', body)
        self.assertIn('"text":"вет"', body)
        self.assertIn("event: done\n", body)

    def test_missing_runtime_task_marks_active_assistant_message_failed(self):
        session = db.create_session(self.profile_id, "Stale task", "qwen2.5:7b-instruct")
        assistant_message = db.create_assistant_message(
            session["id"],
            model="qwen2.5:7b-instruct",
            task_id="ct_missing_runtime",
        )

        app = FastAPI()
        app.include_router(chat_router)
        client = TestClient(app)
        response = client.get("/chat/tasks/ct_missing_runtime")

        self.assertEqual(response.status_code, 404)
        updated_message = db.get_message(assistant_message["id"])
        self.assertEqual(updated_message["status"], "failed")
        self.assertFalse(updated_message["is_partial"])
        self.assertIn("backend был перезапущен", updated_message["error"])

    def test_missing_runtime_sse_marks_active_assistant_message_failed(self):
        session = db.create_session(self.profile_id, "Stale SSE", "qwen2.5:7b-instruct")
        assistant_message = db.create_assistant_message(
            session["id"],
            model="qwen2.5:7b-instruct",
            task_id="ct_missing_sse",
        )

        with self.assertRaises(HTTPException) as ctx:
            chat_routes.get_chat_task_events("ct_missing_sse", request=None)

        self.assertEqual(ctx.exception.status_code, 404)
        updated_message = db.get_message(assistant_message["id"])
        self.assertEqual(updated_message["status"], "failed")
        self.assertFalse(updated_message["is_partial"])

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

    def test_chat_message_lifecycle_helpers(self):
        session = db.create_session(self.profile_id, "Lifecycle test", "qwen2.5:7b-instruct")

        user_message = db.add_message(session["id"], "user", "hello")
        assistant_message = db.create_assistant_message(
            session["id"],
            model="qwen2.5:7b-instruct",
            task_id="ct_test",
        )

        self.assertEqual(user_message["status"], "completed")
        self.assertFalse(user_message["is_partial"])
        self.assertEqual(assistant_message["status"], "generating")
        self.assertTrue(assistant_message["is_partial"])
        self.assertEqual(assistant_message["content"], "")
        self.assertEqual(assistant_message["model"], "qwen2.5:7b-instruct")
        self.assertEqual(assistant_message["task_id"], "ct_test")
        self.assertIsNotNone(assistant_message["generation_started_at"])
        self.assertEqual(db.get_message_by_task_id("ct_test")["id"], assistant_message["id"])

        streaming_message = db.append_message_content(assistant_message["id"], "Привет", status="streaming")
        self.assertEqual(streaming_message["status"], "streaming")
        self.assertEqual(streaming_message["content"], "Привет")
        self.assertTrue(streaming_message["is_partial"])

        completed_message = db.update_message(
            assistant_message["id"],
            content="Привет, готово.",
            reasoning="Внутреннее рассуждение",
            status="completed",
            error=None,
        )
        self.assertEqual(completed_message["status"], "completed")
        self.assertEqual(completed_message["content"], "Привет, готово.")
        self.assertEqual(completed_message["reasoning"], "Внутреннее рассуждение")
        self.assertTrue(completed_message["has_reasoning"])
        self.assertFalse(completed_message["is_partial"])
        self.assertIsNotNone(completed_message["generation_finished_at"])

        messages = db.get_messages(session["id"])
        self.assertEqual([item["id"] for item in messages], [user_message["id"], assistant_message["id"]])
        self.assertTrue(all("updated_at" in item for item in messages))
        self.assertTrue(messages[-1]["has_reasoning"])
        self.assertNotIn("reasoning", messages[-1])

    def test_reasoning_storage_applies_explicit_size_cap(self):
        session = db.create_session(self.profile_id, "Reasoning cap", "qwen3:4b")
        assistant = db.add_message(
            session["id"],
            "assistant",
            "Final",
            reasoning="x" * (db.REASONING_MAX_CHARS + 100),
        )

        self.assertLessEqual(len(assistant["reasoning"]), db.REASONING_MAX_CHARS)
        self.assertTrue(assistant["reasoning"].endswith("[Reasoning truncated by LocalGPT storage limit.]"))

    def test_legacy_chat_messages_migrate_to_completed(self):
        legacy_path = Path(self.tmpdir.name) / "legacy-messages.db"
        db.DB_PATH = legacy_path
        now = "2026-05-06T10:00:00"
        with sqlite3.connect(legacy_path) as conn:
            conn.executescript(
                """
                CREATE TABLE profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT NULL,
                    color TEXT NULL,
                    preferences_json TEXT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE chat_sessions (
                    id TEXT PRIMARY KEY,
                    profile_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'chat',
                    criteria_json TEXT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                );

                CREATE TABLE chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME NOT NULL
                );

                CREATE TABLE app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at DATETIME NOT NULL
                );
                """
            )
            conn.execute(
                """
                INSERT INTO profiles (id, name, description, color, preferences_json, created_at, updated_at, is_active)
                VALUES (1, 'Default', 'Default profile', NULL, NULL, ?, ?, 1)
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT INTO chat_sessions (id, profile_id, title, model_name, role, created_at, updated_at)
                VALUES ('legacy-session', 1, 'Legacy', 'qwen2.5:7b-instruct', 'chat', ?, ?)
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, created_at)
                VALUES ('legacy-session', 'assistant', 'old answer', ?)
                """,
                (now,),
            )
            conn.commit()

        db.init_db()
        messages = db.get_messages("legacy-session")

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "old answer")
        self.assertEqual(messages[0]["status"], "completed")
        self.assertEqual(messages[0]["updated_at"], now)
        self.assertFalse(messages[0]["is_partial"])
        self.assertFalse(messages[0]["has_reasoning"])
        with sqlite3.connect(legacy_path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_messages)").fetchall()}
        self.assertIn("reasoning", columns)

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
        self.assertTrue(any("Языковое правило" in item for item in contents))
        self.assertTrue(any("Ответь на английском" in item for item in contents))

    def test_language_policy_ignores_profile_language_without_user_request(self):
        db.update_profile_preferences(self.profile_id, {"chat": {"system_prompt": "Always answer in English."}})

        prepared = _prepare_chat_request(
            ChatRequest(query="как узнать id папки google drive?", profile_id=self.profile_id, model_name="qwen2.5:3b")
        )
        contents = [item["content"] for item in prepared["messages"]]
        profile_index = next(idx for idx, item in enumerate(contents) if "Always answer in English." in item)
        language_index = next(idx for idx, item in enumerate(contents) if "Ответь на русском" in item)

        self.assertGreater(language_index, profile_index)
        self.assertIn("профильных инструкций не является разрешением", contents[language_index])

    def test_explicit_response_language_can_override_question_language(self):
        instruction = response_language_instruction("Ответь на английском: как узнать ID папки Google Drive?")

        self.assertIn("явно просит ответить на английском", instruction)
        self.assertIn("Ответь на английском", instruction)

    def test_response_formatting_guardrail_is_global(self):
        prepared = _prepare_chat_request(
            ChatRequest(query="проверь расчет 23730 + 11960", profile_id=self.profile_id, model_name="qwen2.5:3b")
        )
        contents = [item["content"] for item in prepared["messages"]]

        self.assertTrue(any("Не используй LaTeX" in item for item in contents))
        self.assertTrue(any("35,690 ₽" in item and "35 690 ₽" in item for item in contents))
        self.assertTrue(any("119 600 ₽" in item and "$1,250" in item and "€1,250" in item for item in contents))

    def test_sanitize_reply_normalizes_latex_currency_format(self):
        raw = r"Итого: \[ 23,730 \, \text{₽} + 11,960 \, \text{₽} = 35,690 \, \text{₽} \]"

        cleaned = sanitize_reply(raw)

        self.assertNotIn(r"\[", cleaned)
        self.assertNotIn(r"\text", cleaned)
        self.assertIn("23 730 ₽ + 11 960 ₽ = 35 690 ₽", cleaned)

    def test_sanitize_reply_normalizes_accidental_currency_glyph_after_amount(self):
        cleaned = sanitize_reply("Итоговая стоимость: 950 670 ⽇")

        self.assertEqual(cleaned, "Итоговая стоимость: 950 670 ₽")

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

        self.assertEqual(ingest["indexed"], 1)
        self.assertEqual(ingest["stats"]["documents"], 1)
        self.assertFalse((source_dir / "project.json").exists())
        self.assertTrue(prepared["rag_chunks"])
        contents = [item["content"] for item in prepared["messages"]]
        rag_index = next(idx for idx, item in enumerate(contents) if "Relevant RAG context" in item)
        query_index = len(contents) - 1
        self.assertLess(rag_index, query_index)
        self.assertIn("Alpha project deadline", contents[rag_index])
        self.assertIn("Markdown sources as authoritative", contents[rag_index])
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

    def test_rag_price_query_prioritizes_pricing_markdown(self):
        source_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        (source_dir / "company.kb.pricing.md").write_text(
            "# Тарифы\n\nБазовая услуга — 9 990 ₽ в месяц.",
            encoding="utf-8",
        )
        (source_dir / "company.context.md").write_text(
            "Компания оказывает услуги по поддержке сайтов.",
            encoding="utf-8",
        )
        rag_service.ingest_sources(self.profile_id)

        results = rag_service.search(self.profile_id, "какие цены есть на услуги", top_k=5)

        self.assertTrue(results)
        self.assertEqual(results[0]["source_id"], "company.kb.pricing.md")
        self.assertIn("9 990 ₽", results[0]["content"])

    def test_rag_ingest_accepts_only_markdown_and_removes_legacy_json_index(self):
        source_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        md_path = source_dir / "plain.md"
        md_path.write_text("Первичная заметка.", encoding="utf-8")
        legacy_json = source_dir / "plain.json"
        legacy_json.write_text('{"fact":"legacy duplicate"}', encoding="utf-8")
        db.create_source_document(
            profile_id=self.profile_id,
            session_id=None,
            source_type=rag_service.SOURCE_TYPE,
            source_id="plain.json",
            title="plain.json",
            content=None,
            metadata={},
        )

        ingest = rag_service.ingest_sources(self.profile_id, force=True)

        self.assertEqual(rag_service.SUPPORTED_SUFFIXES, {".md"})
        self.assertEqual(ingest["scanned"], 1)
        self.assertEqual(ingest["indexed"], 1)
        self.assertEqual(ingest["removed_stale"], 1)
        self.assertTrue(legacy_json.exists())
        self.assertEqual(rag_service.status(self.profile_id)["files"], ["plain.md"])
        self.assertEqual(db.rag_stats(self.profile_id)["documents"], 1)

    def test_rag_delete_file_removes_file_and_auto_companion(self):
        source_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        md_path = source_dir / "delete-me.md"
        md_path.write_text("Удаляемая заметка.", encoding="utf-8")
        rag_service.ingest_sources(self.profile_id, force=True)
        self.assertGreater(db.rag_stats(self.profile_id)["documents"], 0)

        result = rag_service.delete_file(self.profile_id, "delete-me.md")

        self.assertIn("delete-me.md", result["deleted"])
        self.assertFalse(md_path.exists())
        self.assertEqual(db.rag_stats(self.profile_id)["documents"], 0)

    def test_rag_files_are_scoped_per_profile(self):
        first_dir = rag_service.ensure_profile_source_dir(self.profile_id)
        second = db.create_profile("Work", None, None)
        second_dir = rag_service.ensure_profile_source_dir(second["id"])
        (first_dir / "one.md").write_text("Only alpha_unique_profile_fact.", encoding="utf-8")
        (second_dir / "two.md").write_text("Only beta_unique_profile_fact.", encoding="utf-8")

        first_ingest = rag_service.ingest_sources(self.profile_id)
        second_ingest = rag_service.ingest_sources(second["id"])

        self.assertEqual(first_ingest["stats"]["documents"], 1)
        self.assertEqual(second_ingest["stats"]["documents"], 1)
        self.assertTrue(rag_service.search(self.profile_id, "alpha_unique_profile_fact", top_k=3))
        results = rag_service.search(self.profile_id, "beta_unique_profile_fact", top_k=3)
        self.assertFalse(any("beta_unique_profile_fact" in item["content"] for item in results))

    def test_asr_context_transcript_auto_indexes_rag_and_can_be_deleted_from_rag(self):
        session = db.create_session(self.profile_id, "ASR context", "qwen2.5:7b-instruct")
        app = FastAPI()
        app.include_router(transcripts_router)
        app.include_router(rag_routes.router)
        client = TestClient(app)

        response = client.post(
            "/transcripts",
            json={
                "profile_id": self.profile_id,
                "session_id": session["id"],
                "name": "ASR обработанный контекст",
                "content": "unique_asr_context_fact значит решение уже принято.",
                "labels": {"origin": "asr_context"},
            },
        )

        self.assertEqual(response.status_code, 200)
        transcript = response.json()
        source_id = f"transcript:{transcript['id']}"
        self.assertEqual(transcript["rag_index"]["source_id"], source_id)
        self.assertGreater(transcript["rag_index"]["chunks_indexed"], 0)
        self.assertTrue(rag_service.search(self.profile_id, "unique_asr_context_fact", top_k=3))

        status = rag_service.status(self.profile_id)
        self.assertEqual(status["contexts"][0]["source_id"], source_id)

        delete_response = client.delete(
            "/rag/contexts",
            params={"profile_id": self.profile_id, "source_id": source_id},
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertIsNone(db.get_transcript(transcript["id"]))
        self.assertFalse(rag_service.search(self.profile_id, "unique_asr_context_fact", top_k=3))

    def test_full_analysis_skips_cleaner_by_default_and_sanitizes_speakers(self):
        db.update_profile_preferences(self.profile_id, {"settings": {"asr_full_analysis_enabled": True}})
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="raw repeated phrase raw repeated phrase",
            labels={"origin": "asr_tool"},
        )
        responses = [
            '[{"segment_id": 1, "text": "raw repeated phrase"}]',
            '[{"segment_id": 1, "speaker": "Alice", "confidence": 0.95, "text": "raw repeated phrase"}]',
            '{"topic": "demo", "tasks": [], "decisions": [], "risks": [], "open_questions": []}',
            "## Brief Summary\nraw repeated phrase summary",
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

        self.assertEqual(run["cleaned_transcript"], "raw repeated phrase raw repeated phrase")
        self.assertNotIn("cleaner", run["stage_timings"])
        self.assertEqual(run["speaker_mapping"][0]["speaker"], "Unknown speaker")
        self.assertIn("raw repeated phrase summary", run["summary"])
        summary_messages = chat_mock.call_args_list[-1].args[2]
        summary_payload = summary_messages[-1]["content"]
        first_stage_settings = chat_mock.call_args_list[0].kwargs["settings"]
        if config.SETTINGS.ollama_pipeline_num_gpu is None:
            self.assertNotIn("ollama_num_gpu", first_stage_settings)
        else:
            self.assertEqual(first_stage_settings["ollama_num_gpu"], config.SETTINGS.ollama_pipeline_num_gpu)
        self.assertFalse(first_stage_settings["ollama_allow_cpu_fallback"])
        self.assertEqual(first_stage_settings["ollama_keep_alive_effective"], "0")
        self.assertIn("raw repeated phrase", summary_payload)
        saved_transcript = db.get_transcript(transcript["id"])
        self.assertEqual(saved_transcript["latest_pipeline_run_id"], run["id"])
        self.assertIn("raw repeated phrase summary", saved_transcript["summary"])
        self.assertEqual(saved_transcript["structured_json"]["topic"], "demo")
        self.assertTrue(saved_transcript["name"])

    def test_smart_summary_runs_structurer_and_summary_without_cleaner_or_roles(self):
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="generic planning point repeated in another way",
            labels={"origin": "asr_tool"},
        )
        responses = [
            '{"topic": "generic planning", "summary": "generic structure", "tasks": [], "decisions": [], "risks": [], "open_questions": []}',
            "## Brief Summary\ngeneric planning point repeated summary",
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
            run = pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="balanced", action="smart_summary")

        self.assertEqual(run["action"], "smart_summary")
        self.assertEqual(run["cleaned_transcript"], "generic planning point repeated in another way")
        self.assertIn("structurer", run["stage_timings"])
        self.assertIn("summary", run["stage_timings"])
        self.assertNotIn("cleaner", run["stage_timings"])
        self.assertNotIn("speaker_resolver", run["stage_timings"])
        self.assertIn("generic planning point repeated summary", run["summary"])

    def test_smart_summary_respects_disabled_structurer_and_falls_back_to_summary(self):
        model_name = "qwen2.5:7b-instruct"
        db.upsert_model_settings(
            self.profile_id,
            model_name,
            pipeline={"structurer": {"enabled": False}},
        )
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="generic raw note",
            labels={"origin": "asr_tool"},
        )

        with (
            patch.object(pipeline.model_service, "is_model_installed", return_value=True),
            patch.object(
                pipeline.ChatService,
                "chat_completion",
                autospec=True,
                return_value="## Brief Summary\ngeneric raw note fallback summary",
            ),
        ):
            run = pipeline.run_transcript_pipeline(
                transcript_id=transcript["id"],
                preset="balanced",
                action="smart_summary",
                model_name=model_name,
            )

        self.assertIn("summary", run["stage_timings"])
        self.assertNotIn("structurer", run["stage_timings"])
        self.assertIn("smart_summary_structurer_disabled_fallback_summary", run["warnings"])
        self.assertIn("generic raw note fallback summary", run["summary"])

    def test_summary_stage_disabled_returns_clear_error(self):
        model_name = "qwen2.5:7b-instruct"
        db.upsert_model_settings(
            self.profile_id,
            model_name,
            pipeline={"summary": {"enabled": False}},
        )
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="generic raw note",
            labels={"origin": "asr_tool"},
        )

        with self.assertRaises(HTTPException) as raised:
            pipeline.run_transcript_pipeline(
                transcript_id=transcript["id"],
                preset="balanced",
                action="summary",
                model_name=model_name,
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "asr_summary_stage_disabled")

    def test_asr_pipeline_uses_dedicated_settings_without_chat_model_name(self):
        db.upsert_model_settings(
            self.profile_id,
            pipeline.ASR_PIPELINE_SETTINGS_MODEL_ID,
            pipeline={"summary": {"enabled": False}},
        )
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="generic raw note",
            labels={"origin": "asr_tool"},
        )

        with self.assertRaises(HTTPException) as raised:
            pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="balanced", action="summary")

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "asr_summary_stage_disabled")

    def test_asr_pipeline_defaults_disable_ollama_thinking(self):
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="generic raw note",
            labels={"origin": "asr_tool"},
        )

        with (
            patch.object(pipeline.model_service, "is_model_installed", return_value=True),
            patch.object(
                pipeline.ChatService,
                "chat_completion",
                autospec=True,
                return_value="## Brief Summary\ngeneric raw note summary",
            ) as chat_mock,
        ):
            pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="fast", action="summary")

        stage_settings = chat_mock.call_args.kwargs["settings"]
        self.assertIs(stage_settings["ollama_think"], False)
        self.assertFalse(stage_settings["ollama_allow_cpu_fallback"])

    def test_asr_diagnostics_preference_controls_profile_log_dir(self):
        path = config.ASR_DIAGNOSTICS_DIR / f"profile_{self.profile_id}"

        updated = profile_routes.update_profile_preferences(
            self.profile_id,
            ProfilePreferencesUpdate(asr=AsrPreferencesUpdate(diagnostics_enabled=True)),
        )

        self.assertTrue(updated["preferences"]["asr"]["diagnostics_enabled"])
        self.assertTrue(path.is_dir())

        updated = profile_routes.update_profile_preferences(
            self.profile_id,
            ProfilePreferencesUpdate(asr=AsrPreferencesUpdate(diagnostics_enabled=False)),
        )

        self.assertFalse(updated["preferences"]["asr"]["diagnostics_enabled"])
        self.assertFalse(path.exists())

    def test_asr_diagnostics_log_written_when_enabled(self):
        profile_routes.update_profile_preferences(
            self.profile_id,
            ProfilePreferencesUpdate(asr=AsrPreferencesUpdate(diagnostics_enabled=True)),
        )
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="generic raw note",
            labels={"origin": "asr_tool"},
        )

        with (
            patch.object(pipeline.model_service, "is_model_installed", return_value=True),
            patch.object(
                pipeline.ChatService,
                "chat_completion",
                autospec=True,
                return_value="## Brief Summary\ngeneric raw note summary",
            ),
        ):
            run = pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="fast", action="summary")

        path = config.ASR_DIAGNOSTICS_DIR / f"profile_{self.profile_id}" / "pipeline_runs.jsonl"
        payloads = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(payloads[-1]["event"], "pipeline_completed")
        self.assertEqual(payloads[-1]["run_id"], run["id"])

    def test_summary_language_auto_uses_russian_for_cyrillic_transcript(self):
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="обсуждение задачи и повторный акцент на важной задаче",
            labels={"origin": "asr_tool"},
        )

        with (
            patch.object(pipeline.model_service, "is_model_installed", return_value=True),
            patch.object(
                pipeline.ChatService,
                "chat_completion",
                autospec=True,
                return_value="## Краткое резюме\nОбсуждали задачу и повторно подчеркнули важный пункт.",
            ) as chat_mock,
        ):
            run = pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="fast", action="summary")

        self.assertEqual(run["used_settings"]["_asr_output_language"], "ru")
        messages = chat_mock.call_args.args[2]
        self.assertIn("Output language: Russian", messages[0]["content"])
        self.assertIn("## Краткое резюме", messages[1]["content"])

    def test_summary_language_manual_english_overrides_transcript_language(self):
        db.update_profile_preferences(self.profile_id, {"asr": {"analysis_language": "en"}})
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="обсуждение задачи и повторный акцент на важной задаче",
            labels={"origin": "asr_tool"},
        )

        with (
            patch.object(pipeline.model_service, "is_model_installed", return_value=True),
            patch.object(
                pipeline.ChatService,
                "chat_completion",
                autospec=True,
                return_value="## Brief Summary\nresult",
            ) as chat_mock,
        ):
            run = pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="fast", action="summary")

        self.assertEqual(run["used_settings"]["_asr_output_language"], "en")
        messages = chat_mock.call_args.args[2]
        self.assertIn("Output language: English", messages[0]["content"])
        self.assertIn("## Brief Summary", messages[1]["content"])
        self.assertNotIn("## Краткое резюме", messages[1]["content"])

    def test_summary_grounding_retry_replaces_instruction_echo(self):
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="обсуждение задачи и повторный акцент на важной задаче",
            labels={"origin": "asr_tool"},
        )
        responses = [
            (
                "The task is to summarize the following conversation in English:\n\n"
                "**Speaker 1:** Hello! How are you?\n\n"
                "**Speaker 2:** I'm fine, thank you. And you?"
            ),
            "## Краткое резюме\nОбсуждали задачу и повторно подчеркнули важный пункт.",
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
            run = pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="fast", action="summary")

        self.assertIn("Обсуждали задачу", run["summary"])
        self.assertTrue(any(item.startswith("summary_grounding_validation_failed:") for item in run["warnings"]))
        self.assertIn("summary_grounding_retry_succeeded", run["warnings"])
        self.assertEqual(chat_mock.call_count, 2)
        retry_messages = chat_mock.call_args_list[-1].args[2]
        self.assertIn("EVIDENCE_JSON", retry_messages[-1]["content"])
        self.assertIn("Не создавай примеры", retry_messages[0]["content"])

    def test_summary_missing_heading_is_repaired_without_retry(self):
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="обсуждали задачу запуска и повторно уточнили риск по сроку",
            labels={"origin": "asr_tool"},
        )

        with (
            patch.object(pipeline.model_service, "is_model_installed", return_value=True),
            patch.object(
                pipeline.ChatService,
                "chat_completion",
                autospec=True,
                return_value="Обсуждали задачу запуска и повторно уточнили риск по сроку.",
            ) as chat_mock,
        ):
            run = pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="fast", action="summary")

        self.assertTrue(run["summary"].startswith("## Краткое резюме\n"))
        self.assertIn("summary_required_heading_added", run["warnings"])
        self.assertEqual(chat_mock.call_count, 1)

    def test_summary_quality_retry_replaces_generic_dialogue_overview(self):
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="обсуждали задачу запуска и повторно уточнили риск по сроку",
            labels={"origin": "asr_tool"},
        )
        responses = [
            (
                "Вот краткий обзор диалога:\n\n"
                "1. **Участники:** Неidentified ( Speaker 1 ) и Unknown ( Speaker 2 )\n"
                "2. **Темы:**\n- задача запуска\n- риск по сроку\n"
                "3. **Язык:** Русский\n\n"
                "Примечание: из-за отсутствия контекста я не могу предоставить более подробный обзор."
            ),
            (
                "## Краткое резюме\n"
                "Обсуждали задачу запуска и повторно уточнили риск по сроку.\n\n"
                "## Ключевые решения\n- не зафиксировано\n\n"
                "## Задачи\n- задача запуска\n\n"
                "## Риски\n- риск по сроку"
            ),
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
            run = pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="fast", action="summary")

        self.assertIn("## Краткое резюме", run["summary"])
        self.assertNotIn("Speaker 1", run["summary"])
        self.assertNotIn("краткий обзор диалога", run["summary"])
        self.assertTrue(any(item.startswith("summary_grounding_validation_failed:") for item in run["warnings"]))
        self.assertIn("summary_grounding_retry_succeeded", run["warnings"])
        self.assertEqual(chat_mock.call_count, 2)
        retry_messages = chat_mock.call_args_list[-1].args[2]
        self.assertIn("generic_dialogue_overview_output", retry_messages[-1]["content"])

    def test_smart_summary_uses_structured_fallback_when_summary_validation_fails(self):
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="обсуждали задачу запуска и повторно уточнили риск по сроку",
            labels={"origin": "asr_tool"},
        )
        responses = [
            json.dumps(
                {
                    "topic": "задача запуска",
                    "summary": "Обсудили задачу запуска и риск по сроку.",
                    "tasks": [{"task": "подготовить запуск", "context": "повторно уточнили срок", "status": "open"}],
                    "risks": ["риск по сроку"],
                    "open_questions": ["уточнить срок запуска"],
                    "decisions": [],
                    "proposals": [],
                    "next_steps": ["проверить готовность запуска"],
                },
                ensure_ascii=False,
            ),
            (
                "Вот краткий обзор диалога:\n\n"
                "1. **Участники:** Unknown ( Speaker 1 ) и Unknown ( Speaker 2 )\n"
                "2. **Темы:** задача запуска\n"
                "3. **Язык:** Русский"
            ),
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
            run = pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="balanced", action="smart_summary")

        self.assertEqual(chat_mock.call_count, 2)
        self.assertIn("## Краткое резюме", run["summary"])
        self.assertIn("задача запуска", run["summary"])
        self.assertIn("подготовить запуск", run["summary"])
        self.assertNotIn("Speaker 1", run["summary"])
        self.assertTrue(any(item.startswith("summary_grounding_validation_failed:") for item in run["warnings"]))
        self.assertTrue(any(item.startswith("summary_safe_structured_fallback_used:") for item in run["warnings"]))
        self.assertNotIn("summary_grounding_retry_succeeded", run["warnings"])

    def test_summary_grounding_failure_does_not_save_fabricated_summary(self):
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="обсуждение задачи и повторный акцент на важной задаче",
            labels={"origin": "asr_tool"},
        )
        fabricated = (
            "The task is to summarize the following conversation in English:\n\n"
            "**Speaker 1:** Hello! How are you?\n\n"
            "**Speaker 2:** I'm fine, thank you. And you?"
        )

        with (
            patch.object(pipeline.model_service, "is_model_installed", return_value=True),
            patch.object(
                pipeline.ChatService,
                "chat_completion",
                autospec=True,
                return_value=fabricated,
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="fast", action="summary")

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(raised.exception.detail["code"], "asr_summary_grounding_failed")
        saved_transcript = db.get_transcript(transcript["id"])
        self.assertFalse(saved_transcript.get("summary"))

    def test_full_analysis_is_blocked_until_profile_setting_allows_it(self):
        transcript = db.create_transcript(
            profile_id=self.profile_id,
            name="Call",
            content="generic raw note",
            labels={"origin": "asr_tool"},
        )

        with self.assertRaises(HTTPException) as raised:
            pipeline.run_transcript_pipeline(transcript_id=transcript["id"], preset="balanced", action="full")

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(raised.exception.detail["code"], "asr_full_analysis_disabled")

    def test_incomplete_summary_section_lists_remaining_coverage_topics(self):
        topic_a = "tokena tokenb tokenc"
        topic_b = "tokend tokene tokenf"
        structured = {
            "topic": "demo",
            "coverage_topics": [topic_a, topic_b],
            "chunk_count": 2,
            "decisions": [],
            "tasks": [],
        }

        missing = pipeline._missing_coverage_topics("tokena", structured, chunk_count=2)
        summary = pipeline._append_incomplete_summary_section("## test", missing)

        self.assertEqual(missing, [topic_a, topic_b])
        self.assertIn("## Неполное summary: не удалось покрыть следующие темы", summary)
        self.assertIn(topic_a, summary)
        self.assertIn(topic_b, summary)

    def test_segment_digest_preserves_start_and_end_when_compacted(self):
        mapping = [
            {
                "segment_id": index,
                "chunk_id": index // 3,
                "speaker": "Unknown speaker",
                "text": f"segment_{index:02d} " + ("neutral words " * 12),
            }
            for index in range(30)
        ]

        digest = pipeline._segment_digest_for_summary(mapping, max_chars=1300)
        digest_text = json.dumps(digest, ensure_ascii=False)

        self.assertIn("segment_00", digest_text)
        self.assertIn("segment_29", digest_text)
        self.assertIn("middle_segments_omitted_from_digest", digest_text)

    def test_topic_coverage_requires_more_than_single_keyword_for_multiword_topic(self):
        topic = "tokena tokenb tokenc tokend tokene"

        self.assertFalse(pipeline._topic_is_covered(topic, "tokena"))
        self.assertFalse(pipeline._topic_is_covered(topic, "tokena tokenb"))
        self.assertTrue(pipeline._topic_is_covered(topic, "tokena tokenb tokenc tokend tokene"))

    def test_summary_demotes_unconfirmed_decisions_to_proposals(self):
        warnings: list[str] = []
        summary = (
            "## Ключевые решения\n"
            "- проверить tokena\n"
            "- решили tokenb\n"
            "## Предложения / варианты дальнейших действий\n"
            "- не зафиксировано"
        )

        summary = pipeline._demote_unconfirmed_decisions_section(summary, warnings)

        self.assertTrue(any(item.startswith("summary_decisions_demoted:1") for item in warnings))
        decisions = summary.split("## Ключевые решения", 1)[1].split("##", 1)[0]
        proposals = summary.split("## Предложения / варианты дальнейших действий", 1)[1].split("##", 1)[0]
        self.assertNotIn("проверить tokena", decisions)
        self.assertIn("решили tokenb", decisions)
        self.assertIn("проверить tokena", proposals)

    def test_structured_normalization_keeps_current_and_target_state_generic(self):
        warnings: list[str] = []
        normalized = pipeline._normalize_structured_output(
            {
                "topic": "demo",
                "current": "statea stateb statec",
                "target": "statex statey statez",
            },
            warnings,
        )
        merged = pipeline._merge_structured_outputs([normalized])

        self.assertEqual(normalized["current_state"], "statea stateb statec")
        self.assertEqual(normalized["target_state"], "statex statey statez")
        self.assertIn("statea stateb statec", merged["coverage_topics"])
        self.assertIn("statex statey statez", merged["coverage_topics"])

    def test_pipeline_tasks_are_normalized_for_transcript_record(self):
        transcript = db.create_transcript(profile_id=self.profile_id, name="Call", content="raw call")
        responses = [
            '[{"segment_id": 1, "text": "raw call"}]',
            '{"theme": "marker_topic", "summary": "marker_summary", "tasks": [{"title": "marker_task", "details": "marker_context", "owner": "не указано", "status": "open"}], "solutions": ["marker_solution"], "responsible": "Unknown speaker", "schedules": "not specified"}',
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
        self.assertEqual(task["task"], "marker_task")
        self.assertIn("marker_context", task["context"])
        saved_transcript = db.get_transcript(transcript["id"])
        self.assertEqual(saved_transcript["summary"], "marker_summary")
        self.assertEqual(saved_transcript["structured_json"]["tasks"][0]["task"], "marker_task")

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
