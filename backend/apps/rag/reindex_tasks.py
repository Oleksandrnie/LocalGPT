from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app import db
from backend.apps.rag import service

_LOCK = threading.Lock()
_TASKS: dict[str, dict[str, Any]] = {}
_ACTIVE_TASK_ID: str | None = None
_TERMINAL_STATES = {"completed", "failed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _public_task(task: dict[str, Any] | None) -> dict[str, Any] | None:
    if not task:
        return None
    return {
        key: task.get(key)
        for key in (
            "task_id",
            "profile_id",
            "status",
            "embedding_model",
            "embedding",
            "processed_chunks",
            "total_chunks",
            "error_code",
            "created_at",
            "started_at",
            "updated_at",
            "completed_at",
        )
    }


def _update_task(task_id: str, **fields: Any) -> None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        task.update(fields)
        task["updated_at"] = _now()


def _progress(task_id: str, processed_chunks: int, total_chunks: int) -> None:
    _update_task(
        task_id,
        processed_chunks=max(0, int(processed_chunks)),
        total_chunks=max(0, int(total_chunks)),
    )


def _public_error_code(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = str(exc.detail or "")
        if exc.status_code == 409 and detail == "rag_embedding_source_changed":
            return "rag_embedding_source_changed"
        if detail.startswith("rag_embedding_configuration_error"):
            return "rag_embedding_configuration_error"
        if detail.startswith("rag_embedding_provider_unavailable"):
            return "rag_embedding_provider_unavailable"
        if detail == "rag_embedding_provider_incompatible":
            return "rag_embedding_provider_incompatible"
    return "rag_embedding_reindex_failed"


def _run(task_id: str, provider: Any) -> None:
    global _ACTIVE_TASK_ID
    _update_task(task_id, status="running", started_at=_now())
    try:
        result = service.reindex_embeddings(
            int(_TASKS[task_id]["profile_id"]),
            provider=provider,
            progress_callback=lambda processed, total: _progress(task_id, processed, total),
        )
        _update_task(
            task_id,
            status="completed",
            processed_chunks=int(result.get("chunks_reindexed") or 0),
            total_chunks=int(result.get("chunks_reindexed") or 0),
            completed_at=_now(),
            error_code=None,
        )
    except Exception as exc:
        _update_task(
            task_id,
            status="failed",
            error_code=_public_error_code(exc),
            completed_at=_now(),
        )
    finally:
        with _LOCK:
            if _ACTIVE_TASK_ID == task_id:
                _ACTIVE_TASK_ID = None


def start_reindex(profile_id: int) -> dict[str, Any]:
    global _ACTIVE_TASK_ID
    if not db.get_profile(profile_id):
        raise HTTPException(status_code=404, detail="profile_not_found")
    try:
        provider = service._embedding_provider()
    except HTTPException as exc:
        raise HTTPException(status_code=503, detail="rag_embedding_configuration_error") from exc

    with _LOCK:
        if _ACTIVE_TASK_ID:
            active = _TASKS.get(_ACTIVE_TASK_ID)
            if active and active.get("status") not in _TERMINAL_STATES:
                raise HTTPException(status_code=409, detail="rag_embedding_reindex_in_progress")
            _ACTIVE_TASK_ID = None
        terminal_ids = [
            task_id
            for task_id, task in _TASKS.items()
            if task.get("status") in _TERMINAL_STATES
        ]
        for task_id in terminal_ids[:-20]:
            _TASKS.pop(task_id, None)
        task_id = uuid.uuid4().hex
        now = _now()
        task = {
            "task_id": task_id,
            "profile_id": int(profile_id),
            "status": "queued",
            "embedding_model": provider.descriptor.storage_key,
            "embedding": provider.descriptor.as_metadata(),
            "processed_chunks": 0,
            "total_chunks": len(db.list_document_chunks(profile_id)),
            "error_code": None,
            "created_at": now,
            "started_at": None,
            "updated_at": now,
            "completed_at": None,
        }
        _TASKS[task_id] = task
        _ACTIVE_TASK_ID = task_id

    threading.Thread(
        target=_run,
        args=(task_id, provider),
        daemon=True,
        name=f"localgpt_rag_reindex_{task_id[:8]}",
    ).start()
    return _public_task(task) or {}


def get_reindex_task(task_id: str, profile_id: int) -> dict[str, Any] | None:
    with _LOCK:
        task = _TASKS.get(str(task_id or ""))
        if not task or int(task.get("profile_id") or 0) != int(profile_id):
            return None
        return _public_task(task)


def latest_reindex_task(profile_id: int) -> dict[str, Any] | None:
    with _LOCK:
        matches = [
            task
            for task in _TASKS.values()
            if int(task.get("profile_id") or 0) == int(profile_id)
        ]
        latest = max(matches, key=lambda item: str(item.get("created_at") or ""), default=None)
        return _public_task(latest)


def _reset_for_tests() -> None:
    global _ACTIVE_TASK_ID
    with _LOCK:
        _TASKS.clear()
        _ACTIVE_TASK_ID = None
