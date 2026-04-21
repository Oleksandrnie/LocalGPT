from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import db
from app.schemas import TranscriptCreate, TranscriptUpdate

router = APIRouter()


def _get_profile_or_404(profile_id: int) -> dict:
    profile = db.get_profile(profile_id)
    if not profile or not profile.get("is_active", 1):
        raise HTTPException(status_code=404, detail="profile_not_found")
    return profile


@router.get("/transcripts")
def list_transcripts(profile_id: int, session_id: str | None = None, origin: str | None = None):
    _get_profile_or_404(profile_id)
    transcripts = db.list_transcripts(profile_id, session_id=session_id, origin=origin)
    return {"transcripts": transcripts}


@router.post("/transcripts")
def create_transcript(req: TranscriptCreate):
    _get_profile_or_404(req.profile_id)
    if req.session_id:
        session = db.get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="session_not_found")
        if session["profile_id"] != req.profile_id:
            raise HTTPException(status_code=400, detail="session_profile_mismatch")
    try:
        transcript = db.create_transcript(
            profile_id=req.profile_id,
            session_id=req.session_id,
            name=req.name,
            content=req.content,
            source_path=req.source_path,
            language=req.language,
            timeline=req.timeline,
            role_keywords=req.role_keywords,
            labels=req.labels,
        )
        return transcript
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": str(exc), "message": "Контент транскрипта обязателен"}) from exc


@router.get("/transcripts/{transcript_id}")
def get_transcript(transcript_id: int):
    transcript = db.get_transcript(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="transcript_not_found")
    return transcript


@router.patch("/transcripts/{transcript_id}")
def update_transcript(transcript_id: int, req: TranscriptUpdate):
    updated = db.update_transcript(
        transcript_id,
        name=req.name,
        content=req.content,
        language=req.language,
        timeline=req.timeline,
        role_keywords=req.role_keywords,
        labels=req.labels,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="transcript_not_found")
    return updated


@router.delete("/transcripts/{transcript_id}")
def delete_transcript(transcript_id: int):
    transcript = db.get_transcript(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="transcript_not_found")
    db.delete_transcript(transcript_id)
    return {"deleted": transcript_id}


@router.delete("/transcripts")
def delete_transcripts(profile_id: int, session_id: str | None = None, origin: str | None = None):
    _get_profile_or_404(profile_id)
    deleted = db.delete_transcripts(profile_id, session_id=session_id, origin=origin)
    return {"deleted": deleted}
