from __future__ import annotations

from pydantic import BaseModel, Field


class TTSGenerateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice_id: str = Field(..., min_length=1)
    provider: str | None = None


class TTSSpeedProcessRequest(BaseModel):
    id: str = Field(..., min_length=1)
    speed: float


class TTSVoiceDownloadRequest(BaseModel):
    voice_key: str = Field(..., min_length=1)
    force: bool = False


class TTSVoicePreviewRequest(BaseModel):
    voice_id: str | None = None
    voice_key: str | None = None
    text: str | None = None
