from __future__ import annotations

from fastapi import APIRouter, File, Query, UploadFile

from app.schemas import RagIngestRequest, RagSearchRequest, VisionContextExportRequest
from backend.apps.rag import service

router = APIRouter()


@router.get("/rag/status")
def rag_status(profile_id: int | None = Query(default=None)) -> dict[str, object]:
    return service.status(profile_id)


@router.post("/rag/ingest")
def rag_ingest(req: RagIngestRequest) -> dict[str, object]:
    return service.ingest_sources(req.profile_id, force=req.force)


@router.post("/rag/files")
def rag_upload_files(profile_id: int = Query(...), files: list[UploadFile] = File(...)) -> dict[str, object]:
    return service.save_uploaded_files(profile_id, files)


@router.delete("/rag/files")
def rag_delete_file(profile_id: int = Query(...), path: str = Query(...)) -> dict[str, object]:
    return service.delete_file(profile_id, path)


@router.delete("/rag/contexts")
def rag_delete_context(profile_id: int = Query(...), source_id: str = Query(...)) -> dict[str, object]:
    return service.delete_context_source(profile_id, source_id)


@router.post("/rag/vision-contexts")
def rag_export_vision_context(req: VisionContextExportRequest) -> dict[str, object]:
    return service.index_vision_context(
        profile_id=req.profile_id,
        session_id=req.session_id,
        message_id=req.message_id,
        title=req.title,
        text=req.text,
    )


@router.post("/rag/migrate-legacy")
def rag_migrate_legacy(req: RagIngestRequest) -> dict[str, object]:
    return service.migrate_legacy_root_files(req.profile_id)


@router.post("/rag/search")
def rag_search(req: RagSearchRequest) -> dict[str, object]:
    return {
        "profile_id": req.profile_id,
        "results": service.search(req.profile_id, req.query, top_k=req.top_k or 5),
    }
