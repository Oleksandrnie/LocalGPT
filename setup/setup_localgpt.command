#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

set +e
/bin/sh "$SCRIPT_DIR/setup_localgpt.sh" "$@"
setup_exit=$?
set -e
echo
read "?Press Enter to close Terminal..."
exit $setup_exit
