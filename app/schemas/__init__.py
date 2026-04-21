"""Pydantic schemas for LocalGPT."""

from .core import (
    AsrPreferencesUpdate,
    ChatRequest,
    ChatPreferencesUpdate,
    ModelPrepareRequest,
    ModelPullRequest,
    ModelSettingsRequest,
    ModelSettingsReset,
    ProfileCreate,
    ProfilePreferencesUpdate,
    ResetRequest,
    SessionCreate,
    SessionUpdate,
    StorageUpdateRequest,
    TranscriptCreate,
    TranscriptUpdate,
    TtsPreferencesUpdate,
)
from .tts import (
    TTSGenerateRequest,
    TTSSpeedProcessRequest,
    TTSVoiceDownloadRequest,
    TTSVoicePreviewRequest,
)

__all__ = [
    "ChatRequest",
    "ChatPreferencesUpdate",
    "AsrPreferencesUpdate",
    "ModelPrepareRequest",
    "ModelPullRequest",
    "ModelSettingsRequest",
    "ModelSettingsReset",
    "ProfileCreate",
    "ProfilePreferencesUpdate",
    "ResetRequest",
    "SessionCreate",
    "SessionUpdate",
    "StorageUpdateRequest",
    "TranscriptCreate",
    "TranscriptUpdate",
    "TtsPreferencesUpdate",
    "TTSGenerateRequest",
    "TTSSpeedProcessRequest",
    "TTSVoiceDownloadRequest",
    "TTSVoicePreviewRequest",
]
