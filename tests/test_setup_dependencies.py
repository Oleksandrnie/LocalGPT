from __future__ import annotations

import importlib.util
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
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

    def test_setup_uses_canonical_requirements_and_runtime_venv(self) -> None:
        self.assertEqual(setup.REQUIREMENTS, ROOT / "app" / "requirements.txt")
        self.assertEqual(setup.VENV_DIR, ROOT / "venv")
        self.assertEqual(setup.DOT_VENV_DIR, ROOT / ".venv")

    def test_all_setup_entry_points_are_collocated(self) -> None:
        entry_points = (
            "setup_localgpt.command",
            "setup_localgpt.sh",
            "setup_localgpt.bat",
        )
        for name in entry_points:
            with self.subTest(name=name):
                self.assertTrue((ROOT / "setup" / name).is_file())
                self.assertFalse((ROOT / name).exists())
        for name in ("setup_localgpt.command", "setup_localgpt.sh"):
            with self.subTest(executable=name):
                self.assertTrue(os.access(ROOT / "setup" / name, os.X_OK))

    def test_shell_entry_point_resolves_core_from_its_own_directory(self) -> None:
        source = (ROOT / "setup" / "setup_localgpt.sh").read_text(encoding="utf-8")
        self.assertIn('PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)', source)
        self.assertIn('"$SCRIPT_DIR/setup_localgpt.py"', source)
        self.assertIn("python3.13 python3.12 python3.11 python3.10 python3 python", source)

    def test_dot_venv_is_preserved_and_explained(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            requirements = temp / "requirements.txt"
            requirements.write_text("", encoding="utf-8")
            dot_venv = temp / ".venv"
            dot_venv.mkdir()
            output = io.StringIO()
            with (
                patch.object(setup, "REQUIREMENTS", requirements),
                patch.object(setup, "VENV_DIR", temp / "venv"),
                patch.object(setup, "DOT_VENV_DIR", dot_venv),
                patch.object(setup.sys, "version_info", (3, 12, 0)),
                patch.object(setup, "run"),
                patch.object(setup, "ask", return_value=False),
                redirect_stdout(output),
            ):
                setup.install_project_dependencies()
            self.assertIn("The existing .venv is left untouched", output.getvalue())
            self.assertTrue(dot_venv.is_dir())


if __name__ == "__main__":
    unittest.main()
