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
from backend.apps.chat.prompt_policy import data_envelope
from backend.apps.chat.service import (
    ChatService,
    enforce_protected_output,
    guard_stream_events,
    maybe_compress_session_history,
    sanitize_reply,
)
from backend.apps.chat.services import ollama_runtime, vision_context, vision_runtime

TASKS_DIR = config.DATA_DIR / "chat_tasks"
TASKS_DIR.mkdir(parents=True, exist_ok=True)

_PROCESS_CTX = mp.get_context("spawn")
_LOCK = threading.Lock()
_TASKS: dict[str, dict[str, Any]] = {}
_STARTING_BY_PROFILE: dict[int, int] = {}
_FINAL_STATES = {"completed", "failed", "error", "cancelled"}
_ACTIVE_VISION_STATES = {"preparing", "analyzing", "loading_model", "generating", "streaming"}
CHAT_TASK_MAX_ACTIVE_PER_PROFILE = max(1, int(os.getenv("CHAT_TASK_MAX_ACTIVE_PER_PROFILE", "2")))
CHAT_TASK_MAX_ACTIVE_TOTAL = max(CHAT_TASK_MAX_ACTIVE_PER_PROFILE, int(os.getenv("CHAT_TASK_MAX_ACTIVE_TOTAL", "4")))
CHAT_TASK_TIMEOUT_SECONDS = max(30, int(os.getenv("CHAT_TASK_TIMEOUT_SECONDS", "300")))


class ChatTaskCapacityError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _reserve_starting_slot(profile_id: int | None) -> int:
    profile_key = int(profile_id or 0)
    with _LOCK:
        active_tasks = [task for task in _TASKS.values() if task.get("state") not in _FINAL_STATES]
        active_for_profile = sum(1 for task in active_tasks if int(task.get("profile_id") or 0) == profile_key)
        starting_for_profile = int(_STARTING_BY_PROFILE.get(profile_key) or 0)
        starting_total = sum(_STARTING_BY_PROFILE.values())
        if active_for_profile + starting_for_profile >= CHAT_TASK_MAX_ACTIVE_PER_PROFILE:
            raise ChatTaskCapacityError(
                "chat_profile_concurrency_exceeded",
                "The active profile has reached its chat task limit.",
            )
        if len(active_tasks) + starting_total >= CHAT_TASK_MAX_ACTIVE_TOTAL:
            raise ChatTaskCapacityError(
                "chat_runtime_concurrency_exceeded",
                "The LocalGPT runtime has reached its chat task limit.",
            )
        _STARTING_BY_PROFILE[profile_key] = starting_for_profile + 1
    return profile_key


def _release_starting_slot(profile_key: int) -> None:
    with _LOCK:
        remaining = max(0, int(_STARTING_BY_PROFILE.get(profile_key) or 1) - 1)
        if remaining:
            _STARTING_BY_PROFILE[profile_key] = remaining
        else:
            _STARTING_BY_PROFILE.pop(profile_key, None)


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


def _append_stream_chunk_jsonl(path: Path | str | None, sequence: int, text: str) -> None:
    if not path or not text:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sequence": sequence, "text": text}
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        fh.flush()


def _append_delta_jsonl(path: Path | str | None, sequence: int, text: str) -> None:
    _append_stream_chunk_jsonl(path, sequence, text)


def _append_reasoning_jsonl(path: Path | str | None, sequence: int, text: str) -> None:
    _append_stream_chunk_jsonl(path, sequence, text)


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    result = dict(task.get("result") or {}) if isinstance(task.get("result"), dict) else task.get("result")
    if isinstance(result, dict):
        reasoning = result.pop("reasoning", None)
        result["has_reasoning"] = bool(str(reasoning or "").strip())
    return {
        "id": task.get("id"),
        "state": task.get("state"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "session_id": task.get("session_id"),
        "conversation_id": task.get("session_id"),
        "profile_id": task.get("profile_id"),
        "model_name": task.get("model_name"),
        "role": task.get("role"),
        "user_message_id": task.get("user_message_id"),
        "assistant_message_id": task.get("assistant_message_id"),
        "task_id": task.get("id"),
        "message": task.get("message"),
        "error_code": task.get("error_code"),
        "used_settings": task.get("used_settings"),
        "router_notice": task.get("router_notice"),
        "result": result,
        "stream": bool(task.get("stream")),
        "streaming_enabled": bool(task.get("stream")),
        "attachment_ids": list(task.get("attachment_ids") or []),
        "vision_route": task.get("vision_route"),
    }


def _set_attachment_status(
    attachment_ids: list[str],
    status: str,
    *,
    error: str | None = None,
) -> None:
    for attachment_id in attachment_ids:
        try:
            db.update_chat_attachment(attachment_id, status=status, error=error)
        except Exception:
            pass


def _set_worker_status(
    status_path: str,
    attachment_ids: list[str],
    state: str,
    message: str,
) -> None:
    _set_attachment_status(attachment_ids, state)
    _atomic_write_json(status_path, {"state": state, "message": message})


def _chat_worker(
    model_name: str,
    messages: list[dict[str, Any]],
    settings: dict[str, Any],
    session_id: str,
    profile_id: int | None,
    assistant_message_id: int | None,
    stream: bool,
    delta_path: str,
    reasoning_path: str,
    status_path: str,
    result_path: str,
    error_path: str,
    attachment_descriptors: list[dict[str, Any]] | None = None,
    vision_route: dict[str, Any] | None = None,
) -> None:
    attachment_descriptors = list(attachment_descriptors or [])
    attachment_ids = [str(item.get("id") or "") for item in attachment_descriptors if item.get("id")]
    image_paths = [str(item.get("path") or "") for item in attachment_descriptors if item.get("path")]
    derived_vision_context: str | None = None
    ocr_evidence: vision_context.OcrEvidence | None = None
    reasoning = ""
    done_reason: str | None = None
    eval_count: int | None = None
    try:
        service = ChatService()
        completion_model = model_name
        completion_messages = messages
        runtime_mode = str((vision_route or {}).get("mode") or "")
        if attachment_descriptors:
            ocr_mode = vision_context.normalize_ocr_assist_mode(settings.get("ocr_assist"))
            ocr_evidence = vision_context.extract_ocr_evidence(
                image_paths,
                mode=ocr_mode,
                language=str(settings.get("ocr_language") or "").strip() or None,
            )
            completion_messages = vision_context.append_ocr_evidence(messages, ocr_evidence)
            _set_worker_status(
                status_path,
                attachment_ids,
                "loading_model",
                "Loading local vision model.",
            )
            vision_model = str((vision_route or {}).get("vision_model") or model_name)
            response_model = str((vision_route or {}).get("response_model") or model_name)
            max_total_bytes = int(
                settings.get("chat_image_max_total_bytes")
                or config.DEFAULT_RUNTIME_SETTINGS["chat_image_max_total_bytes"]
            )
            if runtime_mode == "ocr_only":
                _set_worker_status(
                    status_path,
                    attachment_ids,
                    "analyzing",
                    "Extracting text locally with OCR.",
                )
                if not ocr_evidence.text:
                    raise vision_runtime.VisionRuntimeError(
                        "OCR_EMPTY_RESULT",
                        "OCR-only режим не нашёл читаемый текст.",
                    )
                completion_model = response_model
                if response_model and response_model not in {
                    vision_runtime.AUTO_ROUTER_MODEL_ID,
                    vision_runtime.LOCAL_CALCULATOR_MODEL_ID,
                    "__ocr_only__",
                }:
                    completion_messages = vision_context.append_ocr_evidence(messages, ocr_evidence)
                else:
                    completion_model = "__ocr_only__"
                    completion_messages = []
            elif runtime_mode == "vision_context":
                _set_worker_status(
                    status_path,
                    attachment_ids,
                    "analyzing",
                    "Analyzing images locally.",
                )
                analysis_messages = [
                    *completion_messages,
                    {
                        "role": "system",
                        "content": (
                            "Сначала извлеки из изображений точный визуальный контекст для другого ассистента: "
                            "объекты, читаемый текст, числа, расположение и неопределённости. "
                            "Не отвечай на исходный вопрос и не выдумывай невидимые детали."
                        ),
                    },
                ]
                derived_vision_context = sanitize_reply(
                    vision_runtime.chat_completion(
                        vision_model,
                        analysis_messages,
                        image_paths,
                        max_total_bytes=max_total_bytes,
                        **service._runtime_kwargs(vision_model, settings, vision=True),
                    )
                )
                completion_model = response_model
                completion_messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": data_envelope(
                            "vision_derived_context",
                            derived_vision_context,
                            provenance={
                                "derived": True,
                                "vision_model": vision_model,
                                "attachment_count": len(attachment_descriptors),
                            },
                            allowed_influence="auxiliary_visual_evidence_only",
                        ),
                    },
                ]
            else:
                completion_model = vision_model
            _set_worker_status(
                status_path,
                attachment_ids,
                "generating",
                "Generating answer from image context.",
            )

        if stream:
            chunks: list[str] = []
            reasoning_chunks: list[str] = []
            sequence = 0
            reasoning_sequence = 0
            streaming_started = False
            if attachment_descriptors and runtime_mode not in {"vision_context", "ocr_only"}:
                delta_source = (
                    event.content
                    for event in guard_stream_events(
                        completion_messages,
                        (
                            ollama_runtime.ChatStreamEvent(content=delta)
                            for delta in vision_runtime.chat_completion_stream(
                                completion_model,
                                completion_messages,
                                image_paths,
                                max_total_bytes=int(
                                    settings.get("chat_image_max_total_bytes")
                                    or config.DEFAULT_RUNTIME_SETTINGS["chat_image_max_total_bytes"]
                                ),
                                **service._runtime_kwargs(completion_model, settings, vision=True),
                            )
                        ),
                    )
                )
            elif runtime_mode == "ocr_only" and completion_model == "__ocr_only__":
                delta_source = iter([ocr_evidence.text if ocr_evidence else ""])
            else:
                event_source = service.chat_completion_stream_events(
                    completion_model,
                    completion_messages,
                    settings=settings,
                )
                for event in event_source:
                    if event.reasoning:
                        reasoning_chunks.append(event.reasoning)
                        reasoning = "".join(reasoning_chunks)
                        if assistant_message_id:
                            db.update_message(assistant_message_id, reasoning=reasoning)
                        reasoning_sequence += 1
                        _append_reasoning_jsonl(reasoning_path, reasoning_sequence, event.reasoning)
                    if event.done:
                        done_reason = event.done_reason
                        eval_count = event.eval_count
                    delta = event.content
                    if not delta:
                        continue
                    if not streaming_started:
                        _atomic_write_json(status_path, {"state": "streaming", "message": "Chat generation streaming."})
                        _set_attachment_status(attachment_ids, "generating")
                        streaming_started = True
                    sequence += 1
                    chunks.append(delta)
                    _append_delta_jsonl(delta_path, sequence, delta)
                    if assistant_message_id:
                        db.append_message_content(assistant_message_id, delta, status="streaming")
                delta_source = None
            if delta_source is not None:
                for delta in delta_source:
                    if not delta:
                        continue
                    if not streaming_started:
                        _atomic_write_json(status_path, {"state": "streaming", "message": "Chat generation streaming."})
                        _set_attachment_status(attachment_ids, "generating")
                        streaming_started = True
                    sequence += 1
                    chunks.append(delta)
                    _append_delta_jsonl(delta_path, sequence, delta)
                    if assistant_message_id:
                        db.append_message_content(assistant_message_id, delta, status="streaming")
            reasoning = "".join(reasoning_chunks)
            reply = sanitize_reply("".join(chunks))
        else:
            if attachment_descriptors and runtime_mode not in {"vision_context", "ocr_only"}:
                reply = sanitize_reply(
                    vision_runtime.chat_completion(
                        completion_model,
                        completion_messages,
                        image_paths,
                        max_total_bytes=int(
                            settings.get("chat_image_max_total_bytes")
                            or config.DEFAULT_RUNTIME_SETTINGS["chat_image_max_total_bytes"]
                        ),
                        **service._runtime_kwargs(completion_model, settings, vision=True),
                    )
                )
            elif runtime_mode == "ocr_only" and completion_model == "__ocr_only__":
                reply = ocr_evidence.text if ocr_evidence else ""
            else:
                completion_result = service.chat_completion_result(
                    completion_model,
                    completion_messages,
                    settings=settings,
                )
                reply = completion_result.content
                reasoning = completion_result.reasoning
                done_reason = completion_result.done_reason
                eval_count = completion_result.eval_count
        enforce_protected_output(completion_messages, reply)
        enforce_protected_output(completion_messages, reasoning)
        service.require_final_answer(
            ollama_runtime.ChatCompletionResult(
                content=reply,
                reasoning=reasoning,
                done_reason=done_reason,
                eval_count=eval_count,
            )
        )
        result_payload: dict[str, Any] = {"reply": reply}
        if reasoning:
            result_payload["reasoning"] = reasoning
        if done_reason:
            result_payload["done_reason"] = done_reason
        if eval_count is not None:
            result_payload["eval_count"] = eval_count
        if derived_vision_context:
            result_payload["vision_context"] = derived_vision_context
        if ocr_evidence:
            result_payload["ocr_evidence"] = ocr_evidence.to_dict()
        _atomic_write_json(result_path, result_payload)
        _set_attachment_status(attachment_ids, "completed")
        if session_id:
            if assistant_message_id:
                db.update_message(
                    assistant_message_id,
                    content=reply,
                    reasoning=reasoning,
                    status="completed",
                    model=completion_model,
                    error=None,
                    is_partial=False,
                )
            if profile_id:
                try:
                    maybe_compress_session_history(
                        service=service,
                        session_id=session_id,
                        profile_id=profile_id,
                        model_name=completion_model,
                        settings=settings,
                    )
                except Exception:
                    pass
    except Exception as exc:  # pragma: no cover - runtime path
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict):
            error_code = str(detail.get("code") or getattr(exc, "code", None) or "chat_generation_failed")
        else:
            error_code = str(getattr(exc, "code", None) or "chat_generation_failed")
        message = "Local model generation failed."
        safe_messages = {
            "Thinking budget exhausted before the model produced a final answer.",
            "The model completed without a final answer.",
        }
        detail_message = str(detail.get("message") or "") if isinstance(detail, dict) else ""
        if error_code == "chat_final_answer_incomplete" and detail_message in safe_messages:
            message = detail_message
        if assistant_message_id:
            try:
                db.update_message(
                    assistant_message_id,
                    status="failed",
                    model=model_name,
                    error=str(message),
                    is_partial=False,
                )
            except Exception:
                pass
        _set_attachment_status(attachment_ids, "failed", error=str(message))
        _atomic_write_json(error_path, {"code": error_code, "message": str(message)})


