from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import StorageUpdateRequest
from ..storage import describe_paths, update_models_dir

router = APIRouter()


@router.get("/storage/paths")
def get_storage_paths():
    return {"paths": describe_paths()}


@router.post("/storage/paths")
def set_storage_paths(req: StorageUpdateRequest):
    target = (req.models_dir or "").strip()
    if not target:
        raise HTTPException(status_code=422, detail={"code": "path_required", "message": "Укажите путь к моделям"})
    paths = update_models_dir(target, move_existing=req.move_existing)
    return {"paths": paths}
