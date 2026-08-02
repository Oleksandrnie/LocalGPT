#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

find_python() {
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN=$(find_python || true)
if [ -z "$PYTHON_BIN" ]; then
  printf 'Python 3.10+ is missing. Install it now? [Y/n] '
  read -r answer
  case "$answer" in n|N|no|NO) echo 'Bootstrap cancelled.'; exit 1 ;; esac

  case "$(uname -s)" in
    Darwin)
      if ! command -v brew >/dev/null 2>&1; then
        printf 'Homebrew is missing. Install it from the official installer? [Y/n] '
        read -r answer
        case "$answer" in n|N|no|NO) echo 'Homebrew is required to continue.'; exit 1 ;; esac
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"; fi
        if [ -x /usr/local/bin/brew ]; then eval "$(/usr/local/bin/brew shellenv)"; fi
      fi
      brew install python
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
      elif command -v dnf >/dev/null 2>&1; then sudo dnf install -y python3 python3-pip
      elif command -v pacman >/dev/null 2>&1; then sudo pacman -S --needed --noconfirm python python-pip
      elif command -v zypper >/dev/null 2>&1; then sudo zypper --non-interactive install python3 python3-pip python3-venv
      else echo 'No supported package manager found.'; exit 1
      fi
      ;;
    *) echo 'Unsupported operating system for this launcher.'; exit 1 ;;
  esac
  PYTHON_BIN=$(find_python || true)
fi

if [ -z "$PYTHON_BIN" ]; then
  echo 'Python 3.10+ is still unavailable. Reopen the terminal and rerun bootstrap.'
  exit 1
fi

exec "$PYTHON_BIN" tools/bootstrap_localgpt.py "$@"
