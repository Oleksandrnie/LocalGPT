from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import config, db
from app.routes import meta, profiles, storage
from app.schemas import ChatRequest, ModelSettingsRequest
from app.services import models as model_service
from backend.apps.chat import routes as chat_routes
from backend.apps.chat import tasks as chat_tasks
from backend.apps.chat.services import model_router
from backend.apps.rag import routes as rag_routes
from backend.apps.tts import router as tts_router
from backend.apps.tts import service as tts_service


ADMIN_HEADER = {"X-LocalGPT-Admin-Token": "synthetic-admin-token"}


class _TimeoutProcess:
    def __init__(self) -> None:
        self.alive = True
        self.terminated = False

    def join(self, timeout=None) -> None:
        return None

    def is_alive(self) -> bool:
        return self.alive

    def terminate(self) -> None:
        self.terminated = True
        self.alive = False

    def kill(self) -> None:
        self.alive = False


class RuntimeSecurityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_db_path = db.DB_PATH
        self.previous_rag_dir = config.RAG_SOURCE_DIR
        self.previous_admin_token = config.SETTINGS.admin_token
        self.previous_tasks_dir = chat_tasks.TASKS_DIR
        root = Path(self.tmpdir.name)
        db.DB_PATH = root / "runtime-security.db"
        config.RAG_SOURCE_DIR = root / "rag"
        config.SETTINGS.admin_token = "synthetic-admin-token"
        chat_tasks.TASKS_DIR = root / "chat-tasks"
        chat_tasks.TASKS_DIR.mkdir(parents=True, exist_ok=True)
        db.init_db()
        self.profile_id = db.ensure_default_profile()
        self.session = db.create_session(self.profile_id, "Security", "qwen2.5:3b")
        self.other_profile_id = int(db.create_profile("Other security profile")["id"])
        self.other_session = db.create_session(self.other_profile_id, "Other", "qwen2.5:3b")
        with chat_tasks._LOCK:
            chat_tasks._TASKS.clear()
            chat_tasks._STARTING_BY_PROFILE.clear()
        with chat_routes._CHAT_TASK_EVENT_CONNECTIONS_LOCK:
            chat_routes._CHAT_TASK_EVENT_CONNECTIONS.clear()

        app = FastAPI()
        app.include_router(meta.router)
        app.include_router(storage.router)
        app.include_router(chat_routes.router)
        app.include_router(rag_routes.router)
        app.include_router(tts_router.router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        with chat_tasks._LOCK:
            chat_tasks._TASKS.clear()
            chat_tasks._STARTING_BY_PROFILE.clear()
        with chat_routes._CHAT_TASK_EVENT_CONNECTIONS_LOCK:
            chat_routes._CHAT_TASK_EVENT_CONNECTIONS.clear()
        db.DB_PATH = self.previous_db_path
        config.RAG_SOURCE_DIR = self.previous_rag_dir
        config.SETTINGS.admin_token = self.previous_admin_token
        chat_tasks.TASKS_DIR = self.previous_tasks_dir
        self.tmpdir.cleanup()

    def test_privileged_routes_deny_missing_or_wrong_token_before_side_effects(self) -> None:
        with (
            patch.object(meta.threading, "Thread") as thread,
            patch.object(db, "cleanup_database_garbage") as cleanup,
            patch.object(storage, "describe_paths") as describe_paths,
        ):
            responses = [
                self.client.post("/runtime/shutdown"),
                self.client.post("/runtime/restart", headers={"X-LocalGPT-Admin-Token": "wrong"}),
                self.client.post("/database/cleanup", json={"vacuum": False}),
                self.client.post("/database/reset", json={"confirm": "RESET_DATABASE", "vacuum": False}),
                self.client.get("/storage/paths"),
            ]

        self.assertEqual([response.status_code for response in responses], [403, 403, 403, 403, 403])
        thread.assert_not_called()
        cleanup.assert_not_called()
        describe_paths.assert_not_called()

    def test_privileged_route_requires_configuration_and_accepts_matching_token(self) -> None:
        config.SETTINGS.admin_token = ""
        unavailable = self.client.post("/runtime/shutdown")
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.json()["detail"]["code"], "admin_token_not_configured")

        config.SETTINGS.admin_token = "synthetic-admin-token"
        with patch.object(meta.threading, "Thread") as thread:
            accepted = self.client.post("/runtime/shutdown", headers=ADMIN_HEADER)
        self.assertEqual(accepted.status_code, 200, accepted.text)
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()

    def test_health_version_and_rag_status_do_not_expose_absolute_paths(self) -> None:
        health = self.client.get("/health")
        version = self.client.get("/version")
        rag = self.client.get("/rag/status", params={"profile_id": self.profile_id})
        combined = f"{health.text}\n{version.text}\n{rag.text}"

        self.assertEqual(health.json(), {"status": "ok"})
        self.assertEqual(version.json(), {"service": "LocalGPT", "api_version": 1})
        self.assertEqual(rag.json()["source_dir"], f"profile:{self.profile_id}")
        self.assertNotIn(str(Path(self.tmpdir.name)), combined)
        self.assertNotIn(str(config.MODEL_PATHS.base), combined)

    def test_model_and_tts_statuses_redact_paths_hosts_and_provider_details(self) -> None:
        marker = f"{self.tmpdir.name}/synthetic-private-runtime"
        storage_info = {
            "model": "qwen2.5:7b-instruct",
            "storage_present": True,
            "storage_size": 1024,
            "storage_size_gb": 0.01,
            "stores": [{"store_path": marker, "manifest_path": marker}],
        }
        partial = {
            "path": marker,
            "store_path": marker,
            "size": 512,
            "size_gb": 0.01,
            "model_candidates": ["qwen2.5:7b-instruct"],
        }
        with (
            patch.object(model_service, "_list_local_models", return_value=[]),
            patch.object(model_service, "_list_active_models", return_value=[]),
            patch.object(model_service, "_pull_statuses", return_value=[]),
            patch.object(
                model_service,
                "_inspect_storage_manifests",
                return_value=({"qwen2.5:7b-instruct": storage_info}, {"sha256:test": {"qwen2.5:7b-instruct"}}),
            ),
            patch.object(model_service, "_list_partial_blobs", return_value=[partial]),
        ):
            models_payload = model_service.list_models()

        class Provider:
            name = "synthetic"

            @staticmethod
            def is_available():
                return False, marker

            @staticmethod
            def list_voices():
                return []

        with patch.object(tts_service, "_provider_by_name", return_value=Provider()):
            tts_payload = tts_service.get_health()

        combined = f"{models_payload}\n{tts_payload}"
        self.assertNotIn(marker, combined)
        self.assertNotIn("store_path", combined)
        self.assertNotIn("manifest_path", combined)
        self.assertNotIn("models_dir", combined)
        self.assertNotIn("message", tts_payload["provider"])

        public_pull = model_service._public_pull_status(
            {
                "state": "error",
                "output_tail": [marker],
            }
        )
        self.assertNotIn(marker, str(public_pull))

        with patch.object(
            tts_service,
            "list_voice_catalog",
            side_effect=tts_service.TTSServiceError(502, "voice_catalog_unavailable", marker),
        ):
            tts_error = self.client.get("/tts/voice-library")
        self.assertEqual(tts_error.status_code, 502)
        self.assertNotIn(marker, tts_error.text)

    def test_router_provider_failure_does_not_return_raw_exception(self) -> None:
        marker = "synthetic-private-router-provider-error"
        with (
            patch.object(model_router.model_residency, "prepare_router_for_request", return_value={}),
            patch.object(model_router.ollama_runtime, "chat_completion", side_effect=RuntimeError(marker)),
        ):
            with self.assertRaises(HTTPException) as raised:
                model_router.route_model("hello")
        self.assertEqual(raised.exception.status_code, 502)
        self.assertNotIn(marker, str(raised.exception.detail))

    def test_prompt_budget_rejects_assembled_history_before_generation(self) -> None:
        request = ChatRequest(query="bounded request", session_id=self.session["id"])
        with patch.object(
            chat_routes,
            "build_messages",
            return_value=[{"role": "user", "content": "x" * 300_000}],
        ):
            with self.assertRaises(HTTPException) as raised:
                chat_routes._prepare_chat_request(request)
        self.assertEqual(raised.exception.status_code, 413)
        self.assertEqual(raised.exception.detail["code"], "chat_prompt_budget_exceeded")

    def test_prompt_budget_records_bound_for_valid_assembled_prompt(self) -> None:
        request = ChatRequest(query="bounded request", session_id=self.session["id"])
        with patch.object(
            chat_routes,
            "build_messages",
            return_value=[{"role": "user", "content": "x" * 1_000}],
        ):
            prepared = chat_routes._prepare_chat_request(request)
        self.assertLessEqual(prepared["prompt_input_chars"], prepared["prompt_budget_chars"])

    def test_profile_and_model_runtime_settings_reject_oversized_limits(self) -> None:
        with self.assertRaises(HTTPException) as profile_error:
            profiles._normalize_runtime_settings({"rag_top_k": 21})
        self.assertEqual(profile_error.exception.status_code, 422)
        self.assertEqual(profile_error.exception.detail["code"], "invalid_rag_top_k")
        with self.assertRaises(ValidationError):
            ModelSettingsRequest(
                profile_id=self.profile_id,
                model_name="qwen2.5:3b",
                num_ctx=1_000_000,
            )

    def test_debug_prompt_is_admin_only_and_returns_metadata_without_prompt_values(self) -> None:
        marker = "synthetic-private-prompt-marker"
        prepared = {
            "messages": [{"role": "system", "content": marker}],
            "prompt_blocks": [{"name": "global_system_policy", "included": True, "chars": len(marker)}],
            "prompt_input_chars": len(marker),
            "effective_settings": {"temperature": 0.2, "private": marker},
            "profile_id": self.profile_id,
            "target_model": "qwen2.5:3b",
            "prompt_warnings": ["processed_transcript_missing"],
        }
        with patch.object(chat_routes, "_prepare_chat_request", return_value=prepared):
            denied = self.client.post("/chat/debug/prompt", json={"query": "debug"})
            allowed = self.client.post("/chat/debug/prompt", headers=ADMIN_HEADER, json={"query": "debug"})

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertNotIn(marker, allowed.text)
        self.assertNotIn("messages", allowed.json())
        self.assertEqual(allowed.json()["used_settings_keys"], ["private", "temperature"])

    def test_task_status_events_and_cancel_require_matching_profile_and_session(self) -> None:
        task = chat_tasks.create_completed_task(
            session_id=self.session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5:3b",
            role="chat",
            used_settings={},
            reply="profile-owned result",
        )
        correct = {"profile_id": self.profile_id, "session_id": self.session["id"]}
        foreign = {"profile_id": self.other_profile_id, "session_id": self.other_session["id"]}

        owned = self.client.get(f"/chat/tasks/{task['id']}", params=correct)
        foreign_status = self.client.get(f"/chat/tasks/{task['id']}", params=foreign)
        unknown_status = self.client.get("/chat/tasks/unknown-task", params=foreign)
        foreign_events = self.client.get(f"/chat/tasks/{task['id']}/events", params=foreign)
        foreign_cancel = self.client.post(f"/chat/tasks/{task['id']}/cancel", params=foreign)

        self.assertEqual(owned.status_code, 200, owned.text)
        self.assertEqual(foreign_status.status_code, 404)
        self.assertEqual(unknown_status.status_code, 404)
        self.assertEqual(foreign_status.json(), unknown_status.json())
        self.assertEqual(foreign_events.status_code, 404)
        self.assertEqual(foreign_cancel.status_code, 404)
        self.assertEqual(chat_tasks.get_chat_task(task["id"])["state"], "completed")

    def test_profile_concurrency_limit_fails_before_starting_process(self) -> None:
        with chat_tasks._LOCK:
            for index in range(chat_tasks.CHAT_TASK_MAX_ACTIVE_PER_PROFILE):
                chat_tasks._TASKS[f"active-{index}"] = {
                    "id": f"active-{index}",
                    "state": "generating",
                    "profile_id": self.profile_id,
                    "session_id": self.session["id"],
                }

        with self.assertRaises(chat_tasks.ChatTaskCapacityError) as raised:
            chat_tasks.start_chat_task(
                session_id=self.session["id"],
                profile_id=self.profile_id,
                model_name="qwen2.5:3b",
                role="chat",
                messages=[{"role": "user", "content": "bounded"}],
                used_settings={},
            )
        self.assertEqual(raised.exception.code, "chat_profile_concurrency_exceeded")
        self.assertEqual(chat_tasks._STARTING_BY_PROFILE, {})

    def test_task_event_connections_are_bounded_per_task(self) -> None:
        task = chat_tasks.create_completed_task(
            session_id=self.session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5:3b",
            role="chat",
            used_settings={},
            reply="done",
        )
        task_id = task["id"]
        reservations = [
            chat_routes._reserve_chat_task_event_connection(task_id)
            for _ in range(chat_routes.CHAT_TASK_EVENT_MAX_CONNECTIONS)
        ]
        self.assertTrue(all(reservations))
        self.assertFalse(chat_routes._reserve_chat_task_event_connection(task_id))
        response = self.client.get(
            f"/chat/tasks/{task_id}/events",
            params={"profile_id": self.profile_id, "session_id": self.session["id"]},
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"]["code"], "chat_task_event_connection_limit")
        for _ in reservations:
            chat_routes._release_chat_task_event_connection(task_id)
        self.assertNotIn(task_id, chat_routes._CHAT_TASK_EVENT_CONNECTIONS)

    def test_ui_keeps_admin_token_session_only_and_scopes_task_requests(self) -> None:
        script = (Path(__file__).parents[1] / "web_ui" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("window.sessionStorage.setItem(ADMIN_TOKEN_SESSION_KEY, token)", script)
        self.assertNotIn("window.localStorage.setItem(ADMIN_TOKEN_SESSION_KEY", script)
        self.assertIn("[ADMIN_TOKEN_HEADER]: token", script)
        self.assertIn("function chatTaskScopedUrl", script)

    def test_monitor_timeout_terminates_process_and_removes_partial_artifacts(self) -> None:
        task_id = "timeout-task"
        process = _TimeoutProcess()
        paths = {
            key: chat_tasks.TASKS_DIR / f"{task_id}.{key}"
            for key in ("result_path", "error_path", "status_path", "delta_path", "reasoning_path")
        }
        for path in paths.values():
            path.write_text("partial-private-data", encoding="utf-8")
        with chat_tasks._LOCK:
            chat_tasks._TASKS[task_id] = {
                "id": task_id,
                "state": "generating",
                "profile_id": self.profile_id,
                "session_id": self.session["id"],
                "attachment_ids": [],
                "_process": process,
                **{key: str(path) for key, path in paths.items()},
            }

        chat_tasks._monitor_task(task_id)

        task = chat_tasks.get_chat_task(task_id)
        self.assertTrue(process.terminated)
        self.assertEqual(task["state"], "failed")
        self.assertEqual(task["error_code"], "chat_task_timeout")
        self.assertTrue(all(not path.exists() for path in paths.values()))

    def test_rag_upload_limits_fail_without_writing_artifacts(self) -> None:
        too_many = [
            ("files", (f"source-{index}.md", b"tiny", "text/markdown"))
            for index in range(13)
        ]
        count_response = self.client.post(
            "/rag/files",
            params={"profile_id": self.profile_id},
            files=too_many,
        )
        with patch("backend.apps.rag.service.MAX_UPLOAD_TOTAL_BYTES", 5):
            bytes_response = self.client.post(
                "/rag/files",
                params={"profile_id": self.profile_id},
                files=[
                    ("files", ("one.md", b"1234", "text/markdown")),
                    ("files", ("two.md", b"5678", "text/markdown")),
                ],
            )

        self.assertEqual(count_response.status_code, 413)
        self.assertEqual(count_response.json()["detail"]["code"], "rag_upload_file_count_exceeded")
        self.assertEqual(bytes_response.status_code, 413)
        self.assertEqual(bytes_response.json()["detail"]["code"], "rag_upload_total_bytes_exceeded")
        source_dir = config.RAG_SOURCE_DIR
        self.assertEqual(list(source_dir.rglob("*.md")), [])


if __name__ == "__main__":
    unittest.main()
