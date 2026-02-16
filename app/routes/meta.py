from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import config, whisper_downloads
from ..schemas import ModelPrepareRequest

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "env": config.SETTINGS.env,
        "default_model": config.SETTINGS.whisper_default_model,
        "whisper_models_dir": str(config.WHISPER_MODELS_DIR),
        "transcripts_dir": str(config.TRANSCRIPTS_DIR),
    }


@router.get("/whisper/models")
def whisper_models() -> dict[str, object]:
    return {
        "models": list(config.ALLOWED_WHISPER_MODELS),
        "default": config.SETTINGS.whisper_default_model,
    }


@router.post("/whisper/models/prepare")
def prepare_model(req: ModelPrepareRequest) -> dict[str, object]:
    try:
        return whisper_downloads.start_prepare_task(req.model)
    except ValueError as exc:
        if str(exc) == "invalid_model":
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_model",
                    "message": f"Недопустимая модель: {req.model}",
                    "allowed": list(config.ALLOWED_WHISPER_MODELS),
                },
            ) from exc
        raise


@router.get("/whisper/models/prepare/{task_id}")
def get_prepare_status(task_id: str) -> dict[str, object]:
    task = whisper_downloads.get_prepare_task(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail={"code": "task_not_found", "message": "Задача подготовки модели не найдена"},
        )
    return task