def _cleanup_task_files(task: dict[str, Any]) -> None:
    _safe_unlink(task.get("result_path"))
    _safe_unlink(task.get("error_path"))
    _safe_unlink(task.get("status_path"))


def _cleanup_failed_stream_artifacts(task: dict[str, Any]) -> None:
    _safe_unlink(task.get("delta_path"))
    _safe_unlink(task.get("reasoning_path"))


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
        _update_assistant_from_task(task, status="cancelled", error=task["message"])
        _set_attachment_status(list(task.get("attachment_ids") or []), "cancelled", error=task["message"])
    elif result:
        task["state"] = "completed"
        task["message"] = "Chat generation completed."
        task["error_code"] = None
        task["result"] = result
        _update_assistant_from_task(
            task,
            status="completed",
            content=str(result.get("reply") or ""),
            reasoning=str(result.get("reasoning") or ""),
            error=None,
        )
        _set_attachment_status(list(task.get("attachment_ids") or []), "completed", error=None)
    elif error:
        task["state"] = "failed"
        task["message"] = error.get("message") or "chat_generation_failed"
        task["error_code"] = error.get("code") or "chat_generation_failed"
        task["result"] = None
        _update_assistant_from_task(task, status="failed", error=task["message"])
        _set_attachment_status(list(task.get("attachment_ids") or []), "failed", error=str(task["message"]))
    else:
        task["state"] = "failed"
        task["message"] = "Chat process exited without result."
        task["error_code"] = "chat_generation_failed"
        task["result"] = None
        _update_assistant_from_task(task, status="failed", error=task["message"])
        _set_attachment_status(list(task.get("attachment_ids") or []), "failed", error=str(task["message"]))

    task["updated_at"] = _utc_now()
    task["pid"] = None
    task.pop("cancel_requested", None)
    task.pop("_process", None)
    task.pop("_monitor", None)
    _cleanup_task_files(task)
    if task.get("state") != "completed":
        _cleanup_failed_stream_artifacts(task)


