import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.apps.asr import whisper


class WhisperLoadingSecurityTests(unittest.TestCase):
    def test_missing_model_is_rejected_before_loading_library(self):
        constructor = Mock()
        fake_module = types.ModuleType("faster_whisper")
        fake_module.WhisperModel = constructor

        with patch.object(whisper, "is_local_model_ready", return_value=False), patch.dict(
            sys.modules, {"faster_whisper": fake_module}
        ):
            with self.assertRaisesRegex(RuntimeError, "WHISPER_MODEL_NOT_FOUND::base"):
                whisper._load_model("base")

        constructor.assert_not_called()

    def test_model_load_uses_local_files_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "base"
            model = object()
            constructor = Mock(return_value=model)
            fake_module = types.ModuleType("faster_whisper")
            fake_module.WhisperModel = constructor
            with patch.object(whisper, "is_local_model_ready", return_value=True), patch.object(
                whisper, "local_model_dir", return_value=model_path
            ), patch.object(whisper.config, "WHISPER_MODELS_DIR", Path(temp_dir)), patch.dict(
                sys.modules, {"faster_whisper": fake_module}
            ), patch.dict(whisper._MODEL_CACHE, {}, clear=True):
                loaded = whisper._load_model("base", device="cpu", compute_type="int8")

        self.assertIs(loaded, model)
        constructor.assert_called_once_with(
            str(model_path),
            device="cpu",
            compute_type="int8",
            download_root=temp_dir,
            local_files_only=True,
        )


if __name__ == "__main__":
    unittest.main()
