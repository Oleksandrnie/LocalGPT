from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import RagIngestRequest, RagSearchRequest
from backend.apps.rag import service

router = APIRouter()


@router.get("/rag/status")
def rag_status(profile_id: int | None = Query(default=None)) -> dict[str, object]:
    return service.status(profile_id)


@router.post("/rag/ingest")
def rag_ingest(req: RagIngestRequest) -> dict[str, object]:
    return service.ingest_sources(req.profile_id, force=req.force)


@router.post("/rag/search")
def rag_search(req: RagSearchRequest) -> dict[str, object]:
    return {
        "profile_id": req.profile_id,
        "results": service.search(req.profile_id, req.query, top_k=req.top_k or 5),
    }
