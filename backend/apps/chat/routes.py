from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from datetime import datetime
from typing import Any, AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app import config, db
from app.security import ADMIN_TOKEN_HEADER, admin_token_matches, public_error_detail, require_admin_token
from app.schemas import ChatDebugPromptRequest, ChatRequest, ResetRequest
from app.services import criteria as criteria_service
from app.services import models as model_service
from backend.apps.chat import tasks as chat_tasks
from backend.apps.chat.service import (
    ChatService,
    apply_generation_budget_policy,
    build_messages,
    estimate_messages_chars,
    maybe_compress_session_history,
    normalize_model_name,
    processed_transcript_context,
    prompt_blocks,
    session_title_hint,
)
from backend.apps.chat.services import (
    attachment_storage,
    local_calculator,
    model_residency,
    model_router,
    vision_context,
    vision_runtime,
)
from backend.apps.rag import service as rag_service

router = APIRouter()
chat_service = ChatService()

CHAT_ROLE = "chat"
MISTRAL_NEMO_MODEL_ID = "mistral-nemo:12b"
CHAT_TASK_EVENT_POLL_INTERVAL_SECONDS = 0.5
CHAT_TASK_EVENT_MAX_CONNECTIONS = 3
_CHAT_TASK_EVENT_CONNECTIONS: dict[str, int] = {}
_CHAT_TASK_EVENT_CONNECTIONS_LOCK = threading.Lock()
CODE_REQUEST_RE = re.compile(
    r"(?i)(\bhtml\b|\bcss\b|\bjavascript\b|\bjs\b|\btypescript\b|\bts\b|\breact\b|\bvue\b|\bsvelte\b|"
    r"\bpython\b|\bfastapi\b|\bdocker\b|\bsql\b|код|скрипт|компонент|верстк|рефактор|отлад)",
)
MISTRAL_CODE_REQUEST_HINT = (
    "Суть запроса: пользователь просит обычный безопасный программный код. "
    "Повторяющиеся фразы в исходном тексте могут быть шумом распознавания; игнорируй повторы и извлеки требования. "
    "Это входит в задачу ассистента: не отказывайся из-за формулировки про компетенцию. "
    "Профильные и RAG-ограничения про факты, тарифы и источники не запрещают написание шаблонного кода. "
    "Служебный русский текст этой подсказки не задаёт язык ответа; используй язык исходного запроса пользователя. "
    "Если пользователь просит вернуть только код, соблюдай это."
)


def _catalog_title(model_id: str) -> str:
    target = str(model_id or "").strip()
    if target == model_router.LOCAL_CALCULATOR_TARGET:
        return "Local Calculator"
    for item in [*config.MODEL_CATALOG, *getattr(config, "UTILITY_MODEL_CATALOG", [])]:
        if item.get("id") == target:
            return str(item.get("title") or target)
    return target


def _chat_model_missing_detail(model_name: str | None = None) -> dict[str, object]:
    target = (model_name or "").strip()
    if target:
        return {
            "code": "chat_model_missing",
            "model": target,
            "message": "Модель не загружена. Загрузите модель и повторите отправку.",
        }
    return {
        "code": "chat_model_not_selected",
        "model": "",
        "message": "Нет доступных моделей. Загрузите модель и повторите отправку.",
    }


def _is_mistral_nemo_model(model_name: str | None) -> bool:
    return str(model_name or "").strip().lower() == MISTRAL_NEMO_MODEL_ID


def _looks_like_code_request(user_query: str) -> bool:
    return bool(CODE_REQUEST_RE.search(str(user_query or "")))


def _apply_mistral_code_request_hint(target_model: str, user_query: str, messages: list[dict[str, str]]) -> bool:
    if not _is_mistral_nemo_model(target_model) or not _looks_like_code_request(user_query):
        return False
    if not messages or messages[-1].get("role") != "user":
        return False
    current = str(messages[-1].get("content") or "")
    if current.startswith(MISTRAL_CODE_REQUEST_HINT):
        return False
    messages[-1] = {
        **messages[-1],
        "content": f"{MISTRAL_CODE_REQUEST_HINT}\n\nИсходный запрос пользователя:\n{current}",
    }
    return True


def _router_model_missing_detail() -> dict[str, object]:
    return {
        "code": "router_model_missing",
        "model": model_router.ROUTER_MODEL_ID,
        "message": (
            f"Router-модель {model_router.ROUTER_MODEL_ID} не установлена. "
            "Установите её в разделе моделей или выберите модель вручную."
        ),
    }


def _auto_target_missing_detail(model_name: str) -> dict[str, object]:
    title = _catalog_title(model_name)
    return {
        "code": "chat_auto_target_model_missing",
        "model": model_name,
        "message": f"Auto выбрал модель {title}, но она не установлена. Установите модель или выберите другую вручную.",
    }


