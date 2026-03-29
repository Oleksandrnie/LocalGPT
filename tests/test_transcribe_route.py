import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import transcript_store
from app.server import app


class TranscribeRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_dir = transcript_store.TRANSCRIPTS_DIR
        transcript_store.TRANSCRIPTS_DIR = Path(self.temp_dir.name)
        self.client = TestClient(app)

    def tearDown(self):
        transcript_store.TRANSCRIPTS_DIR = self.original_dir
        self.temp_dir.cleanup()

    @patch("app.routes.transcribe.transcribe_with_fallback")
    def test_transcribe_creates_transcript(self, mock_transcribe):
        mock_transcribe.return_value = {
            "text": "test transcription",
            "language": "en",
            "duration_sec": 4.5,
        }

        response = self.client.post(
            "/transcribe",
            files={"file": ("sample.wav", b"fake-wav-data", "audio/wav")},
            data={"model": "small", "source_type": "upload"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["text"], "test transcription")
        self.assertEqual(payload["model"], "small")
        self.assertEqual(payload["source_type"], "upload")

        stored = transcript_store.get_transcript(payload["id"])
        self.assertIsNotNone(stored)
        self.assertEqual(stored["text"], "test transcription")

    def test_transcribe_rejects_invalid_model(self):
        response = self.client.post(
            "/transcribe",
            files={"file": ("sample.wav", b"fake-wav-data", "audio/wav")},
            data={"model": "not-real-model"},
        )

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "invalid_model")

    def test_prepare_rejects_invalid_model(self):
        response = self.client.post("/whisper/models/prepare", json={"model": "not-real-model"})
        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "invalid_model")

    @patch("app.routes.transcribe.transcribe_tasks.start_transcription_task")
    def test_start_transcription_task(self, mock_start_task):
        mock_start_task.return_value = {
            "id": "tt_test_123",
            "state": "running",
            "model": "small",
            "source_type": "upload",
            "source_name": "sample.wav",
            "message": "Transcription started.",
            "error_code": None,
            "pid": 12345,
            "result": None,
        }

        response = self.client.post(
            "/transcribe/tasks",
            files={"file": ("sample.wav", b"fake-wav-data", "audio/wav")},
            data={"model": "small", "source_type": "upload"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], "tt_test_123")
        self.assertEqual(payload["state"], "running")
        self.assertEqual(payload["model"], "small")

    @patch("app.routes.transcribe.transcribe_tasks.get_transcription_task")
    def test_get_transcription_task(self, mock_get_task):
        mock_get_task.return_value = {
            "id": "tt_test_123",
            "state": "completed",
            "result": {"id": "tr_1", "text": "done"},
        }

        response = self.client.get("/transcribe/tasks/tt_test_123")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], "tt_test_123")
        self.assertEqual(payload["state"], "completed")

    @patch("app.routes.transcribe.transcribe_tasks.cancel_transcription_task")
    def test_cancel_transcription_task(self, mock_cancel_task):
        mock_cancel_task.return_value = {
            "id": "tt_test_123",
            "state": "cancelling",
            "message": "Stopping transcription...",
        }

        response = self.client.post("/transcribe/tasks/tt_test_123/cancel")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], "tt_test_123")
        self.assertEqual(payload["state"], "cancelling")

    def test_cancel_transcription_task_not_found(self):
        response = self.client.post("/transcribe/tasks/tt_missing/cancel")
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "transcription_task_not_found")

    def test_delete_transcript(self):
        created = transcript_store.create_transcript(
            text="to be deleted",
            source_type="manual",
        )
        response = self.client.delete(f"/transcripts/{created['id']}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["id"], created["id"])
        self.assertIsNone(transcript_store.get_transcript(created["id"]))

    def test_delete_transcript_not_found(self):
        response = self.client.delete("/transcripts/tr_not_found")
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "transcript_not_found")


if __name__ == "__main__":
    unittest.main()
