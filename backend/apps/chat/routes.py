from __future__ import annotations

import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app import config, db
from app.roles import normalize_role
from app.schemas import ChatDebugPromptRequest, ChatRequest, ResetRequest
from app.services import criteria as criteria_service
from app.services import models as model_service
from backend.apps.chat import tasks as chat_tasks
from backend.apps.chat.service import (
    ChatService,
    build_messages,
    evaluate_math_expression,
    estimate_messages_chars,
    maybe_compress_session_history,
    normalize_model_name,
    processed_transcript_context,
    prompt_blocks,
    session_title_hint,
)
from backend.apps.rag import service as rag_service

router = APIRouter()
chat_service = ChatService()


def _debug_allowed(admin_token: str | None = None) -> bool:
    if config.SETTINGS.env in {"local", "dev", "development"}:
        return True
    return bool(config.SETTINGS.admin_token and admin_token == config.SETTINGS.admin_token)


def _ensure_chat_model_available(model_name: str) -> None:
    try:
        installed = model_service.is_model_installed(model_name)
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
    raise HTTPException(
        status_code=424,
        detail={
            "code": "chat_model_missing",
            "model": model_name,
            "message": "Нет загруженных моделей. Перейдите в настройки и скачайте модель.",
        },
    )


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
    role_key = normalize_role(req.role)
    session = None

    if session_id:
        session = db.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session_not_found")
        profile_id = session["profile_id"]
        desired_model = normalize_model_name(req.model or req.model_name, fallback=session.get("model_name"))
        if desired_model != session.get("model_name"):
            session = db.update_session(session_id, model_name=desired_model) or session
        desired_role = normalize_role(req.role or session.get("role"))
        if desired_role != session.get("role"):
            session = db.update_session(session_id, role=desired_role) or session
        role_key = desired_role
        model_name = session["model_name"]
    else:
        if profile_id is None:
            raise HTTPException(status_code=400, detail="profile_id_required")
        _get_profile_or_404(profile_id)
        role_key = normalize_role(req.role)
        model_name = normalize_model_name(req.model or req.model_name, fallback=config.SETTINGS.model)
        title = session_title_hint(req.title, req.query)
        session = db.create_session(profile_id, title=title, model_name=model_name, role=role_key)
        session_id = session["id"]

    model_name = session["model_name"] if session else normalize_model_name(req.model or req.model_name)
    target_model = normalize_model_name(model_name, fallback=config.SETTINGS.model)
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
    if effective_settings.get("rag_enabled", False):
        rag_top_k = int(effective_settings.get("rag_top_k") or 5)
        rag_max_chars = int(effective_settings.get("rag_max_context_chars") or 6000)
        rag_chunks = rag_service.search(int(profile_id), user_query, top_k=rag_top_k)
        rag_context = rag_service.build_context(rag_chunks, max_chars=rag_max_chars)

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

    calc_result = evaluate_math_expression(user_query) if role_key == "calc" else None
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
    role_key = normalize_role(req.role)
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
        prepared = _prepare_chat_request(req)
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
        }
    except HTTPException as exc:
        _log("error", error=str(exc.detail))
        raise
    except Exception as e:
        _log("error", error=str(e))
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")


@router.post("/chat/tasks")
def start_chat_task(req: ChatRequest):
    prepared = _prepare_chat_request(req)
    session_id = prepared["session_id"]
    profile_id = prepared["profile_id"]
    user_query = prepared["user_query"]
    role_key = prepared["role_key"]
    target_model = prepared["target_model"]
    effective_settings = prepared["effective_settings"]
    calc_result = prepared["calc_result"]
    messages = prepared["messages"]
    prompt_warnings = prepared.get("prompt_warnings") or []

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
