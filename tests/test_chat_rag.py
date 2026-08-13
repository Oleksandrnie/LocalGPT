from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config, db
from backend.apps.rag import routes as rag_routes
from backend.apps.rag import service as rag_service


class ChatRagExportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_db_path = db.DB_PATH
        self.previous_rag_dir = config.RAG_SOURCE_DIR
        db.DB_PATH = Path(self.tmpdir.name) / "localgpt-test.db"
        config.RAG_SOURCE_DIR = Path(self.tmpdir.name) / "rag"
        db.init_db()
        self.profile_id = db.ensure_default_profile()
        self.session = db.create_session(self.profile_id, "Chat RAG", "qwen3:0.6b")
        self.user_message = db.add_message(self.session["id"], "user", "Исходный вопрос")
        self.assistant_message = db.add_message(
            self.session["id"],
            "assistant",
            "Финальный ответ с уникальным термином кварцит.",
            reasoning="Скрытая цепочка о секрете reasoning-marker.",
            status="completed",
        )
        app = FastAPI()
        app.include_router(rag_routes.router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        db.DB_PATH = self.previous_db_path
        config.RAG_SOURCE_DIR = self.previous_rag_dir
        self.tmpdir.cleanup()

    def _export(self, message_id: int, text: str, title: str = "Контекст"):
        return self.client.post(
            "/rag/chat-contexts",
            json={
                "profile_id": self.profile_id,
                "session_id": self.session["id"],
                "message_id": message_id,
                "title": title,
                "text": text,
            },
        )

    def test_user_and_completed_assistant_export_with_role_metadata(self) -> None:
        user_response = self._export(self.user_message["id"], "Отредактированный пользовательский контекст.")
        assistant_response = self._export(self.assistant_message["id"], "Проверенный ответ про кварцит.")

        self.assertEqual(user_response.status_code, 200, user_response.text)
        self.assertEqual(assistant_response.status_code, 200, assistant_response.text)
        documents = db.list_source_documents(profile_id=self.profile_id, source_type="chat_context")
        self.assertEqual({item["metadata"]["message_role"] for item in documents}, {"user", "assistant"})
        assistant_document = next(item for item in documents if item["metadata"]["message_role"] == "assistant")
        self.assertEqual(assistant_document["content"], "Проверенный ответ про кварцит.")
        self.assertFalse(assistant_document["metadata"]["reasoning_ingested"])
        self.assertNotIn("reasoning-marker", str(assistant_document))
        results = rag_service.search(self.profile_id, "кварцит", top_k=3)
        self.assertTrue(any(item["source_type"] == "chat_context" for item in results))

    def test_profile_ownership_and_incomplete_assistant_are_rejected(self) -> None:
        other_profile_id = int(db.create_profile("Other")["id"])
        mismatch = self.client.post(
            "/rag/chat-contexts",
            json={
                "profile_id": other_profile_id,
                "session_id": self.session["id"],
                "message_id": self.user_message["id"],
                "text": "Нельзя индексировать",
            },
        )
        self.assertEqual(mismatch.status_code, 403)
        self.assertEqual(mismatch.json()["detail"], "chat_context_session_mismatch")

        active = db.add_message(self.session["id"], "assistant", "Черновик", status="streaming", is_partial=True)
        incomplete = self._export(active["id"], "Черновой контекст")
        self.assertEqual(incomplete.status_code, 422)
        self.assertEqual(incomplete.json()["detail"], "chat_context_assistant_incomplete")

    def test_delete_chat_context_does_not_touch_message_or_other_context(self) -> None:
        first = self._export(self.user_message["id"], "Первый независимый контекст.").json()
        second = self._export(self.assistant_message["id"], "Второй независимый контекст.").json()

        deleted = self.client.delete(
            "/rag/contexts",
            params={"profile_id": self.profile_id, "source_id": first["source_id"]},
        )

        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(deleted.json()["deleted"], [first["source_id"]])
        remaining = db.list_source_documents(profile_id=self.profile_id, source_type="chat_context")
        self.assertEqual([item["source_id"] for item in remaining], [second["source_id"]])
        self.assertIsNotNone(db.get_message(self.user_message["id"]))


if __name__ == "__main__":
    unittest.main()
