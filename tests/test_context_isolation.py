from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import config, db
from app.routes import profiles
from app.schemas import ChatRequest
from backend.apps.chat.routes import _prepare_chat_request
from backend.apps.asr.transcripts import router as transcripts_router
from backend.apps.rag import routes as rag_routes
from backend.apps.rag import service as rag_service


class ContextIsolationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_db_path = db.DB_PATH
        self.previous_rag_dir = config.RAG_SOURCE_DIR
        root = Path(self.tmpdir.name)
        db.DB_PATH = root / "context-isolation.db"
        config.RAG_SOURCE_DIR = root / "rag"
        db.init_db()
        self.profile_a = db.ensure_default_profile()
        self.profile_b = int(db.create_profile("Profile B")['id'])
        self.session_a1 = db.create_session(self.profile_a, "A1", "qwen2.5:3b")
        self.session_a2 = db.create_session(self.profile_a, "A2", "qwen2.5:3b")
        self.session_b1 = db.create_session(self.profile_b, "B1", "qwen2.5:3b")

        app = FastAPI()
        app.include_router(profiles.router)
        app.include_router(rag_routes.router)
        app.include_router(transcripts_router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        db.DB_PATH = self.previous_db_path
        config.RAG_SOURCE_DIR = self.previous_rag_dir
        self.tmpdir.cleanup()

    def _export_chat_context(self, profile_id: int, session_id: str, marker: str) -> None:
        message = db.add_message(session_id, "user", marker, status="completed")
        response = self.client.post(
            "/rag/chat-contexts",
            json={
                "profile_id": profile_id,
                "session_id": session_id,
                "message_id": message["id"],
                "title": marker,
                "text": marker,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_prompt_history_is_exact_completed_pairs_from_active_session(self) -> None:
        for index in range(1, 4):
            db.add_message(self.session_a1["id"], "user", f"a1-user-{index}", status="completed")
            db.add_message(self.session_a1["id"], "assistant", f"a1-assistant-{index}", status="completed")
        db.add_message(self.session_a1["id"], "user", "a1-current-or-orphan", status="completed")
        db.add_message(
            self.session_a1["id"],
            "assistant",
            "a1-failed-assistant",
            status="failed",
            error="synthetic",
        )
        db.add_message(self.session_a2["id"], "user", "canary_A2", status="completed")
        db.add_message(self.session_a2["id"], "assistant", "canary_A2_reply", status="completed")

        history = db.get_prompt_history(self.session_a1["id"], limit_turns=2)

        self.assertEqual(
            [(item["role"], item["content"]) for item in history],
            [
                ("user", "a1-user-2"),
                ("assistant", "a1-assistant-2"),
                ("user", "a1-user-3"),
                ("assistant", "a1-assistant-3"),
            ],
        )
        self.assertNotIn("canary_A2", str(history))
        self.assertNotIn("a1-failed-assistant", str(history))
        self.assertEqual(db.get_prompt_history(self.session_a1["id"], limit_turns=0), [])

    def test_history_turn_setting_defaults_to_six_and_round_trips_zero_and_max(self) -> None:
        defaults = db.effective_settings(self.profile_a, "qwen2.5:3b", config.DEFAULT_SETTINGS)
        self.assertEqual(defaults["effective"]["mem_turns"], 6)

        for value in (0, 1, 6, 100):
            with self.subTest(value=value):
                response = self.client.patch(
                    f"/profiles/{self.profile_a}/preferences",
                    json={"settings": {"mem_turns": value}},
                )
                self.assertEqual(response.status_code, 200, response.text)
                reloaded = db.get_profile(self.profile_a)
                self.assertEqual(reloaded["preferences"]["settings"]["mem_turns"], value)

        rejected = self.client.patch(
            f"/profiles/{self.profile_a}/preferences",
            json={"settings": {"mem_turns": 101}},
        )
        self.assertEqual(rejected.status_code, 422)

    def test_chat_preparation_rejects_foreign_profile_for_known_session(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            _prepare_chat_request(
                ChatRequest(
                    query="isolation check",
                    profile_id=self.profile_b,
                    session_id=self.session_a1["id"],
                )
            )
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "session_not_found")

    def test_prompt_assembly_contains_only_active_session_context_canaries(self) -> None:
        db.update_profile_preferences(
            self.profile_a,
            {
                "settings": {
                    "mem_turns": 6,
                    "summary_memory_enabled": True,
                    "summary_memory_limit": 5,
                    "rag_enabled": True,
                }
            },
        )
        db.add_message(self.session_a1["id"], "user", "history_canary_A1", status="completed")
        db.add_message(self.session_a1["id"], "assistant", "history_reply_A1", status="completed")
        db.add_message(self.session_a2["id"], "user", "history_canary_A2", status="completed")
        db.add_message(
            self.session_a2["id"],
            "assistant",
            "history_reply_A2",
            reasoning="reasoning_canary_A2",
            status="completed",
        )
        db.create_session_summary(
            profile_id=self.profile_a,
            session_id=self.session_a1["id"],
            source_type="chat",
            source_id="a1",
            summary="summary_canary_A1",
        )
        db.create_session_summary(
            profile_id=self.profile_a,
            session_id=self.session_a2["id"],
            source_type="chat",
            source_id="a2",
            summary="summary_canary_A2",
        )
        db.save_session_criteria(self.session_a1["id"], ["criteria_canary_A1"])
        db.save_session_criteria(self.session_a2["id"], ["criteria_canary_A2"])
        db.create_transcript(
            self.profile_a,
            "A1 transcript",
            "transcript_canary_A1",
            session_id=self.session_a1["id"],
        )
        db.create_transcript(
            self.profile_a,
            "A2 transcript",
            "transcript_canary_A2",
            session_id=self.session_a2["id"],
        )
        self._export_chat_context(self.profile_a, self.session_a1["id"], "rag_canary_A1")
        self._export_chat_context(self.profile_a, self.session_a2["id"], "rag_canary_A2")

        prepared = _prepare_chat_request(
            ChatRequest(
                query="history_canary summary_canary criteria_canary transcript_canary rag_canary",
                profile_id=self.profile_a,
                session_id=self.session_a1["id"],
            )
        )
        assembled = "\n".join(str(item.get("content") or "") for item in prepared["messages"])

        for marker in (
            "history_canary_A1",
            "summary_canary_A1",
            "criteria_canary_A1",
            "rag_canary_A1",
        ):
            self.assertIn(marker, assembled)
        for marker in (
            "history_canary_A2",
            "summary_canary_A2",
            "criteria_canary_A2",
            "transcript_canary_A2",
            "rag_canary_A2",
            "reasoning_canary_A2",
        ):
            self.assertNotIn(marker, assembled)
        self.assertEqual(
            db.get_latest_transcript_for_session(self.session_a1["id"])["content"],
            "transcript_canary_A1",
        )

    def test_session_api_uses_uniform_not_found_for_foreign_profile(self) -> None:
        foreign = self.client.get(
            f"/sessions/{self.session_a1['id']}/messages",
            params={"profile_id": self.profile_b},
        )
        unknown = self.client.get(
            "/sessions/unknown/messages",
            params={"profile_id": self.profile_b},
        )

        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(foreign.json(), unknown.json())

    def test_rag_retrieval_allows_profile_wide_and_only_active_session_derived_sources(self) -> None:
        source_dir = rag_service.ensure_profile_source_dir(self.profile_a)
        (source_dir / "profile-wide.md").write_text("profile_A_shared_canary", encoding="utf-8")
        rag_service.ingest_sources(self.profile_a, force=True)
        self._export_chat_context(self.profile_a, self.session_a1["id"], "canary_A1")
        self._export_chat_context(self.profile_a, self.session_a2["id"], "canary_A2")
        self._export_chat_context(self.profile_b, self.session_b1["id"], "canary_B1")

        a1 = rag_service.search(
            self.profile_a,
            "profile_A_shared_canary canary_A1 canary_A2 canary_B1",
            top_k=10,
            session_id=self.session_a1["id"],
        )
        combined = "\n".join(str(item.get("content") or "") for item in a1)
        self.assertIn("profile_A_shared_canary", combined)
        self.assertIn("canary_A1", combined)
        self.assertNotIn("canary_A2", combined)
        self.assertNotIn("canary_B1", combined)

        profile_only = rag_service.search(self.profile_a, "canary_A1", top_k=10)
        self.assertFalse(profile_only)

    def test_session_delete_removes_derived_rag_without_touching_profile_wide_or_sibling(self) -> None:
        source_dir = rag_service.ensure_profile_source_dir(self.profile_a)
        (source_dir / "profile-wide.md").write_text("profile_A_shared_canary", encoding="utf-8")
        rag_service.ingest_sources(self.profile_a, force=True)
        self._export_chat_context(self.profile_a, self.session_a1["id"], "delete_A1")
        self._export_chat_context(self.profile_a, self.session_a2["id"], "keep_A2")

        response = self.client.delete(
            f"/sessions/{self.session_a1['id']}",
            params={"profile_id": self.profile_a},
        )

        self.assertEqual(response.status_code, 200, response.text)
        documents = db.list_source_documents(profile_id=self.profile_a)
        self.assertFalse(any(item.get("session_id") == self.session_a1["id"] for item in documents))
        self.assertTrue(any(item.get("session_id") == self.session_a2["id"] for item in documents))
        self.assertTrue(any(item.get("session_id") is None for item in documents))

    def test_derived_rag_delete_rejects_sibling_session(self) -> None:
        self._export_chat_context(self.profile_a, self.session_a1["id"], "delete_only_A1")
        document = db.list_source_documents(profile_id=self.profile_a, source_type="chat_context")[0]

        foreign = self.client.delete(
            "/rag/contexts",
            params={
                "profile_id": self.profile_a,
                "session_id": self.session_a2["id"],
                "source_id": document["source_id"],
            },
        )

        self.assertEqual(foreign.status_code, 404)
        self.assertIsNotNone(db.get_source_document(document["id"]))

    def test_session_linked_transcript_requires_profile_and_session(self) -> None:
        transcript = db.create_transcript(
            self.profile_a,
            "A1 transcript",
            "transcript_canary_A1",
            session_id=self.session_a1["id"],
        )

        owned = self.client.get(
            f"/transcripts/{transcript['id']}",
            params={"profile_id": self.profile_a, "session_id": self.session_a1["id"]},
        )
        sibling = self.client.get(
            f"/transcripts/{transcript['id']}",
            params={"profile_id": self.profile_a, "session_id": self.session_a2["id"]},
        )
        foreign = self.client.get(
            f"/transcripts/{transcript['id']}",
            params={"profile_id": self.profile_b, "session_id": self.session_b1["id"]},
        )

        self.assertEqual(owned.status_code, 200)
        self.assertEqual(sibling.status_code, 404)
        self.assertEqual(foreign.status_code, 404)


if __name__ == "__main__":
    unittest.main()
