from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import db
from ..asr_whisper import transcribe_with_fallback
from ..services.timeline import build_timeline

router = APIRouter()

LANGUAGE_RE = re.compile(r"^[a-z0-9]{2,8}(?:-[a-z0-9]{2,8})?$")


@router.post("/transcribe")
def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default="small"),
    prompt_preset: str = Form(default="none"),
    language: str = Form(default="auto"),
    session_id: str = Form(default=""),
    profile_id: int = Form(default=0),
):
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=os.path.splitext(file.filename or "")[-1],
    ) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    model_name = (model or os.getenv("WHISPER_MODEL_SIZE", "medium")).strip()

    preset = (prompt_preset or "none").strip().lower()
    if not preset:
        preset = "none"
    if preset not in {"none", "ru", "en"}:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_prompt_preset",
                "message": "prompt_preset must be one of: none, ru, en.",
            },
        )
    preset_value = None if preset == "none" else preset

    language_raw = (language or "auto").strip().lower()
    if language_raw == "":
        language_raw = "auto"
    if language_raw != "auto" and not LANGUAGE_RE.fullmatch(language_raw):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_language",
                "message": "language must be 'auto' или BCP-47 код (например, 'ru', 'en', 'pt-br').",
            },
        )
    preferred_language = None if language_raw == "auto" else language_raw

    sid = (session_id or "").strip()
    profile_id_val = profile_id or 0
    if sid:
        session = db.get_session(sid)
        if not session:
            raise HTTPException(status_code=404, detail={"code": "session_not_found", "message": "Сессия не найдена"})
        profile_id_val = session["profile_id"]
    if not profile_id_val:
        profile_id_val = db.ensure_default_profile()
    profile = db.get_profile(profile_id_val)
    if not profile:
        raise HTTPException(status_code=404, detail="profile_not_found")

    try:
        transcription = transcribe_with_fallback(
            audio_path=tmp_path,
            model_name=model_name,
            prompt_preset=preset_value,
            preferred_language=preferred_language,
        )
        text = transcription.get("text", "") if isinstance(transcription, dict) else str(transcription)
        segments = []
        if isinstance(transcription, dict):
            segments = list(transcription.get("segments") or [])
        timeline = build_timeline(segments)
        if not text:
            raise RuntimeError("empty_transcription")
        detected_language = None
        if isinstance(transcription, dict):
            detected_language = transcription.get("language")
        role_keywords = {}
        if isinstance(transcription, dict):
            role_keywords = transcription.get("role_keywords") or {}

        transcript_record = db.create_transcript(
            profile_id=profile_id_val,
            session_id=sid or None,
            name=os.path.basename(file.filename or tmp_path) or "Транскрипт",
            content=text,
            source_path=file.filename,
            language=detected_language or language_raw,
            timeline=timeline,
            role_keywords=role_keywords,
        )

        return {
            "text": text,
            "model": model_name,
            "prompt_preset": preset,
            "language": language_raw,
            "detected_language": detected_language,
            "segments": segments,
            "timeline": timeline,
            "role_keywords": role_keywords,
            "transcript_id": transcript_record.get("id") if transcript_record else None,
            "profile_id": profile_id_val,
            "session_id": sid or None,
        }
    except RuntimeError as e:
        msg = str(e)
        if msg.startswith("WHISPER_MODEL_NOT_FOUND::"):
            missing_model = msg.split("::", 1)[1] if "::" in msg else model_name
            raise HTTPException(
                status_code=424,
                detail={
                    "code": "whisper_model_missing",
                    "model": missing_model,
                    "message": f'Whisper model "{missing_model}" is not available locally.',
                },
            )
        if msg == "empty_transcription":
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "empty_transcription",
                    "message": "Whisper вернул пустую транскрипцию.",
                },
            )
        raise
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
