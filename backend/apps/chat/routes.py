from __future__ import annotations

import re
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app import config, db
from app.schemas import ChatDebugPromptRequest, ChatRequest, ResetRequest
from app.services import criteria as criteria_service
from app.services import models as model_service
from backend.apps.chat import tasks as chat_tasks
from backend.apps.chat.service import (
    ChatService,
    build_messages,
    estimate_messages_chars,
    maybe_compress_session_history,
    normalize_model_name,
    processed_transcript_context,
    prompt_blocks,
    session_title_hint,
)
from backend.apps.chat.services import local_calculator, model_router, ollama_runtime
from backend.apps.rag import service as rag_service

router = APIRouter()
chat_service = ChatService()

CHAT_ROLE = "chat"
MISTRAL_NEMO_MODEL_ID = "mistral-nemo:12b"
CODE_REQUEST_RE = re.compile(
    r"(?i)(\bhtml\b|\bcss\b|\bjavascript\b|\bjs\b|\btypescript\b|\bts\b|\breact\b|\bvue\b|\bsvelte\b|"
    r"\bpython\b|\bfastapi\b|\bdocker\b|\bsql\b|код|скрипт|компонент|верстк|рефактор|отлад)",
)
MISTRAL_CODE_REQUEST_HINT = (
    "Суть запроса: пользователь просит обычный безопасный программный код. "
    "Повторяющиеся фразы в исходном тексте могут быть шумом распознавания; игнорируй повторы и извлеки требования. "
    "Это входит в задачу ассистента: не отказывайся из-за формулировки про компетенцию. "
    "Профильные и RAG-ограничения про факты, тарифы и источники не запрещают написание шаблонного кода. "
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


def _require_chat_model_selected(model_name: str | None) -> str:
    target = (model_name or "").strip()
    if target:
        return target
    raise HTTPException(status_code=424, detail=_chat_model_missing_detail())


def _debug_allowed(admin_token: str | None = None) -> bool:
    if config.SETTINGS.env in {"local", "dev", "development"}:
        return True
    return bool(config.SETTINGS.admin_token and admin_token == config.SETTINGS.admin_token)


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


def _router_notice(decision: model_router.RouterDecision) -> str:
    if decision.target_model == model_router.LOCAL_CALCULATOR_TARGET:
        return f"Auto выбрал: Local Calculator — {decision.reason or 'точный арифметический расчёт.'}"
    title = _catalog_title(decision.target_model)
    if decision.fallback:
        if decision.fallback_reason == "invalid_json":
            return f"Auto не смог корректно разобрать тип задачи. Использована основная модель {title}."
        if decision.fallback_reason == "low_confidence":
            return f"Auto не уверен в типе задачи. Использована основная модель {title}."
        return f"Auto не смог уверенно определить тип задачи. Использована основная модель {title}."
    return f"Auto выбрал: {title} — {decision.reason}"


def _apply_router_settings(prepared: dict, decision: model_router.RouterDecision) -> None:
    prepared["router_decision"] = decision.as_dict()
    prepared["router_notice"] = _router_notice(decision)
    prepared["effective_settings"] = {
        **(prepared.get("effective_settings") or {}),
        **model_router.router_debug_settings(decision),
    }


def _apply_auto_router(prepared: dict) -> dict:
    selected_model = str(prepared.get("target_model") or "").strip()
    if prepared.get("calc_result") is not None:
        if model_router.is_auto_model(selected_model):
            decision = model_router.RouterDecision(
                intent="calculation",
                target_model=model_router.LOCAL_CALCULATOR_TARGET,
                confidence=1.0,
                reason="Запрос содержит явный арифметический расчёт.",
                backend_override=True,
                backend_override_reason="deterministic_calculation",
            )
            _apply_router_settings(prepared, decision)
            prepared["target_model"] = model_router.LOCAL_CALCULATOR_TARGET
        else:
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
        prepared["effective_settings"] = ollama_runtime.apply_keep_alive_setting(
            selected_model,
            prepared["effective_settings"],
        )
        return prepared

    if not _is_model_installed_or_503(model_router.ROUTER_MODEL_ID):
        raise HTTPException(status_code=424, detail=_router_model_missing_detail())

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
    )
    _apply_router_settings(prepared, decision)

    if decision.target_model == model_router.LOCAL_CALCULATOR_TARGET:
        try:
            calc = local_calculator.calculate(decision.calculation_request, str(prepared.get("user_query") or ""))
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "local_calculator_failed", "message": f"Не удалось выполнить локальный расчёт: {exc}"},
            ) from exc
        prepared["target_model"] = model_router.LOCAL_CALCULATOR_TARGET
        prepared["calc_result"] = f"{calc['result']}\n\n{calc['details']}".strip()
        prepared["effective_settings"] = {
            **prepared["effective_settings"],
            "calculator_result": calc,
        }
        return prepared

    if not _is_model_installed_or_503(decision.target_model):
        raise HTTPException(status_code=424, detail=_auto_target_missing_detail(decision.target_model))

    prepared["target_model"] = decision.target_model
    prepared["effective_settings"] = ollama_runtime.apply_keep_alive_setting(
        decision.target_model,
        prepared.get("effective_settings") or {},
    )
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
    effective_settings = settings_bundle.get("effective") or {}
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
    rag_enabled = bool(effective_settings.get("rag_enabled", False))
    history_user_queries = [
        str(item.get("content") or "")
        for item in history
        if item.get("role") == "user" and str(item.get("content") or "").strip()
    ][-3:]
    if rag_enabled:
        rag_top_k = int(effective_settings.get("rag_top_k") or 5)
        rag_max_chars = int(effective_settings.get("rag_max_context_chars") or 6000)
        rag_query = "\n".join([*history_user_queries, user_query]).strip()
        rag_chunks = rag_service.search(int(profile_id), rag_query or user_query, top_k=rag_top_k)
        rag_context = rag_service.build_context(rag_chunks, max_chars=rag_max_chars)
    effective_settings = {
        **effective_settings,
        "rag_enabled_effective": rag_enabled,
        "rag_chunks_used": len(rag_chunks),
        "rag_context_chars": len(rag_context or ""),
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

    calc = local_calculator.try_calculate_text(user_query)
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
        "prompt_input_chars": estimate_messages_chars(messages),
        "summary_memory": summary_memory,
        "profile_system_prompt": profile_system_prompt,
        "rag_chunks": rag_chunks,
        "rag_context": rag_context,
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
        text = chat_service.chat_completion(target_model, messages, settings=effective_settings)

        if session_id:
            db.add_message(session_id, "user", user_query)
            db.add_message(session_id, "assistant", text)
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
        }
    except HTTPException as exc:
        _log("error", error=str(exc.detail))
        raise
    except Exception as e:
        _log("error", error=str(e))
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")


