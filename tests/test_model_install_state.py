from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services import models as model_service


class ModelInstallStateTests(unittest.TestCase):
    def test_partial_blob_does_not_override_runtime_installed_model(self):
        with (
            patch.object(
                model_service,
                "_list_local_models",
                return_value=[{"name": "qwen2.5:7b-instruct", "installed": True, "runtime_installed": True}],
            ),
            patch.object(model_service, "_list_active_models", return_value=[]),
            patch.object(model_service, "_pull_statuses", return_value=[]),
            patch.object(
                model_service,
                "_inspect_storage_manifests",
                return_value=(
                    {
                        "qwen2.5:7b-instruct": {
                            "model": "qwen2.5:7b-instruct",
                            "storage_present": True,
                            "storage_size_gb": 4.36,
                            "stores": [],
                        }
                    },
                    {"sha256:abc": {"qwen2.5:7b-instruct"}},
                ),
            ),
            patch.object(
                model_service,
                "_list_partial_blobs",
                return_value=[
                    {
                        "digest": "sha256:abc",
                        "size": 1024,
                        "model_candidates": ["qwen2.5:7b-instruct"],
                    }
                ],
            ),
        ):
            payload = model_service.list_models()

        item = next(model for model in payload["catalog"] if model["name"] == "qwen2.5:7b-instruct")
        self.assertEqual(item["state"], "installed")
        self.assertTrue(item["installed"])
        self.assertFalse(item["partial"])
        self.assertTrue(item["partial_blob_found"])
        self.assertFalse(item["missing"])

    def test_missing_runtime_model_with_partial_blob_is_partial(self):
        with (
            patch.object(model_service, "_list_local_models", return_value=[]),
            patch.object(model_service, "_list_active_models", return_value=[]),
            patch.object(model_service, "_pull_statuses", return_value=[]),
            patch.object(
                model_service,
                "_inspect_storage_manifests",
                return_value=({}, {"sha256:abc": {"qwen2.5:7b-instruct"}}),
            ),
            patch.object(
                model_service,
                "_list_partial_blobs",
                return_value=[
                    {
                        "digest": "sha256:abc",
                        "size": 1024,
                        "model_candidates": ["qwen2.5:7b-instruct"],
                    }
                ],
            ),
        ):
            payload = model_service.list_models()

        item = next(model for model in payload["catalog"] if model["name"] == "qwen2.5:7b-instruct")
        self.assertEqual(item["state"], "partial")
        self.assertFalse(item["installed"])
        self.assertTrue(item["partial"])
        self.assertTrue(item["partial_blob_found"])
        self.assertTrue(item["missing"])

    def test_ollama_ps_controls_active_state(self):
        with (
            patch.object(
                model_service,
                "_list_local_models",
                return_value=[{"name": "qwen3:0.6b", "installed": True, "runtime_installed": True}],
            ),
            patch.object(model_service, "_list_active_models", return_value=[{"name": "qwen3:0.6b"}]),
            patch.object(model_service, "_pull_statuses", return_value=[]),
            patch.object(model_service, "_inspect_storage_manifests", return_value=({}, {})),
            patch.object(model_service, "_list_partial_blobs", return_value=[]),
        ):
            payload = model_service.list_models()

        item = next(model for model in payload["utility"] if model["name"] == "qwen3:0.6b")
        self.assertEqual(item["state"], "active")
        self.assertTrue(item["active"])
        self.assertTrue(item["installed"])


if __name__ == "__main__":
    unittest.main()
