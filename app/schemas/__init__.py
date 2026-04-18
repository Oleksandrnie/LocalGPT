"""Pydantic schemas for LocalGPT."""

from .core import (
    ChatRequest,
    ModelPullRequest,
    ModelSettingsRequest,
    ModelSettingsReset,
    ProfileCreate,
    ResetRequest,
    SessionCreate,
    SessionUpdate,
    StorageUpdateRequest,
    TranscriptCreate,
    TranscriptUpdate,
)
from .tts import (
    TTSGenerateRequest,
    TTSSpeedProcessRequest,
    TTSVoiceDownloadRequest,
    TTSVoicePreviewRequest,
)

__all__ = [
    "ChatRequest",
    "ModelPullRequest",
    "ModelSettingsRequest",
    "ModelSettingsReset",
    "ProfileCreate",
    "ResetRequest",
    "SessionCreate",
    "SessionUpdate",
    "StorageUpdateRequest",
    "TranscriptCreate",
    "TranscriptUpdate",
    "TTSGenerateRequest",
    "TTSSpeedProcessRequest",
    "TTSVoiceDownloadRequest",
    "TTSVoicePreviewRequest",
]