@router.post("/chat/tasks")
def start_chat_task(req: ChatRequest):
    prepared = _apply_auto_router(_prepare_chat_request(req))
    session_id = prepared["session_id"]
    profile_id = prepared["profile_id"]
    user_query = prepared["user_query"]
    role_key = prepared["role_key"]
    target_model = prepared["target_model"]
    effective_settings = prepared["effective_settings"]
    calc_result = prepared["calc_result"]
    messages = prepared["messages"]
    prompt_warnings = prepared.get("prompt_warnings") or []
    router_notice = prepared.get("router_notice")

    if calc_result is not None:
        if session_id:
            db.add_message(session_id, "user", user_query)
            db.add_message(session_id, "assistant", calc_result)
        return chat_tasks.create_completed_task(
            session_id=session_id or "",
            profile_id=profile_id,
            model_name=target_model,
            role=role_key,
            used_settings=effective_settings,
            reply=calc_result,
            router_notice=router_notice,
        )

    try:
        _ensure_chat_model_available(target_model)
        task = chat_tasks.start_chat_task(
            session_id=session_id or "",
            profile_id=profile_id,
            model_name=target_model,
            role=role_key,
            messages=messages,
            used_settings=effective_settings,
            router_notice=router_notice,
        )
        if session_id:
            db.add_message(session_id, "user", user_query)
        task["warnings"] = prompt_warnings
        return task
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM task error: {exc}") from exc


@router.get("/chat/tasks/{task_id}")
def get_chat_task(task_id: str) -> dict[str, object]:
    task = chat_tasks.get_chat_task(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail={"code": "chat_task_not_found", "message": "Задача генерации ответа не найдена"},
        )
    return task


@router.post("/chat/tasks/{task_id}/cancel")
def cancel_chat_task(task_id: str) -> dict[str, object]:
    task = chat_tasks.cancel_chat_task(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail={"code": "chat_task_not_found", "message": "Задача генерации ответа не найдена"},
        )
    return task


@router.get("/chat/debug/prompt")
def debug_prompt_get(
    session_id: str | None = None,
    profile_id: int | None = None,
    query: str = "debug",
    model_name: str | None = None,
    admin_token: str | None = Query(default=None),
):
    if not _debug_allowed(admin_token):
        raise HTTPException(status_code=403, detail="forbidden")
    req = ChatRequest(query=query, session_id=session_id, profile_id=profile_id, model_name=model_name)
    prepared = _prepare_chat_request(req)
    return {
        "messages": prepared["messages"],
        "blocks": prepared["prompt_blocks"],
        "input_chars": prepared["prompt_input_chars"],
        "used_settings": prepared["effective_settings"],
        "active_profile": db.get_profile(prepared["profile_id"]),
        "active_model": prepared["target_model"],
        "warnings": prepared.get("prompt_warnings") or [],
    }


@router.post("/chat/debug/prompt")
def debug_prompt_post(req: ChatDebugPromptRequest):
    if not _debug_allowed(req.admin_token):
        raise HTTPException(status_code=403, detail="forbidden")
    prepared = _prepare_chat_request(req)
    return {
        "messages": prepared["messages"],
        "blocks": prepared["prompt_blocks"],
        "input_chars": prepared["prompt_input_chars"],
        "used_settings": prepared["effective_settings"],
        "active_profile": db.get_profile(prepared["profile_id"]),
        "active_model": prepared["target_model"],
        "warnings": prepared.get("prompt_warnings") or [],
    }


@router.get("/chat/debug/pipeline")
def debug_pipeline(run_id: int, admin_token: str | None = Query(default=None)):
    if not _debug_allowed(admin_token):
        raise HTTPException(status_code=403, detail="forbidden")
    run = db.get_pipeline_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="pipeline_run_not_found")
    return run


@router.post("/session/reset")
def reset_session(req: ResetRequest):
    if config.SETTINGS.admin_token and req.admin_token != config.SETTINGS.admin_token:
        raise HTTPException(status_code=403, detail="forbidden")
    sid = req.session_id.strip()
    db.reset_session(sid)
    return {"ok": True}
