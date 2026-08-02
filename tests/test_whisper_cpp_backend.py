import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import config
from backend.apps.asr import downloads, whisper, whisper_cpp
from backend.apps.asr.whisper_cpp import transcribe_with_whisper_cpp, whisper_cpp_model_path, whisper_cpp_runtime_status


class WhisperCppBackendTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.original = {
            "whisper_backend": config.SETTINGS.whisper_backend,
            "whisper_cpp_binary": config.SETTINGS.whisper_cpp_binary,
            "whisper_cpp_models_dir": config.SETTINGS.whisper_cpp_models_dir,
            "whisper_cpp_model_path": config.SETTINGS.whisper_cpp_model_path,
            "whisper_cpp_convert_audio": config.SETTINGS.whisper_cpp_convert_audio,
            "whisper_cpp_threads": config.SETTINGS.whisper_cpp_threads,
            "whisper_cpp_extra_args": config.SETTINGS.whisper_cpp_extra_args,
            "whisper_cpp_download_coreml": config.SETTINGS.whisper_cpp_download_coreml,
            "transcribe_log_file": config.TRANSCRIBE_LOG_FILE,
        }
        config.SETTINGS.whisper_backend = "whisper_cpp"
        config.SETTINGS.whisper_cpp_binary = "/bin/echo"
        config.SETTINGS.whisper_cpp_models_dir = self.tmp / "whisper_cpp"
        config.SETTINGS.whisper_cpp_model_path = str(self.tmp / "whisper_cpp" / "ggml-{model}.bin")
        config.SETTINGS.whisper_cpp_convert_audio = False
        config.SETTINGS.whisper_cpp_threads = 0
        config.SETTINGS.whisper_cpp_extra_args = ()
        config.SETTINGS.whisper_cpp_download_coreml = False
        config.TRANSCRIBE_LOG_FILE = self.tmp / "transcribe.log"
        config.SETTINGS.whisper_cpp_models_dir.mkdir(parents=True, exist_ok=True)
        whisper_cpp.whisper_cpp_vad_model_path().write_bytes(b"vad")
        downloads._TASKS.clear()
        downloads._ACTIVE_BY_MODEL.clear()

    def tearDown(self):
        for key, value in self.original.items():
            if key == "transcribe_log_file":
                config.TRANSCRIBE_LOG_FILE = value
            else:
                setattr(config.SETTINGS, key, value)
        downloads._TASKS.clear()
        downloads._ACTIVE_BY_MODEL.clear()
        self.tmpdir.cleanup()

    def _write_model(self, model: str = "small") -> Path:
        path = whisper_cpp_model_path(model)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ggml")
        return path

    def test_whisper_cpp_runner_parses_json_output(self):
        model_path = self._write_model("small")
        audio_path = self.tmp / "audio.wav"
        audio_path.write_bytes(b"wav")

        def fake_run(command, capture_output, text, check):
            self.assertIn(str(model_path), command)
            self.assertIn("--output-json", command)
            self.assertEqual(command[command.index("--language") + 1], "ru")
            self.assertEqual(command[command.index("--threads") + 1], "4")
            self.assertEqual(command[command.index("--prompt") + 1], "secret prompt")
            self.assertIn("--suppress-nst", command)
            self.assertIn("--no-fallback", command)
            self.assertEqual(command[command.index("--no-speech-thold") + 1], "0.8")
            self.assertEqual(command[command.index("--vad-model") + 1], str(whisper_cpp.whisper_cpp_vad_model_path()))
            output_prefix = Path(command[command.index("--output-file") + 1])
            output_prefix.with_suffix(".json").write_text(
                json.dumps(
                    {
                        "result": {"language": "ru"},
                        "transcription": [
                            {"offsets": {"from": 1000, "to": 2500}, "text": " hello"},
                            {"offsets": {"from": 2500, "to": 4100}, "text": " world"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("backend.apps.asr.whisper_cpp.subprocess.run", side_effect=fake_run):
            result = transcribe_with_whisper_cpp(
                audio_path=audio_path,
                model_name="small",
                prompt="secret prompt",
                language="ru",
                beam_size=3,
                threads=4,
            )

        self.assertEqual(result["text"], "hello\nworld")
        self.assertEqual(result["language"], "ru")
        self.assertEqual(result["segments"][0]["start"], 1.0)
        self.assertEqual(result["segments"][1]["end"], 4.1)
        self.assertEqual(result["runtime"]["backend"], "whisper_cpp")
        self.assertEqual(result["runtime"]["model"], "small")
        self.assertEqual(result["runtime"]["language"], "ru")
        self.assertEqual(result["runtime"]["beam_size"], 3)
        self.assertEqual(result["runtime"]["threads"], 4)
        self.assertTrue(result["runtime"]["prompt_present"])
        self.assertEqual(
            result["runtime"]["decoder_guard_args"],
            ["--suppress-nst", "--no-fallback", "--no-speech-thold", "0.8"],
        )
        self.assertIn("<prompt chars=13>", result["runtime"]["command"])

        log_lines = config.TRANSCRIBE_LOG_FILE.read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in log_lines]
        self.assertEqual(events[0]["event"], "whisper_cpp_start")
        self.assertEqual(events[-1]["event"], "whisper_cpp_done")
        self.assertIn("<prompt chars=13>", events[0]["runtime"]["command"])
        self.assertNotIn("secret prompt", config.TRANSCRIBE_LOG_FILE.read_text(encoding="utf-8"))

    def test_whisper_cpp_runner_collapses_long_repeated_segments(self):
        self._write_model("small")
        audio_path = self.tmp / "audio.wav"
        audio_path.write_bytes(b"wav")

        def fake_run(command, capture_output, text, check):
            output_prefix = Path(command[command.index("--output-file") + 1])
            output_prefix.with_suffix(".json").write_text(
                json.dumps(
                    {
                        "transcription": [
                            {"offsets": {"from": 0, "to": 1000}, "text": " Subtitle editor credit"},
                            {"offsets": {"from": 1000, "to": 2000}, "text": " Subtitle editor credit"},
                            {"offsets": {"from": 2000, "to": 3000}, "text": " Subtitle editor credit"},
                            {"offsets": {"from": 3000, "to": 4000}, "text": " Actual speech"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("backend.apps.asr.whisper_cpp.subprocess.run", side_effect=fake_run):
            result = transcribe_with_whisper_cpp(
                audio_path=audio_path,
                model_name="small",
                prompt=None,
                language="ru",
                beam_size=3,
            )

        self.assertEqual(result["text"], "Subtitle editor credit\nSubtitle editor credit\nActual speech")
        self.assertEqual(len(result["segments"]), 3)

    def test_transcribe_with_fallback_uses_whisper_cpp_backend(self):
        self._write_model("small")
        audio_path = self.tmp / "audio.wav"
        audio_path.write_bytes(b"wav")

        with patch("backend.apps.asr.whisper_cpp.transcribe_with_whisper_cpp") as transcribe:
            transcribe.return_value = {
                "text": "hello",
                "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
                "language": "en",
            }

            result = whisper.transcribe_with_fallback(str(audio_path), "small", preferred_language="en")

        self.assertEqual(result["text"], "hello")
        transcribe.assert_called_once()
        self.assertEqual(transcribe.call_args.kwargs["model_name"], "small")

    def test_prompt_preset_drives_language_when_language_is_auto(self):
        self._write_model("small")
        audio_path = self.tmp / "audio.wav"
        audio_path.write_bytes(b"wav")
        (self.tmp / "whisper_prompt.txt").write_text("local prompt marker", encoding="utf-8")

        with patch("backend.apps.asr.whisper_cpp.transcribe_with_whisper_cpp") as transcribe:
            transcribe.return_value = {
                "text": "привет",
                "segments": [{"start": 0.0, "end": 1.0, "text": "привет"}],
                "language": "ru",
            }

            result = whisper.transcribe_with_fallback(str(audio_path), "small", prompt_preset="ru")

        self.assertEqual(result["text"], "привет")
        transcribe.assert_called_once()
        self.assertEqual(transcribe.call_args.kwargs["language"], "ru")
        self.assertIn("пунктуация", transcribe.call_args.kwargs["prompt"])
        self.assertIn("local prompt marker", transcribe.call_args.kwargs["prompt"])
        self.assertEqual(result["runtime"]["prompt_preset"], "ru")
        self.assertEqual(result["runtime"]["effective_language"], "ru")
        self.assertTrue(result["runtime"]["preset_prompt_used"])
        self.assertTrue(result["runtime"]["local_prompt_used"])

    def test_transcribe_log_rotates_by_size(self):
        config.TRANSCRIBE_LOG_FILE.write_text("x" * 20, encoding="utf-8")

        with patch.dict(os.environ, {"TRANSCRIBE_LOG_MAX_BYTES": "10"}):
            whisper_cpp._log_transcription_event({"event": "next"})

        backup_path = config.TRANSCRIBE_LOG_FILE.with_name(f"{config.TRANSCRIBE_LOG_FILE.name}.1")
        self.assertEqual(backup_path.read_text(encoding="utf-8"), "x" * 20)
        self.assertIn('"event": "next"', config.TRANSCRIBE_LOG_FILE.read_text(encoding="utf-8"))

    def test_model_prepare_listing_uses_ggml_path_in_whisper_cpp_mode(self):
        model_path = self._write_model("medium")

        items = downloads.list_local_models()
        medium = next(item for item in items if item["name"] == "medium")

        self.assertTrue(medium["installed"])
        self.assertTrue(medium["ready"])
        self.assertTrue(medium["runtime_installed"])
        self.assertEqual(medium["repo_id"], "ggerganov/whisper.cpp")
        self.assertEqual(medium["path"], str(model_path))

        task = downloads.start_prepare_task("medium")
        self.assertEqual(task["state"], "completed")
        self.assertEqual(task["repo_id"], "ggerganov/whisper.cpp")

    def test_model_listing_marks_downloaded_model_not_ready_without_cli(self):
        model_path = self._write_model("small")
        missing_binary = self.tmp / "missing" / "whisper-cli"
        config.SETTINGS.whisper_cpp_binary = str(missing_binary)

        status = whisper_cpp_runtime_status("small")
        self.assertTrue(status["model_installed"])
        self.assertFalse(status["runtime_installed"])
        self.assertFalse(status["ready"])
        self.assertIn(str(model_path), status["model_path"])

        items = downloads.list_local_models()
        small = next(item for item in items if item["name"] == "small")

        self.assertTrue(small["installed"])
        self.assertFalse(small["ready"])
        self.assertFalse(small["runtime_installed"])
        self.assertEqual(small["runtime_binary"], str(missing_binary))
        self.assertTrue(any("whisper-cli" in warning for warning in small["warnings"]))
