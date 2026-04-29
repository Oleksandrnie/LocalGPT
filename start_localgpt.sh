#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if command -v python3 >/dev/null 2>&1; then
  exec python3 run_localgpt.py "$@"
fi

if command -v python >/dev/null 2>&1; then
  exec python run_localgpt.py "$@"
fi

echo "Python is not installed or not available in PATH." >&2
exit 1