def _http_exception_detail(exc: HTTPException) -> dict[str, object]:
    detail = exc.detail
    if isinstance(detail, dict):
        return detail
    return {"code": "chat_generation_failed", "message": str(detail or "chat_generation_failed")}


def _sse_event(event: str, payload: dict[str, object]) -> str:
    event_name = re.sub(r"[^A-Za-z0-9_-]", "", str(event or "")) or "message"
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_name}\ndata: {data}\n\n"


def _task_event_base(task: dict[str, object]) -> dict[str, object]:
    return {
        "task_id": task.get("task_id") or task.get("id"),
        "conversation_id": task.get("conversation_id") or task.get("session_id"),
        "assistant_message_id": task.get("assistant_message_id"),
    }


def _chat_task_not_found_detail() -> dict[str, str]:
    return {"code": "chat_task_not_found", "message": "Задача генерации ответа не найдена"}


def _mark_missing_chat_task_failed(task_id: str, *, profile_id: int, session_id: str) -> None:
    message = db.get_message_by_task_id(task_id)
    if not message or message.get("status") not in db.MESSAGE_ACTIVE_STATUSES:
        return
    session = db.get_session(str(message.get("session_id") or ""))
    if (
        str(message.get("session_id") or "") != str(session_id)
        or not session
        or int(session.get("profile_id") or 0) != int(profile_id)
    ):
        return
    db.update_message(
        message["id"],
        status="failed",
        error="Задача генерации ответа не найдена. Возможно, backend был перезапущен во время генерации.",
        is_partial=False,
    )
    for attachment in db.list_chat_attachments(task_id=task_id):
        db.update_chat_attachment(
            str(attachment["id"]),
            status="failed",
            error="Задача генерации ответа не найдена после перезапуска backend.",
        )


def _owned_chat_task(task_id: str, *, profile_id: int, session_id: str) -> dict[str, object]:
    task = chat_tasks.get_chat_task(task_id)
    if (
        not task
        or int(task.get("profile_id") or 0) != int(profile_id)
        or str(task.get("session_id") or "") != str(session_id)
    ):
        if not task:
            _mark_missing_chat_task_failed(task_id, profile_id=profile_id, session_id=session_id)
        raise HTTPException(status_code=404, detail=_chat_task_not_found_detail())
    return task


async def _chat_task_event_stream(
    task_id: str,
    request: Request,
    *,
    profile_id: int,
    session_id: str,
) -> AsyncIterator[str]:
    last_status: str | None = None
    model_selected_sent = False
    delta_offset = 0
    reasoning_offset = 0

    while True:
        task = chat_tasks.get_chat_task(task_id)
        if (
            not task
            or int(task.get("profile_id") or 0) != int(profile_id)
            or str(task.get("session_id") or "") != str(session_id)
        ):
            if not task:
                _mark_missing_chat_task_failed(task_id, profile_id=profile_id, session_id=session_id)
            yield _sse_event(
                "error",
                {
                    "status": "failed",
                    "message": "Задача генерации ответа не найдена",
                    "code": "chat_task_not_found",
                },
            )
            return

        state = str(task.get("state") or "generating")
        model_name = str(task.get("model_name") or "")
        base_payload = _task_event_base(task)

        if state not in {"completed", "failed", "error", "cancelled"} and state != last_status:
            yield _sse_event("status", {**base_payload, "status": state})
            last_status = state

        if model_name and not model_selected_sent:
            yield _sse_event("model_selected", {**base_payload, "model": model_name})
            model_selected_sent = True

        reasoning_chunks, reasoning_offset = chat_tasks.read_chat_task_reasoning(task_id, reasoning_offset)
        for chunk in reasoning_chunks:
            yield _sse_event(
                "reasoning",
                {
                    **base_payload,
                    "sequence": chunk.get("sequence"),
                    "text": chunk.get("text") or "",
                },
            )

        deltas, delta_offset = chat_tasks.read_chat_task_deltas(task_id, delta_offset)
        for delta in deltas:
            yield _sse_event(
                "delta",
                {
                    **base_payload,
                    "sequence": delta.get("sequence"),
                    "text": delta.get("text") or "",
                },
            )

        if state == "completed":
            yield _sse_event("done", {**base_payload, "status": "completed"})
            return

        if state in {"failed", "error"}:
            yield _sse_event(
                "error",
                {
                    **base_payload,
                    "status": "failed",
                    "message": task.get("message") or "Генерация ответа завершилась ошибкой.",
                    "code": task.get("error_code") or "chat_generation_failed",
                },
            )
            return

        if state == "cancelled":
            yield _sse_event("cancelled", {**base_payload, "status": "cancelled"})
            return

        if await request.is_disconnected():
            return

        await asyncio.sleep(CHAT_TASK_EVENT_POLL_INTERVAL_SECONDS)


