#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT_DEFAULT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="${LOCALGPT_PROJECT_ROOT:-${PROJECT_ROOT_DEFAULT}}"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

if [[ ! -f "${PROJECT_ROOT}/run_localgpt.py" ]]; then
  osascript -e 'display alert "LocalGPT" message "run_localgpt.py was not found. Check project path."'
  exit 1
fi

RUNTIME_BASE="${TMPDIR:-/tmp}"
RUNTIME_BASE="${RUNTIME_BASE%/}"
LOG_DIR="${RUNTIME_BASE}/LocalGPT-${UID}"
mkdir -p "${LOG_DIR}"

DOTENV_FILE="${PROJECT_ROOT}/.env"
BACKEND_LOG="${LOG_DIR}/backend.log"
CADDY_LOG="${LOG_DIR}/caddy.log"
BACKEND_PID_FILE="${LOG_DIR}/backend.pid"
CADDY_PID_FILE="${LOG_DIR}/caddy.pid"
BACKEND_PORT_FILE="${LOG_DIR}/backend.port"
CADDY_CONFIG_FILE="${LOG_DIR}/Caddyfile.auto"
LAN_IP_FILE="${LOG_DIR}/lan_ip"
CADDY_CONFIG_CHANGED=0
LAUNCH_AGENT_LABEL="local.localgpt.caddy"
LAUNCH_AGENT_FILE="${HOME}/Library/LaunchAgents/${LAUNCH_AGENT_LABEL}.plist"

BOOTSTRAP_PYTHON="$(command -v python3 2>/dev/null || true)"

read_dotenv_value() {
  local key="$1"
  [[ -f "${DOTENV_FILE}" ]] || {
    echo ""
    return
  }
  /usr/bin/awk -v wanted="${key}" '
    /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
    {
      line = $0
      sub(/^[[:space:]]*/, "", line)
      split(line, parts, "=")
      key = parts[1]
      sub(/[[:space:]]*$/, "", key)
      if (key != wanted) next
      value = line
      sub(/^[^=]*=/, "", value)
      sub(/^[[:space:]]*/, "", value)
      sub(/[[:space:]]*$/, "", value)
      if ((substr(value, 1, 1) == "\"" && substr(value, length(value), 1) == "\"") ||
          (substr(value, 1, 1) == "'"'"'" && substr(value, length(value), 1) == "'"'"'")) {
        value = substr(value, 2, length(value) - 2)
      }
      print value
    }
  ' "${DOTENV_FILE}" | tail -n 1
}

resolve_setting() {
  local key="$1"
  local fallback="${2:-}"
  local value="${(P)key:-}"
  if [[ -n "${value}" ]]; then
    echo "${value}"
    return
  fi
  value="$(read_dotenv_value "${key}")"
  if [[ -n "${value}" ]]; then
    echo "${value}"
    return
  fi
  echo "${fallback}"
}

normalize_port() {
  local value="$1"
  local fallback="$2"
  local label="$3"
  if [[ "${value}" =~ '^[0-9]+$' ]] && (( value > 0 && value < 65536 )); then
    echo "${value}"
    return
  fi
  echo "[!] Invalid ${label} port '${value}', using ${fallback}." >&2
  echo "${fallback}"
}

BACKEND_PORT="$(resolve_setting LOCALGPT_PORT "")"
if [[ -z "${BACKEND_PORT}" ]]; then
  BACKEND_PORT="$(resolve_setting LOCALGPT_BACKEND_PORT "8000")"
fi
HTTPS_PORT="$(resolve_setting LOCALGPT_LAN_HTTPS_PORT "")"
if [[ -z "${HTTPS_PORT}" ]]; then
  HTTPS_PORT="$(resolve_setting LAN_HTTPS_PORT "8443")"
fi
BACKEND_PORT="$(normalize_port "${BACKEND_PORT}" "8000" "backend")"
HTTPS_PORT="$(normalize_port "${HTTPS_PORT}" "8443" "LAN HTTPS")"
BACKEND_HEALTH_URL="http://127.0.0.1:${BACKEND_PORT}/health"

is_pid_alive() {
  local pid="$1"
  [[ -n "${pid}" ]] || return 1
  /bin/kill -0 "${pid}" >/dev/null 2>&1
}

cleanup_stale_pidfile() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 0
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  if ! is_pid_alive "${pid}"; then
    rm -f "${pid_file}"
  fi
}

if [[ "${LOCALGPT_LAUNCHER_LIBRARY_ONLY:-0}" != "1" ]]; then
  cleanup_stale_pidfile "${BACKEND_PID_FILE}"
  cleanup_stale_pidfile "${CADDY_PID_FILE}"
