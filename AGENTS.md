# Repository safety and contribution rules

## Personal data and test exports

Before every commit, inspect all staged paths and review added text hunks. Before every push or pull request, repeat the review over the complete proposed branch range against its target branch (normally `origin/dev`). Run:

```sh
python scripts/check_commit_data.py --staged
python -m ai_repo_safety gate --when commit --target .
```

Before publishing a branch or opening/updating a PR, run:

```sh
python scripts/check_commit_data.py --range origin/dev
python -m ai_repo_safety gate --when push --target .
gitleaks git . --log-opts='origin/dev..HEAD' --redact
```

Use the repository's active Python environment for `ai_repo_safety` when `python` is not on `PATH`. Keep the installed fail-closed `pre-commit` and `pre-push` hooks enabled; never use `--no-verify` to bypass them.

Only `.gitkeep` files may be proposed under `rag_sources/` or `app/data/`. Do not commit Telegram exports, user documents, databases, attachments, generated profile data, credentials, or other runtime files. Test fixtures must be synthetic and must not be copied from a user's real export.

If any candidate file, filename, or added content appears to contain personal data, a real export, database/runtime data, credentials, or non-synthetic test material—or if its status is uncertain—stop. Do not commit, push, create a PR, or update an existing PR until the user decides how to handle it. Report only the relevant paths and ask the user; do not print suspected personal contents. Remove or replace approved data locally before rerunning the complete checks.

The path audit is a guardrail, not a content classifier. Review the proposed diff for personal information even when the path audit passes. For PR checks, use the actual target branch if it differs from `origin/dev`.
