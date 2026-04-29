from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import transcript_store
from ..schemas import TranscriptCreate, TranscriptUpdate

router = APIRouter()


@router.get("/transcripts")
def list_transcripts() -> dict[str, object]:
    return {"items": transcript_store.list_transcripts()}


@router.get("/transcripts/{transcript_id}")
def get_transcript(transcript_id: str) -> dict[str, object]:
    transcript = transcript_store.get_transcript(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail={"code": "transcript_not_found", "message": "Транскрипт не найден"})
    return transcript


@router.post("/transcripts")
def create_transcript(req: TranscriptCreate) -> dict[str, object]:
    try:
        return transcript_store.create_transcript(
            text=req.text,
            source_type=req.source_type,
            source_name=req.source_name,
            model=req.model,
            language=req.language,
            duration_sec=req.duration_sec,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": str(exc), "message": "Текст обязателен"}) from exc


@router.patch("/transcripts/{transcript_id}")
def patch_transcript(transcript_id: str, req: TranscriptUpdate) -> dict[str, object]:
    if req.text is None and req.source_name is None:
        raise HTTPException(status_code=422, detail={"code": "empty_patch", "message": "Нет данных для обновления"})

    try:
        updated = transcript_store.update_transcript(
            transcript_id,
            text=req.text,
            source_name=req.source_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": str(exc), "message": "Текст обязателен"}) from exc

    if not updated:
        raise HTTPException(status_code=404, detail={"code": "transcript_not_found", "message": "Транскрипт не найден"})

    return updated


@router.delete("/transcripts/{transcript_id}")
def remove_transcript(transcript_id: str) -> dict[str, object]:
    deleted = transcript_store.delete_transcript(transcript_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "transcript_not_found", "message": "Транскрипт не найден"})

    return {"ok": True, "id": transcript_id}
