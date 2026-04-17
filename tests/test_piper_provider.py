import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from app import config
from app.providers.tts.piper_provider import PiperProvider


def write_voice_files(root: Path, name: str, payload: dict) -> Path:
    model_path = root / f"{name}.onnx"
    config_path = Path(f"{model_path}.json")
    model_path.write_bytes(b"fake-onnx")
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return model_path


class FakeSynthesisConfig:
    def __init__(self, speaker_id=None):
        self.speaker_id = speaker_id


class FakeChunk:
    def __init__(self, sample_rate: int = 22050, samples: int = 2205):
        self.sample_rate = sample_rate
        self.audio_int16_array = [0] * samples
        self.audio_int16_bytes = b"\x00\x00" * samples


class FakeRuntimeVoice:
    class Config:
        sample_rate = 22050

    config = Config()

    def synthesize(self, text: str, syn_config=None):
        yield FakeChunk()


class FakeUrlopenResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        import io

        self._buffer = io.BytesIO(json.dumps(self.payload).encode("utf-8"))
        return self._buffer

    def __exit__(self, exc_type, exc, tb):
        return False


class PiperProviderTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_dir = config.PIPER_MODELS_DIR
        config.PIPER_MODELS_DIR = Path(self.temp_dir.name)

    def tearDown(self):
        config.PIPER_MODELS_DIR = self.original_dir
        self.temp_dir.cleanup()

    def test_list_voices_discovers_local_model(self):
        write_voice_files(
            config.PIPER_MODELS_DIR,
            "en_US-lessac-medium",
            {
                "audio": {"sample_rate": 22050},
                "espeak": {"voice": "en_US"},
                "num_speakers": 1,
                "phoneme_id_map": {},
                "num_symbols": 1,
            },
        )

        provider = PiperProvider()
        voices = provider.list_voices()

        self.assertEqual(len(voices), 1)
        self.assertEqual(voices[0].language, "en_US")
        self.assertEqual(voices[0].name, "Lessac")

    def test_list_voices_expands_speaker_map(self):
        write_voice_files(
            config.PIPER_MODELS_DIR,
            "ru_RU-demo-medium",
            {
                "audio": {"sample_rate": 22050},
                "espeak": {"voice": "ru_RU"},
                "num_speakers": 2,
                "speaker_id_map": {"narrator": 0, "assistant": 1},
                "phoneme_id_map": {},
                "num_symbols": 1,
            },
        )

        provider = PiperProvider()
        voices = provider.list_voices()

        self.assertEqual(len(voices), 2)
        self.assertTrue(any("Narrator" in voice.name for voice in voices))
        self.assertTrue(any("Assistant" in voice.name for voice in voices))

    def test_synthesize_writes_wav_file(self):
        model_path = write_voice_files(
            config.PIPER_MODELS_DIR,
            "en_US-lessac-medium",
            {
                "audio": {"sample_rate": 22050},
                "espeak": {"voice": "en_US"},
                "num_speakers": 1,
                "phoneme_id_map": {},
                "num_symbols": 1,
            },
        )
        output_path = Path(self.temp_dir.name) / "result.wav"
        provider = PiperProvider()
        voice = provider.list_voices()[0]

        with patch.object(provider, "_runtime_classes", return_value=(object, FakeSynthesisConfig)):
            with patch.object(provider, "_load_runtime_voice", return_value=FakeRuntimeVoice()):
                result = provider.synthesize("Hello world", voice.id, output_path)

        self.assertEqual(Path(result.output_path), output_path)
        self.assertTrue(output_path.exists())
        self.assertGreater(result.duration_sec, 0)

        with wave.open(str(output_path), "rb") as wav_file:
            self.assertEqual(wav_file.getframerate(), 22050)
            self.assertGreater(wav_file.getnframes(), 0)

        self.assertEqual(Path(voice.model_path), model_path.resolve())

    @patch("app.providers.tts.piper_provider.urlopen")
    def test_list_catalog_voices_marks_installed(self, mock_urlopen):
        write_voice_files(
            config.PIPER_MODELS_DIR,
            "en_US-lessac-medium",
            {
                "audio": {"sample_rate": 22050},
                "espeak": {"voice": "en_US"},
                "num_speakers": 1,
                "phoneme_id_map": {},
                "num_symbols": 1,
            },
        )
        mock_urlopen.return_value = FakeUrlopenResponse(
            {
                "en_US-lessac-medium": {
                    "name": "lessac",
                    "quality": "medium",
                    "num_speakers": 1,
                    "aliases": [],
                    "language": {
                        "code": "en_US",
                        "name_english": "English",
                        "country_english": "United States",
                    },
                    "files": {
                        "en/en_US/lessac/medium/en_US-lessac-medium.onnx": {"size_bytes": 12345678},
                    },
                }
            }
        )

        provider = PiperProvider()
        items = provider.list_catalog_voices()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["key"], "en_US-lessac-medium")
        self.assertTrue(items[0]["installed"])
        self.assertEqual(items[0]["download_size_bytes"], 12345678)

    def test_resolve_preview_voice_id_prefers_exact_or_first_speaker(self):
        write_voice_files(
            config.PIPER_MODELS_DIR,
            "ru_RU-demo-medium",
            {
                "audio": {"sample_rate": 22050},
                "espeak": {"voice": "ru_RU"},
                "num_speakers": 2,
                "speaker_id_map": {"narrator": 0, "assistant": 1},
                "phoneme_id_map": {},
                "num_symbols": 1,
            },
        )

        provider = PiperProvider()
        voices = provider.list_voices()

        self.assertEqual(provider.resolve_preview_voice_id(voices[1].id), voices[1].id)
        self.assertEqual(provider.resolve_preview_voice_id("ru_RU-demo-medium"), voices[0].id)

    def test_delete_voice_removes_local_model_files(self):
        model_path = write_voice_files(
            config.PIPER_MODELS_DIR,
            "ru_RU-demo-medium",
            {
                "audio": {"sample_rate": 22050},
                "espeak": {"voice": "ru_RU"},
                "num_speakers": 1,
                "phoneme_id_map": {},
                "num_symbols": 1,
            },
        )

        provider = PiperProvider()
        deleted = provider.delete_voice("ru_RU-demo-medium")

        self.assertTrue(deleted)
        self.assertFalse(model_path.exists())
        self.assertFalse(Path(f"{model_path}.json").exists())


if __name__ == "__main__":
    unittest.main()
