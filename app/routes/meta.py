from __future__ import annotations

import os
import signal
import tempfile
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException

from .. import chat_tasks, config, db
from ..schemas import DatabaseCleanupRequest, DatabaseResetRequest
from ..security import ADMIN_TOKEN_HEADER, require_admin_token
from .. import transcribe_tasks
from ..services import tts_service
from backend.apps.rag import service as rag_service
from backend.apps.chat.services import attachment_storage
from backend.networking import detect_private_lan_ipv4

router = APIRouter()
_USER_ID = os.getuid() if hasattr(os, "getuid") else 0
_DEFAULT_RUNTIME_DIR = Path(tempfile.gettempdir()) / f"LocalGPT-{_USER_ID}"
RUNTIME_DIR = Path(os.getenv("LOCALGPT_RUNTIME_DIR", str(_DEFAULT_RUNTIME_DIR)))
BACKEND_PID_FILE = RUNTIME_DIR / "backend.pid"


def get_network_address_items() -> list[dict[str, object]]:
    if os.getenv("LOCALGPT_LAN_MODE", "0").strip() != "1":
        return []
    lan_ip = detect_private_lan_ipv4()
    if not lan_ip:
        return []
    try:
        port = int(os.getenv("LOCALGPT_PORT", "8000"))
    except ValueError:
        return []
    return [
        {
            "id": "lan",
            "provider_id": "lan",
            "label": "LAN",
            "url": f"http://{lan_ip}:{port}/ui/gui_html.html",
            "detail": "HTTP без TLS и общей авторизации.",
            "trusted": False,
            "copyable": True,
            "priority": 10,
            "security_note": "Любое устройство с доступом к порту может читать и изменять данные LocalGPT. Используйте только в доверенной локальной сети.",
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


def _shutdown_worker() -> None:
    time.sleep(0.45)

    chat_tasks.cancel_all_tasks()
    transcribe_tasks.cancel_all_tasks()
    tts_service.cancel_all_tasks()

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
def health():
    return {"status": "ok"}


@router.get("/version")
def version():
    return {"service": "LocalGPT", "api_version": 1}


@router.post("/runtime/shutdown")
def shutdown_runtime(admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER)):
    require_admin_token(admin_token)
    worker = threading.Thread(target=_shutdown_worker, daemon=True)
    worker.start()
    return {"status": "accepted", "message": "Shutdown started"}


@router.post("/runtime/restart")
def restart_backend_runtime(admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER)):
    require_admin_token(admin_token)
    worker = threading.Thread(target=_restart_backend_worker, daemon=True)
    worker.start()
    return {"status": "accepted", "message": "Backend restart started"}


@router.post("/database/cleanup")
def cleanup_database(
    req: DatabaseCleanupRequest,
    admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
):
    require_admin_token(req.admin_token or admin_token)
    return db.cleanup_database_garbage(vacuum=req.vacuum)


@router.post("/database/reset")
def reset_database(
    req: DatabaseResetRequest,
    admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
):
    require_admin_token(req.admin_token or admin_token)
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

    attachment_storage.delete_all_attachments()
    result = db.reset_database(vacuum=req.vacuum)
    rag_service.ensure_profile_source_dir(int(result["default_profile_id"]))
    return result
