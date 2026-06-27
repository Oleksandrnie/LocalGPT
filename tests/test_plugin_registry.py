from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.apps.plugins import registry
from backend.apps.plugins import tailscale


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

    def test_manifest_docs_include_open_url_for_available_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "tailscale", _manifest("tailscale", name="Tailscale Remote Access"))
            (root / "tailscale" / "README.md").write_text("# Tailscale docs\n", encoding="utf-8")

            result = registry.scan_plugins(plugins_dir=root, enabled_state={}).as_response()

        docs = result["plugins"][0]["docs_status"]
        self.assertEqual(docs[0]["path"], "README.md")
        self.assertTrue(docs[0]["available"])
        self.assertEqual(docs[0]["url"], "/plugins/tailscale/docs/README.md")

    def test_get_plugin_doc_reads_manifest_doc_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "tailscale", _manifest("tailscale", name="Tailscale Remote Access"))
            (root / "tailscale" / "README.md").write_text("# Tailscale docs\n", encoding="utf-8")

            doc = registry.get_plugin_doc("tailscale", "README.md", plugins_dir=root)

            with self.assertRaises(registry.PluginDocError):
                registry.get_plugin_doc("tailscale", "../secret.txt", plugins_dir=root)

        self.assertEqual(doc["content"], "# Tailscale docs\n")
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

    def test_list_plugins_attaches_trusted_tailscale_handler_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "tailscale", _manifest("tailscale", name="Tailscale Remote Access"))

            with patch.dict(
                registry.TRUSTED_HANDLER_STATUS,
                {
                    "tailscale": lambda request=None: {
                        "manual_command_template": "tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>",
                        "manual_command": "tailscale serve --bg http://127.0.0.1:8000",
                        "security_warnings": list(registry.tailscale.SECURITY_WARNINGS),
                        "cli_available": False,
                    }
                },
            ):
                result = registry.list_plugins(plugins_dir=root, enabled_state={})

        plugin = result["plugins"][0]
        self.assertEqual(plugin["id"], "tailscale")
        self.assertIn("handler_status", plugin)
        self.assertEqual(
            plugin["handler_status"]["manual_command_template"],
            "tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>",
        )
        self.assertIn("Do not expose LocalGPT directly to the public internet.", plugin["security_warnings"])

    def test_tailscale_manual_command_uses_request_server_port_before_defaults(self) -> None:
        class Request:
            scope = {"server": ("127.0.0.1", 8003)}

        with tempfile.TemporaryDirectory() as tmp:
            stale_port_file = Path(tmp) / "backend.port"
            stale_port_file.write_text("8001", encoding="utf-8")
            with (
                patch.object(tailscale, "_BACKEND_PORT_FILE", stale_port_file),
                patch.dict("os.environ", {"LOCALGPT_PORT": "8000", "LOCALGPT_BACKEND_PORT": "8002"}),
            ):
                self.assertEqual(tailscale.detect_localgpt_port(Request()), 8003)
                self.assertEqual(
                    tailscale.manual_command(request=Request()),
                    "tailscale serve --bg http://127.0.0.1:8003",
                )

    def test_network_addresses_uses_enabled_trusted_tailscale_handler_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "tailscale", _manifest("tailscale", name="Tailscale Remote Access"))
            result = registry.list_network_addresses(
                plugins_dir=root,
                enabled_state={"tailscale": True},
                handler_status={
                    "tailscale": {
                        "address_available": True,
                        "url": "https://macbook.example.ts.net/ui/gui_html.html",
                    }
                },
            )

        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["provider_id"], "tailscale")
        self.assertEqual(result["items"][0]["url"], "https://macbook.example.ts.net/ui/gui_html.html")

    def test_network_addresses_omits_disabled_tailscale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_manifest(root, "tailscale", _manifest("tailscale", name="Tailscale Remote Access"))
            result = registry.list_network_addresses(
                plugins_dir=root,
                enabled_state={},
                handler_status={
                    "tailscale": {
                        "address_available": True,
                        "url": "https://macbook.example.ts.net/ui/gui_html.html",
                    }
                },
            )

        self.assertEqual(result["items"], [])
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