def _update_assistant_from_task(
    task: dict[str, Any],
    *,
    status: str,
    content: str | None = None,
    reasoning: str | None = None,
    error: str | None = None,
) -> None:
    assistant_message_id = task.get("assistant_message_id")
    if not assistant_message_id:
        return
    try:
        updates: dict[str, Any] = {
            "status": status,
            "model": task.get("model_name"),
            "error": error,
            "is_partial": status in db.MESSAGE_ACTIVE_STATUSES,
        }
        if content is not None:
            updates["content"] = content
        if reasoning is not None:
            updates["reasoning"] = reasoning
        db.update_message(assistant_message_id, **updates)
    except Exception:
        pass


def _refresh_task_locked(task: dict[str, Any]) -> None:
    if task.get("state") in _FINAL_STATES:
        return
    status = _read_json(task.get("status_path"))
    status_state = str((status or {}).get("state") or "").strip()
    if status_state in _ACTIVE_VISION_STATES and task.get("state") not in {"cancelling", "cancelled"}:
        task["state"] = status_state
        task["message"] = str((status or {}).get("message") or "Chat generation in progress.")
        task["updated_at"] = _utc_now()
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
        process.join(timeout=CHAT_TASK_TIMEOUT_SECONDS)
        if process.is_alive():
            try:
                process.terminate()
            except Exception:
                pass
            process.join(timeout=1.5)
            if process.is_alive():
                try:
                    process.kill()
                except Exception:
                    pass
                process.join(timeout=1.0)
            with _LOCK:
                task = _TASKS.get(task_id)
                if task and task.get("state") not in _FINAL_STATES:
                    task["state"] = "failed"
                    task["message"] = "Chat generation exceeded the runtime timeout."
                    task["error_code"] = "chat_task_timeout"
                    task["result"] = None
                    task["updated_at"] = _utc_now()
                    task["pid"] = None
                    _update_assistant_from_task(task, status="failed", error=task["message"])
                    _set_attachment_status(list(task.get("attachment_ids") or []), "failed", error=task["message"])
                    task.pop("_process", None)
                    task.pop("_monitor", None)
                    _cleanup_task_files(task)
                    _cleanup_failed_stream_artifacts(task)
            return

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
    user_message_id: int | None = None,
    assistant_message_id: int | None = None,
    router_notice: str | None = None,
    attachment_descriptors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    task_id = _generate_id()
    now = _utc_now()
    if assistant_message_id:
        db.update_message(
            assistant_message_id,
            content=reply,
            status="completed",
            model=model_name,
            error=None,
            task_id=task_id,
            is_partial=False,
        )
    task = {
        "id": task_id,
        "state": "completed",
        "created_at": now,
        "updated_at": now,
        "session_id": session_id,
        "profile_id": profile_id,
        "model_name": model_name,
        "role": role,
        "user_message_id": user_message_id,
        "assistant_message_id": assistant_message_id,
        "message": "Chat generation completed.",
        "error_code": None,
        "pid": None,
        "used_settings": used_settings,
        "router_notice": router_notice,
        "result": {"reply": reply},
        "stream": False,
        "attachment_ids": [str(item.get("id")) for item in (attachment_descriptors or []) if item.get("id")],
        "vision_route": None,
    }
    for attachment_id in task["attachment_ids"]:
        db.update_chat_attachment(
            attachment_id,
            session_id=session_id,
            message_id=user_message_id,
            task_id=task_id,
            status="completed",
            error=None,
        )
    with _LOCK:
        _TASKS[task_id] = task
    return _public_task(task)


