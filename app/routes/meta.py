from __future__ import annotations

import os
import signal
import tempfile
import threading
import time
from pathlib import Path

from fastapi import APIRouter

from ..services import tts_service

router = APIRouter()
_DEFAULT_RUNTIME_DIR = Path(tempfile.gettempdir()) / f"LocalGPT-{os.getuid()}"
RUNTIME_DIR = Path(os.getenv("LOCALGPT_RUNTIME_DIR", str(_DEFAULT_RUNTIME_DIR)))
BACKEND_PID_FILE = RUNTIME_DIR / "backend.pid"
CADDY_PID_FILE = RUNTIME_DIR / "caddy.pid"


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


@router.post("/runtime/shutdown")
def shutdown_runtime() -> dict[str, object]:
    worker = threading.Thread(target=_shutdown_worker, daemon=True)
    worker.start()
    return {"status": "accepted", "message": "Shutdown started"}
