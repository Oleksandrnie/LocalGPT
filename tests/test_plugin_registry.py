from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.apps.plugins import registry


def _write_manifest(root: Path, plugin_id: str, payload: dict) -> None:
    plugin_dir = root / plugin_id
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _manifest(plugin_id: str, *, name: str | None = None) -> dict:
    return {
        "id": plugin_id,
        "name": name or plugin_id.title(),
        "type": "runtime_connectivity",
        "version": "0.1.0",
        "enabled_by_default": False,
        "description": "Test plugin manifest.",
        "permissions": ["read_runtime_status"],
        "dangerous_permissions": [],
        "docs": ["README.md"],
    }


class PluginRegistryTests(unittest.TestCase):
    def test_empty_plugins_dir_returns_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = registry.scan_plugins(plugins_dir=Path(tmp), enabled_state={}).as_response()

        self.assertEqual(result["plugins"], [])
        self.assertEqual(result["invalid_plugins"], [])
        self.assertIn("No plugins installed", result["message"])

    def test_trusted_tailscale_manifest_is_detected_but_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "tailscale", _manifest("tailscale", name="Tailscale Remote Access"))

            result = registry.scan_plugins(plugins_dir=root, enabled_state={}).as_response()

        self.assertEqual(len(result["plugins"]), 1)
        plugin = result["plugins"][0]
        self.assertEqual(plugin["id"], "tailscale")
        self.assertTrue(plugin["trusted"])
        self.assertFalse(plugin["enabled"])
        self.assertFalse(plugin["effective_enabled"])
        self.assertEqual(plugin["status"], "disabled")

    def test_unknown_manifest_is_untrusted_and_has_no_effective_enable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "unknown", _manifest("unknown", name="Unknown Plugin"))

            result = registry.scan_plugins(plugins_dir=root, enabled_state={"unknown": True}).as_response()

        plugin = result["plugins"][0]
        self.assertFalse(plugin["trusted"])
        self.assertTrue(plugin["enabled"])
        self.assertFalse(plugin["effective_enabled"])
        self.assertEqual(plugin["status"], "untrusted")
        self.assertEqual(plugin["execution"], "unavailable")

    def test_invalid_manifest_is_reported_without_breaking_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad").mkdir()
            (root / "bad" / "plugin.json").write_text("{not-json", encoding="utf-8")

            result = registry.scan_plugins(plugins_dir=root, enabled_state={}).as_response()

        self.assertEqual(result["plugins"], [])
        self.assertEqual(len(result["invalid_plugins"]), 1)
        self.assertEqual(result["invalid_plugins"][0]["status"], "invalid")
        self.assertFalse(result["invalid_plugins"][0]["trusted"])


if __name__ == "__main__":
    unittest.main()
