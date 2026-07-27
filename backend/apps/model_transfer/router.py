from fastapi import APIRouter

from .inventory import export_inventory

router = APIRouter(prefix="/model-transfer", tags=["model-transfer"])


@router.get("/export-preview")
def get_export_preview():
    return export_inventory()
