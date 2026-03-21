from __future__ import annotations

import os
from pathlib import Path
import signal
import socket
import threading
import time

from fastapi import APIRouter, HTTPException
from fastapi import Request

from .. import config, whisper_downloads
from ..schemas import ModelPrepareRequest

router = APIRouter()
RUNTIME_DIR = Path(os.getenv("LTRNSRB_RUNTIME_DIR", "/tmp/LTrnsrb"))
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


def _get_ios_url(request: Request) -> str | None:
    if config.SETTINGS.ios_access_url:
        return config.SETTINGS.ios_access_url

    host = (request.headers.get("host") or "").strip()
    if host and not host.startswith(("127.0.0.1", "localhost", "[::1]")):
        return f"https://{host}/ui/gui_html.html"

    lan_ip = _detect_lan_ip()
    if lan_ip:
        return f"https://{lan_ip}:{config.SETTINGS.ios_https_port}/ui/gui_html.html"
    return None


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

    caddy_pid = _read_pid(CADDY_PID_FILE)
    if caddy_pid:
        _terminate_pid(caddy_pid)
    _safe_unlink(CADDY_PID_FILE)

    backend_pid = _read_pid(BACKEND_PID_FILE)
    if backend_pid:
        _terminate_pid(backend_pid)
    _safe_unlink(BACKEND_PID_FILE)

    # Fallback: ensure this API process also exits even if launcher PID was missing.
    time.sleep(0.35)
    _terminate_pid(os.getpid())


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    return {
        "status": "ok",
        "env": config.SETTINGS.env,
        "default_model": config.SETTINGS.whisper_default_model,
        "whisper_models_dir": str(config.WHISPER_MODELS_DIR),
        "transcripts_dir": str(config.TRANSCRIPTS_DIR),
        "ios_url": _get_ios_url(request),
    }


@router.get("/whisper/models")
def whisper_models() -> dict[str, object]:
    return {
        "models": list(config.ALLOWED_WHISPER_MODELS),
        "default": config.SETTINGS.whisper_default_model,
    }


@router.post("/whisper/models/prepare")
def prepare_model(req: ModelPrepareRequest) -> dict[str, object]:
    try:
        return whisper_downloads.start_prepare_task(req.model, force=bool(req.force))
    except ValueError as exc:
        if str(exc) == "invalid_model":
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_model",
                    "message": f"Недопустимая модель: {req.model}",
                    "allowed": list(config.ALLOWED_WHISPER_MODELS),
                },
            ) from exc
        raise


@router.get("/whisper/models/update-check/{model_name}")
def check_model_update(model_name: str) -> dict[str, object]:
    try:
        return whisper_downloads.check_model_update(model_name)
    except ValueError as exc:
        if str(exc) == "invalid_model":
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_model",
                    "message": f"Недопустимая модель: {model_name}",
                    "allowed": list(config.ALLOWED_WHISPER_MODELS),
                },
            ) from exc
        raise


@router.get("/whisper/models/prepare/{task_id}")
def get_prepare_status(task_id: str) -> dict[str, object]:
    task = whisper_downloads.get_prepare_task(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail={"code": "task_not_found", "message": "Задача подготовки модели не найдена"},
        )
    return task


@router.post("/runtime/shutdown")
def shutdown_runtime() -> dict[str, object]:
    worker = threading.Thread(target=_shutdown_worker, daemon=True)
    worker.start()
    return {"status": "accepted", "message": "Shutdown started"}
