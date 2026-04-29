from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


SourceType = Literal["upload", "recording", "manual"]


class TranscriptCreate(BaseModel):
    text: str
    source_type: SourceType = "manual"
    source_name: str | None = None
    model: str | None = None
    language: str | None = None
    duration_sec: float | None = None


class TranscriptUpdate(BaseModel):
    text: str | None = None
    source_name: str | None = None


class ModelPrepareRequest(BaseModel):
    model: str
    force: bool = False
