from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app import config, db
from backend.apps.chat.schemas import (
    AttachmentCleanupRequest,
    AttachmentCleanupResult,
    ChatAttachmentListResponse,
    ChatAttachmentResponse,
)
from backend.apps.chat.services import attachment_storage


router = APIRouter()


def _raise_storage_error(exc: attachment_storage.AttachmentStorageError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message, **exc.details},
    ) from exc


def _effective_image_settings(profile_id: int, session_id: str | None) -> dict[str, Any]:
    model_name = config.SETTINGS.model or "__chat_attachments__"
    if session_id:
        session = db.get_session(session_id)
        if session and int(session.get("profile_id") or 0) == int(profile_id):
            model_name = str(session.get("model_name") or model_name)
    return db.effective_settings(int(profile_id), model_name, config.DEFAULT_SETTINGS).get("effective") or {}


def _public_attachment(record: dict[str, Any]) -> ChatAttachmentResponse:
    profile_id = int(record["profile_id"])
    query = urlencode({"profile_id": profile_id})
    attachment_id = str(record["id"])
    return ChatAttachmentResponse(
        id=attachment_id,
        profile_id=profile_id,
        session_id=record.get("session_id"),
        message_id=record.get("message_id"),
        task_id=record.get("task_id"),
        mime_type=str(record.get("mime_type") or ""),
        original_name=str(record.get("original_name") or "image"),
        size_bytes=int(record.get("size_bytes") or 0),
        width=int(record.get("width") or 0),
        height=int(record.get("height") or 0),
        status=str(record.get("status") or "ready"),
        thumbnail_url=f"/chat/attachments/{attachment_id}/thumbnail?{query}",
        media_url=f"/chat/attachments/{attachment_id}?{query}",
        created_at=str(record.get("created_at") or ""),
        updated_at=str(record.get("updated_at") or ""),
        error=record.get("error"),
    )


@router.post("/chat/attachments", response_model=ChatAttachmentResponse)
def upload_chat_attachment(
    file: UploadFile = File(...),
    profile_id: int = Form(...),
    session_id: str | None = Form(default=None),
) -> ChatAttachmentResponse:
    try:
        settings = _effective_image_settings(profile_id, session_id)
        record = attachment_storage.store_upload(
            file_stream=file.file,
            filename=file.filename,
            content_type=file.content_type,
            profile_id=profile_id,
            session_id=(session_id or "").strip() or None,
            settings=settings,
        )
        return _public_attachment(record)
    except attachment_storage.AttachmentStorageError as exc:
        _raise_storage_error(exc)
    finally:
        file.file.close()


@router.get("/chat/attachments", response_model=ChatAttachmentListResponse)
def list_chat_attachments(
    profile_id: int,
    session_id: str | None = None,
    message_id: int | None = None,
) -> ChatAttachmentListResponse:
    profile = db.get_profile(profile_id)
    if not profile or not profile.get("is_active", 1):
        raise HTTPException(status_code=404, detail={"code": "PROFILE_NOT_FOUND", "message": "Профиль не найден."})
    records = db.list_chat_attachments(
        profile_id=profile_id,
        session_id=(session_id or "").strip() or None,
        message_id=message_id,
    )
    return ChatAttachmentListResponse(attachments=[_public_attachment(record) for record in records])


@router.get("/chat/attachments/cache")
def get_chat_attachment_cache(profile_id: int) -> dict[str, Any]:
    try:
        return attachment_storage.attachment_cache_stats(profile_id=profile_id)
    except attachment_storage.AttachmentStorageError as exc:
        _raise_storage_error(exc)


def _owned_path(attachment_id: str, profile_id: int, field: str) -> tuple[dict[str, Any], Path]:
    try:
        record = attachment_storage.get_owned_attachment(attachment_id, profile_id)
        return record, attachment_storage.resolve_storage_path(str(record.get(field) or ""))
    except attachment_storage.AttachmentStorageError as exc:
        _raise_storage_error(exc)


@router.get("/chat/attachments/{attachment_id}")
def get_chat_attachment_media(attachment_id: str, profile_id: int = Query(...)) -> FileResponse:
    record, path = _owned_path(attachment_id, profile_id, "storage_path")
    if not path.is_file():
        raise HTTPException(status_code=404, detail={"code": "ATTACHMENT_NOT_FOUND", "message": "Файл вложения не найден."})
    return FileResponse(
        path,
        media_type=str(record.get("mime_type") or "application/octet-stream"),
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/chat/attachments/{attachment_id}/thumbnail")
def get_chat_attachment_thumbnail(attachment_id: str, profile_id: int = Query(...)) -> FileResponse:
    _, path = _owned_path(attachment_id, profile_id, "thumbnail_path")
    if not path.is_file():
        raise HTTPException(status_code=404, detail={"code": "ATTACHMENT_NOT_FOUND", "message": "Thumbnail не найден."})
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "private, no-store"})


@router.delete("/chat/attachments/{attachment_id}")
def delete_chat_attachment(attachment_id: str, profile_id: int = Query(...)) -> dict[str, Any]:
    try:
        return {"deleted": True, **attachment_storage.delete_attachment(attachment_id, profile_id)}
    except attachment_storage.AttachmentStorageError as exc:
        _raise_storage_error(exc)


@router.post("/chat/attachments/cleanup", response_model=AttachmentCleanupResult)
def cleanup_chat_attachments(req: AttachmentCleanupRequest) -> AttachmentCleanupResult:
    try:
        result = attachment_storage.cleanup_attachments(
            profile_id=req.profile_id,
            scope=req.scope,
            temporary_ttl_seconds=req.temporary_ttl_seconds,
        )
        return AttachmentCleanupResult(**result)
    except attachment_storage.AttachmentStorageError as exc:
        _raise_storage_error(exc)