def _reserve_chat_task_event_connection(task_id: str) -> bool:
    with _CHAT_TASK_EVENT_CONNECTIONS_LOCK:
        current = int(_CHAT_TASK_EVENT_CONNECTIONS.get(task_id) or 0)
        if current >= CHAT_TASK_EVENT_MAX_CONNECTIONS:
            return False
        _CHAT_TASK_EVENT_CONNECTIONS[task_id] = current + 1
        return True


def _release_chat_task_event_connection(task_id: str) -> None:
    with _CHAT_TASK_EVENT_CONNECTIONS_LOCK:
        remaining = int(_CHAT_TASK_EVENT_CONNECTIONS.get(task_id) or 0) - 1
        if remaining > 0:
            _CHAT_TASK_EVENT_CONNECTIONS[task_id] = remaining
        else:
            _CHAT_TASK_EVENT_CONNECTIONS.pop(task_id, None)


async def _bounded_chat_task_event_stream(
    task_id: str,
    request: Request,
    *,
    profile_id: int,
    session_id: str,
) -> AsyncIterator[str]:
    try:
        async for event in _chat_task_event_stream(
            task_id,
            request,
            profile_id=profile_id,
            session_id=session_id,
        ):
            yield event
    finally:
        _release_chat_task_event_connection(task_id)


def _require_chat_model_selected(model_name: str | None) -> str:
    target = (model_name or "").strip()
    if target:
        return target
    raise HTTPException(status_code=424, detail=_chat_model_missing_detail())


def _debug_allowed(admin_token: str | None = None) -> bool:
    return admin_token_matches(admin_token)


def _debug_prompt_metadata(prepared: dict[str, Any]) -> dict[str, object]:
    return {
        "blocks": prepared["prompt_blocks"],
        "input_chars": prepared["prompt_input_chars"],
        "message_count": len(prepared.get("messages") or []),
        "used_settings_keys": sorted(str(key) for key in (prepared.get("effective_settings") or {})),
        "profile_id": prepared["profile_id"],
        "active_model": prepared["target_model"],
        "warning_codes": [str(item) for item in (prepared.get("prompt_warnings") or [])],
    }


def _ensure_chat_model_available(model_name: str) -> None:
    target = _require_chat_model_selected(model_name)
    try:
        installed = model_service.is_model_installed(target)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        raise HTTPException(
            status_code=503,
            detail={
                "code": "ollama_unavailable",
                "message": detail.get("message") or "Ollama недоступна. Проверьте, что Ollama запущена.",
            },
        ) from exc
    if installed:
        return
    raise HTTPException(status_code=424, detail=_chat_model_missing_detail(target))


def _is_model_installed_or_503(model_name: str) -> bool:
    try:
        return model_service.is_model_installed(model_name)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        raise HTTPException(
            status_code=503,
            detail={
                "code": "ollama_unavailable",
                "message": detail.get("message") or "Ollama недоступна. Проверьте, что Ollama запущена.",
            },
        ) from exc


def _router_notice(_decision: model_router.RouterDecision) -> str:
    # Keep normal router decisions in used_settings/model_selected only.
    # Returning human text here caused success toasts after the answer completed.
    return ""


def _apply_router_settings(prepared: dict, decision: model_router.RouterDecision) -> None:
    prepared["router_decision"] = decision.as_dict()
    prepared["router_notice"] = _router_notice(decision)
    prepared["effective_settings"] = {
        **(prepared.get("effective_settings") or {}),
        **model_router.router_debug_settings(decision),
    }


