#!/usr/bin/env python3
"""Create a repo-local AI Repo Safety environment and activate tracked Git hooks."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".repo-safety-venv"
REQUIREMENTS = ROOT / "requirements-dev.txt"
HOOKS = ROOT / ".githooks"


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", subprocess.list2cmdline(command))
    return subprocess.run(command, cwd=ROOT, text=True, check=check)


def python_from_venv() -> Path:
    candidates = (VENV / "Scripts" / "python.exe", VENV / "bin" / "python")
    return next((path for path in candidates if path.is_file()), candidates[-1])


def interpreter_version(command: list[str]) -> tuple[int, int] | None:
    result = subprocess.run(
        command + ["-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        return None
    try:
        major, minor = result.stdout.strip().split(".", 1)
        return int(major), int(minor)
    except ValueError:
        return None


def find_python() -> list[str] | None:
    options = [[sys.executable]]
    for project_python in (ROOT / "venv" / "Scripts" / "python.exe", ROOT / "venv" / "bin" / "python"):
        if project_python.is_file():
            options.append([str(project_python)])
    if os.name == "nt":
        options.extend([["py", "-3.12"], ["py", "-3"], ["python3.12"], ["python3"], ["python"]])
    else:
        options.extend([["python3.12"], ["python3"], ["python"]])
    for option in options:
        executable = option[0] if len(option) == 1 else shutil.which(option[0])
        if executable:
            version = interpreter_version([executable, *option[1:]])
            if version is not None and version >= (3, 12):
                return [executable, *option[1:]]
    return None


def safety_python() -> Path:
    path = python_from_venv()
    if not path.is_file():
        raise RuntimeError("Safety environment is missing. Run `python scripts/setup_repo_safety.py`.")
    return path


def setup() -> int:
    if not (ROOT / ".git").exists():
        raise RuntimeError("Run this script from a Git checkout of LocalGPT.")
    if not HOOKS.is_dir() or not (HOOKS / "pre-commit").is_file() or not (HOOKS / "pre-push").is_file():
        raise RuntimeError("Tracked .githooks files are missing; restore them from the repository before setup.")

    python = python_from_venv()
    if not python.is_file():
        creator = find_python()
        if creator is None:
            raise RuntimeError("Python 3.12+ is required. Install it and rerun this script.")
        run(creator + ["-m", "venv", str(VENV)])
        python = python_from_venv()
    version = interpreter_version([str(python)])
    if version is None or version < (3, 12):
        raise RuntimeError(f"The existing safety environment uses Python {version}; recreate it with Python 3.12+.")

    run([str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    configured_hooks = subprocess.run(
        ["git", "config", "--local", "--get", "core.hooksPath"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    existing_hooks_path = configured_hooks.stdout.strip()
    if existing_hooks_path and existing_hooks_path != ".githooks":
        raise RuntimeError(
            f"A different local core.hooksPath is already configured ({existing_hooks_path}); "
            "review it and change it to .githooks before rerunning setup."
        )
    run(["git", "config", "--local", "core.hooksPath", ".githooks"])

    missing = [name for name in ("gitleaks", "trufflehog") if shutil.which(name) is None]
    if missing:
        print("Setup complete, but required scanners are not on the current PATH:", ", ".join(missing), file=sys.stderr)
        print("Install them using docs/repo-safety.md before committing or pushing; hooks will refuse while missing.", file=sys.stderr)
    print(f"Safety environment ready: {python}")
    print("Tracked fail-closed hooks enabled at .githooks (repository-local Git config).")
    return 0


def gate(when: str) -> int:
    python = safety_python()
    return run([str(python), "-m", "ai_repo_safety", "gate", "--when", when, "--target", str(ROOT)], check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("install", help="create the local environment and enable hooks")
    gate_parser = subparsers.add_parser("gate", help="run an AI Repo Safety gate from the local environment")
    gate_parser.add_argument("--when", choices=("commit", "push", "tag", "auto"), required=True)
    args = parser.parse_args()
    try:
        if args.command == "install":
            return setup()
        return gate(args.when)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"[repo-safety] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
