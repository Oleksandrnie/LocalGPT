from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException
from typing import Any

from pydantic import BaseModel

from .. import config, db
from ..roles import DEFAULT_PROFILE_PERSONA_VERSION
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
from ..services.thinking import normalize_thinking_setting
from ..services.chat import normalize_model_name, session_title_hint
from backend.apps.rag import service as rag_service
from backend.apps.chat.services import attachment_storage

router = APIRouter()
CHAT_ROLE = "chat"


def _get_profile_or_404(profile_id: int) -> dict:
    profile = db.get_profile(profile_id)
    if not profile or not profile.get("is_active", 1):
        raise HTTPException(status_code=404, detail="profile_not_found")
    return profile


def _get_owned_session_or_404(profile_id: int, session_id: str) -> dict:
    session = db.get_session(session_id)
    if not session or int(session.get("profile_id") or 0) != int(profile_id):
        raise HTTPException(status_code=404, detail="session_not_found")
    return session


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


def _normalize_analysis_language(value: str) -> str:
    normalized = (value or "").strip().lower()
    if not normalized or normalized == "none":
        normalized = "auto"
    if normalized not in {"auto", "ru", "en"}:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_asr_analysis_language", "message": "Допустимый язык анализа ASR: auto, ru, en."},
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


def _normalize_ollama_think(value: bool | str | None, model_name: str = "") -> str | None:
    return normalize_thinking_setting(value, model_name)


def _normalize_token_budget(value: int | None, key: str) -> int | None:
    if value is None:
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": f"invalid_{key}", "message": f"{key} must be an integer."},
        ) from exc
    minimum = config.THINKING_TOKEN_BUDGET_MIN if key == "thinking_tokens" else 1
    if normalized < minimum or normalized > 32768:
        raise HTTPException(
            status_code=422,
            detail={"code": f"invalid_{key}", "message": f"{key} must be between {minimum} and 32768."},
        )
    return normalized


def _asr_diagnostics_profile_dir(profile_id: int) -> Path:
    return config.ASR_DIAGNOSTICS_DIR / f"profile_{int(profile_id)}"


