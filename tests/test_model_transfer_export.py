from __future__ import annotations

import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from backend.apps.model_transfer import export_service
from backend.apps.model_transfer.manifest import BundleManifest


class ModelTransferExportTests(unittest.TestCase):
    def test_export_creates_valid_stored_zip64_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "models"
            root.mkdir()
            first = root / "model.bin"
            first.write_bytes(b"model bytes")
            unit = {
                "id": "whisper-cpp:tiny",
                "family": "whisper-cpp",
                "model_id": "tiny",
                "complete": True,
                "_root": root,
                "_files": [first],
            }
            with (
                patch.object(export_service.config, "DATA_DIR", Path(temp)),
                patch.object(export_service, "export_units", return_value=[unit]),
            ):
                started = export_service.start_export([unit["id"]])
                for _ in range(100):
                    task = export_service.get_task(started["task_id"])
                    if task["status"] != "running":
                        break
                    time.sleep(0.01)
                self.assertEqual(task["status"], "completed")
                archive, _ = export_service.archive_path(started["task_id"])
                with zipfile.ZipFile(archive) as bundle:
                    self.assertTrue(all(item.compress_type == zipfile.ZIP_STORED for item in bundle.infolist()))
                    manifest = BundleManifest.parse(bundle.read("manifest.json"))
                    self.assertEqual(manifest.models[0]["id"], unit["id"])
                    self.assertEqual(bundle.read(manifest.files[0].path), b"model bytes")


if __name__ == "__main__":
    unittest.main()
