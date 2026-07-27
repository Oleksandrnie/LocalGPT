from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app import config, db
from app.routes import profiles as profile_routes
from backend.apps.chat import attachments
from backend.apps.chat.services import attachment_storage


def _image_bytes(image_format: str = "PNG", *, size: tuple[int, int] = (24, 16)) -> bytes:
    buffer = io.BytesIO()
    mode = "RGBA" if image_format in {"PNG", "WEBP"} else "RGB"
    image = Image.new(mode, size, (32, 96, 160, 255) if mode == "RGBA" else (32, 96, 160))
    image.save(buffer, format=image_format)
    return buffer.getvalue()


class ChatAttachmentApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.previous_db_path = db.DB_PATH
        self.previous_attachments_dir = config.CHAT_ATTACHMENTS_DIR
        db.DB_PATH = Path(self.tmpdir.name) / "localgpt-test.db"
        config.CHAT_ATTACHMENTS_DIR = Path(self.tmpdir.name) / "chat-attachments"
        db.init_db()
        self.profile_id = db.ensure_default_profile()
        self.app = FastAPI()
        self.app.include_router(attachments.router)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        db.DB_PATH = self.previous_db_path
        config.CHAT_ATTACHMENTS_DIR = self.previous_attachments_dir
        self.tmpdir.cleanup()

    def _upload(
        self,
        *,
        payload: bytes | None = None,
        filename: str = "screen.png",
        content_type: str = "image/png",
        profile_id: int | None = None,
        session_id: str | None = None,
    ):
        data = {"profile_id": str(profile_id or self.profile_id)}
        if session_id:
            data["session_id"] = session_id
        return self.client.post(
            "/chat/attachments",
            data=data,
            files={"file": (filename, payload if payload is not None else _image_bytes(), content_type)},
        )

    def test_upload_returns_metadata_and_profile_owned_media(self) -> None:
        response = self._upload()

        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()
        self.assertEqual(item["profile_id"], self.profile_id)
        self.assertEqual(item["mime_type"], "image/png")
        self.assertEqual((item["width"], item["height"]), (24, 16))
        self.assertEqual(item["status"], "ready")
        self.assertNotIn("screen.png", item["media_url"])

        record = db.get_chat_attachment(item["id"])
        self.assertIsNotNone(record)
        self.assertFalse(Path(record["storage_path"]).is_absolute())
        self.assertNotIn("screen.png", record["storage_path"])
        self.assertTrue(attachment_storage.resolve_storage_path(record["storage_path"]).is_file())
        self.assertTrue(attachment_storage.resolve_storage_path(record["thumbnail_path"]).is_file())

        media = self.client.get(item["media_url"])
        thumbnail = self.client.get(item["thumbnail_url"])
        self.assertEqual(media.status_code, 200)
        self.assertEqual(media.headers["content-type"], "image/png")
        self.assertEqual(thumbnail.status_code, 200)
        self.assertEqual(thumbnail.headers["content-type"], "image/webp")
        self.assertEqual(media.headers["cache-control"], "private, no-store")

    def test_upload_normalizes_jpeg_and_webp(self) -> None:
        for image_format, filename, content_type, expected_mime in (
            ("JPEG", "photo.jpg", "image/jpeg", "image/jpeg"),
            ("WEBP", "preview.webp", "image/webp", "image/webp"),
        ):
            with self.subTest(image_format=image_format):
                response = self._upload(
                    payload=_image_bytes(image_format),
                    filename=filename,
                    content_type=content_type,
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["mime_type"], expected_mime)

    def test_invalid_or_unsupported_image_leaves_no_record_or_file(self) -> None:
        corrupt = self._upload(payload=b"not an image", filename="../../secret.png")
        unsupported = self._upload(
            payload=_image_bytes(),
            filename="screen.gif",
            content_type="image/gif",
        )

        self.assertEqual(corrupt.status_code, 422)
        self.assertEqual(corrupt.json()["detail"]["code"], "INVALID_IMAGE")
        self.assertEqual(unsupported.status_code, 422)
        self.assertEqual(unsupported.json()["detail"]["code"], "UNSUPPORTED_IMAGE_TYPE")
        self.assertEqual(db.list_chat_attachments(profile_id=self.profile_id), [])
        runtime_files = [path for path in config.CHAT_ATTACHMENTS_DIR.rglob("*") if path.is_file()]
        self.assertEqual(runtime_files, [])

    def test_file_size_limit_is_backend_owned(self) -> None:
        db.update_profile_preferences(
            self.profile_id,
            {"settings": {"chat_image_max_file_bytes": 16}},
        )

        response = self._upload(payload=_image_bytes())

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "IMAGE_TOO_LARGE")
        self.assertEqual(response.json()["detail"]["max_file_bytes"], 16)
        self.assertEqual(db.list_chat_attachments(profile_id=self.profile_id), [])

    def test_media_and_delete_enforce_profile_ownership(self) -> None:
        item = self._upload().json()
        other_profile = db.create_profile("Other")

        media = self.client.get(
            f"/chat/attachments/{item['id']}",
            params={"profile_id": other_profile["id"]},
        )
        deletion = self.client.delete(
            f"/chat/attachments/{item['id']}",
            params={"profile_id": other_profile["id"]},
        )

        self.assertEqual(media.status_code, 403)
        self.assertEqual(media.json()["detail"]["code"], "ATTACHMENT_OWNERSHIP_MISMATCH")
        self.assertEqual(deletion.status_code, 403)
        self.assertIsNotNone(db.get_chat_attachment(item["id"]))

    def test_delete_removes_database_record_and_files(self) -> None:
        item = self._upload().json()
        record = db.get_chat_attachment(item["id"])
        image_path = attachment_storage.resolve_storage_path(record["storage_path"])
        thumbnail_path = attachment_storage.resolve_storage_path(record["thumbnail_path"])

        response = self.client.delete(item["media_url"])

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["deleted"])
        self.assertIsNone(db.get_chat_attachment(item["id"]))
        self.assertFalse(image_path.exists())
        self.assertFalse(thumbnail_path.exists())

    def test_session_delete_cleans_owned_attachment_files(self) -> None:
        session = db.create_session(self.profile_id, "Images", "qwen2.5:7b-instruct")
        item = self._upload(session_id=session["id"]).json()
        record = db.get_chat_attachment(item["id"])
        image_path = attachment_storage.resolve_storage_path(record["storage_path"])

        result = profile_routes.delete_chat_session(session["id"])

        self.assertEqual(result["deleted"], session["id"])
        self.assertIsNone(db.get_chat_attachment(item["id"]))
        self.assertFalse(image_path.exists())

    def test_cleanup_reports_deleted_bytes(self) -> None:
        first = self._upload().json()
        second = self._upload().json()
        expected_bytes = first["size_bytes"] + second["size_bytes"]

        response = self.client.post(
            "/chat/attachments/cleanup",
            json={"scope": "profile", "profile_id": self.profile_id},
        )

        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["deleted_count"], 2)
        self.assertEqual(result["deleted_bytes"], expected_bytes)
        self.assertEqual(result["skipped_active_count"], 0)
        self.assertEqual(db.list_chat_attachments(profile_id=self.profile_id), [])

    def test_storage_path_resolution_rejects_traversal(self) -> None:
        with self.assertRaises(attachment_storage.AttachmentStorageError) as raised:
            attachment_storage.resolve_storage_path("../../outside.png")
        self.assertEqual(raised.exception.code, "ATTACHMENT_PATH_INVALID")


if __name__ == "__main__":
    unittest.main()
