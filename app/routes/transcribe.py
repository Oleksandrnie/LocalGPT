from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import config, transcript_store
from ..asr_whisper import transcribe_with_fallback

router = APIRouter()


@router.post("/transcribe")
def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default="small"),
    source_type: str = Form(default="upload"),
) -> dict[str, object]:
    selected_model = (model or config.SETTINGS.whisper_default_model).strip()
    if selected_model not in config.ALLOWED_WHISPER_MODELS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_model",
                "message": f"Недопустимая модель: {selected_model}",
                "allowed": list(config.ALLOWED_WHISPER_MODELS),
            },
        )

    source_name = Path(file.filename or "uploaded_file").name
    suffix = Path(source_name).suffix

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        temp_path = tmp_file.name

    try:
        result = transcribe_with_fallback(temp_path, selected_model)
        text = (result.get("text") or "").strip()

        if not text:
            raise HTTPException(
                status_code=502,
                detail={"code": "empty_transcription", "message": "Whisper вернул пустую транскрипцию"},
            )

        created = transcript_store.create_transcript(
            text=text,
            source_type=source_type,
            source_name=source_name,
            model=selected_model,
            language=result.get("language"),
            duration_sec=result.get("duration_sec"),
        )
        return created
    except ValueError as exc:
        if str(exc) == "invalid_model":
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_model",
                    "message": f"Недопустимая модель: {selected_model}",
                    "allowed": list(config.ALLOWED_WHISPER_MODELS),
                },
            ) from exc
        raise
    except RuntimeError as exc:
        code = str(exc)
        if code == "model_prepare_failed":
            raise HTTPException(
                status_code=502,
                detail={"code": "model_prepare_failed", "message": "Не удалось подготовить модель Whisper"},
            ) from exc
        if code == "audio_file_missing":
            raise HTTPException(
                status_code=400,
                detail={"code": "audio_file_missing", "message": "Временный файл для транскрибации не найден"},
            ) from exc
        raise HTTPException(status_code=502, detail={"code": "transcription_failed", "message": str(exc)}) from exc
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass
