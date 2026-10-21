from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, StrictBool, StrictStr, field_validator, model_validator


CHAT_QUERY_MAX_CHARS = 32_000
CHAT_CONTEXT_MAX_CHARS = 64_000
CHAT_TRANSCRIPT_MAX_CHARS = 100_000
CHAT_CRITERIA_MAX_ITEMS = 200
CHAT_CRITERION_MAX_CHARS = 4_000
CHAT_UNTRUSTED_TOTAL_MAX_CHARS = 128_000
RAG_QUERY_MAX_CHARS = 16_000
RAG_TOP_K_MAX = 20


class ChatRequest(BaseModel):
    query: str = Field(max_length=CHAT_QUERY_MAX_CHARS)
    context: str | None = Field(default=None, max_length=CHAT_CONTEXT_MAX_CHARS)
    session_id: str | None = Field(default=None, max_length=128)
    profile_id: int | None = None
    transcript: str | None = Field(default=None, max_length=CHAT_TRANSCRIPT_MAX_CHARS)
    criteria: list[str] | None = Field(default=None, max_length=CHAT_CRITERIA_MAX_ITEMS)
    model: str | None = Field(default=None, max_length=200)
    model_name: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=160)
    role: str | None = Field(default=None, max_length=80)
    stream: bool = False
    attachment_ids: list[str] | None = Field(default=None, max_length=10)

    @field_validator("criteria")
    @classmethod
    def _bound_criteria(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(len(str(item or "")) > CHAT_CRITERION_MAX_CHARS for item in value):
            raise ValueError("criterion_too_large")
        return value

    @field_validator("attachment_ids")
    @classmethod
    def _bound_attachment_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(len(str(item or "")) > 128 for item in value):
            raise ValueError("attachment_id_too_large")
        return value

    @model_validator(mode="after")
    def _bound_untrusted_total(self) -> "ChatRequest":
        total = len(self.query or "") + len(self.context or "") + len(self.transcript or "")
        total += sum(len(str(item or "")) for item in (self.criteria or []))
        if total > CHAT_UNTRUSTED_TOTAL_MAX_CHARS:
            raise ValueError("chat_untrusted_input_too_large")
        return self


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
    system_prompt: str | None = Field(default=None, max_length=32_000)


class ProfileUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    system_prompt: str | None = Field(default=None, max_length=32_000)


class ChatPreferencesUpdate(BaseModel):
    dictation_model: str | None = None
    system_prompt: str | None = Field(default=None, max_length=32_000)


class AsrPreferencesUpdate(BaseModel):
    studio_model: str | None = None
    prompt_preset: str | None = None
    beam_size: int | None = None
    threads: int | None = None
    analysis_language: str | None = None
    analysis_prompt: str | None = None
    diagnostics_enabled: bool | None = None


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
    model_name: str = Field(min_length=1, max_length=200)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    num_ctx: int | None = Field(default=None, ge=1_024, le=262_144)
    mem_turns: int | None = Field(default=None, ge=0, le=100)
    ollama_keep_alive: str | None = None
    ollama_think: StrictBool | StrictStr | None = None
    pipeline_enabled: bool | None = None
    summary_memory_enabled: bool | None = None
    rag_enabled: bool | None = None
    default_pipeline_preset: str | None = None
    max_transcript_chars: int | None = Field(default=None, ge=1, le=100_000)
    max_context_chars: int | None = Field(default=None, ge=1, le=256_000)
    summary_memory_limit: int | None = Field(default=None, ge=1, le=100)
    rag_top_k: int | None = Field(default=None, ge=1, le=RAG_TOP_K_MAX)
    rag_max_context_chars: int | None = Field(default=None, ge=1, le=128_000)
    pipeline: dict[str, Any] | None = None


class RagIngestRequest(BaseModel):
    profile_id: int
    force: bool = False


class RagReindexRequest(BaseModel):
    profile_id: int


class RagSearchRequest(BaseModel):
    profile_id: int
    session_id: str | None = Field(default=None, max_length=128)
    query: str = Field(min_length=1, max_length=RAG_QUERY_MAX_CHARS)
    top_k: int | None = Field(default=None, ge=1, le=RAG_TOP_K_MAX)


class VisionContextExportRequest(BaseModel):
    profile_id: int
    session_id: str
    message_id: int
    title: str | None = None
    text: str


class ChatContextExportRequest(BaseModel):
    profile_id: int
    session_id: str
    message_id: int
    title: str | None = None
    text: str


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
    admin_token: str | None = None


class DatabaseCleanupRequest(BaseModel):
    vacuum: bool = True
    admin_token: str | None = None


class DatabaseResetRequest(BaseModel):
    confirm: str = Field(max_length=64)
    vacuum: bool = True
    admin_token: str | None = None


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
