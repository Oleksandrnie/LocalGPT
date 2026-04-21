from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str
    context: str | None = None
    session_id: str | None = None
    profile_id: int | None = None
    transcript: str | None = None
    criteria: list[str] | None = None
    model: str | None = None
    model_name: str | None = None
    title: str | None = None
    role: str | None = None


class ModelPullRequest(BaseModel):
    model: str


class ModelPrepareRequest(BaseModel):
    model: str
    force: bool = False


class ProfileCreate(BaseModel):
    name: str
    description: str | None = None
    color: str | None = None


class ChatPreferencesUpdate(BaseModel):
    dictation_model: str | None = None


class AsrPreferencesUpdate(BaseModel):
    studio_model: str | None = None
    prompt_preset: str | None = None


class TtsPreferencesUpdate(BaseModel):
    provider: str | None = None
    voice_id: str | None = None
    speed: str | None = None


class ProfilePreferencesUpdate(BaseModel):
    chat: ChatPreferencesUpdate | None = None
    asr: AsrPreferencesUpdate | None = None
    tts: TtsPreferencesUpdate | None = None


class SessionCreate(BaseModel):
    profile_id: int
    title: str | None = None
    model_name: str | None = None
    role: str | None = None


class SessionUpdate(BaseModel):
    title: str | None = None
    model_name: str | None = None
    role: str | None = None


class ModelSettingsRequest(BaseModel):
    profile_id: int
    model_name: str
    temperature: float | None = None
    max_tokens: int | None = None
    num_ctx: int | None = None
    mem_turns: int | None = None


class ModelSettingsReset(BaseModel):
    profile_id: int
    model_name: str


class TranscriptCreate(BaseModel):
    profile_id: int
    session_id: str | None = None
    name: str
    content: str
    source_path: str | None = None
    language: str | None = None
    timeline: list[dict] | None = None
    role_keywords: dict | None = None
    labels: dict | None = None


class TranscriptUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    language: str | None = None
    timeline: list[dict] | None = None
    role_keywords: dict | None = None
    labels: dict | None = None


class ResetRequest(BaseModel):
    session_id: str
    admin_token: str | None = None


class StorageUpdateRequest(BaseModel):
    models_dir: str
    move_existing: bool = False