def _apply_auto_router(prepared: dict) -> dict:
    selected_model = str(prepared.get("target_model") or "").strip()
    if selected_model == model_router.LOCAL_CALCULATOR_TARGET:
        calc = local_calculator.try_calculate_text(str(prepared.get("user_query") or ""), force=True)
        if calc:
            prepared["calc_result"] = f"{calc['result']}\n\n{calc['details']}".strip()
            prepared["effective_settings"] = {
                **(prepared.get("effective_settings") or {}),
                "model_selection_mode": "calculator",
                "calculator_result": calc,
                "calculator_backend_override": True,
            }
        else:
            prepared["calc_result"] = (
                "Не удалось распознать расчёт. Выберите обычную модель для текстового вопроса "
                "или напишите арифметику явно: например, `сумма 10 20`, `10 + 20`, `100 минус 7`."
            )
            prepared["effective_settings"] = {
                **(prepared.get("effective_settings") or {}),
                "model_selection_mode": "calculator",
                "calculator_backend_override": False,
                "calculator_error": "calculation_not_recognized",
            }
        return prepared

    if prepared.get("calc_result") is not None:
        prepared["effective_settings"] = {
            **(prepared.get("effective_settings") or {}),
            "model_selection_mode": "manual",
        }
        return prepared

    if not model_router.is_auto_model(selected_model):
        prepared["effective_settings"] = {
            **(prepared.get("effective_settings") or {}),
            "model_selection_mode": "manual",
        }
        prepared["effective_settings"] = model_residency.apply_target_settings(
            selected_model,
            prepared["effective_settings"],
            mode="manual",
        )
        prepared["effective_settings"] = apply_generation_budget_policy(prepared["effective_settings"])
        return prepared

    if not _is_model_installed_or_503(model_router.ROUTER_MODEL_ID):
        raise HTTPException(status_code=424, detail=_router_model_missing_detail())

    auto_effective_settings = dict(prepared.get("effective_settings") or {})
    auto_effective_settings.pop("ollama_keep_alive", None)
    auto_effective_settings.pop("ollama_keep_alive_effective", None)
    decision = model_router.route_model(
        str(prepared.get("user_query") or ""),
        {
            "profile_id": prepared.get("profile_id"),
            "session_id": prepared.get("session_id"),
            "role": prepared.get("role_key"),
            "rag_enabled": bool((prepared.get("effective_settings") or {}).get("rag_enabled_effective")),
            "recent_user_queries": prepared.get("recent_user_queries") or [],
            "has_transcript_context": bool(prepared.get("transcript_text")),
            "criteria_count": len(prepared.get("active_criteria") or []),
        },
        settings=auto_effective_settings,
    )
    if decision.target_model == model_router.LOCAL_CALCULATOR_TARGET:
        decision = model_router.RouterDecision(
            intent="unknown",
            target_model=model_router.FALLBACK_TARGET_MODEL,
            confidence=0.0,
            reason="Local Calculator доступен только при ручном выборе в селекте.",
            fallback=True,
            fallback_reason="calculator_manual_only",
            raw_response=decision.raw_response,
            runtime_debug=decision.runtime_debug,
        )
    _apply_router_settings(prepared, decision)

    if not _is_model_installed_or_503(decision.target_model):
        raise HTTPException(status_code=424, detail=_auto_target_missing_detail(decision.target_model))

    prepared["target_model"] = decision.target_model
    target_settings = dict(prepared.get("effective_settings") or {})
    target_settings.pop("ollama_keep_alive", None)
    target_settings.pop("ollama_keep_alive_effective", None)
    target_overrides = (
        db.effective_settings(int(prepared["profile_id"]), decision.target_model, config.DEFAULT_SETTINGS).get("overrides")
        or {}
    )
    if target_overrides.get("ollama_keep_alive"):
        target_settings["ollama_keep_alive"] = target_overrides["ollama_keep_alive"]
    for key in ("ollama_think", "output_tokens", "thinking_tokens"):
        if target_overrides.get(key) is not None:
            target_settings[key] = target_overrides[key]
    prepared["effective_settings"] = model_residency.apply_target_settings(
        decision.target_model,
        target_settings,
        mode="auto",
    )
    prepared["effective_settings"] = apply_generation_budget_policy(prepared["effective_settings"])
    return prepared


def _get_profile_or_404(profile_id: int) -> dict:
    profile = db.get_profile(profile_id)
    if not profile or not profile.get("is_active", 1):
        raise HTTPException(status_code=404, detail="profile_not_found")
    return profile


