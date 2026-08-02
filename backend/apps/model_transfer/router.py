from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .inventory import export_inventory
from . import export_service
from .import_service import (
    apply_import,
    clear_upload_storage,
    discard_upload,
    inspect_archive,
    register_upload,
    upload_storage_dir,
    upload_storage_summary,
)
from .manifest import BundleValidationError

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


@router.post("/import-inspect")
async def inspect_import(bundle: UploadFile = File(...)):
    if not str(bundle.filename or "").lower().endswith(".localgpt-models"):
        raise HTTPException(422, detail={"code": "bundle_invalid", "message": "Выберите файл .localgpt-models."})
    staging = upload_storage_dir()
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / f"{__import__('uuid').uuid4()}.localgpt-models"
    keep = False
    try:
        with path.open("wb") as target:
            while chunk := await bundle.read(1024 * 1024):
                target.write(chunk)
        result = inspect_archive(path)
        upload_id = register_upload(path)
        keep = True
        return {**result, "upload_id": upload_id}
    except BundleValidationError as exc:
        raise HTTPException(422, detail={"code": exc.code, "message": str(exc)}) from exc
    finally:
        if not keep:
            path.unlink(missing_ok=True)


class ImportRequest(BaseModel):
    upload_id: str


@router.post("/imports")
def import_bundle(request: ImportRequest):
    try:
        return apply_import(request.upload_id)
    except BundleValidationError as exc:
        raise HTTPException(409 if exc.code == "target_conflict" else 422, detail={"code": exc.code, "message": str(exc)}) from exc


@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: str):
    if not discard_upload(upload_id):
        raise HTTPException(404, detail={"code": "upload_not_found"})
    return {"deleted": True}


@router.get("/uploads")
def get_upload_storage():
    return upload_storage_summary()


@router.delete("/uploads")
def clear_uploads():
    return clear_upload_storage()