def _sync_asr_diagnostics_dir(profile_id: int, enabled: bool) -> None:
    path = _asr_diagnostics_profile_dir(profile_id)
    if enabled:
        path.mkdir(parents=True, exist_ok=True)
    else:
        shutil.rmtree(path, ignore_errors=True)


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
        "streaming_enabled",
        "pipeline_enabled",
        "asr_full_analysis_enabled",
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
        "show_router_thinking_toggle",
        "chat_images_enabled",
        "max_images_per_message",
        "chat_image_max_file_bytes",
        "chat_image_max_total_bytes",
        "chat_image_max_pixels",
        "chat_image_max_side",
        "vision_model",
        "vision_num_ctx",
        "vision_output_tokens",
        "vision_fallback",
        "ocr_assist",
        "ocr_language",
    }
    cleaned = {key: value[key] for key in allowed if key in value}
    if "max_images_per_message" in cleaned:
        try:
            raw_max_images = int(cleaned["max_images_per_message"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_max_images_per_message", "message": "Лимит изображений должен быть от 1 до 10."},
            ) from exc
        if raw_max_images < 1 or raw_max_images > 10:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_max_images_per_message", "message": "Лимит изображений должен быть от 1 до 10."},
            )
    preset = cleaned.get("default_pipeline_preset")
    if preset is not None and str(preset).strip().lower() not in {"fast", "balanced", "deep"}:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_pipeline_preset", "message": "Pipeline preset must be fast, balanced или deep."},
        )
    if preset is not None:
        cleaned["default_pipeline_preset"] = str(preset).strip().lower()
    bounded_positive_ints = {
        "mem_turns": 100,
        "max_transcript_chars": 100_000,
        "max_context_chars": 256_000,
        "summary_memory_limit": 100,
        "rag_top_k": 20,
        "rag_max_context_chars": 128_000,
        "max_resident_target_models": 5,
        "max_images_per_message": 10,
        "chat_image_max_file_bytes": 50 * 1024 * 1024,
        "chat_image_max_total_bytes": 100 * 1024 * 1024,
        "chat_image_max_pixels": 100_000_000,
        "chat_image_max_side": 32_768,
    }
    for key in (
        "mem_turns",
        "max_transcript_chars",
        "max_context_chars",
        "summary_memory_limit",
        "rag_top_k",
        "rag_max_context_chars",
        "max_resident_target_models",
        "max_images_per_message",
        "chat_image_max_file_bytes",
        "chat_image_max_total_bytes",
        "chat_image_max_pixels",
        "chat_image_max_side",
    ):
        if key in cleaned and cleaned[key] is not None:
            try:
                parsed = int(cleaned[key])
                minimum = 0 if key == "mem_turns" else 1
                if parsed < minimum:
                    raise ValueError
                if parsed > bounded_positive_ints[key]:
                    raise ValueError
                cleaned[key] = parsed
            except (TypeError, ValueError) as exc:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": f"invalid_{key}",
                        "message": f"{key} must be between {minimum} and {bounded_positive_ints[key]}.",
                    },
                ) from exc
    for key in (
        "streaming_enabled",
        "asr_full_analysis_enabled",
        "rag_enabled",
        "allow_light_with_heavy",
        "single_large_target_model",
        "preload_model_on_manual_select",
        "show_router_thinking_toggle",
        "chat_images_enabled",
    ):
        if key in cleaned and cleaned[key] is not None:
            cleaned[key] = _normalize_bool_setting(cleaned[key])
    if "vision_model" in cleaned:
        vision_model = str(cleaned["vision_model"] or "auto").strip() or "auto"
        allowed_vision_models = {
            "auto",
            *(str(item.get("id") or "") for item in getattr(config, "VISION_MODEL_CATALOG", [])),
        }
        if vision_model not in allowed_vision_models:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_vision_model", "message": "Выберите Auto или модель из Vision-каталога."},
            )
        cleaned["vision_model"] = vision_model
    if "vision_num_ctx" in cleaned:
        try:
            vision_num_ctx = int(cleaned["vision_num_ctx"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_vision_num_ctx",
                    "message": "Vision context должен быть целым числом от 4096 до 131072.",
                },
            ) from exc
        if vision_num_ctx < 4096 or vision_num_ctx > 131072:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_vision_num_ctx",
                    "message": "Vision context должен быть целым числом от 4096 до 131072.",
                },
            )
        cleaned["vision_num_ctx"] = vision_num_ctx
    if "vision_output_tokens" in cleaned:
        try:
            vision_output_tokens = int(cleaned["vision_output_tokens"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_vision_output_tokens",
                    "message": "Vision output tokens должен быть целым числом от 128 до 8192; legacy 0 означает 1024.",
                },
            ) from exc
        if vision_output_tokens != 0 and not 128 <= vision_output_tokens <= 8192:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_vision_output_tokens",
                    "message": "Vision output tokens должен быть целым числом от 128 до 8192; legacy 0 означает 1024.",
                },
            )
        cleaned["vision_output_tokens"] = vision_output_tokens or config.DEFAULT_RUNTIME_SETTINGS["vision_output_tokens"]
    if "vision_fallback" in cleaned:
        fallback = str(cleaned["vision_fallback"] or "").strip().lower()
        if fallback not in {"vision_context", "error"}:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_vision_fallback", "message": "vision_fallback must be vision_context or error."},
            )
        cleaned["vision_fallback"] = fallback
    if "ocr_assist" in cleaned:
        ocr_assist = str(cleaned["ocr_assist"] or "").strip().lower()
        if ocr_assist not in {"auto", "on", "off", "ocr_only"}:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_ocr_assist", "message": "ocr_assist must be auto, on, off or ocr_only."},
            )
        cleaned["ocr_assist"] = ocr_assist
    if "ocr_language" in cleaned:
        cleaned["ocr_language"] = str(cleaned["ocr_language"] or "").strip()[:120]
    if (
        "chat_image_max_file_bytes" in cleaned
        and "chat_image_max_total_bytes" in cleaned
        and int(cleaned["chat_image_max_file_bytes"]) > int(cleaned["chat_image_max_total_bytes"])
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_chat_image_byte_limits",
                "message": "Лимит одного изображения не может превышать общий лимит.",
            },
        )
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
            profile = db.update_profile_preferences(
                int(profile["id"]),
                {
                    "chat": {
                        "system_prompt": system_prompt,
                        "persona_origin": "user",
                        "persona_version": DEFAULT_PROFILE_PERSONA_VERSION,
                    }
                },
            ) or profile
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
            {
                "chat": {
                    "system_prompt": str(req.system_prompt or "").strip(),
                    "persona_origin": "user",
                    "persona_version": DEFAULT_PROFILE_PERSONA_VERSION,
                }
            },
        ) or profile
    return profile


