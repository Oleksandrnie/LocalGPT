from __future__ import annotations

import json
import unittest

from backend.apps.model_transfer.manifest import BundleManifest, BundleValidationError, validate_bundle_path


class ModelTransferManifestTests(unittest.TestCase):
    def _manifest(self, **changes):
        payload = {
            "schema": "localgpt-model-bundle",
            "version": 1,
            "bundle_id": "bundle-1",
            "created_at": "2026-07-27T00:00:00Z",
            "models": [{
                "id": "ollama:qwen3:8b",
                "family": "ollama",
                "model_id": "qwen3:8b",
                "files": ["payload/ollama/blobs/sha256-test"],
            }],
            "files": [{"path": "payload/ollama/blobs/sha256-test", "size": 4, "sha256": "a" * 64}],
        }
        payload.update(changes)
        return json.dumps(payload).encode()

    def test_accepts_strict_v1_manifest(self):
        parsed = BundleManifest.parse(self._manifest())
        self.assertEqual(parsed.bundle_id, "bundle-1")
        self.assertEqual(parsed.files[0].size, 4)

    def test_rejects_traversal_and_windows_paths(self):
        for path in ("payload/../secret", "/payload/file", r"payload\file"):
            with self.subTest(path=path), self.assertRaises(BundleValidationError) as ctx:
                validate_bundle_path(path)
            self.assertEqual(ctx.exception.code, "unsafe_bundle_path")

    def test_rejects_case_insensitive_duplicate(self):
        files = [
            {"path": "payload/piper/A.onnx", "size": 1, "sha256": "a" * 64},
            {"path": "payload/piper/a.onnx", "size": 1, "sha256": "b" * 64},
        ]
        with self.assertRaises(BundleValidationError) as ctx:
            BundleManifest.parse(self._manifest(files=files))
        self.assertEqual(ctx.exception.code, "bundle_invalid")

    def test_rejects_unknown_version(self):
        with self.assertRaises(BundleValidationError) as ctx:
            BundleManifest.parse(self._manifest(version=2))
        self.assertEqual(ctx.exception.code, "unsupported_bundle_version")

    def test_rejects_model_file_from_another_family(self):
        models = [{
            "id": "piper:voice",
            "family": "piper",
            "model_id": "voice",
            "files": ["payload/ollama/blobs/sha256-test"],
        }]
        with self.assertRaises(BundleValidationError) as ctx:
            BundleManifest.parse(self._manifest(models=models))
        self.assertEqual(ctx.exception.code, "bundle_invalid")


if __name__ == "__main__":
    unittest.main()
