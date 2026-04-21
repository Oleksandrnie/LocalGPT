from __future__ import annotations

import time
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app import config, db
from app.roles import normalize_role
from app.schemas import ChatRequest, ResetRequest
from app.services import criteria as criteria_service
from backend.apps.chat import tasks as chat_tasks
from backend.apps.chat.service import (
    ChatService,
    build_messages,
    evaluate_math_expression,
    normalize_model_name,
    session_title_hint,
)

router = APIRouter()
chat_service = ChatService()


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
    settings_bundle = db.effective_settings(profile_id, model_name, config.DEFAULT_SETTINGS)  # type: ignore[arg-type]
    effective_settings = settings_bundle.get("effective") or {}
    mem_turns = int(effective_settings.get("mem_turns") or config.SETTINGS.mem_turns)
    history = db.get_messages(session_id, limit_pairs=mem_turns) if session_id else []

    request_criteria = [c for c in (req.criteria or []) if isinstance(c, str)]
    cleaned_criteria = criteria_service.normalize_criteria_list(request_criteria) if request_criteria else []
    if cleaned_criteria and session_id:
        db.save_session_criteria(session_id, cleaned_criteria)
    stored_criteria = db.get_session_criteria(session_id) if session_id else []
    active_criteria = cleaned_criteria or stored_criteria or []

    if not transcript_text and session_id:
        latest_transcript = db.get_latest_transcript_for_session(session_id)
        transcript_text = (latest_transcript.get("content") if latest_transcript else "") or ""

    calc_result = evaluate_math_expression(user_query) if role_key == "calc" else None
    messages = build_messages(
        role=role_key,
        user_query=user_query,
        context=req.context,
        transcript=transcript_text,
        criteria=active_criteria,
        history=history,
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
            }

        text = chat_service.chat_completion(target_model, messages, settings=effective_settings)

        if session_id:
            db.add_message(session_id, "user", user_query)
            db.add_message(session_id, "assistant", text)

        _log("ok", reply=text)
        return {
            "reply": text,
            "session_id": session_id,
            "profile_id": profile_id,
            "model_name": target_model,
            "role": role_key,
            "used_settings": effective_settings,
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
        return task
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


@router.post("/session/reset")
def reset_session(req: ResetRequest):
    if config.SETTINGS.admin_token and req.admin_token != config.SETTINGS.admin_token:
        raise HTTPException(status_code=403, detail="forbidden")
    sid = req.session_id.strip()
    db.reset_session(sid)
    return {"ok": True}
