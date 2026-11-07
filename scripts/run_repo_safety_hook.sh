#!/usr/bin/env sh
# Shared fail-closed runner for the tracked pre-commit and pre-push hooks.
set -u

WHEN=${1:-}
case "$WHEN" in
  commit|push) ;;
  *) echo "[repo-safety] unsupported hook action: $WHEN" >&2; exit 2 ;;
esac

HOOK_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$HOOK_DIR/.." && pwd)
cd "$ROOT"

# GitHub Desktop and other GUI clients may start Git with a reduced PATH.
# Add the local safety environment and common binary locations first.
PATH="$ROOT/.repo-safety-venv/bin:$ROOT/.repo-safety-venv/Scripts:$PATH"
case "$(uname -s 2>/dev/null || true)" in
  Darwin)
    PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/local/sbin:$PATH"
    LOGIN_SHELL=${SHELL:-/bin/zsh}
    ;;
  Linux*)
    PATH="${HOME:-}/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
    LOGIN_SHELL=${SHELL:-/bin/bash}
    ;;
  *)
    LOGIN_SHELL=${SHELL:-}
    ;;
esac

# Pick up user-installed scanner paths from the login environment when a GUI
# process did not inherit them. Ignore shell startup output and retain the
# original PATH if the shell cannot be queried.
if [ -n "$LOGIN_SHELL" ] && [ -x "$LOGIN_SHELL" ]; then
  LOGIN_PATH=$("$LOGIN_SHELL" -lc 'printf "%s\n" "$PATH"' 2>/dev/null | tail -n 1 || true)
  if [ -n "$LOGIN_PATH" ]; then
    PATH="$LOGIN_PATH:$PATH"
  fi
fi
export PATH

PYTHON=
if [ -x "$ROOT/.repo-safety-venv/Scripts/python.exe" ]; then
  PYTHON="$ROOT/.repo-safety-venv/Scripts/python.exe"
elif [ -x "$ROOT/.repo-safety-venv/bin/python" ]; then
  PYTHON="$ROOT/.repo-safety-venv/bin/python"
fi

if [ -z "$PYTHON" ]; then
  echo "[repo-safety] local safety environment is missing; run python scripts/setup_repo_safety.py" >&2
  exit 1
fi
if ! "$PYTHON" -c 'import ai_repo_safety.gate' >/dev/null 2>&1; then
  echo "[repo-safety] safety package is missing from the local environment; rerun python scripts/setup_repo_safety.py" >&2
  exit 1
fi

if [ "$WHEN" = commit ]; then
  "$PYTHON" scripts/check_commit_data.py --staged || exit $?
  exec "$PYTHON" -m ai_repo_safety gate --when commit --target "$ROOT"
fi

BASE=${LOCALGPT_SAFETY_BASE:-origin/dev}
"$PYTHON" scripts/check_commit_data.py --range "$BASE" || exit $?
gitleaks git . --log-opts="$BASE..HEAD" --redact || exit $?
exec "$PYTHON" -m ai_repo_safety gate --when push --target "$ROOT"
