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


if __name__ == "__main__":
    unittest.main()
