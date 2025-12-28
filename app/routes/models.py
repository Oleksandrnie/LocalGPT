from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services import models as model_service
from ..schemas import ModelPullRequest

router = APIRouter()


@router.get("/models")
def list_models():
    return model_service.list_models()


@router.post("/models/pull")
def pull_model(req: ModelPullRequest):
    model = (req.model or "").strip()
    if not model:
        raise HTTPException(status_code=422, detail={"code": "model_required", "message": "Укажите модель"})
    return model_service.start_model_pull(model)


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