fi

read_pid_file() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || {
    echo ""
    return
  }
  cat "${pid_file}" 2>/dev/null || true
}

read_backend_port_file() {
  local port=""
  [[ -f "${BACKEND_PORT_FILE}" ]] || {
    echo ""
    return
  }
  port="$(cat "${BACKEND_PORT_FILE}" 2>/dev/null | tr -cd '0-9' || true)"
  echo "${port}"
}

set_backend_port() {
  local port="$1"
  [[ -n "${port}" ]] || return
  BACKEND_PORT="${port}"
  BACKEND_HEALTH_URL="http://127.0.0.1:${BACKEND_PORT}/health"
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

  local hosts="https://${lan_ip}:${HTTPS_PORT}"
  if [[ -n "${host_label}" ]]; then
    hosts="${hosts}, https://${host_label}.local:${HTTPS_PORT}"
  fi
  echo "${hosts}"
}

build_caddy_upstreams() {
  local preferred_port="${BACKEND_PORT:-8000}"
  echo "127.0.0.1:${preferred_port}"
}

write_caddy_config() {
  local lan_ip="$1"
  local hosts=""
  local upstreams=""
  local next_config="${CADDY_CONFIG_FILE}.next"
  hosts="$(build_caddy_hosts "${lan_ip}")"
  upstreams="$(build_caddy_upstreams)"
  cat > "${next_config}" <<EOF
{
  admin off
  auto_https disable_redirects
}
${hosts} {
  bind ${lan_ip}
  tls internal
  reverse_proxy ${upstreams} {
    lb_try_duration 5s
    lb_try_interval 250ms
    flush_interval -1
  }
}
EOF
  if [[ -f "${CADDY_CONFIG_FILE}" ]] && cmp -s "${next_config}" "${CADDY_CONFIG_FILE}"; then
    rm -f "${next_config}"
    CADDY_CONFIG_CHANGED=0
    return
  fi
  mv "${next_config}" "${CADDY_CONFIG_FILE}"
  CADDY_CONFIG_CHANGED=1
}

stop_caddy_launch_agent() {
  if [[ -x "/bin/launchctl" ]]; then
    /bin/launchctl bootout "gui/${UID}/${LAUNCH_AGENT_LABEL}" >/dev/null 2>&1 || true
    /bin/launchctl bootout "gui/${UID}" "${LAUNCH_AGENT_FILE}" >/dev/null 2>&1 || true
  fi
}

