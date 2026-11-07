"""Bounded, ephemeral retrieval jobs with cooperative user cancellation.

Jobs deliberately have no overall deadline. A cancelled worker still consumes a
slot until its current local provider call returns and it observes cancellation.
"""
from __future__ import annotations

from collections.abc import Callable
from secrets import token_urlsafe
import threading
from time import monotonic
from typing import Any

from fastapi import HTTPException

MAX_ACTIVE_TOTAL = 4
MAX_ACTIVE_PER_PROFILE = 2
MAX_RETAINED_TASKS = 64
RESULT_TTL_SECONDS = 15 * 60
_LOCK = threading.RLock()
_TASKS: dict[str, dict[str, Any]] = {}


class SearchCancelled(Exception):
    """Raised at a retrieval phase boundary after an explicit cancellation."""


def _public(task: dict[str, Any]) -> dict[str, Any]:
    return {key: task.get(key) for key in (
        "task_id", "state", "profile_id", "session_id", "result", "error",
    )}


def _owned(task_id: str, profile_id: int, session_id: str | None) -> dict[str, Any]:
    task = _TASKS.get(task_id)
    if not task or task["profile_id"] != profile_id or task["session_id"] != session_id:
        raise HTTPException(404, {"code": "knowledge_search_task_not_found",
                                  "message": "Задача поиска не найдена."})
    return task


def _prune(*, reserve_slot: bool = False) -> None:
    now = monotonic()
    finished = sorted((task for task in _TASKS.values() if not task["running"]),
                      key=lambda task: task["finished_at"])
    for task in finished:
        if (now - task["finished_at"] > RESULT_TTL_SECONDS
                or len(_TASKS) > MAX_RETAINED_TASKS - int(reserve_slot)):
            _TASKS.pop(task["task_id"], None)


def start(*, profile_id: int, session_id: str | None,
          work: Callable[[Callable[[], None]], dict[str, Any]],
          persist: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    with _LOCK:
        _prune(reserve_slot=True)
        running = [task for task in _TASKS.values() if task["running"]]
        if (len(running) >= MAX_ACTIVE_TOTAL
                or sum(task["profile_id"] == profile_id for task in running) >= MAX_ACTIVE_PER_PROFILE):
            raise HTTPException(429, {"code": "knowledge_search_capacity_exceeded",
                                      "message": "Дождитесь завершения предыдущего поиска и повторите запрос."})
        task_id = "ks_" + token_urlsafe(18)
        task = {"task_id": task_id, "profile_id": profile_id, "session_id": session_id,
                "state": "running", "running": True, "cancel": threading.Event(),
                "result": None, "error": None, "finished_at": None}
        _TASKS[task_id] = task

        def check_cancelled() -> None:
            if task["cancel"].is_set():
                raise SearchCancelled()

        def run() -> None:
            try:
                check_cancelled()
                result = work(check_cancelled)
                # Cancellation and persistence are serialized: once cancellation
                # succeeds no late user/assistant messages can be written.
                with _LOCK:
                    check_cancelled()
                    task["result"] = persist(result)
                    task["state"] = "completed"
            except SearchCancelled:
                with _LOCK:
                    task["state"] = "cancelled"
            except Exception as exc:
                with _LOCK:
                    if task["cancel"].is_set():
                        task["state"] = "cancelled"
                    else:
                        task["state"] = "failed"
                        detail = exc.detail if isinstance(exc, HTTPException) else None
                        task["error"] = {"status_code": exc.status_code if isinstance(exc, HTTPException) else 500,
                                         "detail": detail or {"code": "knowledge_search_failed",
                                                               "message": "Поиск не выполнен. Повторите запрос."}}
            finally:
                with _LOCK:
                    task["running"] = False
                    task["finished_at"] = monotonic()

        thread = threading.Thread(target=run, name=f"knowledge-search-{task_id}", daemon=True)
        task["thread"] = thread
        try:
            thread.start()
        except Exception:
            _TASKS.pop(task_id, None)
            raise
        return _public(task)


def get(task_id: str, *, profile_id: int, session_id: str | None) -> dict[str, Any]:
    with _LOCK:
        _prune()
        return _public(_owned(task_id, profile_id, session_id))


def cancel(task_id: str, *, profile_id: int, session_id: str | None) -> dict[str, Any]:
    with _LOCK:
        task = _owned(task_id, profile_id, session_id)
        if task["state"] == "running":
            task["cancel"].set()
            task["state"] = "cancelled"
        return _public(task)


def reset(*, join_timeout: float = 5) -> None:
    """Cancel and join workers before clearing state (isolated tests/shutdown)."""
    with _LOCK:
        tasks = list(_TASKS.values())
        for task in tasks:
            task["cancel"].set()
    for task in tasks:
        task["thread"].join(timeout=join_timeout)
    with _LOCK:
        # Never forget a live worker: it must continue counting toward capacity.
        for task in tasks:
            if not task["thread"].is_alive():
                _TASKS.pop(task["task_id"], None)
