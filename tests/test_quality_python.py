import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "quality_python.py"
SPEC = importlib.util.spec_from_file_location("quality_python", SCRIPT)
quality_python = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quality_python)


class QualityPythonScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self._git("init", "--initial-branch=main")
        self._git("config", "user.name", "LocalGPT test")
        self._git("config", "user.email", "localgpt-test@example.invalid")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True)

    def _commit(self, message):
        self._git("add", "--all")
        self._git("commit", "-m", message)
        return self._git("rev-parse", "HEAD").stdout.strip()

    def test_initial_push_without_base_scans_every_tracked_python_file(self):
        (self.root / "app.py").write_text("pass\n", encoding="utf-8")
        (self.root / "backend").mkdir()
        (self.root / "backend" / "worker.py").write_text("pass\n", encoding="utf-8")
        (self.root / "README.md").write_text("source\n", encoding="utf-8")
        self._commit("initial")

        files, full_scan = quality_python.collect_python_files(
            self.root,
            {"PUSH_BASE_SHA": "0" * 40, "DEFAULT_BRANCH": "main"},
        )

        self.assertTrue(full_scan)
        self.assertEqual(set(files), {"app.py", "backend/worker.py"})

    def test_default_branch_dispatch_scans_all_when_base_is_head(self):
        (self.root / "app.py").write_text("pass\n", encoding="utf-8")
        self._commit("initial")
        self._git("update-ref", "refs/remotes/origin/main", "HEAD")

        files, full_scan = quality_python.collect_python_files(self.root, {"DEFAULT_BRANCH": "main"})

        self.assertTrue(full_scan)
        self.assertEqual(files, ["app.py"])

    def test_distinct_merge_base_scans_only_changed_python_files(self):
        (self.root / "app.py").write_text("pass\n", encoding="utf-8")
        (self.root / "worker.py").write_text("pass\n", encoding="utf-8")
        base = self._commit("initial")
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        self._commit("change app")

        files, full_scan = quality_python.collect_python_files(self.root, {"PR_BASE_SHA": base})

        self.assertFalse(full_scan)
        self.assertEqual(files, ["app.py"])


if __name__ == "__main__":
    unittest.main()
