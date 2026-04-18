import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import asr_whisper


class SnapshotDirsTestCase(unittest.TestCase):
    def test_snapshot_dirs_uses_only_project_hf_cache(self):
        repo_id = "Systran/faster-whisper-small"

        with tempfile.TemporaryDirectory() as temp_dir:
            project_cache = Path(temp_dir) / "project-hf-cache"
            project_snapshot = project_cache / "models--Systran--faster-whisper-small" / "snapshots" / "local-project"
            project_snapshot.mkdir(parents=True)

            fake_home_snapshot = (
                Path(temp_dir)
                / "home-cache"
                / "models--Systran--faster-whisper-small"
                / "snapshots"
                / "home-copy"
            )
            fake_home_snapshot.mkdir(parents=True)

            with patch.object(asr_whisper.config, "HF_CACHE_DIR", project_cache):
                with patch("app.asr_whisper.Path.home", return_value=Path(temp_dir) / "home-cache"):
                    snapshots = asr_whisper._snapshot_dirs(repo_id)

        self.assertEqual(snapshots, [project_snapshot])


if __name__ == "__main__":
    unittest.main()
