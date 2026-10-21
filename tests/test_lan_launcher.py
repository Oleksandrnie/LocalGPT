from __future__ import annotations

import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_localgpt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT_ROOT / "tools" / "LTrnsrb.sh"


class LanLauncherContractTestCase(unittest.TestCase):
    def test_ordinary_launchers_are_local_only_and_lan_is_explicit(self) -> None:
        for name in ("start_localgpt.command", "start_localgpt.sh"):
            with self.subTest(name=name):
                source = (PROJECT_ROOT / name).read_text(encoding="utf-8")
                self.assertNotIn("start_localgpt_lan", source)
                self.assertIn("--stop", source)
                self.assertNotIn('exec /bin/zsh "$SCRIPT_DIR/tools/LTrnsrb.sh"', source)

        self.assertIn("start_localgpt_lan.sh", (PROJECT_ROOT / "start_localgpt_lan.command").read_text(encoding="utf-8"))
        self.assertIn("tools/LTrnsrb.sh", (PROJECT_ROOT / "start_localgpt_lan.sh").read_text(encoding="utf-8"))
        for name in ("stop_localgpt_lan.command", "stop_localgpt_lan.sh"):
            with self.subTest(stop_entry=name):
                self.assertIn("--stop", (PROJECT_ROOT / name).read_text(encoding="utf-8"))
        self.assertIn('"${1:-}" == "--stop"', (PROJECT_ROOT / "tools/LTrnsrb.sh").read_text(encoding="utf-8"))

    def _render(self, *, backend_port: int = 8123, https_port: int = 9443) -> str:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "Caddyfile.auto"
            script = "\n".join(
                (
                    "export LOCALGPT_LAUNCHER_LIBRARY_ONLY=1",
                    f"source {shlex.quote(str(LAUNCHER))}",
                    f"BACKEND_PORT={backend_port}",
                    f"HTTPS_PORT={https_port}",
                    f"CADDY_CONFIG_FILE={shlex.quote(str(config_path))}",
                    "write_caddy_config 192.168.50.25",
                    'cat "$CADDY_CONFIG_FILE"',
                )
            )
            completed = subprocess.run(
                ["/bin/zsh", "-c", script],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            return completed.stdout

    def test_generated_caddy_config_binds_private_ip_and_actual_backend_port(self) -> None:
        config = self._render()

        self.assertIn("https://192.168.50.25:9443", config)
        self.assertIn("bind 192.168.50.25", config)
        self.assertIn("reverse_proxy 127.0.0.1:8123", config)
        self.assertIn("auto_https disable_redirects", config)
        self.assertNotIn("0.0.0.0", config)
        self.assertNotIn("reverse_proxy 127.0.0.1:8000", config)

    def test_changed_upstream_marks_config_for_caddy_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "Caddyfile.auto"
            script = "\n".join(
                (
                    "export LOCALGPT_LAUNCHER_LIBRARY_ONLY=1",
                    f"source {shlex.quote(str(LAUNCHER))}",
                    "HTTPS_PORT=9443",
                    f"CADDY_CONFIG_FILE={shlex.quote(str(config_path))}",
                    "BACKEND_PORT=8123",
                    "write_caddy_config 192.168.50.25",
                    'first="$CADDY_CONFIG_CHANGED"',
                    "write_caddy_config 192.168.50.25",
                    'same="$CADDY_CONFIG_CHANGED"',
                    "BACKEND_PORT=8124",
                    "write_caddy_config 192.168.50.25",
                    'changed="$CADDY_CONFIG_CHANGED"',
                    'printf "%s %s %s" "$first" "$same" "$changed"',
                )
            )
            completed = subprocess.run(
                ["/bin/zsh", "-c", script],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.stdout, "1 0 1")

    def test_occupied_backend_port_selects_a_different_actual_port(self) -> None:
        occupied_port = 18123
        with patch.object(run_localgpt, "can_bind_port", side_effect=lambda _host, port: port != occupied_port):
            actual_port = run_localgpt.find_available_port("127.0.0.1", occupied_port, attempts=10)

        self.assertNotEqual(actual_port, occupied_port)
        self.assertGreater(actual_port, 0)

    def test_no_browser_mode_reports_url_without_invoking_open(self) -> None:
        script = "\n".join(
            (
                "export LOCALGPT_LAUNCHER_LIBRARY_ONLY=1",
                "export LOCALGPT_NO_BROWSER=1",
                f"source {shlex.quote(str(LAUNCHER))}",
                "open_url https://192.168.50.25:9443/ui/gui_html.html",
            )
        )
        completed = subprocess.run(
            ["/bin/zsh", "-c", script],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("Browser opening disabled", completed.stdout)


if __name__ == "__main__":
    unittest.main()
