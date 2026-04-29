import tempfile
import unittest
import wave
from pathlib import Path

from app.services.audio_postprocess_service import apply_speed_to_wav, probe_wav_duration


def create_silent_wav(path: Path, duration_sec: float = 1.0, sample_rate: int = 16000) -> None:
    frames = int(duration_sec * sample_rate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frames)


class AudioPostprocessServiceTestCase(unittest.TestCase):
    def test_probe_wav_duration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            wav_path = Path(temp_dir) / "input.wav"
            create_silent_wav(wav_path, duration_sec=1.5)

            duration = probe_wav_duration(wav_path)

        self.assertAlmostEqual(duration, 1.5, places=2)

    def test_apply_speed_to_wav(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.wav"
            output_path = Path(temp_dir) / "output.wav"
            create_silent_wav(input_path, duration_sec=1.6)

            duration = apply_speed_to_wav(input_path, output_path, 2.0)

            self.assertTrue(output_path.exists())
            self.assertLess(duration, 1.0)
            self.assertGreater(duration, 0.6)


if __name__ == "__main__":
    unittest.main()