stop_pid_file_process() {
  local pid_file="$1"
  local pid=""
  pid="$(read_pid_file "${pid_file}")"
  [[ -n "${pid}" ]] || return 0
  if ! is_pid_alive "${pid}"; then
    rm -f "${pid_file}"
    return 0
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

caddy_listener_on_https_port() {
  local pid=""
  for pid in $(listeners_on_port "${HTTPS_PORT}"); do
    local command=""
    command="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
    if [[ "${command}" == *"caddy"* ]]; then
      echo "${pid}"
      return 0
    fi
  done
  return 1
}

stop_caddy_listener_on_https_port() {
  local pid=""
  for pid in $(listeners_on_port "${HTTPS_PORT}"); do
    local command=""
    command="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
    if [[ "${command}" == *"caddy"* ]]; then
      /bin/kill "${pid}" >/dev/null 2>&1 || true
    fi
  done
}

write_caddy_launch_agent() {
  mkdir -p "$(dirname "${LAUNCH_AGENT_FILE}")"
  LOCALGPT_LAUNCH_AGENT_LABEL="${LAUNCH_AGENT_LABEL}" \
  LOCALGPT_LAUNCH_AGENT_FILE="${LAUNCH_AGENT_FILE}" \
  LOCALGPT_CADDY_BIN="${CADDY_BIN}" \
  LOCALGPT_CADDY_CONFIG_FILE="${CADDY_CONFIG_FILE}" \
  LOCALGPT_CADDY_WORKING_DIR="${LOG_DIR}" \
  LOCALGPT_CADDY_LOG="${CADDY_LOG}" \
  LOCALGPT_PATH="${PATH}" \
  "${BOOTSTRAP_PYTHON}" - <<'PY'
import os
import plistlib

plist = {
    "Label": os.environ["LOCALGPT_LAUNCH_AGENT_LABEL"],
    "ProgramArguments": [
        os.environ["LOCALGPT_CADDY_BIN"],
        "run",
        "--config",
        os.environ["LOCALGPT_CADDY_CONFIG_FILE"],
    ],
    "WorkingDirectory": os.environ["LOCALGPT_CADDY_WORKING_DIR"],
    "RunAtLoad": True,
    "KeepAlive": False,
    "StandardOutPath": os.environ["LOCALGPT_CADDY_LOG"],
    "StandardErrorPath": os.environ["LOCALGPT_CADDY_LOG"],
    "EnvironmentVariables": {
        "HOME": os.path.expanduser("~"),
        "PATH": os.environ["LOCALGPT_PATH"],
    },
}

with open(os.environ["LOCALGPT_LAUNCH_AGENT_FILE"], "wb") as handle:
    plistlib.dump(plist, handle)
PY
}

start_caddy_launch_agent() {
  [[ -x "/bin/launchctl" ]] || return 1
  write_caddy_launch_agent
  stop_caddy_launch_agent
  if ! /bin/launchctl bootstrap "gui/${UID}" "${LAUNCH_AGENT_FILE}" >>"${CADDY_LOG}" 2>&1; then
    return 1
  fi
  /bin/launchctl kickstart -k "gui/${UID}/${LAUNCH_AGENT_LABEL}" >>"${CADDY_LOG}" 2>&1 || true
  return 0
}

health_ok_http() {
  local url="$1"
  curl -fsS --max-time 2 "${url}" >/dev/null 2>&1
}

health_ok_localgpt_port() {
  local port="$1"
  curl -fsS --max-time 2 "http://127.0.0.1:${port}/health" 2>/dev/null | grep -q '"status":"ok"'
}

discover_existing_backend_port() {
  local start="${BACKEND_PORT:-8000}"
  local end=$((start + 99))
  local port="${start}"
  while (( port <= end )); do
    if health_ok_localgpt_port "${port}"; then
      echo "${port}"
      return 0
    fi
    port=$((port + 1))
  done

  port=8000
  while (( port <= 8099 )); do
    if health_ok_localgpt_port "${port}"; then
      echo "${port}"
      return 0
    fi
    port=$((port + 1))
  done

  return 1
}

health_ok_https_insecure() {
  local url="$1"
  curl -kfsS --max-time 3 "${url}" >/dev/null 2>&1
}

open_url() {
  local url="$1"
  if [[ "${LOCALGPT_NO_BROWSER:-0}" == "1" ]]; then
    echo "[i] Browser opening disabled: ${url}"
    return 0
  fi
  open "${url}"
}

wait_for_backend_ready() {
  local url="$1"
  local pid="$2"
  local retries="${3:-80}"
  local delay="${4:-0.5}"
  local i=0
  while [[ "${i}" -lt "${retries}" ]]; do
    if health_ok_http "${url}"; then
      return 0
    fi
    if ! is_pid_alive "${pid}"; then
      return 1
    fi
    sleep "${delay}"
    i=$((i + 1))
  done
  return 1
}

wait_for_https_health() {
  local url="$1"
  local retries="${2:-60}"
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
  local existing_port=""
  existing_port="$(read_backend_port_file)"
  if [[ -n "${existing_port}" ]]; then
    set_backend_port "${existing_port}"
  fi

  if [[ -n "${backend_pid}" ]] && is_pid_alive "${backend_pid}" && health_ok_http "${BACKEND_HEALTH_URL}"; then
    return 0
  fi

  if [[ -z "${backend_pid}" ]] && health_ok_http "${BACKEND_HEALTH_URL}"; then
    echo "${BACKEND_PORT}" > "${BACKEND_PORT_FILE}"
    echo "[i] Reusing existing LocalGPT backend: ${BACKEND_HEALTH_URL}"
    return 0
  fi

  local discovered_port=""
  discovered_port="$(discover_existing_backend_port || true)"
  if [[ -n "${discovered_port}" ]]; then
    set_backend_port "${discovered_port}"
    echo "${BACKEND_PORT}" > "${BACKEND_PORT_FILE}"
    echo "[i] Reusing existing LocalGPT backend: ${BACKEND_HEALTH_URL}"
    return 0
  fi

  if [[ -n "${backend_pid}" ]] && is_pid_alive "${backend_pid}"; then
    stop_pid_file_process "${BACKEND_PID_FILE}"
  fi

  rm -f "${BACKEND_PORT_FILE}"

  (
    cd "${PROJECT_ROOT}"
    export LOCALGPT_RUNTIME_DIR="${LOG_DIR}"
    export PYTHONPATH="${PROJECT_ROOT}"
    nohup "${BOOTSTRAP_PYTHON}" run_localgpt.py --no-browser --no-reload --exec-backend --host 127.0.0.1 --port "${BACKEND_PORT}" --port-file "${BACKEND_PORT_FILE}" >>"${BACKEND_LOG}" 2>&1 &
    echo "$!" > "${BACKEND_PID_FILE}"
  )

  backend_pid="$(read_pid_file "${BACKEND_PID_FILE}")"
  for _ in {1..120}; do
    existing_port="$(read_backend_port_file)"
    if [[ -n "${existing_port}" ]]; then
      set_backend_port "${existing_port}"
      break
    fi
    if ! is_pid_alive "${backend_pid}"; then
      break
    fi
    sleep 0.25
  done

  if ! wait_for_backend_ready "${BACKEND_HEALTH_URL}" "${backend_pid}" 240 0.5; then
    osascript -e "display alert \"LocalGPT\" message \"Backend did not start. Check ${BACKEND_LOG}\""
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

start_or_restart_caddy() {
  local lan_ip="$1"
  local https_health_url="https://${lan_ip}:${HTTPS_PORT}/health"
  local caddy_pid=""
  caddy_pid="$(read_pid_file "${CADDY_PID_FILE}")"

  if [[ "${CADDY_CONFIG_CHANGED}" != "1" ]] && [[ -n "${caddy_pid}" ]] && is_pid_alive "${caddy_pid}" && health_ok_https_insecure "${https_health_url}"; then
    return 0
  fi

  if [[ -z "${caddy_pid}" ]] && health_ok_https_insecure "${https_health_url}"; then
    caddy_pid="$(caddy_listener_on_https_port || true)"
    if [[ -n "${caddy_pid}" ]]; then
      echo "${caddy_pid}" > "${CADDY_PID_FILE}"
    fi
    return 0
  fi

  if [[ -n "${caddy_pid}" ]] && is_pid_alive "${caddy_pid}"; then
    stop_caddy_launch_agent
    stop_pid_file_process "${CADDY_PID_FILE}"
  fi

  stop_caddy_launch_agent
  stop_caddy_listener_on_https_port
  rm -f "${CADDY_PID_FILE}"

  if ! start_caddy_launch_agent; then
    (
      cd "${PROJECT_ROOT}"
      "${CADDY_BIN}" start --config "${CADDY_CONFIG_FILE}" >>"${CADDY_LOG}" 2>&1
    )
  fi

  if ! wait_for_https_health "${https_health_url}" 80 0.25; then
    osascript -e "display alert \"LocalGPT\" message \"Caddy did not start HTTPS correctly. Check ${CADDY_LOG}\""
    return 1
  fi
  caddy_pid="$(caddy_listener_on_https_port || true)"
  if [[ -n "${caddy_pid}" ]]; then
    echo "${caddy_pid}" > "${CADDY_PID_FILE}"
  fi
  return 0
}

if [[ "${LOCALGPT_LAUNCHER_LIBRARY_ONLY:-0}" == "1" ]]; then
  return 0 2>/dev/null || exit 0
fi

if [[ "${1:-}" == "--stop" ]]; then
  stop_caddy_launch_agent
  caddy_pid="$(read_pid_file "${CADDY_PID_FILE}")"
  if [[ -n "${caddy_pid}" ]]; then
    caddy_command="$(ps -p "${caddy_pid}" -o command= 2>/dev/null || true)"
    if [[ "${caddy_command}" == *"caddy"*"${CADDY_CONFIG_FILE}"* ]]; then
      stop_pid_file_process "${CADDY_PID_FILE}"
    else
      rm -f "${CADDY_PID_FILE}"
    fi
  fi
  echo "[i] LocalGPT LAN HTTPS listener stopped."
  exit 0
fi

if [[ -z "${BOOTSTRAP_PYTHON}" ]]; then
  osascript -e 'display alert "LocalGPT" message "Python 3 was not found."'
  exit 1
fi

start_backend || exit 1

CADDY_BIN="$(resolve_caddy)"
if [[ -z "${CADDY_BIN}" ]]; then
  message="Caddy was not found. LAN HTTPS is unavailable; opening LocalGPT on this Mac. Install it with: brew install caddy"
  echo "[!] ${message}" >&2
  osascript -e "display alert \"LocalGPT\" message \"${message}\""
  open_url "http://127.0.0.1:${BACKEND_PORT}/ui/gui_html.html"
  exit 0
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
  echo "${LAN_IP}" > "${LAN_IP_FILE}"
  echo "[i] LocalGPT LAN URL: https://${LAN_IP}:${HTTPS_PORT}/ui/gui_html.html"
  echo "[i] Backend remains local: http://127.0.0.1:${BACKEND_PORT}"
  open_url "https://${LAN_IP}:${HTTPS_PORT}/ui/gui_html.html"
else
  osascript -e 'display alert "LocalGPT" message "LAN IP was not detected. Opening localhost UI instead."'
  open_url "http://127.0.0.1:${BACKEND_PORT}/ui/gui_html.html"
fi
