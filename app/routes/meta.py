from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi import Request

from .. import chat_tasks, config, db
from ..schemas import DatabaseCleanupRequest, DatabaseResetRequest
from .. import transcribe_tasks
from ..services import tts_service
from backend.apps.rag import service as rag_service

router = APIRouter()
_USER_ID = os.getuid() if hasattr(os, "getuid") else 0
_DEFAULT_RUNTIME_DIR = Path(tempfile.gettempdir()) / f"LocalGPT-{_USER_ID}"
RUNTIME_DIR = Path(os.getenv("LOCALGPT_RUNTIME_DIR", str(_DEFAULT_RUNTIME_DIR)))
BACKEND_PID_FILE = RUNTIME_DIR / "backend.pid"
CADDY_PID_FILE = RUNTIME_DIR / "caddy.pid"
CADDY_LAUNCH_AGENT_LABEL = "local.localgpt.caddy"


def _is_private_lan_ipv4(value: str | None) -> bool:
    ip = (value or "").strip()
    if not ip:
        return False
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        octets = [int(part) for part in parts]
    except ValueError:
        return False
    if any(part < 0 or part > 255 for part in octets):
        return False
    return (
        octets[0] == 10
        or (octets[0] == 192 and octets[1] == 168)
        or (octets[0] == 172 and 16 <= octets[1] <= 31)
    )


def _command_output(args: list[str]) -> str:
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def _detect_wifi_interface() -> str | None:
    output = _command_output(["/usr/sbin/networksetup", "-listallhardwareports"])
    want_wifi = False
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line == "Hardware Port: Wi-Fi":
            want_wifi = True
            continue
        if want_wifi and line.startswith("Device:"):
            return line.split(":", 1)[1].strip() or None
    return None


def _ipconfig_addr(interface: str | None) -> str | None:
    if not interface:
        return None
    value = _command_output(["/usr/sbin/ipconfig", "getifaddr", interface])
    return value if _is_private_lan_ipv4(value) else None


def _detect_lan_ip() -> str | None:
    for interface in [_detect_wifi_interface(), "en0", "en1", "en2"]:
        lan_ip = _ipconfig_addr(interface)
        if lan_ip:
            return lan_ip

    default_route = _command_output(["/sbin/route", "get", "default"])
    default_interface = ""
    for raw_line in default_route.splitlines():
        line = raw_line.strip()
        if line.startswith("interface:"):
            default_interface = line.split(":", 1)[1].strip()
            break
    lan_ip = _ipconfig_addr(default_interface)
    if lan_ip:
        return lan_ip

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("1.1.1.1", 80))
            lan_ip = sock.getsockname()[0]
    except OSError:
        return None

    if not _is_private_lan_ipv4(lan_ip):
        return None
    return lan_ip


def _get_access_url(request: Request) -> str | None:
    host = (request.headers.get("host") or "").strip()
    if host:
        return f"{request.url.scheme}://{host}/ui/gui_html.html"
    return None


def _is_tcp_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def _lan_https_port() -> str:
    port = (os.getenv("LAN_HTTPS_PORT", "") or "").strip()
    if not port:
        port = (os.getenv("IOS_HTTPS_PORT", "8443") or "").strip()
    return port or "8443"


def _get_lan_url(request: Request) -> str | None:
    explicit = (os.getenv("LAN_ACCESS_URL", "") or "").strip()
    if not explicit:
        explicit = (os.getenv("IOS_ACCESS_URL", "") or "").strip()
    if explicit:
        return explicit

    host = (request.headers.get("host") or "").strip()
    if host and not host.startswith(("127.0.0.1", "localhost", "[::1]")):
        return f"https://{host}/ui/gui_html.html"

    lan_ip = _detect_lan_ip()
    if not lan_ip:
        return None

    port = _lan_https_port()
    try:
        port_int = int(port)
    except ValueError:
        return None
    if not _is_tcp_port_open(lan_ip, port_int):
        return None
    return f"https://{lan_ip}:{port}/ui/gui_html.html"


def get_network_address_items(request: Request) -> list[dict[str, object]]:
    lan_url = _get_lan_url(request)
    if not lan_url:
        return []
    return [
        {
            "id": "lan",
            "provider_id": "lan",
            "label": "LAN",
            "url": lan_url,
            "detail": "LAN HTTPS через Caddy.",
            "trusted": True,
            "copyable": True,
            "priority": 10,
            "security_note": "Доступен только когда LAN HTTPS listener реально отвечает.",
        }
    ]


