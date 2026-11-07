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


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    profile_id: int = Field(gt=0)
    session_id: str | None = Field(default=None, max_length=128)
    model_name: str = Field(default="", max_length=200)
    top_k: int = Field(default=8, ge=1, le=20)

    model_config = {"extra": "forbid"}


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
