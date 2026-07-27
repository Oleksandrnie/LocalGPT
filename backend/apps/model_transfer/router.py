from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .inventory import export_inventory
from . import export_service

router = APIRouter(prefix="/model-transfer", tags=["model-transfer"])


@router.get("/export-preview")
def get_export_preview():
    return export_inventory()


class ExportRequest(BaseModel):
    models: list[str]


@router.post("/exports")
def create_export(request: ExportRequest):
    try:
        return export_service.start_export(request.models)
    except ValueError as exc:
        raise HTTPException(422, detail={"code": str(exc)}) from exc


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    task = export_service.get_task(task_id)
    if not task:
        raise HTTPException(404, detail={"code": "task_not_found"})
    return task


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    task = export_service.cancel(task_id)
    if not task:
        raise HTTPException(404, detail={"code": "task_not_found"})
    return task


@router.get("/exports/{task_id}/download")
def download_export(task_id: str):
    result = export_service.archive_path(task_id)
    if not result:
        raise HTTPException(409, detail={"code": "export_not_ready"})
    path, filename = result
    return FileResponse(path, filename=filename, media_type="application/octet-stream")
