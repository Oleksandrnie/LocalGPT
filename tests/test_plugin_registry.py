from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app import db
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
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.tmpdir.name) / "plugin-registry.db"
        db.init_db()

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.tmpdir.cleanup()

    def test_empty_plugins_dir_returns_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = registry.scan_plugins(plugins_dir=Path(tmp), enabled_state={}).as_response()

        self.assertEqual(result["plugins"], [])
        self.assertEqual(result["invalid_plugins"], [])
        self.assertIn("No plugins installed", result["message"])

    def test_manifest_without_backend_handler_is_detected_but_untrusted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "example_plugin", _manifest("example_plugin", name="Example Plugin"))
            result = registry.scan_plugins(plugins_dir=root, enabled_state={}).as_response()

        self.assertEqual(len(result["plugins"]), 1)
        plugin = result["plugins"][0]
        self.assertEqual(plugin["id"], "example_plugin")
        self.assertFalse(plugin["trusted"])
        self.assertFalse(plugin["enabled"])
        self.assertFalse(plugin["effective_enabled"])
        self.assertEqual(plugin["status"], "untrusted")

    def test_manifest_docs_include_open_url_for_available_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "example_plugin", _manifest("example_plugin", name="Example Plugin"))
            (root / "example_plugin" / "README.md").write_text("# Example docs\n", encoding="utf-8")
            result = registry.scan_plugins(plugins_dir=root, enabled_state={}).as_response()

        docs = result["plugins"][0]["docs_status"]
        self.assertEqual(docs[0]["path"], "README.md")
        self.assertTrue(docs[0]["available"])
        self.assertEqual(docs[0]["url"], "/plugins/example_plugin/docs/README.md")

    def test_get_plugin_doc_reads_manifest_doc_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "example_plugin", _manifest("example_plugin", name="Example Plugin"))
            (root / "example_plugin" / "README.md").write_text("# Example docs\n", encoding="utf-8")
            doc = registry.get_plugin_doc("example_plugin", "README.md", plugins_dir=root)

            with self.assertRaises(registry.PluginDocError):
                registry.get_plugin_doc("example_plugin", "../secret.txt", plugins_dir=root)

        self.assertEqual(doc["content"], "# Example docs\n")
        self.assertEqual(doc["filename"], "README.md")

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

    def test_no_plugins_are_trusted_without_backend_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "example_plugin", _manifest("example_plugin", name="Example Plugin"))
            result = registry.list_plugins(plugins_dir=root, enabled_state={"example_plugin": True})

        self.assertEqual(registry.TRUSTED_PLUGIN_IDS, frozenset())
        self.assertEqual(registry.TRUSTED_HANDLER_STATUS, {})
        self.assertEqual(registry.TRUSTED_NETWORK_ADDRESS_ITEMS, {})
        plugin = result["plugins"][0]
        self.assertFalse(plugin["trusted"])
        self.assertFalse(plugin["effective_enabled"])
        self.assertNotIn("handler_status", plugin)

    def test_network_addresses_ignore_untrusted_plugin_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "example_plugin", _manifest("example_plugin", name="Example Plugin"))
            result = registry.list_network_addresses(
                plugins_dir=root,
                enabled_state={"example_plugin": True},
                handler_status={
                    "example_plugin": {
                        "address_available": True,
                        "url": "https://example.invalid/ui/gui_html.html",
                    }
                },
            )

        self.assertEqual(result["items"], [])
        self.assertEqual(result["providers"], [])
        self.assertIn("No network addresses", result["message"])

    def test_network_addresses_includes_core_lan_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = registry.list_network_addresses(
                plugins_dir=Path(tmp),
                enabled_state={},
                core_items=[
                    {
                        "id": "lan",
                        "provider_id": "lan",
                        "label": "LAN",
                        "url": "https://192.168.1.10:8443/ui/gui_html.html",
                        "copyable": True,
                        "priority": 10,
                    }
                ],
            )

        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["provider_id"], "lan")
        self.assertEqual(result["items"][0]["url"], "https://192.168.1.10:8443/ui/gui_html.html")
        self.assertEqual(result["message"], "")


if __name__ == "__main__":
    unittest.main()
