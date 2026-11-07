from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositorySafetyHookTests(unittest.TestCase):
    def test_hooks_delegate_to_shared_runner(self) -> None:
        self.assertIn('"$HOOK_DIR/../scripts/run_repo_safety_hook.sh" commit', (ROOT / ".githooks" / "pre-commit").read_text())
        self.assertIn('"$HOOK_DIR/../scripts/run_repo_safety_hook.sh" push', (ROOT / ".githooks" / "pre-push").read_text())

    def test_push_gate_uses_the_same_target_for_both_scanners(self) -> None:
        source = (ROOT / "scripts" / "run_repo_safety_hook.sh").read_text()
        self.assertIn('BASE=${LOCALGPT_SAFETY_BASE:-origin/dev}', source)
        self.assertIn('gitleaks git . --log-opts="$BASE..HEAD"', source)
        self.assertIn('GIT_CONFIG_VALUE_1="refs/heads/${BASE_BRANCH}"', source)
        self.assertNotIn("CareerFlow", source)


if __name__ == "__main__":
    unittest.main()
