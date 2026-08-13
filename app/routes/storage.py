from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from ..schemas import StorageUpdateRequest
from ..security import ADMIN_TOKEN_HEADER, require_admin_token
from ..storage import describe_paths, update_models_dir

router = APIRouter()


@router.get("/storage/paths")
def get_storage_paths(admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER)):
    require_admin_token(admin_token)
    return {"paths": describe_paths()}


@router.post("/storage/paths")
def set_storage_paths(
    req: StorageUpdateRequest,
    admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER),
):
    require_admin_token(req.admin_token or admin_token)
    target = (req.models_dir or "").strip()
    if not target:
        raise HTTPException(status_code=422, detail={"code": "path_required", "message": "Укажите путь к моделям"})
    paths = update_models_dir(target, move_existing=req.move_existing)
    return {"paths": paths}