def create_failed_task(
    *,
    session_id: str,
    profile_id: int | None,
    model_name: str,
    role: str,
    used_settings: dict[str, Any],
    message: str,
    error_code: str = "chat_generation_failed",
    user_message_id: int | None = None,
    assistant_message_id: int | None = None,
    router_notice: str | None = None,
    attachment_descriptors: list[dict[str, Any]] | None = None,
    vision_route: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task_id = _generate_id()
    now = _utc_now()
    if assistant_message_id:
        db.update_message(
            assistant_message_id,
            status="failed",
            model=model_name,
            error=message,
            task_id=task_id,
            is_partial=False,
        )
    task = {
        "id": task_id,
        "state": "failed",
        "created_at": now,
        "updated_at": now,
        "session_id": session_id,
        "profile_id": profile_id,
        "model_name": model_name,
        "role": role,
        "user_message_id": user_message_id,
        "assistant_message_id": assistant_message_id,
        "message": message,
        "error_code": error_code,
        "pid": None,
        "used_settings": used_settings,
        "router_notice": router_notice,
        "result": None,
        "stream": False,
        "attachment_ids": [str(item.get("id")) for item in (attachment_descriptors or []) if item.get("id")],
        "vision_route": vision_route,
    }
    for attachment_id in task["attachment_ids"]:
        db.update_chat_attachment(
            attachment_id,
            session_id=session_id,
            message_id=user_message_id,
            task_id=task_id,
            status="failed",
            error=message,
        )
    with _LOCK:
        _TASKS[task_id] = task
    return _public_task(task)


def start_chat_task(
    *,
    session_id: str,
    profile_id: int | None,
    model_name: str,
    role: str,
    messages: list[dict[str, Any]],
    used_settings: dict[str, Any],
    user_message_id: int | None = None,
    assistant_message_id: int | None = None,
    router_notice: str | None = None,
    stream: bool = False,
    attachment_descriptors: list[dict[str, Any]] | None = None,
    vision_route: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task_id = _generate_id()
    now = _utc_now()
    descriptors = list(attachment_descriptors or [])
    attachment_ids = [str(item.get("id")) for item in descriptors if item.get("id")]
    result_path = _artifact_path(task_id, "result")
    error_path = _artifact_path(task_id, "error")
    delta_path = _artifact_path(task_id, "deltas")
    reasoning_path = _artifact_path(task_id, "reasoning")
    status_path = _artifact_path(task_id, "status")

    if assistant_message_id:
        db.update_message(
            assistant_message_id,
            status="generating",
            model=model_name,
            task_id=task_id,
            is_partial=True,
        )
    for attachment_id in attachment_ids:
        db.update_chat_attachment(
            attachment_id,
            session_id=session_id,
            message_id=user_message_id,
            task_id=task_id,
            status="preparing",
            error=None,
        )

    profile_key = _reserve_starting_slot(profile_id)
    try:
        process = _PROCESS_CTX.Process(
            target=_chat_worker,
            args=(
                model_name,
                messages,
                used_settings,
                session_id,
                profile_id,
                assistant_message_id,
                bool(stream),
                str(delta_path),
                str(reasoning_path),
                str(status_path),
                str(result_path),
                str(error_path),
                descriptors,
                vision_route,
            ),
            daemon=True,
            name=f"localgpt_chat_{task_id}",
        )
        process.start()
    except Exception:
        _release_starting_slot(profile_key)
        _safe_unlink(result_path)
        _safe_unlink(error_path)
        _safe_unlink(delta_path)
        _safe_unlink(reasoning_path)
        _safe_unlink(status_path)
        if assistant_message_id:
            db.update_message(
                assistant_message_id,
                status="failed",
                model=model_name,
                error="Failed to start chat generation process.",
                is_partial=False,
            )
        _set_attachment_status(attachment_ids, "failed", error="Failed to start chat generation process.")
        raise

    task = {
        "id": task_id,
        "state": "preparing" if attachment_ids else "generating",
        "created_at": now,
        "updated_at": now,
        "session_id": session_id,
        "profile_id": profile_id,
        "model_name": model_name,
        "role": role,
        "user_message_id": user_message_id,
        "assistant_message_id": assistant_message_id,
        "message": "Chat generation started.",
        "error_code": None,
        "pid": process.pid,
        "used_settings": used_settings,
        "router_notice": router_notice,
        "result": None,
        "result_path": str(result_path),
        "error_path": str(error_path),
        "delta_path": str(delta_path),
        "reasoning_path": str(reasoning_path),
        "status_path": str(status_path),
        "stream": bool(stream),
        "cancel_requested": False,
        "attachment_ids": attachment_ids,
        "vision_route": vision_route,
        "_process": process,
    }

    monitor = threading.Thread(target=_monitor_task, args=(task_id,), daemon=True, name=f"localgpt_chat_monitor_{task_id}")
    task["_monitor"] = monitor

    with _LOCK:
        _TASKS[task_id] = task
    _release_starting_slot(profile_key)

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


def _read_chat_task_chunks(
    task_id: str,
    *,
    path_key: str,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    if not task_id:
        return [], offset
    with _LOCK:
        task = _TASKS.get(task_id)
        chunk_path = task.get(path_key) if task else None
    if not chunk_path:
        return [], offset
    target = Path(str(chunk_path))
    if not target.exists():
        return [], offset

    chunks: list[dict[str, Any]] = []
    try:
        with target.open("rb") as fh:
            fh.seek(max(0, int(offset or 0)))
            for raw_line in fh:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict) and payload.get("text"):
                    chunks.append(
                        {
                            "sequence": payload.get("sequence"),
                            "text": str(payload.get("text") or ""),
                        }
                    )
            next_offset = fh.tell()
    except OSError:
        return chunks, offset
    return chunks, next_offset


def read_chat_task_deltas(task_id: str, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
    return _read_chat_task_chunks(task_id, path_key="delta_path", offset=offset)


def read_chat_task_reasoning(task_id: str, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
    return _read_chat_task_chunks(task_id, path_key="reasoning_path", offset=offset)


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
