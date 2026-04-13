import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.server import app
from app.services.tts_service import TTSServiceError


def create_silent_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 1600)


class TTSRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("app.routers.tts.tts_service.get_health")
    def test_tts_health(self, mock_health):
        mock_health.return_value = {"status": "ok", "default_provider": "piper"}

        response = self.client.get("/tts/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @patch("app.routers.tts.tts_service.list_voices")
    def test_tts_voices(self, mock_list_voices):
        mock_list_voices.return_value = [{"id": "voice-1", "name": "Demo", "available": True}]

        response = self.client.get("/tts/voices")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["id"], "voice-1")

    @patch("app.routers.tts.tts_service.start_generation")
    def test_tts_generate(self, mock_start_generation):
        mock_start_generation.return_value = {"id": "tts_1", "status": "queued"}

        response = self.client.post(
            "/tts/generate",
            json={"text": "Hello world", "voice_id": "voice-1"},
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["id"], "tts_1")

    @patch("app.routers.tts.tts_service.start_generation")
    def test_tts_generate_error(self, mock_start_generation):
        mock_start_generation.side_effect = TTSServiceError(422, "voice_not_found", "Voice missing")

        response = self.client.post(
            "/tts/generate",
            json={"text": "Hello world", "voice_id": "voice-1"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "voice_not_found")

    @patch("app.routers.tts.tts_service.start_speed_processing")
    def test_tts_process_speed(self, mock_start_speed):
        mock_start_speed.return_value = {"id": "tts_1", "status": "queued"}

        response = self.client.post("/tts/process-speed", json={"id": "tts_1", "speed": 1.25})

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "queued")

    @patch("app.routers.tts.tts_service.list_history")
    def test_tts_history(self, mock_list_history):
        mock_list_history.return_value = [{"id": "tts_1", "status": "completed"}]

        response = self.client.get("/tts/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["id"], "tts_1")

    @patch("app.routers.tts.tts_service.get_history_item")
    def test_tts_history_item(self, mock_get_history_item):
        mock_get_history_item.return_value = {"id": "tts_1", "status": "completed"}

        response = self.client.get("/tts/history/tts_1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "tts_1")

    @patch("app.routers.tts.tts_service.delete_history_item")
    def test_tts_history_delete(self, mock_delete_history_item):
        response = self.client.delete("/tts/history/tts_1")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        mock_delete_history_item.assert_called_once_with("tts_1")

    @patch("app.routers.tts.tts_service.resolve_output_file")
    def test_tts_output(self, mock_resolve_output_file):
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "result.wav"
            create_silent_wav(wav_path)
            mock_resolve_output_file.return_value = (str(wav_path), "result.wav")

            response = self.client.get("/tts/output/tts_1?variant=base")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "audio/wav")


if __name__ == "__main__":
    unittest.main()
