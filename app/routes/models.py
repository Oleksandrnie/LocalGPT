from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import config, db
from ..services import models as model_service
from ..schemas import ModelPreloadRequest, ModelPullRequest
from backend.apps.chat.services import model_residency

router = APIRouter()


@router.get("/models")
def list_models():
    return model_service.list_models()


@router.post("/models/pull")
def pull_model(req: ModelPullRequest):
    model = model_service.validate_pull_model_ref(req.model)
    return model_service.start_model_pull(model)


@router.post("/models/preload")
def preload_model(req: ModelPreloadRequest):
    model = (req.model or "").strip()
    if not model:
        raise HTTPException(status_code=422, detail={"code": "model_required", "message": "Укажите модель"})
    if not model_service.is_model_installed(model):
        raise HTTPException(
            status_code=424,
            detail={"code": "chat_model_missing", "model": model, "message": "Модель не установлена локально."},
        )
    settings = {}
    if req.profile_id is not None:
        profile = db.get_profile(req.profile_id)
        if profile:
            settings = (db.effective_settings(req.profile_id, model, config.DEFAULT_SETTINGS).get("effective") or {})
    debug = model_residency.preload_target_model(model, settings, mode="manual")
    return {"ok": True, "model": model, **debug}


@router.get("/models/pull/{task_id}")
def pull_status(task_id: str):
    return model_service.pull_status(task_id)


@router.get("/models/downloads")
def pull_statuses():
    return model_service.pull_statuses()


@router.post("/models/pull/{task_id}/cancel")
def cancel_pull(task_id: str):
    return model_service.cancel_model_pull(task_id)


@router.post("/models/pull/{task_id}/pause")
def pause_pull(task_id: str):
    return model_service.pause_model_pull(task_id)


@router.post("/models/pull/{task_id}/resume")
def resume_pull(task_id: str):
    return model_service.resume_model_pull(task_id)


@router.delete("/models/{model_name}")
def delete_model(model_name: str):
    return model_service.delete_model(model_name)
