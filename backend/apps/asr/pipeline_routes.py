from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app import db
from app.schemas import TranscriptPipelineRequest, TranscriptSpeakerOverridesRequest, TranscriptSummaryRequest
from backend.apps.asr import pipeline as pipeline_service

router = APIRouter()


def _get_transcript_or_404(
    transcript_id: int,
    *,
    profile_id: int,
    session_id: str | None,
) -> dict:
    transcript = db.get_transcript(transcript_id)
    owned_session = str((transcript or {}).get("session_id") or "")
    if (
        not transcript
        or int(transcript.get("profile_id") or 0) != int(profile_id)
        or (owned_session and owned_session != str(session_id or ""))
    ):
        raise HTTPException(status_code=404, detail="transcript_not_found")
    return transcript


@router.post("/transcripts/{transcript_id}/pipeline")
def run_pipeline(
    transcript_id: int,
    req: TranscriptPipelineRequest,
    profile_id: int,
    session_id: str | None = None,
):
    _get_transcript_or_404(transcript_id, profile_id=profile_id, session_id=session_id)
    return pipeline_service.run_transcript_pipeline(
        transcript_id=transcript_id,
        preset=req.preset,
        action=req.action,
        model_name=req.model_name,
    )


@router.get("/transcripts/{transcript_id}/pipeline/latest")
def latest_pipeline(transcript_id: int, profile_id: int, session_id: str | None = None):
    _get_transcript_or_404(transcript_id, profile_id=profile_id, session_id=session_id)
    run = db.get_latest_pipeline_run(transcript_id)
    if not run:
        raise HTTPException(status_code=404, detail="pipeline_run_not_found")
    return run


@router.patch("/transcripts/{transcript_id}/pipeline/{run_id}/speakers")
def update_pipeline_speakers(
    transcript_id: int,
    run_id: int,
    req: TranscriptSpeakerOverridesRequest,
    profile_id: int,
    session_id: str | None = None,
):
    _get_transcript_or_404(transcript_id, profile_id=profile_id, session_id=session_id)
    run = db.get_pipeline_run(run_id)
    if not run or int(run.get("transcript_id") or 0) != int(transcript_id):
        raise HTTPException(status_code=404, detail="pipeline_run_not_found")
    return pipeline_service.update_speakers(run_id, req.overrides or {})


@router.post("/transcripts/{transcript_id}/pipeline/{run_id}/summary")
def regenerate_pipeline_summary(
    transcript_id: int,
    run_id: int,
    req: TranscriptSummaryRequest,
    profile_id: int,
    session_id: str | None = None,
):
    _get_transcript_or_404(transcript_id, profile_id=profile_id, session_id=session_id)
    run = db.get_pipeline_run(run_id)
    if not run or int(run.get("transcript_id") or 0) != int(transcript_id):
        raise HTTPException(status_code=404, detail="pipeline_run_not_found")
    return pipeline_service.regenerate_summary(run_id, save_memory=req.save_memory)
