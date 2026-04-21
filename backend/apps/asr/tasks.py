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
from app.services.timeline import build_timeline
from backend.apps.asr.whisper import transcribe_with_fallback

TASKS_DIR = config.DATA_DIR / "transcribe_tasks"
TASKS_DIR.mkdir(parents=True, exist_ok=True)

_PROCESS_CTX = mp.get_context("spawn")
_LOCK = threading.Lock()
_TASKS: dict[str, dict[str, Any]] = {}
_FINAL_STATES = {"completed", "error", "cancelled"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _generate_id() -> str:
    now = datetime.now(timezone.utc)
    return f"tt_{now:%Y%m%d_%H%M%S}_{token_hex(3)}"


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
        "model": task.get("model"),
        "source_name": task.get("source_name"),
        "origin": task.get("origin"),
        "message": task.get("message"),
        "error_code": task.get("error_code"),
        "pid": task.get("pid"),
        "result": task.get("result"),
    }


def _error_payload_from_exception(exc: Exception, selected_model: str) -> dict[str, Any]:
    if isinstance(exc, RuntimeError):
        code = str(exc)
        if code.startswith("WHISPER_MODEL_NOT_FOUND::"):
            missing_model = code.split("::", 1)[1] if "::" in code else selected_model
            return {
                "code": "whisper_model_missing",
                "model": missing_model,
                "message": f'Whisper model "{missing_model}" is not available locally.',
            }
        if code == "empty_transcription":
            return {"code": "empty_transcription", "message": "Whisper вернул пустую транскрипцию."}
    return {"code": "transcription_failed", "message": str(exc) or "transcription_failed"}


def _transcription_worker(
    input_path: str,
    model: str,
    prompt_preset: str,
    preferred_language: str | None,
    source_name: str,
    profile_id: int,
    session_id: str | None,
    store_result: bool,
    origin: str | None,
    result_path: str,
    error_path: str,
) -> None:
    try:
        transcription = transcribe_with_fallback(
            audio_path=input_path,
            model_name=model,
            prompt_preset=None if prompt_preset == "none" else prompt_preset,
            preferred_language=preferred_language,
        )
        text = transcription.get("text", "") if isinstance(transcription, dict) else str(transcription)
        segments = list(transcription.get("segments") or []) if isinstance(transcription, dict) else []
        timeline = build_timeline(segments)
        if not text:
            raise RuntimeError("empty_transcription")

        detected_language = transcription.get("language") if isinstance(transcription, dict) else None
        role_keywords = transcription.get("role_keywords") or {} if isinstance(transcription, dict) else {}
        transcript_record = None

        if store_result:
            labels = {"origin": origin} if origin else None
            transcript_record = db.create_transcript(
                profile_id=profile_id,
                session_id=session_id,
                name=source_name or "Транскрипт",
                content=text,
                source_path=source_name,
                language=detected_language or preferred_language or "auto",
                timeline=timeline,
                role_keywords=role_keywords,
                labels=labels,
            )

        _atomic_write_json(
            result_path,
            {
                "text": text,
                "model": model,
                "prompt_preset": prompt_preset,
                "language": preferred_language or "auto",
                "detected_language": detected_language,
                "segments": segments,
                "timeline": timeline,
                "role_keywords": role_keywords,
                "transcript_id": transcript_record.get("id") if transcript_record else None,
                "profile_id": profile_id or None,
                "session_id": session_id or None,
                "stored": bool(store_result),
                "origin": origin or None,
            },
        )
    except Exception as exc:  # pragma: no cover - runtime path
        _atomic_write_json(error_path, _error_payload_from_exception(exc, model))
    finally:
        _safe_unlink(input_path)


def _cleanup_task_files(task: dict[str, Any]) -> None:
    _safe_unlink(task.get("input_path"))
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
        task["message"] = "Transcription cancelled."
        task["error_code"] = "task_cancelled"
        task["result"] = None
    elif result:
        task["state"] = "completed"
        task["message"] = "Transcription completed."
        task["error_code"] = None
        task["result"] = result
    elif error:
        task["state"] = "error"
        task["message"] = error.get("message") or "transcription_failed"
        task["error_code"] = error.get("code") or "transcription_failed"
        task["result"] = None
    else:
        task["state"] = "error"
        task["message"] = "Transcription process exited without result."
        task["error_code"] = "transcription_failed"
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


def start_transcription_task(
    *,
    input_path: str,
    model: str,
    prompt_preset: str,
    preferred_language: str | None,
    source_name: str,
    profile_id: int,
    session_id: str | None,
    store_result: bool,
    origin: str | None = None,
) -> dict[str, Any]:
    task_id = _generate_id()
    now = _utc_now()
    result_path = _artifact_path(task_id, "result")
    error_path = _artifact_path(task_id, "error")

    process = _PROCESS_CTX.Process(
        target=_transcription_worker,
        args=(
            input_path,
            model,
            prompt_preset,
            preferred_language,
            source_name,
            profile_id,
            session_id,
            store_result,
            origin,
            str(result_path),
            str(error_path),
        ),
        daemon=True,
        name=f"localgpt_transcribe_{task_id}",
    )

    try:
        process.start()
    except Exception:
        _safe_unlink(input_path)
        _safe_unlink(result_path)
        _safe_unlink(error_path)
        raise

    task = {
        "id": task_id,
        "state": "running",
        "created_at": now,
        "updated_at": now,
        "model": model,
        "source_name": source_name,
        "origin": origin or None,
        "message": "Transcription started.",
        "error_code": None,
        "pid": process.pid,
        "result": None,
        "input_path": str(input_path),
        "result_path": str(result_path),
        "error_path": str(error_path),
        "cancel_requested": False,
        "_process": process,
    }

    monitor = threading.Thread(target=_monitor_task, args=(task_id,), daemon=True, name=f"localgpt_transcribe_monitor_{task_id}")
    task["_monitor"] = monitor

    with _LOCK:
        _TASKS[task_id] = task

    monitor.start()
    return _public_task(task)


def get_transcription_task(task_id: str) -> dict[str, Any] | None:
    if not task_id:
        return None
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return None
        _refresh_task_locked(task)
        return _public_task(task)


def cancel_transcription_task(task_id: str) -> dict[str, Any] | None:
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
        task["message"] = "Stopping transcription..."
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

    return get_transcription_task(task_id)


def cancel_all_tasks() -> int:
    with _LOCK:
        task_ids = [task_id for task_id, task in _TASKS.items() if task.get("state") not in _FINAL_STATES]

    cancelled = 0
    for task_id in task_ids:
        task = cancel_transcription_task(task_id)
        if task is not None:
            cancelled += 1
    return cancelled
