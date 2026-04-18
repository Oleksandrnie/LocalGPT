from __future__ import annotations

import os
import signal
import socket
import tempfile
import threading
import time
from pathlib import Path

from fastapi import APIRouter
from fastapi import Request

from .. import config
from ..roles import DEFAULT_ROLE, list_roles
from .. import transcribe_tasks
from ..services import tts_service

router = APIRouter()
_USER_ID = os.getuid() if hasattr(os, "getuid") else 0
_DEFAULT_RUNTIME_DIR = Path(tempfile.gettempdir()) / f"LocalGPT-{_USER_ID}"
RUNTIME_DIR = Path(os.getenv("LOCALGPT_RUNTIME_DIR", str(_DEFAULT_RUNTIME_DIR)))
BACKEND_PID_FILE = RUNTIME_DIR / "backend.pid"
CADDY_PID_FILE = RUNTIME_DIR / "caddy.pid"


def _detect_lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("1.1.1.1", 80))
            lan_ip = sock.getsockname()[0]
    except OSError:
        return None

    if not lan_ip or lan_ip.startswith("127."):
        return None
    return lan_ip


def _get_access_url(request: Request) -> str | None:
    host = (request.headers.get("host") or "").strip()
    if host:
        return f"{request.url.scheme}://{host}/ui/gui_html.html"
    return None


def _get_lan_url(request: Request) -> str | None:
    explicit = (os.getenv("IOS_ACCESS_URL", "") or "").strip()
    if explicit:
        return explicit

    host = (request.headers.get("host") or "").strip()
    if host and not host.startswith(("127.0.0.1", "localhost", "[::1]")):
        return f"https://{host}/ui/gui_html.html"

    lan_ip = _detect_lan_ip()
    if not lan_ip:
        return None

    port = os.getenv("IOS_HTTPS_PORT", "8443").strip() or "8443"
    return f"https://{lan_ip}:{port}/ui/gui_html.html"


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


def _shutdown_worker() -> None:
    time.sleep(0.45)

    transcribe_tasks.cancel_all_tasks()
    tts_service.cancel_all_tasks()

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
        "ios_url": _get_lan_url(request),
    }


@router.get("/version")
def version():
    return {"env": config.SETTINGS.env, "model": config.SETTINGS.model, "base_url": config.SETTINGS.base_url}


@router.get("/roles")
def roles():
    return {"roles": list_roles(), "default": DEFAULT_ROLE}


@router.post("/runtime/shutdown")
def shutdown_runtime():
    worker = threading.Thread(target=_shutdown_worker, daemon=True)
    worker.start()
    return {"status": "accepted", "message": "Shutdown started"}
