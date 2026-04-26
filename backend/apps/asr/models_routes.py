from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import config
from app.schemas import ModelPrepareRequest
from backend.apps.asr import downloads as whisper_downloads

router = APIRouter()


def _raise_invalid_model(model_name: str) -> None:
    raise HTTPException(
        status_code=422,
        detail={
            "code": "invalid_model",
            "message": f"Недопустимая Whisper-модель: {model_name}",
            "allowed": list(config.ALLOWED_WHISPER_MODELS),
        },
    )


@router.get("/whisper/models")
def whisper_models() -> dict[str, object]:
    return {
        "items": whisper_downloads.list_local_models(),
        "models": list(config.ALLOWED_WHISPER_MODELS),
        "default": config.SETTINGS.whisper_default_model,
        "studio_default": config.ASR_STUDIO_DEFAULT_MODEL,
        "downloads": whisper_downloads.list_prepare_tasks(),
    }


@router.post("/whisper/models/prepare")
def prepare_model(req: ModelPrepareRequest) -> dict[str, object]:
    try:
        return whisper_downloads.start_prepare_task(req.model, force=bool(req.force))
    except ValueError as exc:
        if str(exc) == "invalid_model":
            _raise_invalid_model(req.model)
        raise


@router.get("/whisper/models/prepare/{task_id}")
def get_prepare_status(task_id: str) -> dict[str, object]:
    task = whisper_downloads.get_prepare_task(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail={"code": "task_not_found", "message": "Задача подготовки Whisper-модели не найдена."},
        )
    return task


@router.get("/whisper/models/update-check/{model_name}")
def check_model_update(model_name: str) -> dict[str, object]:
    try:
        return whisper_downloads.check_model_update(model_name)
    except ValueError as exc:
        if str(exc) == "invalid_model":
            _raise_invalid_model(model_name)
        raise


@router.delete("/whisper/models/{model_name}")
def delete_model(model_name: str) -> dict[str, object]:
    try:
        return whisper_downloads.delete_local_model(model_name)
    except ValueError as exc:
        if str(exc) == "invalid_model":
            _raise_invalid_model(model_name)
        raise
    except whisper_downloads.PrepareModelError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
