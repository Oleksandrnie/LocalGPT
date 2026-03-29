#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT_DEFAULT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="${LTRNSRB_PROJECT_ROOT:-${PROJECT_ROOT_DEFAULT}}"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if [[ ! -f "${PROJECT_ROOT}/run_localgpt.py" ]]; then
  osascript -e 'display alert "LTrnsrb" message "run_localgpt.py was not found. Check project path."'
  exit 1
fi

RUNTIME_BASE="${TMPDIR:-/tmp}"
RUNTIME_BASE="${RUNTIME_BASE%/}"
LOG_DIR="${RUNTIME_BASE}/LTrnsrb-${UID}"
mkdir -p "${LOG_DIR}"
BACKEND_LOG="${LOG_DIR}/backend.log"
CADDY_LOG="${LOG_DIR}/caddy.log"
BACKEND_PID_FILE="${LOG_DIR}/backend.pid"
CADDY_PID_FILE="${LOG_DIR}/caddy.pid"
CADDY_CONFIG_FILE="${LOG_DIR}/Caddyfile.auto"
LAN_IP_FILE="${LOG_DIR}/lan_ip"
BACKEND_PORT=8000
HTTPS_PORT=8443
BACKEND_HEALTH_URL="http://127.0.0.1:${BACKEND_PORT}/health"

BACKEND_PYTHON="${PROJECT_ROOT}/venv/bin/python"
if [[ ! -x "${BACKEND_PYTHON}" ]]; then
  BACKEND_PYTHON="$(command -v python3 2>/dev/null || true)"
fi
if [[ -z "${BACKEND_PYTHON}" ]]; then
  osascript -e 'display alert "LTrnsrb" message "Python 3 was not found."'
  exit 1
fi

is_pid_alive() {
  local pid="$1"
  if [[ -z "${pid}" ]]; then
    return 1
  fi
  /bin/kill -0 "${pid}" >/dev/null 2>&1
}

cleanup_stale_pidfile() {
  local pid_file="$1"
  if [[ ! -f "${pid_file}" ]]; then
    return
  fi
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  if ! is_pid_alive "${pid}"; then
    rm -f "${pid_file}"
  fi
}

cleanup_stale_pidfile "${BACKEND_PID_FILE}"
cleanup_stale_pidfile "${CADDY_PID_FILE}"

read_pid_file() {
  local pid_file="$1"
  if [[ ! -f "${pid_file}" ]]; then
    echo ""
    return
  fi
  cat "${pid_file}" 2>/dev/null || true
}

