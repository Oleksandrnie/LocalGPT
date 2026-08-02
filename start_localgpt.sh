#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

# On macOS, the ordinary no-argument launcher also provides private LAN HTTPS
# through Caddy. Explicit arguments keep the direct backend launcher behavior.
if [ "$(uname -s)" = "Darwin" ] && [ "$#" -eq 0 ]; then
  exec /bin/zsh "$SCRIPT_DIR/tools/LTrnsrb.sh"
fi

if [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
  exec "$SCRIPT_DIR/venv/bin/python" run_localgpt.py "$@"
fi

for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    exec "$candidate" run_localgpt.py "$@"
  fi
done

echo "Python 3.10+ is not installed or not available in PATH." >&2
exit 1
