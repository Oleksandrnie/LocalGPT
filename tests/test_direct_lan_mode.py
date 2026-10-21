from __future__ import annotations

import contextlib
import io
import os
import socket
import unittest
from unittest.mock import MagicMock, patch

import run_localgpt
from app.routes import meta
from backend.networking import detect_private_lan_ipv4, is_loopback_bind_host, is_private_lan_ipv4


class DirectLanModeTests(unittest.TestCase):
    def test_private_lan_ipv4_accepts_only_rfc1918_addresses(self) -> None:
        for address in ("10.0.0.7", "172.16.0.8", "192.168.1.9"):
            with self.subTest(address=address):
                self.assertTrue(is_private_lan_ipv4(address))

        for address in ("100.64.0.10", "8.8.8.8", "not-an-ip", None):
            with self.subTest(address=address):
                self.assertFalse(is_private_lan_ipv4(address))

    def test_private_ipv4_detection_uses_route_selection_and_filters_result(self) -> None:
        socket_context = MagicMock()
        fake_socket = MagicMock()
        socket_context.__enter__.return_value = fake_socket
        fake_socket.getsockname.return_value = ("192.168.1.42", 0)

        with patch("backend.networking.socket.socket", return_value=socket_context) as make_socket:
            self.assertEqual(detect_private_lan_ipv4(), "192.168.1.42")

        make_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)
        fake_socket.connect.assert_called_once_with(("192.0.2.1", 9))

        fake_socket.getsockname.return_value = ("100.64.0.42", 0)
        with patch("backend.networking.socket.socket", return_value=socket_context):
            self.assertIsNone(detect_private_lan_ipv4())

    def test_loopback_bind_detection(self) -> None:
        for host in ("127.0.0.1", "localhost", "::1", "[::1]"):
            with self.subTest(host=host):
                self.assertTrue(is_loopback_bind_host(host))

        for host in ("0.0.0.0", "::", "192.168.1.5", "example.local"):
            with self.subTest(host=host):
                self.assertFalse(is_loopback_bind_host(host))

    def test_runner_sets_lan_mode_only_for_non_loopback_bind(self) -> None:
        with patch("run_localgpt.run") as run:
            run_localgpt.start_backend("python", host="127.0.0.1", port=8000, reload_enabled=False)
        self.assertEqual(run.call_args.kwargs["env"]["LOCALGPT_LAN_MODE"], "0")

        with patch("run_localgpt.run") as run:
            run_localgpt.start_backend("python", host="0.0.0.0", port=8000, reload_enabled=False)
        self.assertEqual(run.call_args.kwargs["env"]["LOCALGPT_LAN_MODE"], "1")

    def test_network_bind_warning_includes_private_url_and_risk(self) -> None:
        output = io.StringIO()
        with patch("run_localgpt.detect_private_lan_ipv4", return_value="192.168.1.42"):
            with contextlib.redirect_stdout(output):
                run_localgpt.report_access_mode("0.0.0.0", 8123)

        self.assertIn("without application-wide authentication or TLS", output.getvalue())
        self.assertIn("read and change LocalGPT data", output.getvalue())
        self.assertIn("http://192.168.1.42:8123/ui/gui_html.html", output.getvalue())

    def test_loopback_warning_does_not_claim_network_access(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run_localgpt.report_access_mode("127.0.0.1", 8123)

        self.assertIn("Local-only bind", output.getvalue())
        self.assertNotIn("LAN UI URL", output.getvalue())
        self.assertNotIn("without application-wide authentication", output.getvalue())

    def test_network_address_is_only_exposed_in_lan_mode(self) -> None:
        with patch.dict(os.environ, {"LOCALGPT_LAN_MODE": "0", "LOCALGPT_PORT": "8123"}):
            with patch("app.routes.meta.detect_private_lan_ipv4") as detect_address:
                self.assertEqual(meta.get_network_address_items(), [])
                detect_address.assert_not_called()

        with patch.dict(os.environ, {"LOCALGPT_LAN_MODE": "1", "LOCALGPT_PORT": "8123"}):
            with patch("app.routes.meta.detect_private_lan_ipv4", return_value="192.168.1.42"):
                items = meta.get_network_address_items()

        self.assertEqual(items[0]["url"], "http://192.168.1.42:8123/ui/gui_html.html")
        self.assertFalse(items[0]["trusted"])
        self.assertIn("без TLS и общей авторизации", items[0]["detail"])


if __name__ == "__main__":
    unittest.main()
