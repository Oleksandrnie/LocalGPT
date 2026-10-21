from __future__ import annotations

import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.apps.model_transfer import export_service, import_service
from backend.apps.model_transfer.manifest import BundleManifest
from backend.apps.model_transfer.import_service import inspect_archive


class ModelTransferExportTests(unittest.TestCase):
    @staticmethod
    def _wait(task_id: str):
        for _ in range(100):
            task = export_service.get_task(task_id)
            if task["status"] != "running":
                return task
            time.sleep(0.01)
        return export_service.get_task(task_id)

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
                inspected = inspect_archive(archive)
                self.assertTrue(inspected["valid"])
                self.assertEqual(inspected["models"][0]["id"], unit["id"])

    def test_bundle_imports_into_different_provider_roots_without_source_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "source-device" / "custom-models"
            destination = base / "destination-device" / "other-models"
            source.mkdir(parents=True)
            fixtures = [
                ("ollama:qwen2.5vl:7b", "ollama", "qwen2.5vl:7b", "manifests/registry.ollama.ai/library/qwen2.5vl/7b"),
                ("ollama:embeddinggemma:latest", "ollama", "embeddinggemma:latest", "blobs/sha256-embedding"),
                ("faster-whisper:large-v3", "faster-whisper", "large-v3", "large-v3/model.bin"),
                ("whisper-cpp:large-v3-turbo", "whisper-cpp", "large-v3-turbo", "ggml-large-v3-turbo.bin"),
                ("piper:ru/voice", "piper", "ru/voice", "ru/voice.onnx"),
            ]
            units = []
            for unit_id, family, model_id, relative in fixtures:
                root = source / family
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"{family}:{model_id}".encode("utf-8"))
                units.append({
                    "id": unit_id,
                    "family": family,
                    "model_id": model_id,
                    "complete": True,
                    "_root": root,
                    "_files": [path],
                })
            with (
                patch.object(export_service.config, "DATA_DIR", base / "export-data"),
                patch.object(export_service, "export_units", return_value=units),
            ):
                started = export_service.start_export([unit["id"] for unit in units])
                task = self._wait(started["task_id"])
                self.assertEqual(task["status"], "completed")
                archive, _ = export_service.archive_path(started["task_id"])
                with zipfile.ZipFile(archive) as bundle:
                    manifest_raw = bundle.read("manifest.json").decode("utf-8")
                    self.assertNotIn(str(source), manifest_raw)
                    self.assertNotIn(str(base.parent), manifest_raw)
                imported_bundle = base / "upload.localgpt-models"
                imported_bundle.write_bytes(archive.read_bytes())

            destination_paths = SimpleNamespace(
                ollama=destination / "ollama",
                whisper=destination / "faster-whisper",
                whisper_cpp=destination / "whisper-cpp",
                piper=destination / "piper",
            )
            with (
                patch.object(import_service.config, "MODEL_PATHS", destination_paths),
                patch.object(import_service.config, "DATA_DIR", base / "import-data"),
            ):
                result = import_service.apply_import(import_service.register_upload(imported_bundle))
            self.assertEqual(result["published_files"], len(fixtures))
            self.assertIn("whisper_cpp_cli", result["runtime_requirements"])
            self.assertIn("ollama_runtime", result["runtime_requirements"])
            for _, family, _, relative in fixtures:
                configured_root = {
                    "ollama": destination_paths.ollama,
                    "faster-whisper": destination_paths.whisper,
                    "whisper-cpp": destination_paths.whisper_cpp,
                    "piper": destination_paths.piper,
                }[family]
                self.assertTrue((configured_root / relative).is_file())


if __name__ == "__main__":
    unittest.main()
