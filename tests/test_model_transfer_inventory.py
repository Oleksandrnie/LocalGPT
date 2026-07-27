from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.apps.model_transfer import inventory


class ModelTransferInventoryTests(unittest.TestCase):
    def test_ollama_inventory_deduplicates_shared_blob_size(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifests = root / "manifests" / "registry.ollama.ai" / "library"
            blob = root / "blobs" / "sha256-shared"
            blob.parent.mkdir(parents=True)
            blob.write_bytes(b"shared")
            payload = {"config": {"digest": "sha256:shared", "size": 6}, "layers": []}
            for model in ("one", "two"):
                path = manifests / model / "latest"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload), encoding="utf-8")
            paths = SimpleNamespace(ollama=root, whisper=root / "whisper", whisper_cpp=root / "cpp", piper=root / "piper")
            with (
                patch.object(inventory.config, "MODEL_PATHS", paths),
                patch.object(inventory.downloads, "list_local_models", return_value=[]),
                patch.object(inventory.PiperProvider, "list_voices", return_value=[]),
            ):
                result = inventory.export_inventory()
            self.assertEqual(result["complete_count"], 2)
            expected = blob.stat().st_size + sum(path.stat().st_size for path in manifests.rglob("latest"))
            self.assertEqual(result["total_unique_size"], expected)

    def test_partial_ollama_model_is_not_selectable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifests" / "registry.ollama.ai" / "library" / "broken" / "latest"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"config": {"digest": "sha256:missing"}, "layers": []}), encoding="utf-8")
            paths = SimpleNamespace(ollama=root, whisper=root / "whisper", whisper_cpp=root / "cpp", piper=root / "piper")
            with (
                patch.object(inventory.config, "MODEL_PATHS", paths),
                patch.object(inventory.downloads, "list_local_models", return_value=[]),
                patch.object(inventory.PiperProvider, "list_voices", return_value=[]),
            ):
                result = inventory.export_inventory()
            self.assertFalse(result["models"][0]["selectable"])
            self.assertEqual(result["models"][0]["reason"], "missing_blob")


if __name__ == "__main__":
    unittest.main()
