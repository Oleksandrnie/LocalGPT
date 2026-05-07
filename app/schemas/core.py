from __future__ import annotations

from typing import Any

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
    stream: bool = False


class ModelPullRequest(BaseModel):
    model: str


class ModelPreloadRequest(BaseModel):
    model: str
    profile_id: int | None = None


class ModelPrepareRequest(BaseModel):
    model: str
    force: bool = False


class ProfileCreate(BaseModel):
    name: str
    description: str | None = None
    color: str | None = None
    system_prompt: str | None = None


class ProfileUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    system_prompt: str | None = None


class ChatPreferencesUpdate(BaseModel):
    dictation_model: str | None = None
    system_prompt: str | None = None


class AsrPreferencesUpdate(BaseModel):
    studio_model: str | None = None
    prompt_preset: str | None = None
    beam_size: int | None = None
    threads: int | None = None


class TtsPreferencesUpdate(BaseModel):
    provider: str | None = None
    voice_id: str | None = None
    speed: str | None = None


class ProfilePreferencesUpdate(BaseModel):
    chat: ChatPreferencesUpdate | None = None
    asr: AsrPreferencesUpdate | None = None
    tts: TtsPreferencesUpdate | None = None
    settings: dict[str, Any] | None = None


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
    ollama_keep_alive: str | None = None
    pipeline_enabled: bool | None = None
    summary_memory_enabled: bool | None = None
    rag_enabled: bool | None = None
    default_pipeline_preset: str | None = None
    max_transcript_chars: int | None = None
    max_context_chars: int | None = None
    summary_memory_limit: int | None = None
    rag_top_k: int | None = None
    rag_max_context_chars: int | None = None
    pipeline: dict[str, Any] | None = None


class RagIngestRequest(BaseModel):
    profile_id: int
    force: bool = False


class RagSearchRequest(BaseModel):
    profile_id: int
    query: str
    top_k: int | None = None


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
    summary: str | None = None
    structured_json: dict[str, Any] | list[Any] | None = None
    latest_pipeline_run_id: int | None = None


class TranscriptUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    language: str | None = None
    timeline: list[dict] | None = None
    role_keywords: dict | None = None
    labels: dict | None = None
    summary: str | None = None
    structured_json: dict[str, Any] | list[Any] | None = None
    latest_pipeline_run_id: int | None = None


class ResetRequest(BaseModel):
    session_id: str
    admin_token: str | None = None


class StorageUpdateRequest(BaseModel):
    models_dir: str
    move_existing: bool = False


class DatabaseCleanupRequest(BaseModel):
    vacuum: bool = True


class DatabaseResetRequest(BaseModel):
    confirm: str
    vacuum: bool = True


class TranscriptPipelineRequest(BaseModel):
    preset: str | None = None
    action: str | None = None
    model_name: str | None = None


class TranscriptSpeakerOverridesRequest(BaseModel):
    overrides: dict[str, str] | None = None


class TranscriptSummaryRequest(BaseModel):
    save_memory: bool = True


class ChatDebugPromptRequest(ChatRequest):
    admin_token: str | None = None
