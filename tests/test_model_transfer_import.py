from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.apps.model_transfer import import_service
from backend.apps.model_transfer.manifest import BundleValidationError


class ModelTransferImportTests(unittest.TestCase):
    def _bundle(self, base: Path, content: bytes = b"weights") -> Path:
        entry = "payload/piper/voice.onnx"
        manifest = {
            "schema": "localgpt-model-bundle",
            "version": 1,
            "bundle_id": "test-bundle",
            "created_at": "2026-07-28T00:00:00Z",
            "models": [{"id": "piper:voice", "family": "piper", "model_id": "voice", "files": [entry]}],
            "files": [{"path": entry, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}],
        }
        path = base / f"{__import__('uuid').uuid4()}.localgpt-models"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as bundle:
            bundle.writestr(entry, content)
            bundle.writestr("manifest.json", json.dumps(manifest))
        return path

    def _paths(self, base: Path):
        return SimpleNamespace(
            ollama=base / "ollama",
            whisper=base / "whisper",
            whisper_cpp=base / "whisper_cpp",
            piper=base / "piper",
        )

    def test_clean_import_and_identical_reimport(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            with patch.object(import_service.config, "MODEL_PATHS", self._paths(base)), patch.object(import_service.config, "DATA_DIR", base / "data"):
                first = import_service.apply_import(import_service.register_upload(self._bundle(base)))
                self.assertEqual(first["published_files"], 1)
                self.assertEqual((base / "piper" / "voice.onnx").read_bytes(), b"weights")
                second = import_service.apply_import(import_service.register_upload(self._bundle(base)))
                self.assertEqual(second["published_files"], 0)
                self.assertEqual(second["skipped_files"], 1)

    def test_conflict_does_not_replace_existing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            target = base / "piper" / "voice.onnx"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"existing")
            with patch.object(import_service.config, "MODEL_PATHS", self._paths(base)), patch.object(import_service.config, "DATA_DIR", base / "data"):
                with self.assertRaises(BundleValidationError) as ctx:
                    import_service.apply_import(import_service.register_upload(self._bundle(base)))
            self.assertEqual(ctx.exception.code, "target_conflict")
            self.assertEqual(target.read_bytes(), b"existing")

    def test_discard_removes_staged_upload(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = self._bundle(Path(temp))
            upload_id = import_service.register_upload(archive)
            self.assertTrue(import_service.discard_upload(upload_id))
            self.assertFalse(archive.exists())
            self.assertFalse(import_service.discard_upload(upload_id))

    def test_upload_storage_summary_and_cleanup_only_delete_upload_bundles(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            uploads = base / "data" / "model_transfer" / "uploads"
            uploads.mkdir(parents=True)
            bundle = uploads / "kept-for-import.localgpt-models"
            bundle.write_bytes(b"bundle")
            unrelated = uploads / "notes.txt"
            unrelated.write_text("keep")
            nested = uploads / "nested"
            nested.mkdir()
            nested_bundle = nested / "nested.localgpt-models"
            nested_bundle.write_bytes(b"nested")
            with patch.object(import_service.config, "DATA_DIR", base / "data"):
                upload_id = import_service.register_upload(bundle)
                self.assertEqual(import_service.upload_storage_summary(), {"file_count": 1, "total_size": 6})
                self.assertEqual(import_service.clear_upload_storage(), {"deleted_files": 1, "freed_size": 6})
                self.assertFalse(bundle.exists())
                self.assertTrue(unrelated.exists())
                self.assertTrue(nested_bundle.exists())
                with self.assertRaises(BundleValidationError):
                    import_service.apply_import(upload_id)


if __name__ == "__main__":
    unittest.main()