def _prepare_chat_request(req: ChatRequest) -> dict:
    session_id = (req.session_id or "").strip() or None
    profile_id = req.profile_id
    user_query = (req.query or "").strip() or "проанализируй"
    transcript_text = (req.transcript or "").strip()
    role_key = CHAT_ROLE
    session = None

    if session_id:
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session_not_found")
        profile_id = session["profile_id"]
        desired_model = normalize_model_name(req.model or req.model_name, fallback=session.get("model_name"))
        desired_model = _require_chat_model_selected(desired_model)
        if desired_model != session.get("model_name"):
            session = db.update_session(session_id, model_name=desired_model) or session
        role_key = CHAT_ROLE
        model_name = session["model_name"]
    else:
        if profile_id is None:
            raise HTTPException(status_code=400, detail="profile_id_required")
        _get_profile_or_404(profile_id)
        model_name = normalize_model_name(req.model or req.model_name, fallback=config.SETTINGS.model)
        model_name = _require_chat_model_selected(model_name)
        title = session_title_hint(req.title, req.query)
        session = db.create_session(profile_id, title=title, model_name=model_name, role=CHAT_ROLE)
        session_id = session["id"]

    model_name = session["model_name"] if session else normalize_model_name(req.model or req.model_name)
    target_model = _require_chat_model_selected(normalize_model_name(model_name, fallback=config.SETTINGS.model))
    profile = _get_profile_or_404(int(profile_id))
    profile_preferences = profile.get("preferences") or {}
    profile_system_prompt = str(((profile_preferences.get("chat") or {}).get("system_prompt") or "")).strip()
    settings_bundle = db.effective_settings(profile_id, model_name, config.DEFAULT_SETTINGS)  # type: ignore[arg-type]
    effective_settings = apply_generation_budget_policy(settings_bundle.get("effective") or {})
    mem_turns = int(effective_settings.get("mem_turns") or config.SETTINGS.mem_turns)
    history = db.get_messages(session_id, limit_pairs=mem_turns) if session_id else []
    summary_limit = int(effective_settings.get("summary_memory_limit") or 0)
    summary_memory = (
        db.list_session_summaries(session_id, limit=summary_limit)
        if session_id and effective_settings.get("summary_memory_enabled", True) and summary_limit > 0
        else []
    )
    rag_chunks = []
    rag_context = ""
    rag_diagnostics: dict[str, Any] = {}
    rag_enabled = bool(effective_settings.get("rag_enabled", False))
    history_user_queries = [
        str(item.get("content") or "")
        for item in history
        if item.get("role") == "user" and str(item.get("content") or "").strip()
    ][-3:]
    if rag_enabled:
        rag_top_k = int(effective_settings.get("rag_top_k") or 5)
        rag_max_chars = int(effective_settings.get("rag_max_context_chars") or 6000)
        rag_query = "\n".join([user_query, *reversed(history_user_queries)]).strip()
        rag_result = rag_service.search_with_diagnostics(int(profile_id), rag_query or user_query, top_k=rag_top_k)
        rag_chunks = rag_result["results"]
        rag_diagnostics = rag_result["diagnostics"]
        rag_context = rag_service.build_context(
            rag_chunks,
            max_chars=rag_max_chars,
            diagnostics=rag_diagnostics,
        )
    effective_settings = {
        **effective_settings,
        "rag_enabled_effective": rag_enabled,
        "rag_chunks_used": len(rag_chunks),
        "rag_context_chars": len(rag_context or ""),
        "rag_retrieval_strategy": rag_service.retrieval_strategy(),
        "rag_evidence_status": rag_diagnostics.get("overall_status") if rag_diagnostics else "disabled",
    }

    request_criteria = [c for c in (req.criteria or []) if isinstance(c, str)]
    cleaned_criteria = criteria_service.normalize_criteria_list(request_criteria) if request_criteria else []
    if cleaned_criteria and session_id:
        db.save_session_criteria(session_id, cleaned_criteria)
    stored_criteria = db.get_session_criteria(session_id) if session_id else []
    active_criteria = cleaned_criteria or stored_criteria or []

    latest_transcript = None
    if not transcript_text and session_id:
        latest_transcript = db.get_latest_transcript_for_session(session_id)
        max_transcript_chars = int(effective_settings.get("max_transcript_chars") or 24000)
        transcript_text, transcript_warnings = processed_transcript_context(latest_transcript, max_transcript_chars)
    else:
        transcript_warnings = []

    calc = local_calculator.try_calculate_text(user_query, force=True) if target_model == model_router.LOCAL_CALCULATOR_TARGET else None
    calc_result = f"{calc['result']}\n\n{calc['details']}".strip() if calc else None
    if calc:
        effective_settings = {
            **effective_settings,
            "calculator_result": calc,
            "calculator_backend_override": True,
        }
    messages = build_messages(
        role=role_key,
        user_query=user_query,
        context=req.context,
        profile_system_prompt=profile_system_prompt,
        transcript=None if latest_transcript else transcript_text,
        processed_transcript=transcript_text if latest_transcript else None,
        criteria=active_criteria,
        history=history,
        summary_memory=summary_memory,
        rag_context=rag_context,
    )
    prompt_input_chars = estimate_messages_chars(messages)
    num_ctx = int(effective_settings.get("num_ctx") or config.SETTINGS.num_ctx)
    output_tokens = int(effective_settings.get("provider_num_predict") or effective_settings.get("output_tokens") or 1)
    prompt_budget_chars = min(256_000, max(8_000, (num_ctx - output_tokens) * 4))
    if prompt_input_chars > prompt_budget_chars:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "chat_prompt_budget_exceeded",
                "max_chars": prompt_budget_chars,
            },
        )
    if _apply_mistral_code_request_hint(target_model, user_query, messages):
        effective_settings = {
            **effective_settings,
            "mistral_code_request_hint": True,
        }
    blocks = prompt_blocks(
        context=req.context,
        profile_system_prompt=profile_system_prompt,
        summary_memory=summary_memory,
        rag_context=rag_context,
        processed_transcript=transcript_text if latest_transcript else None,
        transcript=None if latest_transcript else transcript_text,
        criteria=active_criteria,
        history=history,
        user_query=user_query,
    )

    return {
        "session_id": session_id,
        "profile_id": profile_id,
        "user_query": user_query,
        "transcript_text": transcript_text,
        "role_key": role_key,
        "session": session,
        "target_model": target_model,
        "effective_settings": effective_settings,
        "active_criteria": active_criteria,
        "messages": messages,
        "prompt_blocks": blocks,
        "prompt_input_chars": prompt_input_chars,
        "prompt_budget_chars": prompt_budget_chars,
        "summary_memory": summary_memory,
        "profile_system_prompt": profile_system_prompt,
        "rag_chunks": rag_chunks,
        "rag_context": rag_context,
        "rag_diagnostics": rag_diagnostics,
        "recent_user_queries": history_user_queries,
        "prompt_warnings": transcript_warnings,
        "calc_result": calc_result,
    }