is_private_ipv4() {
  local ip="$1"
  case "${ip}" in
    10.*|192.168.*|172.1[6-9].*|172.2[0-9].*|172.3[0-1].*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

detect_wifi_interface() {
  /usr/sbin/networksetup -listallhardwareports 2>/dev/null | awk '
    $0 ~ /Hardware Port: Wi-Fi/ {want=1; next}
    want && $1 == "Device:" {print $2; exit}
  '
}

detect_lan_ip() {
  local ip=""
  local wifi_iface=""
  wifi_iface="$(detect_wifi_interface)"
  if [[ -n "${wifi_iface}" ]]; then
    ip="$(ipconfig getifaddr "${wifi_iface}" 2>/dev/null || true)"
    if [[ -n "${ip}" ]] && is_private_ipv4 "${ip}"; then
      echo "${ip}"
      return
    fi
  fi

  local iface=""
  for iface in en0 en1 en2; do
    ip="$(ipconfig getifaddr "${iface}" 2>/dev/null || true)"
    if [[ -n "${ip}" ]] && is_private_ipv4 "${ip}"; then
      echo "${ip}"
      return
    fi
  done

  local default_iface=""
  default_iface="$(route get default 2>/dev/null | awk '/interface:/{print $2}' | head -n 1)"
  if [[ -n "${default_iface}" ]]; then
    ip="$(ipconfig getifaddr "${default_iface}" 2>/dev/null || true)"
    if [[ -n "${ip}" ]] && is_private_ipv4 "${ip}"; then
      echo "${ip}"
      return
    fi
  fi

  echo ""
}

build_caddy_hosts() {
  local lan_ip="$1"
  local host_label=""
  host_label="$(scutil --get LocalHostName 2>/dev/null || true)"
  if [[ -z "${host_label}" ]]; then
    host_label="$(hostname -s 2>/dev/null || true)"
  fi
  host_label="$(echo "${host_label}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9.-')"

  local hosts="https://${lan_ip}:8443"
  if [[ -n "${host_label}" ]]; then
    hosts="${hosts}, https://${host_label}.local:8443"
  fi
  echo "${hosts}"
}

write_caddy_config() {
  local lan_ip="$1"
  local hosts=""
  hosts="$(build_caddy_hosts "${lan_ip}")"
  cat > "${CADDY_CONFIG_FILE}" <<EOF
{
  admin off
}
${hosts} {
  tls internal
  reverse_proxy 127.0.0.1:8000
}
EOF
}

stop_pid_file_process() {
  local pid_file="$1"
  local pid=""
  pid="$(read_pid_file "${pid_file}")"
  if [[ -z "${pid}" ]]; then
    return
  fi
  if ! is_pid_alive "${pid}"; then
    rm -f "${pid_file}"
    return
  fi
  /bin/kill "${pid}" >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ! is_pid_alive "${pid}"; then
      break
    fi
    sleep 0.2
  done
  if is_pid_alive "${pid}"; then
    /bin/kill -9 "${pid}" >/dev/null 2>&1 || true
  fi
  rm -f "${pid_file}"
}

listeners_on_port() {
  local port="$1"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null | sort -u
}

health_ok_http() {
  local url="$1"
  curl -fsS --max-time 2 "${url}" >/dev/null 2>&1
}

health_ok_https_insecure() {
  local url="$1"
  curl -kfsS --max-time 3 "${url}" >/dev/null 2>&1
}

wait_for_http_health() {
  local url="$1"
  local retries="${2:-40}"
  local delay="${3:-0.25}"
  local i=0
  while [[ "${i}" -lt "${retries}" ]]; do
    if health_ok_http "${url}"; then
      return 0
    fi
    sleep "${delay}"
    i=$((i + 1))
  done
  return 1
}

wait_for_https_health() {
  local url="$1"
  local retries="${2:-40}"
  local delay="${3:-0.25}"
  local i=0
  while [[ "${i}" -lt "${retries}" ]]; do
    if health_ok_https_insecure "${url}"; then
      return 0
    fi
    sleep "${delay}"
    i=$((i + 1))
  done
  return 1
}

start_backend() {
  local backend_pid=""
  backend_pid="$(read_pid_file "${BACKEND_PID_FILE}")"

  if [[ -n "${backend_pid}" ]] && is_pid_alive "${backend_pid}" && health_ok_http "${BACKEND_HEALTH_URL}"; then
    return 0
  fi

  if [[ -n "${backend_pid}" ]] && is_pid_alive "${backend_pid}"; then
    stop_pid_file_process "${BACKEND_PID_FILE}"
  fi

  if ! health_ok_http "${BACKEND_HEALTH_URL}"; then
    local pid
    for pid in $(listeners_on_port "${BACKEND_PORT}"); do
      /bin/kill "${pid}" >/dev/null 2>&1 || true
    done
    sleep 0.3
    for pid in $(listeners_on_port "${BACKEND_PORT}"); do
      /bin/kill -9 "${pid}" >/dev/null 2>&1 || true
    done
  fi

  (
    cd "${PROJECT_ROOT}"
    export LTRNSRB_RUNTIME_DIR="${LOG_DIR}"
    export PYTHONPATH="${PROJECT_ROOT}"
    nohup "${BACKEND_PYTHON}" -m uvicorn app.server:app --host 127.0.0.1 --port "${BACKEND_PORT}" --log-level info >>"${BACKEND_LOG}" 2>&1 &
    echo "$!" > "${BACKEND_PID_FILE}"
  )

  if ! wait_for_http_health "${BACKEND_HEALTH_URL}" 60 0.25; then
    osascript -e "display alert \"LTrnsrb\" message \"Backend did not start. Check ${BACKEND_LOG}\""
    return 1
  fi
  return 0
}

start_or_restart_caddy() {
  local lan_ip="$1"
  local https_health_url="https://${lan_ip}:${HTTPS_PORT}/health"
  local caddy_pid=""
  caddy_pid="$(read_pid_file "${CADDY_PID_FILE}")"

  if [[ -n "${caddy_pid}" ]] && is_pid_alive "${caddy_pid}" && health_ok_https_insecure "${https_health_url}"; then
    return 0
  fi

  if [[ -n "${caddy_pid}" ]] && is_pid_alive "${caddy_pid}"; then
    stop_pid_file_process "${CADDY_PID_FILE}"
  fi

  (
    cd "${PROJECT_ROOT}"
    nohup "${CADDY_BIN}" run --config "${CADDY_CONFIG_FILE}" >>"${CADDY_LOG}" 2>&1 &
    echo "$!" > "${CADDY_PID_FILE}"
  )

  if ! wait_for_https_health "${https_health_url}" 80 0.25; then
    osascript -e "display alert \"LTrnsrb\" message \"Caddy did not start HTTPS correctly. Check ${CADDY_LOG}\""
    return 1
  fi
  return 0
}

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

start_backend || exit 1

CADDY_BIN="$(resolve_caddy)"
if [[ -z "${CADDY_BIN}" ]]; then
  osascript -e 'display alert "LTrnsrb" message "Caddy was not found. Install: brew install caddy"'
  exit 1
fi

LAN_IP="$(detect_lan_ip)"
PREV_LAN_IP="$(cat "${LAN_IP_FILE}" 2>/dev/null || true)"

if [[ -n "${LAN_IP}" ]]; then
  write_caddy_config "${LAN_IP}"
fi

if [[ -f "${CADDY_PID_FILE}" ]] && [[ -n "${LAN_IP}" ]] && [[ "${PREV_LAN_IP}" != "${LAN_IP}" ]]; then
  stop_pid_file_process "${CADDY_PID_FILE}"
fi

if [[ -n "${LAN_IP}" ]]; then
  start_or_restart_caddy "${LAN_IP}" || exit 1
else
  osascript -e 'display alert "LTrnsrb" message "LAN IP was not detected. Open local UI on 127.0.0.1."'
fi

if [[ -n "${LAN_IP}" ]]; then
  echo "${LAN_IP}" > "${LAN_IP_FILE}"
fi

if [[ -n "${LAN_IP}" ]]; then
  open "https://${LAN_IP}:8443/ui/gui_html.html"
else
  open "http://127.0.0.1:8000/ui/gui_html.html"
fi
