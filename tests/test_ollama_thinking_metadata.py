from __future__ import annotations

import io
import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import models as model_service


class OllamaThinkingMetadataTests(unittest.TestCase):
    def test_named_levels_are_normalized_without_raw_payload(self):
        details = model_service._show_json_details({
            "thinking": {"values": ["low", "medium", "high", "low"], "default": "medium", "path": "/secret"},
            "template": "/secret/raw-template",
        })
        self.assertEqual(details, {"thinking": {"values": ["low", "medium", "high"], "default": "medium"}})

    def test_boolean_levels_and_explicit_unsupported_are_preserved(self):
        for values, default in (([False, True], True), ([False], False), ([True], True)):
            with self.subTest(values=values):
                self.assertEqual(model_service._normalize_thinking({"values": values, "default": default}),
                                 {"values": values, "default": default})

    def test_absent_and_malformed_metadata_are_unknown(self):
        malformed = [None, False, {}, {"values": []}, {"values": "low"},
                     {"values": [1]}, {"values": [None]}, {"values": [{}]},
                     {"values": ["low", "/secret/path"]}, {"values": ["a" * 65]},
                     {"values": ["low\n"]}, {"values": ["low"] * 33}]
        for value in malformed:
            with self.subTest(value=value):
                self.assertIsNone(model_service._normalize_thinking(value))
                self.assertNotIn("thinking", model_service._show_json_details({"thinking": value}))
        self.assertNotIn("thinking", model_service._show_json_details({"capabilities": ["thinking"]}))
        self.assertNotIn("thinking", model_service._show_plain_details("Capabilities\n  thinking\n"))

    def test_default_must_be_a_declared_typed_value(self):
        for default in (None, 0, 1, "high", {}, "/secret/path"):
            with self.subTest(default=default):
                self.assertEqual(model_service._normalize_thinking({"values": [False, "low"], "default": default}),
                                 {"values": [False, "low"], "default": None})

    def test_native_show_uses_configured_endpoint_without_cli(self):
        payload = {"thinking": {"values": ["low", "high"], "default": "high"}, "template": "/secret"}
        with (
            patch.object(model_service.config, "SETTINGS", SimpleNamespace(base_url="http://example.invalid:11434/v1/")),
            patch.object(model_service, "urlopen", return_value=io.BytesIO(json.dumps(payload).encode())) as opener,
            patch.object(model_service.subprocess, "run") as run,
        ):
            details = model_service._show_model_details("custom:latest")
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, "http://example.invalid:11434/api/show")
        self.assertEqual(request.method, "POST")
        self.assertEqual(json.loads(request.data), {"model": "custom:latest"})
        self.assertEqual(details, {"thinking": payload["thinking"]})
        run.assert_not_called()

    def test_native_show_failure_or_invalid_payload_retains_json_cli_fallback(self):
        completed = subprocess.CompletedProcess([], 0, stdout='{"thinking":{"values":[false],"default":false}}')
        for raw in (b"not json", b"[]", b'{"error":"unavailable"}'):
            with (
                self.subTest(raw=raw),
                patch.object(model_service, "urlopen", return_value=io.BytesIO(raw)),
                patch.object(model_service.subprocess, "run", return_value=completed),
            ):
                self.assertEqual(model_service._show_model_details("custom"),
                                 {"thinking": {"values": [False], "default": False}})
        with (
            patch.object(model_service, "urlopen", side_effect=OSError("offline")),
            patch.object(model_service.subprocess, "run", return_value=completed),
        ):
            self.assertEqual(model_service._show_model_details("custom")["thinking"]["values"], [False])

    def test_inventory_propagates_custom_and_catalog_metadata_without_raw_fields(self):
        catalog_model = "catalog:latest"
        custom_model = "custom:latest"
        listing = "\n".join(json.dumps({"name": name, "details": {"thinking": {"raw": "/secret"}}})
                            for name in (catalog_model, custom_model))
        metadata = {catalog_model: {"values": [False], "default": False},
                    custom_model: {"values": ["low", "high"], "default": "low"}}
        def show(request, **_kwargs):
            name = json.loads(request.data)["model"]
            return io.BytesIO(json.dumps({"thinking": metadata[name], "template": "/secret"}).encode())
        with (
            patch.object(model_service.config, "MODEL_CATALOG", [{"id": catalog_model}, {"id": "missing"}]),
            patch.object(model_service.config, "VISION_MODEL_CATALOG", []),
            patch.object(model_service.config, "UTILITY_MODEL_CATALOG", []),
            patch.object(model_service.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=listing)),
            patch.object(model_service, "urlopen", side_effect=show),
            patch.object(model_service, "_list_active_models", return_value=[]),
            patch.object(model_service, "_pull_statuses", return_value=[]),
            patch.object(model_service, "_inspect_storage_manifests", return_value=({}, {})),
            patch.object(model_service, "_list_partial_blobs", return_value=[]),
        ):
            result = model_service.list_models()
        installed = {item["name"]: item for item in result["installed"]}
        for name, thinking in metadata.items():
            self.assertEqual(installed[name]["thinking"], thinking)
            self.assertEqual(installed[name]["details"]["thinking"], thinking)
        self.assertFalse(installed[custom_model]["configured"])
        self.assertEqual(result["catalog"][0]["thinking"], metadata[catalog_model])
        self.assertEqual(result["catalog"][0]["runtime"]["thinking"], metadata[catalog_model])
        self.assertIsNone(result["catalog"][1]["thinking"])
        self.assertNotIn("/secret", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
