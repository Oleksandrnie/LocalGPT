from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Any

from pydantic import BaseModel

from .. import config, db
from ..schemas import (
    ModelSettingsRequest,
    ModelSettingsReset,
    ProfileCreate,
    ProfilePreferencesUpdate,
    ProfileUpdate,
    SessionCreate,
    SessionUpdate,
)
from ..services import criteria as criteria_service
from ..services.chat import normalize_model_name, session_title_hint
from backend.apps.rag import service as rag_service

router = APIRouter()
CHAT_ROLE = "chat"


def _get_profile_or_404(profile_id: int) -> dict:
    profile = db.get_profile(profile_id)
    if not profile or not profile.get("is_active", 1):
        raise HTTPException(status_code=404, detail="profile_not_found")
    return profile


def _normalize_whisper_model(model_name: str) -> str:
    normalized = (model_name or "").strip()
    if normalized not in config.ALLOWED_WHISPER_MODELS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_whisper_model",
                "message": f"Недопустимая Whisper-модель: {normalized or model_name}",
                "allowed": list(config.ALLOWED_WHISPER_MODELS),
            },
        )
    return normalized


def _normalize_prompt_preset(value: str) -> str:
    normalized = (value or "").strip().lower()
    if not normalized or normalized == "none":
        normalized = "auto"
    if normalized not in {"auto", "ru", "en"}:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_prompt_preset", "message": "Допустимые prompt preset: auto, ru, en."},
        )
    return normalized


def _normalize_asr_beam_size(value: int | None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_asr_beam_size", "message": "Beam должен быть целым числом от 1 до 10."},
        ) from exc
    if parsed < 1 or parsed > 10:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_asr_beam_size", "message": "Beam должен быть целым числом от 1 до 10."},
        )
    return parsed


def _normalize_asr_threads(value: int | None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_asr_threads", "message": "Threads должен быть целым числом от 0 до 32."},
        ) from exc
    if parsed < 0 or parsed > 32:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_asr_threads", "message": "Threads должен быть целым числом от 0 до 32."},
        )
    return parsed


def _normalize_tts_provider(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized != "piper":
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_tts_provider", "message": "Сейчас поддерживается только TTS provider piper."},
        )
    return normalized


def _normalize_tts_speed(value: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_tts_speed", "message": "Скорость TTS должна быть числом."},
        ) from exc
    if number <= 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_tts_speed", "message": "Скорость TTS должна быть больше нуля."},
        )
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _normalize_bool_setting(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def _normalize_keep_alive_setting(value: object, key: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise HTTPException(
            status_code=422,
            detail={"code": f"invalid_{key}", "message": f"{key} must be a keep_alive value like 30s, 2m or 1h."},
        )
    return text


def _normalize_runtime_settings(value: dict | None) -> dict:
    if not isinstance(value, dict):
        return {}
    allowed = {
        "mem_turns",
        "pipeline_enabled",
        "summary_memory_enabled",
        "rag_enabled",
        "default_pipeline_preset",
        "max_transcript_chars",
        "max_context_chars",
        "summary_memory_limit",
        "rag_top_k",
        "rag_max_context_chars",
        "pipeline",
        "max_resident_target_models",
        "allow_light_with_heavy",
        "single_large_target_model",
        "preload_model_on_manual_select",
        "auto_target_keep_alive",
        "manual_keep_alive",
        "code_model_keep_alive",
        "heavy_model_keep_alive",
        "router_keep_alive",
    }
    cleaned = {key: value[key] for key in allowed if key in value}
    preset = cleaned.get("default_pipeline_preset")
    if preset is not None and str(preset).strip().lower() not in {"fast", "balanced", "deep"}:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_pipeline_preset", "message": "Pipeline preset must be fast, balanced или deep."},
        )
    if preset is not None:
        cleaned["default_pipeline_preset"] = str(preset).strip().lower()
    for key in (
        "mem_turns",
        "max_transcript_chars",
        "max_context_chars",
        "summary_memory_limit",
        "rag_top_k",
        "rag_max_context_chars",
        "max_resident_target_models",
    ):
        if key in cleaned and cleaned[key] is not None:
            try:
                parsed = max(1, int(cleaned[key]))
                cleaned[key] = min(5, parsed) if key == "max_resident_target_models" else parsed
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=422,
                    detail={"code": f"invalid_{key}", "message": f"{key} must be a positive integer."},
                ) from exc
    for key in ("allow_light_with_heavy", "single_large_target_model", "preload_model_on_manual_select"):
        if key in cleaned and cleaned[key] is not None:
            cleaned[key] = _normalize_bool_setting(cleaned[key])
    for key in (
        "auto_target_keep_alive",
        "manual_keep_alive",
        "code_model_keep_alive",
        "heavy_model_keep_alive",
        "router_keep_alive",
    ):
        if key in cleaned and cleaned[key] is not None:
            cleaned[key] = _normalize_keep_alive_setting(cleaned[key], key)
    return cleaned


@router.get("/profiles")
def list_profiles():
    profiles = db.list_profiles()
    return {"profiles": profiles}


