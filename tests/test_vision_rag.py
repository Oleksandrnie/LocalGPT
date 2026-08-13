from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app import config, db
from backend.apps.rag import service as rag_service


class VisionRagExportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_db_path = db.DB_PATH
        self.previous_rag_dir = config.RAG_SOURCE_DIR
        db.DB_PATH = Path(self.tmpdir.name) / "localgpt-test.db"
        config.RAG_SOURCE_DIR = Path(self.tmpdir.name) / "rag"
        db.init_db()
        self.profile_id = db.ensure_default_profile()
        self.session = db.create_session(self.profile_id, "Vision", "qwen2.5vl:3b")
        self.user_message = db.add_message(self.session["id"], "user", "Что на схеме?")
        db.create_chat_attachment(
            attachment_id="vision-rag-1",
            profile_id=self.profile_id,
            session_id=self.session["id"],
            mime_type="image/png",
            original_name="diagram.png",
            storage_path="profile-1/images/private.png",
            thumbnail_path="profile-1/thumbnails/private.webp",
            size_bytes=100,
            width=100,
            height=80,
            sha256="digest",
            status="completed",
        )
        db.update_chat_attachment(
            "vision-rag-1",
            message_id=self.user_message["id"],
            task_id="ct-export",
        )

    def tearDown(self) -> None:
        db.DB_PATH = self.previous_db_path
        config.RAG_SOURCE_DIR = self.previous_rag_dir
        self.tmpdir.cleanup()

    def test_explicit_export_indexes_only_edited_text_and_safe_references(self) -> None:
        result = rag_service.index_vision_context(
            profile_id=self.profile_id,
            session_id=self.session["id"],
            message_id=self.user_message["id"],
            title="Архитектурная схема",
            text="На схеме показаны API, очередь задач и локальная модель.",
        )

        self.assertTrue(result["indexed"])
        self.assertEqual(result["source_type"], "vision_context")
        documents = db.list_source_documents(profile_id=self.profile_id, source_type="vision_context")
        self.assertEqual(len(documents), 1)
        document = documents[0]
        self.assertEqual(document["content"], "На схеме показаны API, очередь задач и локальная модель.")
        self.assertEqual(document["metadata"]["attachment_ids"], ["vision-rag-1"])
        self.assertFalse(document["metadata"]["binary_ingested"])
        self.assertNotIn("private.png", str(document))
        self.assertNotIn("storage_path", str(document))

        search = rag_service.search(
            self.profile_id,
            "локальная модель",
            top_k=3,
            session_id=self.session["id"],
        )
        self.assertTrue(any(item["source_type"] == "vision_context" for item in search))
        status = rag_service.status(self.profile_id, session_id=self.session["id"])
        self.assertTrue(any(item["source_type"] == "vision_context" for item in status["contexts"]))

    def test_binary_data_uri_and_unrelated_message_are_rejected(self) -> None:
        with self.assertRaises(HTTPException) as binary_error:
            rag_service.index_vision_context(
                profile_id=self.profile_id,
                session_id=self.session["id"],
                message_id=self.user_message["id"],
                title=None,
                text="data:image/png;base64,AAAA",
            )
        self.assertEqual(binary_error.exception.detail, "vision_context_binary_forbidden")

        unrelated = db.add_message(self.session["id"], "user", "Без картинки")
        with self.assertRaises(HTTPException) as missing_error:
            rag_service.index_vision_context(
                profile_id=self.profile_id,
                session_id=self.session["id"],
                message_id=unrelated["id"],
                title=None,
                text="Производный текст",
            )
        self.assertEqual(missing_error.exception.detail, "vision_context_attachments_required")

    def test_vision_context_can_be_deleted_without_touching_chat_attachment(self) -> None:
        result = rag_service.index_vision_context(
            profile_id=self.profile_id,
            session_id=self.session["id"],
            message_id=self.user_message["id"],
            title=None,
            text="Производный текст для удаления.",
        )

        deleted = rag_service.delete_context_source(self.profile_id, self.session["id"], result["source_id"])

        self.assertEqual(deleted["deleted"], [result["source_id"]])
        self.assertEqual(db.list_source_documents(profile_id=self.profile_id, source_type="vision_context"), [])
        self.assertIsNotNone(db.get_chat_attachment("vision-rag-1"))


if __name__ == "__main__":
    unittest.main()