@router.post("/chat")
def chat(req: ChatRequest):
    started = time.perf_counter()
    session_id = None
    profile_id = req.profile_id
    user_query = (req.query or "").strip() or "проанализируй"
    transcript_text = (req.transcript or "").strip()
    role_key = CHAT_ROLE
    target_model: str | None = None
    active_criteria: list[str] = []

    def _log(status: str, reply: str | None = None, error: str | None = None) -> None:
        payload = {
            "ts": datetime.utcnow().isoformat(),
            "status": status,
            "session_id": session_id,
            "profile_id": profile_id,
            "model": target_model,
            "role": role_key,
            "query": user_query,
            "criteria_count": len(active_criteria),
            "transcript_chars": len(transcript_text),
            "reply": reply,
            "error": error,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
        chat_service.log_chat_event(payload)

    try:
        if getattr(req, "attachment_ids", None):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "VISION_TASK_ENDPOINT_REQUIRED",
                    "message": "Запросы с изображениями выполняются через /chat/tasks.",
                },
            )
        prepared = _apply_auto_router(_prepare_chat_request(req))
        session_id = prepared["session_id"]
        profile_id = prepared["profile_id"]
        user_query = prepared["user_query"]
        transcript_text = prepared["transcript_text"]
        role_key = prepared["role_key"]
        target_model = prepared["target_model"]
        active_criteria = prepared["active_criteria"]
        effective_settings = prepared["effective_settings"]
        calc_result = prepared["calc_result"]
        messages = prepared["messages"]
        prompt_warnings = prepared.get("prompt_warnings") or []
        router_notice = prepared.get("router_notice")

        if calc_result is not None:
            if session_id:
                db.add_message(session_id, "user", user_query)
                db.add_message(session_id, "assistant", calc_result)
            _log("ok", reply=calc_result)
            return {
                "reply": calc_result,
                "session_id": session_id,
                "profile_id": profile_id,
                "model_name": target_model,
                "role": role_key,
                "used_settings": effective_settings,
                "warnings": prompt_warnings,
                "router_notice": router_notice,
            }

        _ensure_chat_model_available(target_model)
        completion = chat_service.chat_completion_result(target_model, messages, settings=effective_settings)
        text = completion.content

        if session_id:
            db.add_message(session_id, "user", user_query)
            db.add_message(session_id, "assistant", text, reasoning=completion.reasoning)
            try:
                maybe_compress_session_history(
                    service=chat_service,
                    session_id=session_id,
                    profile_id=profile_id,
                    model_name=target_model,
                    settings=effective_settings,
                )
            except Exception as exc:
                chat_service.log_chat_event(
                    {
                        "ts": datetime.utcnow().isoformat(),
                        "status": "memory_compression_error",
                        "session_id": session_id,
                        "profile_id": profile_id,
                        "model": target_model,
                        "error": str(exc),
                    }
                )

        _log("ok", reply=text)
        return {
            "reply": text,
            "session_id": session_id,
            "profile_id": profile_id,
            "model_name": target_model,
            "role": role_key,
            "used_settings": effective_settings,
            "warnings": prompt_warnings,
            "router_notice": router_notice,
            "has_reasoning": bool(completion.reasoning.strip()),
        }
    except HTTPException as exc:
        _log("error", error=str(exc.detail))
        raise
    except Exception as e:
        _log("error", error=str(e))
        raise HTTPException(
            status_code=502,
            detail=public_error_detail("chat_generation_failed", "Local model generation failed."),
        ) from e


