from __future__ import annotations

import json
import multiprocessing as mp
import os
import signal
import threading
from datetime import datetime, timezone
from pathlib import Path
from secrets import token_hex
from tempfile import NamedTemporaryFile
from typing import Any

from app import config, db
from backend.apps.chat.service import ChatService, maybe_compress_session_history

TASKS_DIR = config.DATA_DIR / "chat_tasks"
TASKS_DIR.mkdir(parents=True, exist_ok=True)

_PROCESS_CTX = mp.get_context("spawn")
_LOCK = threading.Lock()
_TASKS: dict[str, dict[str, Any]] = {}
_FINAL_STATES = {"completed", "error", "cancelled"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _generate_id() -> str:
    now = datetime.now(timezone.utc)
    return f"ct_{now:%Y%m%d_%H%M%S}_{token_hex(3)}"


def _artifact_path(task_id: str, suffix: str) -> Path:
    return TASKS_DIR / f"{task_id}.{suffix}.json"


def _safe_unlink(path: Path | str | None) -> None:
    if not path:
        return
    try:
        Path(path).unlink()
    except OSError:
        pass


def _read_json(path: Path | str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _atomic_write_json(path: Path | str, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, dir=str(target.parent), encoding="utf-8") as tmp_file:
        json.dump(payload, tmp_file, ensure_ascii=False, indent=2)
        tmp_file.flush()
        temp_name = tmp_file.name
    Path(temp_name).replace(target)


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task.get("id"),
        "state": task.get("state"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "session_id": task.get("session_id"),
        "profile_id": task.get("profile_id"),
        "model_name": task.get("model_name"),
        "role": task.get("role"),
        "message": task.get("message"),
        "error_code": task.get("error_code"),
        "pid": task.get("pid"),
        "used_settings": task.get("used_settings"),
        "router_notice": task.get("router_notice"),
        "result": task.get("result"),
    }


def _chat_worker(
    model_name: str,
    messages: list[dict[str, str]],
    settings: dict[str, Any],
    session_id: str,
    profile_id: int | None,
    result_path: str,
    error_path: str,
) -> None:
    try:
        service = ChatService()
        reply = service.chat_completion(model_name, messages, settings=settings)
        if session_id:
            db.add_message(session_id, "assistant", reply)
            if profile_id:
                try:
                    maybe_compress_session_history(
                        service=service,
                        session_id=session_id,
                        profile_id=profile_id,
                        model_name=model_name,
                        settings=settings,
                    )
                except Exception:
                    pass
        _atomic_write_json(result_path, {"reply": reply})
    except Exception as exc:  # pragma: no cover - runtime path
        message = getattr(exc, "detail", None) or str(exc) or "chat_generation_failed"
        _atomic_write_json(error_path, {"code": "chat_generation_failed", "message": str(message)})


def _cleanup_task_files(task: dict[str, Any]) -> None:
    _safe_unlink(task.get("result_path"))
    _safe_unlink(task.get("error_path"))


def _finalize_task_locked(task: dict[str, Any]) -> None:
    if task.get("state") in _FINAL_STATES:
        return

    result = _read_json(task.get("result_path"))
    error = _read_json(task.get("error_path"))
    cancel_requested = bool(task.get("cancel_requested")) or task.get("state") == "cancelling"

    if cancel_requested:
        task["state"] = "cancelled"
        task["message"] = "Chat generation cancelled."
        task["error_code"] = "task_cancelled"
        task["result"] = None
    elif result:
        task["state"] = "completed"
        task["message"] = "Chat generation completed."
        task["error_code"] = None
        task["result"] = result
    elif error:
        task["state"] = "error"
        task["message"] = error.get("message") or "chat_generation_failed"
        task["error_code"] = error.get("code") or "chat_generation_failed"
        task["result"] = None
    else:
        task["state"] = "error"
        task["message"] = "Chat process exited without result."
        task["error_code"] = "chat_generation_failed"
        task["result"] = None

    task["updated_at"] = _utc_now()
    task["pid"] = None
    task.pop("cancel_requested", None)
    task.pop("_process", None)
    task.pop("_monitor", None)
    _cleanup_task_files(task)


def _refresh_task_locked(task: dict[str, Any]) -> None:
    if task.get("state") in _FINAL_STATES:
        return
    process = task.get("_process")
    if process is not None and process.is_alive():
        return
    _finalize_task_locked(task)


def _monitor_task(task_id: str) -> None:
    process = None
    with _LOCK:
        task = _TASKS.get(task_id)
        if task:
            process = task.get("_process")

    if process is not None:
        process.join()

    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        _refresh_task_locked(task)


def create_completed_task(
    *,
    session_id: str,
    profile_id: int | None,
    model_name: str,
    role: str,
    used_settings: dict[str, Any],
    reply: str,
    router_notice: str | None = None,
) -> dict[str, Any]:
    task_id = _generate_id()
    now = _utc_now()
    task = {
        "id": task_id,
        "state": "completed",
        "created_at": now,
        "updated_at": now,
        "session_id": session_id,
        "profile_id": profile_id,
        "model_name": model_name,
        "role": role,
        "message": "Chat generation completed.",
        "error_code": None,
        "pid": None,
        "used_settings": used_settings,
        "router_notice": router_notice,
        "result": {"reply": reply},
    }
    with _LOCK:
        _TASKS[task_id] = task
    return _public_task(task)


def start_chat_task(
    *,
    session_id: str,
    profile_id: int | None,
    model_name: str,
    role: str,
    messages: list[dict[str, str]],
    used_settings: dict[str, Any],
    router_notice: str | None = None,
) -> dict[str, Any]:
    task_id = _generate_id()
    now = _utc_now()
    result_path = _artifact_path(task_id, "result")
    error_path = _artifact_path(task_id, "error")

    process = _PROCESS_CTX.Process(
        target=_chat_worker,
        args=(
            model_name,
            messages,
            used_settings,
            session_id,
            profile_id,
            str(result_path),
            str(error_path),
        ),
        daemon=True,
        name=f"localgpt_chat_{task_id}",
    )

    try:
        process.start()
    except Exception:
        _safe_unlink(result_path)
        _safe_unlink(error_path)
        raise

    task = {
        "id": task_id,
        "state": "running",
        "created_at": now,
        "updated_at": now,
        "session_id": session_id,
        "profile_id": profile_id,
        "model_name": model_name,
        "role": role,
        "message": "Chat generation started.",
        "error_code": None,
        "pid": process.pid,
        "used_settings": used_settings,
        "router_notice": router_notice,
        "result": None,
        "result_path": str(result_path),
        "error_path": str(error_path),
        "cancel_requested": False,
        "_process": process,
    }

    monitor = threading.Thread(target=_monitor_task, args=(task_id,), daemon=True, name=f"localgpt_chat_monitor_{task_id}")
    task["_monitor"] = monitor

    with _LOCK:
        _TASKS[task_id] = task

    monitor.start()
    return _public_task(task)


def get_chat_task(task_id: str) -> dict[str, Any] | None:
    if not task_id:
        return None
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return None
        _refresh_task_locked(task)
        return _public_task(task)


def cancel_chat_task(task_id: str) -> dict[str, Any] | None:
    if not task_id:
        return None

    process = None
    pid = None
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return None
        _refresh_task_locked(task)
        if task.get("state") in _FINAL_STATES:
            return _public_task(task)

        task["cancel_requested"] = True
        task["state"] = "cancelling"
        task["message"] = "Stopping chat generation..."
        task["updated_at"] = _utc_now()
        process = task.get("_process")
        pid = task.get("pid")

    if process is not None and process.is_alive():
        try:
            process.terminate()
        except Exception:
            if pid:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except OSError:
                    pass
        process.join(timeout=1.5)
        if process.is_alive():
            try:
                process.kill()
            except Exception:
                if pid:
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except OSError:
                        pass
            process.join(timeout=1.0)

    return get_chat_task(task_id)


def cancel_all_tasks() -> int:
    with _LOCK:
        task_ids = [task_id for task_id, task in _TASKS.items() if task.get("state") not in _FINAL_STATES]

    cancelled = 0
    for task_id in task_ids:
        task = cancel_chat_task(task_id)
        if task is not None:
            cancelled += 1
    return cancelled
