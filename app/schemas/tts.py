from __future__ import annotations

from pydantic import BaseModel, Field


class TTSGenerateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice_id: str = Field(..., min_length=1)
    provider: str | None = None


class TTSSpeedProcessRequest(BaseModel):
    id: str = Field(..., min_length=1)
    speed: float
