from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from ..schemas.tts import (
    TTSGenerateRequest,
    TTSSpeedProcessRequest,
    TTSVoiceDownloadRequest,
    TTSVoicePreviewRequest,
)
from ..services import tts_service

router = APIRouter()


def _cleanup_temp_file(file_path: str) -> None:
    try:
        Path(file_path).unlink()
    except OSError:
        pass


def _raise_service_error(exc: tts_service.TTSServiceError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    ) from exc


@router.get("/tts/health")
def tts_health() -> dict[str, object]:
    return tts_service.get_health()


@router.get("/tts/voices")
def tts_voices() -> dict[str, object]:
    return {"items": tts_service.list_voices()}


@router.get("/tts/voice-library")
def tts_voice_library(force_refresh: bool = Query(default=False)) -> dict[str, object]:
    try:
        return {"items": tts_service.list_voice_catalog(force_refresh=bool(force_refresh))}
    except tts_service.TTSServiceError as exc:
        _raise_service_error(exc)


@router.post("/tts/voice-library/download", status_code=202)
def tts_voice_library_download(req: TTSVoiceDownloadRequest) -> dict[str, object]:
    try:
        return tts_service.start_voice_download(req.voice_key, force=bool(req.force))
    except tts_service.TTSServiceError as exc:
        _raise_service_error(exc)


@router.get("/tts/voice-library/download/{task_id}")
def tts_voice_library_download_status(task_id: str) -> dict[str, object]:
    try:
        return tts_service.get_voice_download_task(task_id)
    except tts_service.TTSServiceError as exc:
        _raise_service_error(exc)


@router.get("/tts/voice-library/downloads")
def tts_voice_library_downloads() -> dict[str, object]:
    return {"items": tts_service.list_voice_download_tasks()}


@router.delete("/tts/voice-library/{voice_key}")
def tts_voice_library_delete(voice_key: str) -> dict[str, object]:
    try:
        return tts_service.delete_voice(voice_key)
    except tts_service.TTSServiceError as exc:
        _raise_service_error(exc)


@router.post("/tts/voice-library/preview")
def tts_voice_library_preview(req: TTSVoicePreviewRequest):
    try:
        path, filename = tts_service.create_voice_preview_file(
            voice_id=req.voice_id,
            voice_key=req.voice_key,
            text=req.text,
        )
    except tts_service.TTSServiceError as exc:
        _raise_service_error(exc)

    return FileResponse(
        path,
        media_type="audio/wav",
        filename=filename,
        background=BackgroundTask(_cleanup_temp_file, path),
    )


@router.post("/tts/generate", status_code=202)
def tts_generate(req: TTSGenerateRequest) -> dict[str, object]:
    try:
        return tts_service.start_generation(
            text=req.text,
            voice_id=req.voice_id,
            provider=req.provider,
        )
    except tts_service.TTSServiceError as exc:
        _raise_service_error(exc)


@router.post("/tts/process-speed", status_code=202)
def tts_process_speed(req: TTSSpeedProcessRequest) -> dict[str, object]:
    try:
        return tts_service.start_speed_processing(req.id, req.speed)
    except tts_service.TTSServiceError as exc:
        _raise_service_error(exc)


@router.get("/tts/history")
def tts_history() -> dict[str, object]:
    return {"items": tts_service.list_history()}


@router.get("/tts/history/{record_id}")
def tts_history_item(record_id: str) -> dict[str, object]:
    try:
        return tts_service.get_history_item(record_id)
    except tts_service.TTSServiceError as exc:
        _raise_service_error(exc)


@router.delete("/tts/history/{record_id}")
def tts_delete_history_item(record_id: str) -> dict[str, object]:
    try:
        tts_service.delete_history_item(record_id)
    except tts_service.TTSServiceError as exc:
        _raise_service_error(exc)
    return {"ok": True, "id": record_id}


@router.get("/tts/output/{record_id}")
def tts_output(
    record_id: str,
    variant: Literal["base", "processed"] = Query(default="base"),
    speed: float | None = Query(default=None),
    download: bool = Query(default=False),
):
    try:
        path, filename = tts_service.resolve_output_file(record_id, variant=variant, speed=speed)
    except tts_service.TTSServiceError as exc:
        _raise_service_error(exc)

    return FileResponse(
        path,
        media_type="audio/wav",
        filename=filename if download else None,
    )
