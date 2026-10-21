from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.schemas import (
    ChatContextExportRequest,
    RagIngestRequest,
    RagReindexRequest,
    RagSearchRequest,
    VisionContextExportRequest,
)
from backend.apps.rag import reindex_tasks, service

router = APIRouter()


@router.get("/rag/status")
def rag_status(
    profile_id: int | None = Query(default=None),
    session_id: str | None = Query(default=None),
) -> dict[str, object]:
    payload = service.status(profile_id, session_id=session_id)
    if profile_id is not None:
        payload["embedding_generation"]["operation"] = reindex_tasks.latest_reindex_task(profile_id)
    return payload


@router.get("/rag/audit")
def rag_audit(profile_id: int = Query(...)) -> dict[str, object]:
    return service.audit_corpus(profile_id)


@router.post("/rag/ingest")
def rag_ingest(req: RagIngestRequest) -> dict[str, object]:
    return service.ingest_sources(req.profile_id, force=req.force)


@router.post("/rag/reindex", status_code=202)
def rag_reindex(req: RagReindexRequest) -> dict[str, object]:
    return reindex_tasks.start_reindex(req.profile_id)


@router.get("/rag/reindex/{task_id}")
def rag_reindex_status(task_id: str, profile_id: int = Query(...)) -> dict[str, object]:
    task = reindex_tasks.get_reindex_task(task_id, profile_id)
    if not task:
        raise HTTPException(status_code=404, detail="rag_embedding_reindex_task_not_found")
    return task


@router.post("/rag/files")
def rag_upload_files(profile_id: int = Query(...), files: list[UploadFile] = File(...)) -> dict[str, object]:
    return service.save_uploaded_files(profile_id, files)


@router.delete("/rag/files")
def rag_delete_file(profile_id: int = Query(...), path: str = Query(...)) -> dict[str, object]:
    return service.delete_file(profile_id, path)


@router.delete("/rag/contexts")
def rag_delete_context(
    profile_id: int = Query(...),
    session_id: str = Query(...),
    source_id: str = Query(...),
) -> dict[str, object]:
    return service.delete_context_source(profile_id, session_id, source_id)


@router.post("/rag/vision-contexts")
def rag_export_vision_context(req: VisionContextExportRequest) -> dict[str, object]:
    return service.index_vision_context(
        profile_id=req.profile_id,
        session_id=req.session_id,
        message_id=req.message_id,
        title=req.title,
        text=req.text,
    )


@router.post("/rag/chat-contexts")
def rag_export_chat_context(req: ChatContextExportRequest) -> dict[str, object]:
    return service.index_chat_context(
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
    result = service.search_with_diagnostics(
        req.profile_id,
        req.query,
        top_k=req.top_k or 5,
        session_id=req.session_id,
    )
    return {
        "profile_id": req.profile_id,
        **result,
    }
