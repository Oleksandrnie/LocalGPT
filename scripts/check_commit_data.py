#!/usr/bin/env python3
"""Block commits/PRs that add likely user exports or runtime data by path."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import PurePosixPath

ALLOW_IN_DATA = {".gitkeep"}
DATA_ROOTS = {"rag_sources", "app/data"}
SENSITIVE_SUFFIXES = {
    ".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".pfx",
    ".ovpn", ".zip", ".7z", ".rar",
}


def suspicious(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    parts = PurePosixPath(normalized).parts
    name = parts[-1] if parts else ""
    lower = name.casefold()
    if any(normalized == root or normalized.startswith(root + "/") for root in DATA_ROOTS):
        return name not in ALLOW_IN_DATA
    if PurePosixPath(lower).suffix in SENSITIVE_SUFFIXES:
        return True
    export_suffixes = {".html", ".json", ".jsonl", ".zip", ".txt", ".pdf", ".docx"}
    if lower.startswith(("chartexport", "telegram_export", "chat_export")) and PurePosixPath(lower).suffix in export_suffixes:
        return True
    if lower.startswith("messages") and lower.endswith(".html"):
        return True
    if lower in {"credentials.json", "service-account.json", "token.json", "tokens.json", "secrets.json"}:
        return True
    return False


def changed_paths(args: argparse.Namespace) -> list[str]:
    if args.staged:
        cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
    else:
        cmd = ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{args.range}...HEAD"]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return sorted(set(result.stdout.splitlines()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="check staged additions/renames")
    group.add_argument("--range", metavar="BASE", help="check changes in BASE...HEAD")
    args = parser.parse_args()
    paths = changed_paths(args)
    matches = [path for path in paths if suspicious(path)]
    if matches:
        print("Potential user data in proposed changes; stop and ask the user before commit/push/PR:", file=sys.stderr)
        for path in matches:
            print(f"  {path}", file=sys.stderr)
        return 2
    print(f"Data-path audit passed ({len(paths)} changed paths checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
