from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatAttachmentResponse(BaseModel):
    id: str
    profile_id: int
    session_id: str | None = None
    message_id: int | None = None
    task_id: str | None = None
    mime_type: str
    original_name: str
    size_bytes: int
    width: int
    height: int
    status: str
    thumbnail_url: str
    media_url: str
    created_at: str
    updated_at: str
    error: str | None = None


class ChatAttachmentListResponse(BaseModel):
    attachments: list[ChatAttachmentResponse]


class AttachmentCleanupRequest(BaseModel):
    scope: Literal["profile", "orphans"] = "profile"
    profile_id: int
    temporary_ttl_seconds: int = Field(default=24 * 60 * 60, ge=60, le=30 * 24 * 60 * 60)


class AttachmentCleanupResult(BaseModel):
    scope: str
    profile_id: int
    deleted_count: int
    deleted_bytes: int
    skipped_active_count: int = 0
    errors: list[str] = Field(default_factory=list)
