#!/bin/zsh
set -euo pipefail

PROJECT_ROOT="/Users/oleksandrniemchenko/my_personal_files/LocalGPT"
if [[ ! -f "${PROJECT_ROOT}/run_localgpt.py" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if [[ ! -f "${PROJECT_ROOT}/run_localgpt.py" ]]; then
  osascript -e 'display alert "LTrnsrb" message "run_localgpt.py was not found. Check project path."'
  exit 1
fi

LOG_DIR="/tmp/LTrnsrb"
mkdir -p "${LOG_DIR}"
BACKEND_LOG="${LOG_DIR}/backend.log"
CADDY_LOG="${LOG_DIR}/caddy.log"

resolve_caddy() {
  local detected
  detected="$(command -v caddy 2>/dev/null || true)"
  if [[ -n "${detected}" ]]; then
    echo "${detected}"
    return
  fi
  if [[ -x "/opt/homebrew/bin/caddy" ]]; then
    echo "/opt/homebrew/bin/caddy"
    return
  fi
  if [[ -x "/usr/local/bin/caddy" ]]; then
    echo "/usr/local/bin/caddy"
    return
  fi
  echo ""
}

is_backend_running() {
  /usr/bin/pgrep -f "uvicorn app.server:app --host 127.0.0.1 --port 8000" >/dev/null 2>&1
}

is_caddy_running() {
  /usr/bin/pgrep -f "caddy run --config Caddyfile.lan" >/dev/null 2>&1
}

if ! is_backend_running; then
  (
    cd "${PROJECT_ROOT}"
    nohup python3 run_localgpt.py >>"${BACKEND_LOG}" 2>&1 &
  )
fi

CADDY_BIN="$(resolve_caddy)"
if [[ -z "${CADDY_BIN}" ]]; then
  osascript -e 'display alert "LTrnsrb" message "Caddy was not found. Install: brew install caddy"'
  exit 1
fi

if ! is_caddy_running; then
  (
    cd "${PROJECT_ROOT}"
    nohup "${CADDY_BIN}" run --config Caddyfile.lan >>"${CADDY_LOG}" 2>&1 &
  )
fi

sleep 1

IFACE="$(route get default 2>/dev/null | awk '/interface:/{print $2}' | head -n 1)"
LAN_IP=""
if [[ -n "${IFACE}" ]]; then
  LAN_IP="$(ipconfig getifaddr "${IFACE}" 2>/dev/null || true)"
fi

if [[ -n "${LAN_IP}" ]]; then
  open "https://${LAN_IP}:8443/ui/gui_html.html"
else
  open "http://127.0.0.1:8000/ui/gui_html.html"
fi
