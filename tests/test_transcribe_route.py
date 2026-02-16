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


if __name__ == "__main__":
    unittest.main()
