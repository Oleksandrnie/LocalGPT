from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "setup_localgpt", ROOT / "setup" / "setup_localgpt.py"
)
assert SPEC and SPEC.loader
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


class SetupDependencyTests(unittest.TestCase):
    def test_supported_operating_systems_are_normalized(self) -> None:
        expectations = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}
        for reported, expected in expectations.items():
            with self.subTest(reported=reported), patch.object(
                setup.platform, "system", return_value=reported
            ):
                self.assertEqual(setup.host_os(), expected)

    def test_unknown_operating_system_fails_explicitly(self) -> None:
        with patch.object(setup.platform, "system", return_value="Plan9"):
            with self.assertRaises(setup.SetupError):
                setup.host_os()

    def test_linux_package_manager_detection_has_stable_precedence(self) -> None:
        with patch.object(setup.shutil, "which", side_effect=lambda name: "/bin/apt-get" if name == "apt-get" else None):
            self.assertEqual(setup.linux_package_manager(), "apt-get")

    def test_missing_commands_only_returns_absent_tools(self) -> None:
        with patch.object(setup.shutil, "which", side_effect=lambda name: f"/bin/{name}" if name == "git" else None):
            self.assertEqual(setup.missing_commands(["git", "ffmpeg"]), ["ffmpeg"])

    def test_model_installation_is_not_part_of_setup_contract(self) -> None:
        source = (ROOT / "setup" / "setup_localgpt.py").read_text(encoding="utf-8")
        self.assertNotIn("ollama pull", source)
        self.assertNotIn("setup_whisper_cpp", source)


if __name__ == "__main__":
    unittest.main()
