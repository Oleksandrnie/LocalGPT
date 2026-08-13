from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import config, db
from backend.apps.chat import tasks as chat_tasks
from backend.apps.chat.services import attachment_storage, vision_runtime


class _AliveProcess:
    def is_alive(self) -> bool:
        return True


class ChatVisionLifecycleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_db_path = db.DB_PATH
        self.previous_attachments_dir = config.CHAT_ATTACHMENTS_DIR
        self.previous_tasks_dir = chat_tasks.TASKS_DIR
        db.DB_PATH = Path(self.tmpdir.name) / "localgpt-test.db"
        config.CHAT_ATTACHMENTS_DIR = Path(self.tmpdir.name) / "attachments"
        chat_tasks.TASKS_DIR = Path(self.tmpdir.name) / "tasks"
        chat_tasks.TASKS_DIR.mkdir(parents=True, exist_ok=True)
        db.init_db()
        self.profile_id = db.ensure_default_profile()
        self.session = db.create_session(self.profile_id, "Vision", "qwen2.5vl:3b")

    def tearDown(self) -> None:
        chat_tasks._TASKS.clear()
        db.DB_PATH = self.previous_db_path
        config.CHAT_ATTACHMENTS_DIR = self.previous_attachments_dir
        chat_tasks.TASKS_DIR = self.previous_tasks_dir
        self.tmpdir.cleanup()

    def _attachment(self, *, attachment_id: str = "vision-1", size: int = 12) -> dict:
        image_path = config.CHAT_ATTACHMENTS_DIR / f"profile-{self.profile_id}" / "images" / f"{attachment_id}.png"
        thumbnail_path = config.CHAT_ATTACHMENTS_DIR / f"profile-{self.profile_id}" / "thumbs" / f"{attachment_id}.webp"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"x" * size)
        thumbnail_path.write_bytes(b"thumb")
        root = config.CHAT_ATTACHMENTS_DIR.resolve()
        return db.create_chat_attachment(
            attachment_id=attachment_id,
            profile_id=self.profile_id,
            session_id=None,
            mime_type="image/png",
            original_name="screen.png",
            storage_path=image_path.resolve().relative_to(root).as_posix(),
            thumbnail_path=thumbnail_path.resolve().relative_to(root).as_posix(),
            size_bytes=size,
            width=16,
            height=12,
            sha256="digest",
            status="ready",
        )

    def test_preflight_returns_internal_descriptor_and_enforces_count(self) -> None:
        first = self._attachment()

        descriptors = attachment_storage.prepare_chat_attachments(
            [first["id"]],
            profile_id=self.profile_id,
            session_id=self.session["id"],
            settings={
                "chat_images_enabled": True,
                "max_images_per_message": 1,
                "chat_image_max_total_bytes": 64,
            },
        )

        self.assertEqual(descriptors[0]["id"], first["id"])
        self.assertTrue(Path(descriptors[0]["path"]).is_file())
        second = self._attachment(attachment_id="vision-2")
        with self.assertRaises(attachment_storage.AttachmentStorageError) as raised:
            attachment_storage.prepare_chat_attachments(
                [first["id"], second["id"]],
                profile_id=self.profile_id,
                session_id=self.session["id"],
                settings={"chat_images_enabled": True, "max_images_per_message": 1},
            )
        self.assertEqual(raised.exception.code, "TOO_MANY_IMAGES")

    def test_failed_task_links_attachment_without_exposing_path(self) -> None:
        attachment = self._attachment()
        user_message = db.add_message(self.session["id"], "user", "analyze")
        assistant_message = db.create_assistant_message(self.session["id"], model="qwen2.5vl:3b")
        descriptor = attachment_storage.prepare_chat_attachments(
            [attachment["id"]],
            profile_id=self.profile_id,
            session_id=self.session["id"],
            settings={"chat_images_enabled": True},
        )[0]

        task = chat_tasks.create_failed_task(
            session_id=self.session["id"],
            profile_id=self.profile_id,
            model_name="qwen2.5vl:3b",
            role="chat",
            used_settings={},
            message="vision unavailable",
            user_message_id=user_message["id"],
            assistant_message_id=assistant_message["id"],
            attachment_descriptors=[descriptor],
        )

        linked = db.get_chat_attachment(attachment["id"])
        self.assertEqual(linked["message_id"], user_message["id"])
        self.assertEqual(linked["task_id"], task["id"])
        self.assertEqual(linked["status"], "failed")
        self.assertNotIn("path", str(task))

    def test_direct_worker_updates_attachment_and_persists_answer(self) -> None:
        attachment = self._attachment()
        user_message = db.add_message(self.session["id"], "user", "what is shown")
        assistant_message = db.create_assistant_message(self.session["id"], model="qwen2.5vl:3b")
        descriptor = attachment_storage.prepare_chat_attachments(
            [attachment["id"]],
            profile_id=self.profile_id,
            session_id=self.session["id"],
            settings={"chat_images_enabled": True},
        )[0]
        result_path = Path(self.tmpdir.name) / "result.json"
        error_path = Path(self.tmpdir.name) / "error.json"
        status_path = Path(self.tmpdir.name) / "status.json"
        delta_path = Path(self.tmpdir.name) / "deltas.jsonl"
        reasoning_path = Path(self.tmpdir.name) / "reasoning.jsonl"

        with patch.object(vision_runtime, "chat_completion", return_value="A local image answer") as completion:
            chat_tasks._chat_worker(
                "qwen2.5vl:3b",
                [{"role": "user", "content": "what is shown"}],
                {"ocr_assist": "off"},
                self.session["id"],
                self.profile_id,
                assistant_message["id"],
                False,
                str(delta_path),
                str(reasoning_path),
                str(status_path),
                str(result_path),
                str(error_path),
                [descriptor],
                {
                    "mode": "direct",
                    "vision_model": "qwen2.5vl:3b",
                    "response_model": "qwen2.5vl:3b",
                },
            )

        self.assertFalse(error_path.exists())
        self.assertEqual(chat_tasks._read_json(result_path)["reply"], "A local image answer")
        self.assertEqual(db.get_message(assistant_message["id"])["status"], "completed")
        self.assertEqual(db.get_chat_attachment(attachment["id"])["status"], "completed")
        completion.assert_called_once()

    def test_refresh_exposes_vision_status_and_cancel_finalizes_attachment(self) -> None:
        attachment = self._attachment()
        db.update_chat_attachment(attachment["id"], status="analyzing")
        status_path = Path(self.tmpdir.name) / "status.json"
        chat_tasks._atomic_write_json(status_path, {"state": "analyzing", "message": "Analyzing locally."})
        task = {
            "id": "ct-test",
            "state": "preparing",
            "updated_at": "",
            "status_path": str(status_path),
            "attachment_ids": [attachment["id"]],
            "_process": _AliveProcess(),
        }

        chat_tasks._refresh_task_locked(task)
        self.assertEqual(task["state"], "analyzing")

        task["state"] = "cancelling"
        task["cancel_requested"] = True
        task.pop("_process")
        chat_tasks._finalize_task_locked(task)
        self.assertEqual(task["state"], "cancelled")
        self.assertEqual(db.get_chat_attachment(attachment["id"])["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
