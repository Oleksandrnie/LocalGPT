#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

"$SCRIPT_DIR/tools/LTrnsrb.sh" --stop

if [[ -x "$SCRIPT_DIR/venv/bin/python" ]]; then
  exec "$SCRIPT_DIR/venv/bin/python" run_localgpt.py "$@"
fi

for candidate in python3.14 python3.13 python3.12 python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    exec "$candidate" run_localgpt.py "$@"
  fi
done

echo "Python 3.11+ is not installed or not available in PATH."
exit 1