@router.post("/chat/tasks")
def start_chat_task(req: ChatRequest):
    prepared = _prepare_chat_request(req)
    session_id = prepared["session_id"]
    profile_id = prepared["profile_id"]
    user_query = prepared["user_query"]
    role_key = prepared["role_key"]
    target_model = prepared["target_model"]
    effective_settings = prepared["effective_settings"]
    prompt_warnings = prepared.get("prompt_warnings") or []
    stream_requested = bool(getattr(req, "stream", False))
    effective_settings = {**effective_settings, "streaming_enabled": stream_requested}
    attachment_ids = list(dict.fromkeys(str(item or "").strip() for item in (req.attachment_ids or []) if str(item or "").strip()))
    attachment_descriptors: list[dict[str, object]] = []
    vision_route: dict[str, object] | None = None
    preflight_error: HTTPException | None = None
    if attachment_ids:
        try:
            attachment_descriptors = attachment_storage.prepare_chat_attachments(
                attachment_ids,
                profile_id=int(profile_id),
                session_id=str(session_id),
                settings=effective_settings,
            )
            model_state = model_service.list_models()
            ocr_mode = vision_context.normalize_ocr_assist_mode(effective_settings.get("ocr_assist"))
            installed_records = model_state.get("installed") or []
            installed_names = {
                str(item.get("name") or "")
                for item in installed_records
                if isinstance(item, dict) and item.get("name")
            }
            if ocr_mode == "ocr_only":
                response_model = (
                    target_model
                    if target_model in installed_names
                    else "__ocr_only__"
                )
                vision_route = {
                    "mode": "ocr_only",
                    "vision_model": "",
                    "response_model": response_model,
                    "reason": "explicit_ocr_only_degraded_mode",
                    "capabilities": ["ocr"],
                }
                target_model = response_model
            else:
                plan = vision_runtime.resolve_vision_route(
                    selected_model=target_model,
                    configured_vision_model=str(effective_settings.get("vision_model") or "auto"),
                    installed_models=installed_records,
                )
                if (
                    plan.mode == "vision_context"
                    and str(effective_settings.get("vision_fallback") or "vision_context") == "error"
                ):
                    raise vision_runtime.VisionRuntimeError(
                        "VISION_TEXT_MODEL_FALLBACK_DISABLED",
                        "Выбранная chat-модель не поддерживает изображения, а vision-context fallback отключён.",
                        details={
                            "response_model": plan.response_model,
                            "vision_model": plan.vision_model,
                        },
                    )
                vision_route = plan.to_dict()
                target_model = plan.response_model
            prepared["target_model"] = target_model
            prepared["vision_route"] = vision_route
            prepared["effective_settings"] = {
                **effective_settings,
                "vision_route": vision_route,
                "vision_attachment_count": len(attachment_descriptors),
                "vision_total_bytes": sum(int(item.get("size_bytes") or 0) for item in attachment_descriptors),
            }
            effective_settings = prepared["effective_settings"]
        except attachment_storage.AttachmentStorageError as exc:
            preflight_error = HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.message, **exc.details},
            )
        except vision_runtime.VisionRuntimeError as exc:
            preflight_error = HTTPException(
                status_code=424,
                detail={"code": exc.code, "message": exc.message, **exc.details},
            )

    user_message = db.add_message(session_id, "user", user_query) if session_id else {}
    assistant_message = (
        db.create_assistant_message(session_id, model=target_model)
        if session_id
        else {}
    )
    user_message_id = int(user_message["id"]) if user_message.get("id") is not None else None
    assistant_message_id = int(assistant_message["id"]) if assistant_message.get("id") is not None else None

    def _failed_task_from_http(exc: HTTPException) -> dict[str, object]:
        detail = _http_exception_detail(exc)
        message = str(detail.get("message") or detail.get("detail") or detail.get("code") or exc.detail)
        code = str(detail.get("code") or "chat_generation_failed")
        failed_model = str(detail.get("model") or target_model or "")
        task = chat_tasks.create_failed_task(
            session_id=session_id or "",
            profile_id=profile_id,
            model_name=failed_model,
            role=role_key,
            used_settings=effective_settings,
            message=message,
            error_code=code,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            router_notice=prepared.get("router_notice"),
            attachment_descriptors=attachment_descriptors,
            vision_route=vision_route,
        )
        task["warnings"] = prompt_warnings
        return task

    if preflight_error is not None:
        return _failed_task_from_http(preflight_error)

    if not attachment_descriptors:
        try:
            prepared = _apply_auto_router(prepared)
        except HTTPException as exc:
            return _failed_task_from_http(exc)

    target_model = prepared["target_model"]
    effective_settings = prepared["effective_settings"]
    calc_result = prepared["calc_result"]
    messages = prepared["messages"]
    router_notice = prepared.get("router_notice")
    effective_settings = {**effective_settings, "streaming_enabled": stream_requested}

    if assistant_message_id:
        db.update_message(assistant_message_id, model=target_model)

    if calc_result is not None:
        return chat_tasks.create_completed_task(
            session_id=session_id or "",
            profile_id=profile_id,
            model_name=target_model,
            role=role_key,
            used_settings=effective_settings,
            reply=calc_result,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            router_notice=router_notice,
            attachment_descriptors=attachment_descriptors,
        )

    if not attachment_descriptors:
        try:
            _ensure_chat_model_available(target_model)
        except HTTPException as exc:
            return _failed_task_from_http(exc)

    try:
        task = chat_tasks.start_chat_task(
            session_id=session_id or "",
            profile_id=profile_id,
            model_name=target_model,
            role=role_key,
            messages=messages,
            used_settings=effective_settings,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            router_notice=router_notice,
            stream=stream_requested,
            attachment_descriptors=attachment_descriptors,
            vision_route=vision_route,
        )
        task["warnings"] = prompt_warnings
        return task
    except chat_tasks.ChatTaskCapacityError as exc:
        task = chat_tasks.create_failed_task(
            session_id=session_id or "",
            profile_id=profile_id,
            model_name=target_model,
            role=role_key,
            used_settings=effective_settings,
            message=exc.message,
            error_code=exc.code,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            router_notice=router_notice,
            attachment_descriptors=attachment_descriptors,
            vision_route=vision_route,
        )
        task["warnings"] = prompt_warnings
        return task
    except Exception as exc:
        task = chat_tasks.create_failed_task(
            session_id=session_id or "",
            profile_id=profile_id,
            model_name=target_model,
            role=role_key,
            used_settings=effective_settings,
            message="Local model task failed to start.",
            error_code="chat_task_start_failed",
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            router_notice=router_notice,
            attachment_descriptors=attachment_descriptors,
            vision_route=vision_route,
        )
        task["warnings"] = prompt_warnings
        return task