def _read_pid(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        pid = int(raw)
    except ValueError:
        return None
    return pid if pid > 1 else None


def _terminate_pid(pid: int) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return False


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _stop_caddy_launch_agent() -> None:
    if sys.platform != "darwin" or not hasattr(os, "getuid"):
        return
    uid = os.getuid()
    launch_agent_file = Path.home() / "Library" / "LaunchAgents" / f"{CADDY_LAUNCH_AGENT_LABEL}.plist"
    commands = [
        ["/bin/launchctl", "bootout", f"gui/{uid}/{CADDY_LAUNCH_AGENT_LABEL}"],
        ["/bin/launchctl", "bootout", f"gui/{uid}", str(launch_agent_file)],
    ]
    for command in commands:
        try:
            subprocess.run(command, check=False, capture_output=True, timeout=2)
        except (OSError, subprocess.SubprocessError):
            continue


def _shutdown_worker() -> None:
    time.sleep(0.45)

    chat_tasks.cancel_all_tasks()
    transcribe_tasks.cancel_all_tasks()
    tts_service.cancel_all_tasks()

    _stop_caddy_launch_agent()

    caddy_pid = _read_pid(CADDY_PID_FILE)
    if caddy_pid:
        _terminate_pid(caddy_pid)
    _safe_unlink(CADDY_PID_FILE)

    backend_pid = _read_pid(BACKEND_PID_FILE)
    if backend_pid:
        _terminate_pid(backend_pid)
    _safe_unlink(BACKEND_PID_FILE)

    time.sleep(0.35)
    _terminate_pid(os.getpid())


def _restart_backend_worker() -> None:
    time.sleep(0.45)

    chat_tasks.cancel_all_tasks()
    transcribe_tasks.cancel_all_tasks()
    tts_service.cancel_all_tasks()

    argv = [sys.executable, *sys.argv]
    try:
        os.execv(sys.executable, argv)
    except OSError:
        os._exit(1)


@router.get("/health")
def health(request: Request):
    tts_health = tts_service.get_health()
    return {
        "status": "ok",
        "env": config.SETTINGS.env,
        "model": config.SETTINGS.model,
        "num_ctx": config.SETTINGS.num_ctx,
        "max_tokens": config.SETTINGS.max_tokens,
        "mem_turns": config.SETTINGS.mem_turns,
        "temperature": config.SETTINGS.temperature,
        "models_dir": str(config.MODEL_PATHS.base),
        "chat_models_dir": str(config.MODEL_PATHS.ollama),
        "asr_models_dir": str(config.MODEL_PATHS.whisper),
        "tts_models_dir": str(config.MODEL_PATHS.tts),
        "piper_models_dir": str(config.MODEL_PATHS.piper),
        "ollama_models_dir": str(config.MODEL_PATHS.ollama),
        "whisper_models_dir": str(config.MODEL_PATHS.whisper),
        "tts": {
            "enabled": tts_health.get("tts_enabled"),
            "provider": tts_health.get("default_provider"),
            "available": tts_health.get("provider", {}).get("available"),
            "voices_count": tts_health.get("provider", {}).get("voices_count"),
        },
        "access_url": _get_access_url(request),
        "lan_url": _get_lan_url(request),
        "ios_url": _get_lan_url(request),
    }


@router.get("/version")
def version():
    return {"env": config.SETTINGS.env, "model": config.SETTINGS.model, "base_url": config.SETTINGS.base_url}


@router.post("/runtime/shutdown")
def shutdown_runtime():
    worker = threading.Thread(target=_shutdown_worker, daemon=True)
    worker.start()
    return {"status": "accepted", "message": "Shutdown started"}


@router.post("/runtime/restart")
def restart_backend_runtime():
    worker = threading.Thread(target=_restart_backend_worker, daemon=True)
    worker.start()
    return {"status": "accepted", "message": "Backend restart started"}


@router.post("/database/cleanup")
def cleanup_database(req: DatabaseCleanupRequest):
    return db.cleanup_database_garbage(vacuum=req.vacuum)


@router.post("/database/reset")
def reset_database(req: DatabaseResetRequest):
    if req.confirm != "RESET_DATABASE":
        raise HTTPException(
            status_code=422,
            detail={"code": "database_reset_confirmation_required", "message": "Подтвердите полную очистку БД."},
        )

    chat_tasks.cancel_all_tasks()
    transcribe_tasks.cancel_all_tasks()
    tts_service.cancel_all_tasks()

    for profile in db.list_profiles(include_inactive=True):
        profile_id = profile.get("id")
        if profile_id is not None:
            rag_service.delete_profile_source_dir(int(profile_id))

    result = db.reset_database(vacuum=req.vacuum)
    rag_service.ensure_profile_source_dir(int(result["default_profile_id"]))
    return result
