#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

set +e
/bin/sh "$SCRIPT_DIR/setup_localgpt.sh" "$@"
status=$?
set -e
echo
read "?Press Enter to close Terminal..."
exit $status
