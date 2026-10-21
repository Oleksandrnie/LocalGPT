from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, check=check, capture_output=True)


def collect_python_files(root: Path, env: dict[str, str] | None = None) -> tuple[list[str], bool]:
    env = env or os.environ
    candidates = [env.get("PR_BASE_SHA", ""), env.get("PUSH_BASE_SHA", "")]
    default_branch = env.get("DEFAULT_BRANCH", "")
    if default_branch:
        candidates.append(f"origin/{default_branch}")

    base = None
    for candidate in candidates:
        if not candidate or set(candidate) == {"0"}:
            continue
        if _git(root, "rev-parse", "--verify", candidate, check=False).returncode == 0:
            base = candidate
            break

    head = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
    full_scan = base is None
    if base is not None:
        base_sha = _git(root, "rev-parse", "--verify", base).stdout.decode().strip()
        merge_base = _git(root, "merge-base", base, "HEAD", check=False)
        full_scan = base_sha == head or merge_base.returncode != 0

    if full_scan:
        raw_paths = _git(root, "ls-files", "-z", "--", "*.py").stdout
    else:
        raw_paths = _git(
            root, "diff", "--name-only", "-z", "--diff-filter=ACMRT", f"{base}...HEAD"
        ).stdout
    paths = [path for path in raw_paths.decode().split("\0") if path and path.endswith(".py")]
    return [path for path in paths if (root / path).is_file()], full_scan


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python_files, full_scan = collect_python_files(root)
    if full_scan:
        print(f"Scanning all tracked Python files ({len(python_files)} files).")
    elif python_files:
        print(f"Scanning changed Python files ({len(python_files)} files).")
    else:
        print("No changed Python files to lint.")
        return 0

    if not python_files:
        return 0

    tools = Path(sys.executable).parent
    subprocess.run(
        [str(tools / "ruff"), "check", "--select", "E4,E7,E9,F", *python_files],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [str(tools / "bandit"), "-q", "-ll", "-iii", *python_files],
        cwd=root,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