@router.patch("/profiles/{profile_id}/preferences")
def update_profile_preferences(profile_id: int, req: ProfilePreferencesUpdate):
    _get_profile_or_404(profile_id)
    updates: dict[str, dict[str, Any]] = {}
    asr_diagnostics_enabled: bool | None = None

    if req.chat and req.chat.dictation_model is not None:
        updates.setdefault("chat", {})["dictation_model"] = _normalize_whisper_model(req.chat.dictation_model)
    if req.chat and req.chat.system_prompt is not None:
        updates.setdefault("chat", {})["system_prompt"] = req.chat.system_prompt.strip()
        updates.setdefault("chat", {})["persona_origin"] = "user"
        updates.setdefault("chat", {})["persona_version"] = DEFAULT_PROFILE_PERSONA_VERSION

    if req.asr:
        if req.asr.studio_model is not None:
            updates.setdefault("asr", {})["studio_model"] = _normalize_whisper_model(req.asr.studio_model)
        if req.asr.prompt_preset is not None:
            updates.setdefault("asr", {})["prompt_preset"] = _normalize_prompt_preset(req.asr.prompt_preset)
        if req.asr.beam_size is not None:
            updates.setdefault("asr", {})["beam_size"] = _normalize_asr_beam_size(req.asr.beam_size)
        if req.asr.threads is not None:
            updates.setdefault("asr", {})["threads"] = _normalize_asr_threads(req.asr.threads)
        if req.asr.analysis_language is not None:
            updates.setdefault("asr", {})["analysis_language"] = _normalize_analysis_language(req.asr.analysis_language)
        if req.asr.analysis_prompt is not None:
            updates.setdefault("asr", {})["analysis_prompt"] = str(req.asr.analysis_prompt or "").strip()[:4000]
        if req.asr.diagnostics_enabled is not None:
            asr_diagnostics_enabled = _normalize_bool_setting(req.asr.diagnostics_enabled)
            updates.setdefault("asr", {})["diagnostics_enabled"] = asr_diagnostics_enabled

    if req.tts:
        if req.tts.provider is not None:
            updates.setdefault("tts", {})["provider"] = _normalize_tts_provider(req.tts.provider)
        if req.tts.voice_id is not None:
            updates.setdefault("tts", {})["voice_id"] = req.tts.voice_id.strip()
        if req.tts.speed is not None:
            updates.setdefault("tts", {})["speed"] = _normalize_tts_speed(req.tts.speed)

    runtime_settings = _normalize_runtime_settings(req.settings)
    if runtime_settings:
        current_settings = (_get_profile_or_404(profile_id).get("preferences") or {}).get("settings") or {}
        merged_runtime_settings = {**current_settings, **runtime_settings}
        if int(merged_runtime_settings.get("chat_image_max_file_bytes") or 0) > int(
            merged_runtime_settings.get("chat_image_max_total_bytes") or 0
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_chat_image_byte_limits",
                    "message": "Лимит одного изображения не может превышать общий лимит.",
                },
            )
        updates["settings"] = runtime_settings

    if not updates:
        return _get_profile_or_404(profile_id)

    updated = db.update_profile_preferences(profile_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="profile_not_found")
    if asr_diagnostics_enabled is not None:
        _sync_asr_diagnostics_dir(profile_id, asr_diagnostics_enabled)
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
    attachment_storage.delete_profile_attachments(profile_id)
    _sync_asr_diagnostics_dir(profile_id, False)
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
def delete_chat_session(session_id: str, profile_id: int):
    _get_owned_session_or_404(profile_id, session_id)
    attachment_storage.delete_session_attachments(session_id)
    db.delete_session(session_id)
    return {"deleted": session_id}


@router.patch("/sessions/{session_id}")
def update_chat_session(session_id: str, req: SessionUpdate, profile_id: int):
    _get_owned_session_or_404(profile_id, session_id)
    new_model = normalize_model_name(req.model_name) if req.model_name else None
    updated = db.update_session(session_id, title=req.title, model_name=new_model, role=None)
    if not updated:
        raise HTTPException(status_code=404, detail="session_not_found")
    return updated


@router.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str, profile_id: int, limit: int | None = None):
    _get_owned_session_or_404(profile_id, session_id)
    messages = db.get_messages(session_id, limit_pairs=limit if limit else None)
    return {"session_id": session_id, "messages": messages}


class SessionCriteriaPayload(BaseModel):
    criteria: list[str] | None = None


@router.get("/sessions/{session_id}/criteria")
def get_session_criteria(session_id: str, profile_id: int):
    _get_owned_session_or_404(profile_id, session_id)
    criteria = db.get_session_criteria(session_id) or []
    return {"session_id": session_id, "criteria": criteria}


@router.post("/sessions/{session_id}/criteria")
def save_session_criteria(session_id: str, payload: SessionCriteriaPayload, profile_id: int):
    _get_owned_session_or_404(profile_id, session_id)
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
    output_tokens = _normalize_token_budget(
        req.output_tokens if req.output_tokens is not None else req.max_tokens,
        "output_tokens",
    )
    thinking_tokens = _normalize_token_budget(req.thinking_tokens, "thinking_tokens")
    db.upsert_model_settings(
        req.profile_id,
        model,
        temperature=req.temperature,
        max_tokens=output_tokens,
        output_tokens=output_tokens,
        thinking_tokens=thinking_tokens,
        num_ctx=req.num_ctx,
        mem_turns=None,
        ollama_keep_alive=(req.ollama_keep_alive.strip() if isinstance(req.ollama_keep_alive, str) and req.ollama_keep_alive.strip() else None),
        ollama_think=_normalize_ollama_think(req.ollama_think, model),
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
    if model == "__asr_pipeline__":
        db.upsert_model_settings(
            req.profile_id,
            model,
            ollama_think="off",
            pipeline=config.DEFAULT_PIPELINE,
        )
    return db.effective_settings(req.profile_id, model, config.DEFAULT_SETTINGS)
