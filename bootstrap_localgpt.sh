#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if [ "$(uname -s)" = "Linux" ] && [ ! -t 0 ] && [ "${LOCALGPT_BOOTSTRAP_TERMINAL:-0}" != "1" ]; then
  for terminal in x-terminal-emulator gnome-terminal konsole xterm; do
    if command -v "$terminal" >/dev/null 2>&1; then
      case "$terminal" in
        gnome-terminal) exec "$terminal" -- env LOCALGPT_BOOTSTRAP_TERMINAL=1 "$SCRIPT_DIR/bootstrap_localgpt.sh" "$@" ;;
        konsole) exec "$terminal" -e env LOCALGPT_BOOTSTRAP_TERMINAL=1 "$SCRIPT_DIR/bootstrap_localgpt.sh" "$@" ;;
        *) exec "$terminal" -e env LOCALGPT_BOOTSTRAP_TERMINAL=1 "$SCRIPT_DIR/bootstrap_localgpt.sh" "$@" ;;
      esac
    fi
  done
fi

find_python() {
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

run_as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo 'Administrative privileges are required, but sudo is missing.'
    exit 1
  fi
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
      if command -v apt-get >/dev/null 2>&1; then run_as_root apt-get update && run_as_root apt-get install -y python3 python3-venv python3-pip
      elif command -v dnf >/dev/null 2>&1; then run_as_root dnf install -y python3 python3-pip
      elif command -v pacman >/dev/null 2>&1; then run_as_root pacman -S --needed --noconfirm python python-pip
      elif command -v zypper >/dev/null 2>&1; then run_as_root zypper --non-interactive install python3 python3-pip python3-venv
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
