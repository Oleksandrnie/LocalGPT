from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config, db
from ..roles import normalize_role
from ..schemas import ModelSettingsRequest, ModelSettingsReset, ProfileCreate, SessionCreate, SessionUpdate
from ..services import criteria as criteria_service
from ..services.chat import normalize_model_name, session_title_hint

router = APIRouter()


def _get_profile_or_404(profile_id: int) -> dict:
    profile = db.get_profile(profile_id)
    if not profile or not profile.get("is_active", 1):
        raise HTTPException(status_code=404, detail="profile_not_found")
    return profile


@router.get("/profiles")
def list_profiles():
    profiles = db.list_profiles()
    return {"profiles": profiles}


@router.post("/profiles")
def create_profile(req: ProfileCreate):
    try:
        profile = db.create_profile(req.name, req.description, req.color)
        return profile
    except ValueError:
        raise HTTPException(status_code=422, detail={"code": "profile_name_required", "message": "Укажите имя профиля"})


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: int):
    profiles = db.list_profiles()
    if len(profiles) <= 1:
        raise HTTPException(
            status_code=400,
            detail={"code": "cannot_delete_last_profile", "message": "Нельзя удалить единственный профиль"},
        )
    db.delete_profile(profile_id)
    db.ensure_default_profile()
    return {"deleted": profile_id}


@router.get("/sessions")
def list_chat_sessions(profile_id: int):
    _get_profile_or_404(profile_id)
    sessions = db.list_sessions(profile_id)
    return {"sessions": sessions}


@router.post("/sessions")
def create_chat_session(req: SessionCreate):
    _get_profile_or_404(req.profile_id)
    title = session_title_hint(req.title, None)
    model_name = normalize_model_name(req.model_name, fallback=config.SETTINGS.model)
    role = normalize_role(req.role)
    try:
        session = db.create_session(req.profile_id, title=title, model_name=model_name, role=role)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": str(exc), "message": "Укажите название сессии"}) from exc
    return session


@router.delete("/sessions/{session_id}")
def delete_chat_session(session_id: str):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found")
    db.delete_session(session_id)
    return {"deleted": session_id}


@router.patch("/sessions/{session_id}")
def update_chat_session(session_id: str, req: SessionUpdate):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found")
    new_model = normalize_model_name(req.model_name) if req.model_name else None
    new_role = normalize_role(req.role) if req.role else None
    updated = db.update_session(session_id, title=req.title, model_name=new_model, role=new_role)
    if not updated:
        raise HTTPException(status_code=404, detail="session_not_found")
    return updated


@router.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str, limit: int | None = None):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found")
    messages = db.get_messages(session_id, limit_pairs=limit if limit else None)
    return {"session_id": session_id, "messages": messages}


class SessionCriteriaPayload(BaseModel):
    criteria: list[str] | None = None


@router.get("/sessions/{session_id}/criteria")
def get_session_criteria(session_id: str):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found")
    criteria = db.get_session_criteria(session_id) or []
    return {"session_id": session_id, "criteria": criteria}


@router.post("/sessions/{session_id}/criteria")
def save_session_criteria(session_id: str, payload: SessionCriteriaPayload):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session_not_found")
    cleaned = criteria_service.normalize_criteria_list(payload.criteria or [])
    db.save_session_criteria(session_id, cleaned)
    return {"session_id": session_id, "criteria": cleaned}


@router.get("/model_settings")
def get_model_settings(profile_id: int, model_name: str):
    _get_profile_or_404(profile_id)
    model = normalize_model_name(model_name)
    return db.effective_settings(profile_id, model, config.DEFAULT_SETTINGS)


@router.post("/model_settings")
def save_model_settings(req: ModelSettingsRequest):
    _get_profile_or_404(req.profile_id)
    model = normalize_model_name(req.model_name)
    db.upsert_model_settings(
        req.profile_id,
        model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        num_ctx=req.num_ctx,
        mem_turns=req.mem_turns,
    )
    return db.effective_settings(req.profile_id, model, config.DEFAULT_SETTINGS)


@router.post("/model_settings/reset_to_defaults")
def reset_model_settings(req: ModelSettingsReset):
    _get_profile_or_404(req.profile_id)
    model = normalize_model_name(req.model_name)
    db.reset_model_settings(req.profile_id, model)
    return db.effective_settings(req.profile_id, model, config.DEFAULT_SETTINGS)
