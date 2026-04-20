from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import config, db, transcribe_tasks
from ..asr_whisper import transcribe_with_fallback
from ..services.timeline import build_timeline

router = APIRouter()

LANGUAGE_RE = re.compile(r"^[a-z0-9]{2,8}(?:-[a-z0-9]{2,8})?$")


def _store_upload_temp(file: UploadFile) -> tuple[str, str]:
    source_name = Path(file.filename or "uploaded_file").name
    suffix = Path(source_name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        temp_path = tmp_file.name
    return temp_path, source_name


def _normalize_preset(prompt_preset: str) -> tuple[str, str | None]:
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
    return preset, None if preset == "none" else preset


def _normalize_language(language: str) -> tuple[str, str | None]:
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
    return language_raw, None if language_raw == "auto" else language_raw


def _resolve_transcript_context(*, session_id: str, profile_id: int, store_result: bool) -> tuple[str | None, int]:
    sid = (session_id or "").strip() or None
    profile_id_val = profile_id or 0

    if not store_result:
        return sid, profile_id_val

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
    return sid, profile_id_val


def _transcribe_sync(
    *,
    tmp_path: str,
    source_name: str,
    model_name: str,
    preset: str,
    preset_value: str | None,
    language_raw: str,
    preferred_language: str | None,
    session_id: str | None,
    profile_id: int,
    store_result: bool,
    origin: str | None,
) -> dict[str, object]:
    transcript_record = None
    transcription = transcribe_with_fallback(
        audio_path=tmp_path,
        model_name=model_name,
        prompt_preset=preset_value,
        preferred_language=preferred_language,
    )
    text = transcription.get("text", "") if isinstance(transcription, dict) else str(transcription)
    segments = list(transcription.get("segments") or []) if isinstance(transcription, dict) else []
    timeline = build_timeline(segments)
    if not text:
        raise RuntimeError("empty_transcription")
    detected_language = transcription.get("language") if isinstance(transcription, dict) else None
    role_keywords = transcription.get("role_keywords") or {} if isinstance(transcription, dict) else {}

    if store_result:
        labels = {"origin": origin} if origin else None
        transcript_record = db.create_transcript(
            profile_id=profile_id,
            session_id=session_id,
            name=source_name or "Транскрипт",
            content=text,
            source_path=source_name,
            language=detected_language or language_raw,
            timeline=timeline,
            role_keywords=role_keywords,
            labels=labels,
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
        "profile_id": profile_id or None,
        "session_id": session_id or None,
        "stored": store_result,
        "origin": origin or None,
    }


@router.post("/transcribe")
def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default="small"),
    prompt_preset: str = Form(default="none"),
    language: str = Form(default="auto"),
    session_id: str = Form(default=""),
    profile_id: int = Form(default=0),
    store_result: bool = Form(default=True),
    origin: str = Form(default=""),
):
    tmp_path, source_name = _store_upload_temp(file)
    model_name = (model or config.SETTINGS.whisper_default_model).strip()
    preset, preset_value = _normalize_preset(prompt_preset)
    language_raw, preferred_language = _normalize_language(language)
    sid, profile_id_val = _resolve_transcript_context(
        session_id=session_id,
        profile_id=profile_id,
        store_result=bool(store_result),
    )

    try:
        return _transcribe_sync(
            tmp_path=tmp_path,
            source_name=source_name,
            model_name=model_name,
            preset=preset,
            preset_value=preset_value,
            language_raw=language_raw,
            preferred_language=preferred_language,
            session_id=sid,
            profile_id=profile_id_val,
            store_result=bool(store_result),
            origin=(origin or "").strip() or None,
        )
    except RuntimeError as exc:
        msg = str(exc)
        if msg.startswith("WHISPER_MODEL_NOT_FOUND::"):
            missing_model = msg.split("::", 1)[1] if "::" in msg else model_name
            raise HTTPException(
                status_code=424,
                detail={
                    "code": "whisper_model_missing",
                    "model": missing_model,
                    "message": f'Whisper model "{missing_model}" is not available locally.',
                },
            ) from exc
        if msg == "empty_transcription":
            raise HTTPException(
                status_code=502,
                detail={"code": "empty_transcription", "message": "Whisper вернул пустую транскрипцию."},
            ) from exc
        raise
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@router.post("/transcribe/tasks")
def start_transcription_task(
    file: UploadFile = File(...),
    model: str = Form(default="small"),
    prompt_preset: str = Form(default="none"),
    language: str = Form(default="auto"),
    session_id: str = Form(default=""),
    profile_id: int = Form(default=0),
    store_result: bool = Form(default=True),
    origin: str = Form(default=""),
):
    tmp_path, source_name = _store_upload_temp(file)
    model_name = (model or config.SETTINGS.whisper_default_model).strip()
    preset, _ = _normalize_preset(prompt_preset)
    _, preferred_language = _normalize_language(language)
    sid, profile_id_val = _resolve_transcript_context(
        session_id=session_id,
        profile_id=profile_id,
        store_result=bool(store_result),
    )

    try:
        return transcribe_tasks.start_transcription_task(
            input_path=tmp_path,
            model=model_name,
            prompt_preset=preset,
            preferred_language=preferred_language,
            source_name=source_name,
            profile_id=profile_id_val,
            session_id=sid,
            store_result=bool(store_result),
            origin=(origin or "").strip() or None,
        )
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


@router.get("/transcribe/tasks/{task_id}")
def get_transcription_task(task_id: str) -> dict[str, object]:
    task = transcribe_tasks.get_transcription_task(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail={"code": "transcription_task_not_found", "message": "Задача транскрибации не найдена"},
        )
    return task


@router.post("/transcribe/tasks/{task_id}/cancel")
def cancel_transcription_task(task_id: str) -> dict[str, object]:
    task = transcribe_tasks.cancel_transcription_task(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail={"code": "transcription_task_not_found", "message": "Задача транскрибации не найдена"},
        )
    return task