@router.post("/profiles")
def create_profile(req: ProfileCreate):
    try:
        profile = db.create_profile(req.name, req.description, req.color)
        system_prompt = str(req.system_prompt or "").strip()
        if system_prompt:
            profile = db.update_profile_preferences(int(profile["id"]), {"chat": {"system_prompt": system_prompt}}) or profile
        rag_service.ensure_profile_source_dir(int(profile["id"]))
        return profile
    except ValueError:
        raise HTTPException(status_code=422, detail={"code": "profile_name_required", "message": "Укажите имя профиля"})


@router.patch("/profiles/{profile_id}")
def update_profile(profile_id: int, req: ProfileUpdate):
    _get_profile_or_404(profile_id)
    fields_set = getattr(req, "model_fields_set", None)
    if fields_set is None:
        fields_set = getattr(req, "__fields_set__", set())
    profile_updates = {}
    if "name" in fields_set:
        profile_updates["name"] = req.name
    if "description" in fields_set:
        profile_updates["description"] = req.description
    if "color" in fields_set:
        profile_updates["color"] = req.color
    try:
        profile = db.update_profile(profile_id, **profile_updates)
    except ValueError:
        raise HTTPException(status_code=422, detail={"code": "profile_name_required", "message": "Укажите имя профиля"})
    if not profile:
        raise HTTPException(status_code=404, detail="profile_not_found")

    if "system_prompt" in fields_set:
        profile = db.update_profile_preferences(
            profile_id,
            {"chat": {"system_prompt": str(req.system_prompt or "").strip()}},
        ) or profile
    return profile


@router.patch("/profiles/{profile_id}/preferences")
def update_profile_preferences(profile_id: int, req: ProfilePreferencesUpdate):
    _get_profile_or_404(profile_id)
    updates: dict[str, dict[str, Any]] = {}

    if req.chat and req.chat.dictation_model is not None:
        updates.setdefault("chat", {})["dictation_model"] = _normalize_whisper_model(req.chat.dictation_model)
    if req.chat and req.chat.system_prompt is not None:
        updates.setdefault("chat", {})["system_prompt"] = req.chat.system_prompt.strip()

    if req.asr:
        if req.asr.studio_model is not None:
            updates.setdefault("asr", {})["studio_model"] = _normalize_whisper_model(req.asr.studio_model)
        if req.asr.prompt_preset is not None:
            updates.setdefault("asr", {})["prompt_preset"] = _normalize_prompt_preset(req.asr.prompt_preset)
        if req.asr.beam_size is not None:
            updates.setdefault("asr", {})["beam_size"] = _normalize_asr_beam_size(req.asr.beam_size)
        if req.asr.threads is not None:
            updates.setdefault("asr", {})["threads"] = _normalize_asr_threads(req.asr.threads)

    if req.tts:
        if req.tts.provider is not None:
            updates.setdefault("tts", {})["provider"] = _normalize_tts_provider(req.tts.provider)
        if req.tts.voice_id is not None:
            updates.setdefault("tts", {})["voice_id"] = req.tts.voice_id.strip()
        if req.tts.speed is not None:
            updates.setdefault("tts", {})["speed"] = _normalize_tts_speed(req.tts.speed)

    runtime_settings = _normalize_runtime_settings(req.settings)
    if runtime_settings:
        updates["settings"] = runtime_settings

    if not updates:
        return _get_profile_or_404(profile_id)

    updated = db.update_profile_preferences(profile_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="profile_not_found")
    return updated


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: int):
    profiles = db.list_profiles()
    if len(profiles) <= 1:
        raise HTTPException(
            status_code=400,
            detail={"code": "cannot_delete_last_profile", "message": "Нельзя удалить единственный профиль"},
        )
    rag_service.delete_profile_source_dir(profile_id)
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
    try:
        session = db.create_session(req.profile_id, title=title, model_name=model_name, role=CHAT_ROLE)
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
    updated = db.update_session(session_id, title=req.title, model_name=new_model, role=None)
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
        mem_turns=None,
        ollama_keep_alive=(req.ollama_keep_alive.strip() if isinstance(req.ollama_keep_alive, str) and req.ollama_keep_alive.strip() else None),
        pipeline_enabled=req.pipeline_enabled,
        summary_memory_enabled=req.summary_memory_enabled,
        rag_enabled=req.rag_enabled,
        default_pipeline_preset=req.default_pipeline_preset,
        max_transcript_chars=req.max_transcript_chars,
        max_context_chars=req.max_context_chars,
        summary_memory_limit=req.summary_memory_limit,
        rag_top_k=req.rag_top_k,
        rag_max_context_chars=req.rag_max_context_chars,
        pipeline=req.pipeline,
    )
    return db.effective_settings(req.profile_id, model, config.DEFAULT_SETTINGS)


@router.post("/model_settings/reset_to_defaults")
def reset_model_settings(req: ModelSettingsReset):
    _get_profile_or_404(req.profile_id)
    model = normalize_model_name(req.model_name)
    db.reset_model_settings(req.profile_id, model)
    return db.effective_settings(req.profile_id, model, config.DEFAULT_SETTINGS)