@router.get("/chat/tasks/{task_id}")
def get_chat_task(
    task_id: str,
    profile_id: int = Query(...),
    session_id: str = Query(..., min_length=1, max_length=128),
) -> dict[str, object]:
    return _owned_chat_task(task_id, profile_id=profile_id, session_id=session_id)


@router.get("/chat/messages/{message_id}/reasoning")
def get_chat_message_reasoning(message_id: int, profile_id: int = Query(...)) -> dict[str, object]:
    _get_profile_or_404(profile_id)
    message = db.get_message(message_id)
    if not message or str(message.get("role") or "") != "assistant":
        raise HTTPException(
            status_code=404,
            detail={"code": "chat_reasoning_not_found", "message": "Reasoning is not available for this message."},
        )
    session = db.get_session(str(message.get("session_id") or ""))
    if not session or int(session.get("profile_id") or 0) != int(profile_id):
        raise HTTPException(
            status_code=403,
            detail={"code": "chat_reasoning_profile_mismatch", "message": "Message does not belong to this profile."},
        )
    reasoning = str(message.get("reasoning") or "").strip()
    if not reasoning:
        raise HTTPException(
            status_code=404,
            detail={"code": "chat_reasoning_not_found", "message": "Reasoning is not available for this message."},
        )
    return {
        "message_id": int(message["id"]),
        "session_id": str(message["session_id"]),
        "reasoning": reasoning,
    }


@router.get("/chat/tasks/{task_id}/events")
def get_chat_task_events(
    task_id: str,
    request: Request,
    profile_id: int = Query(...),
    session_id: str = Query(..., min_length=1, max_length=128),
) -> StreamingResponse:
    _owned_chat_task(task_id, profile_id=profile_id, session_id=session_id)
    if not _reserve_chat_task_event_connection(task_id):
        raise HTTPException(
            status_code=429,
            detail={
                "code": "chat_task_event_connection_limit",
                "message": "Слишком много подключений к потоку задачи.",
            },
        )
    return StreamingResponse(
        _bounded_chat_task_event_stream(task_id, request, profile_id=profile_id, session_id=session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/tasks/{task_id}/cancel")
def cancel_chat_task(
    task_id: str,
    profile_id: int = Query(...),
    session_id: str = Query(..., min_length=1, max_length=128),
) -> dict[str, object]:
    _owned_chat_task(task_id, profile_id=profile_id, session_id=session_id)
    task = chat_tasks.cancel_chat_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=_chat_task_not_found_detail())
    return task


@router.get("/chat/debug/prompt")
def debug_prompt_get(
    session_id: str | None = None,
    profile_id: int | None = None,
    query: str = "debug",
    model_name: str | None = None,
    admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
):
    require_admin_token(admin_token)
    req = ChatRequest(query=query, session_id=session_id, profile_id=profile_id, model_name=model_name)
    prepared = _prepare_chat_request(req)
    return _debug_prompt_metadata(prepared)


@router.post("/chat/debug/prompt")
def debug_prompt_post(
    req: ChatDebugPromptRequest,
    admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
):
    require_admin_token(req.admin_token or admin_token)
    prepared = _prepare_chat_request(req)
    return _debug_prompt_metadata(prepared)


@router.get("/chat/debug/pipeline")
def debug_pipeline(
    run_id: int,
    admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
):
    require_admin_token(admin_token)
    run = db.get_pipeline_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="pipeline_run_not_found")
    return {
        "id": run.get("id"),
        "transcript_id": run.get("transcript_id"),
        "status": run.get("status"),
        "action": run.get("action"),
        "summary_chars": len(str(run.get("summary") or "")),
        "cleaned_transcript_chars": len(str(run.get("cleaned_transcript") or "")),
        "has_structured_json": run.get("structured_json") is not None,
        "created_at": run.get("created_at"),
        "updated_at": run.get("updated_at"),
    }


@router.post("/session/reset")
def reset_session(req: ResetRequest):
    require_admin_token(req.admin_token)
    sid = req.session_id.strip()
    attachment_storage.delete_session_attachments(sid)
    db.reset_session(sid)
    return {"ok": True}
