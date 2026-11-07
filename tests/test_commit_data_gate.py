import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "check_commit_data.py"
SPEC = importlib.util.spec_from_file_location("commit_data_gate", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CommitDataGateTests(unittest.TestCase):
    def test_only_gitkeep_is_allowed_in_runtime_data_roots(self):
        for path in ("rag_sources/.gitkeep", "app/data/profile-3/.gitkeep"):
            with self.subTest(path=path):
                self.assertFalse(MODULE.suspicious(path))
        for path in ("rag_sources/messages.html", "app/data/profile-3/history.db", "app/data/README.md"):
            with self.subTest(path=path):
                self.assertTrue(MODULE.suspicious(path))

    def test_user_export_and_database_names_are_blocked_anywhere(self):
        for path in ("tests/messages42.html", "fixtures/ChatExport_private.zip", "var/profile.sqlite3"):
            with self.subTest(path=path):
                self.assertTrue(MODULE.suspicious(path))

    def test_normal_source_and_synthetic_inline_fixtures_are_not_path_blocked(self):
        for path in ("backend/apps/telegram_search/parser.py", "tests/test_telegram_search.py", "web_ui/gui_html.html", "docs/knowledge/telegram_export_search_spec.md", "tests/chat_history_loading.test.mjs"):
            with self.subTest(path=path):
                self.assertFalse(MODULE.suspicious(path))


if __name__ == "__main__":
    unittest.main()
