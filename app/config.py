from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UI_DIR = PROJECT_ROOT / "web_ui"
PROMPTS_DIR = Path(__file__).with_name("prompts")
LOG_DIR = PROJECT_ROOT / "tmp_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
CHAT_LOG_FILE = LOG_DIR / "chat.log"
PIPELINE_LOG_FILE = LOG_DIR / "pipeline.log"
DATA_DIR = PROJECT_ROOT / "app" / "data"
RAG_SOURCE_DIR = PROJECT_ROOT / "rag_sources"
DEFAULT_TTS_SPEED_OPTIONS = (1.0, 1.25, 1.5, 1.75, 2.0)
ALLOWED_WHISPER_MODELS = (
    "tiny",
    "base",
    "small",
    "medium",
    "large-v3",
    "large-v3-turbo",
)
ASR_STUDIO_DEFAULT_MODEL = "large-v3-turbo"


def _parse_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


def _parse_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_path(raw: str | None, fallback: Path) -> Path:
    if not raw:
        return fallback.expanduser().resolve()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _parse_speed_options(raw: str | None) -> tuple[float, ...]:
    if not raw:
        return DEFAULT_TTS_SPEED_OPTIONS

    values: list[float] = []
    seen: set[float] = set()
    for chunk in raw.split(","):
        item = chunk.strip()
        if not item:
            continue
        try:
            value = round(float(item), 2)
        except ValueError:
            continue
        if value < 1.0 or value > 2.0 or value in seen:
            continue
        values.append(value)
        seen.add(value)

    return tuple(values) if values else DEFAULT_TTS_SPEED_OPTIONS


@dataclass
class ModelPaths:
    base: Path
    ollama: Path
    whisper: Path
    hf_cache: Path
    ctranslate2_cache: Path
    tts: Path
    piper: Path

    def ensure(self) -> "ModelPaths":
        for path in (
            self.base,
            self.ollama,
            self.whisper,
            self.hf_cache,
            self.ctranslate2_cache,
            self.tts,
            self.piper,
        ):
            _ensure_dir(path)
        return self

    def as_response(self) -> dict[str, str]:
        return {
            "base": str(self.base),
            "chat": str(self.ollama),
            "asr": str(self.whisper),
            "tts": str(self.tts),
            "ollama": str(self.ollama),
            "whisper": str(self.whisper),
            "piper": str(self.piper),
            "hf_cache": str(self.hf_cache),
            "ctranslate2_cache": str(self.ctranslate2_cache),
        }


@dataclass
class Settings:
    env: str
    base_url: str
    api_key: str
    model: str
    temperature: float
    max_tokens: int
    num_ctx: int
    mem_turns: int
    admin_token: str
    tts_enabled: bool
    tts_default_provider: str
    tts_audio_format: str
    tts_max_text_chars: int
    tts_speed_options: tuple[float, ...]
    whisper_default_model: str
    whisper_compute_type: str
    whisper_device: str
    whisper_beam_size: int
    whisper_fallback_language: str


MODEL_RECOMMENDATIONS = [
    {"name": "qwen2.5:3b", "label": "Лёгкая (≈3B)"},
    {"name": "qwen2.5:7b-instruct", "label": "Инструкционная 7B"},
    {"name": "qwen2.5-7b-long", "label": "Длинный контекст 7B"},
    {"name": "llama3:8b", "label": "LLaMA 3 8B"},
    {"name": "mistral:7b", "label": "Mistral 7B"},
]

DEFAULT_PIPELINE = {
    "cleaner": {
        "enabled": True,
        "model": "qwen2.5:3b",
        "temperature": 0.2,
        "max_tokens": 1200,
    },
    "segmenter": {
        "enabled": True,
        "model": "qwen2.5:3b",
        "temperature": 0.1,
        "max_tokens": 1600,
    },
    "speaker_resolver": {
        "enabled": True,
        "model": "qwen2.5:3b",
        "temperature": 0.1,
        "max_tokens": 1800,
    },
    "structurer": {
        "enabled": True,
        "model": "mistral:7b",
        "temperature": 0.3,
        "max_tokens": 2000,
    },
    "summary": {
        "enabled": True,
        "model": "mistral:7b",
        "temperature": 0.3,
        "max_tokens": 2000,
    },
}

DEFAULT_RUNTIME_SETTINGS = {
    "pipeline_enabled": True,
    "summary_memory_enabled": True,
    "rag_enabled": False,
    "default_pipeline_preset": "balanced",
    "max_transcript_chars": 24000,
    "max_context_chars": 16000,
    "summary_memory_limit": 5,
    "rag_top_k": 5,
    "rag_max_context_chars": 6000,
    "pipeline": DEFAULT_PIPELINE,
}


def build_model_paths(base_dir: Path | str | None = None) -> ModelPaths:
    use_env_overrides = base_dir is None
    base = _resolve_path(str(base_dir), PROJECT_ROOT / "models") if base_dir else _resolve_path(os.getenv("MODELS_DIR"), PROJECT_ROOT / "models")
    ollama_env = (os.getenv("OLLAMA_MODELS_DIR") or os.getenv("OLLAMA_MODELS")) if use_env_overrides else None
    whisper_env = os.getenv("WHISPER_MODELS_DIR") if use_env_overrides else None
    hf_env = (os.getenv("HF_CACHE_DIR") or os.getenv("HUGGINGFACE_HUB_CACHE") or os.getenv("HF_HOME")) if use_env_overrides else None
    ct2_env = (os.getenv("CTRANSLATE2_CACHE_DIR") or os.getenv("CT2_TRANSLATORS_CACHE")) if use_env_overrides else None
    tts_env = os.getenv("TTS_MODELS_DIR") if use_env_overrides else None
    piper_env = os.getenv("PIPER_MODELS_DIR") if use_env_overrides else None

    paths = ModelPaths(
        base=base,
        ollama=_resolve_path(ollama_env, base / "ollama"),
        whisper=_resolve_path(whisper_env, base / "whisper"),
        hf_cache=_resolve_path(hf_env, base / "hf_cache"),
        ctranslate2_cache=_resolve_path(ct2_env, base / "ctranslate2_cache"),
        tts=_resolve_path(tts_env, base / "tts"),
        piper=_resolve_path(piper_env, _resolve_path(tts_env, base / "tts") / "piper"),
    )
    return paths.ensure()


def apply_model_env(paths: ModelPaths) -> None:
    os.environ["MODELS_DIR"] = str(paths.base)
    os.environ["OLLAMA_MODELS"] = str(paths.ollama)
    os.environ["OLLAMA_MODELS_DIR"] = str(paths.ollama)
    os.environ["WHISPER_MODELS_DIR"] = str(paths.whisper)
    os.environ["HF_HOME"] = str(paths.hf_cache)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(paths.hf_cache)
    os.environ["HF_CACHE_DIR"] = str(paths.hf_cache)
    os.environ["CTRANSLATE2_CACHE_DIR"] = str(paths.ctranslate2_cache)
    os.environ["CT2_TRANSLATORS_CACHE"] = str(paths.ctranslate2_cache)
    os.environ["TTS_MODELS_DIR"] = str(paths.tts)
    os.environ["PIPER_MODELS_DIR"] = str(paths.piper)


def _load_settings() -> Settings:
    audio_format = (os.getenv("TTS_AUDIO_FORMAT", "wav") or "wav").strip().lower()
    if audio_format != "wav":
        audio_format = "wav"
    raw_whisper_model = (os.getenv("WHISPER_MODEL_SIZE", "medium") or "medium").strip()
    whisper_default_model = raw_whisper_model if raw_whisper_model in ALLOWED_WHISPER_MODELS else "medium"

    return Settings(
        env=os.getenv("ENV", "local"),
        base_url=os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1"),
        api_key=os.getenv("LOCAL_API_KEY", "LOCAL-KEY"),
        model=os.getenv("LOCAL_MODEL", "qwen2.5:3b"),
        temperature=_parse_float("TEMP", 0.25),
        max_tokens=_parse_int("MAX_TOKENS", 512),
        num_ctx=_parse_int("NUM_CTX", 32768),
        mem_turns=_parse_int("MEM_TURNS", 6),
        admin_token=os.getenv("ADMIN_TOKEN", ""),
        tts_enabled=_parse_bool("TTS_ENABLED", True),
        tts_default_provider=(os.getenv("TTS_DEFAULT_PROVIDER", "piper") or "piper").strip().lower(),
        tts_audio_format=audio_format,
        tts_max_text_chars=max(1, _parse_int("TTS_MAX_TEXT_CHARS", 15000)),
        tts_speed_options=_parse_speed_options(os.getenv("TTS_SPEED_OPTIONS")),
        whisper_default_model=whisper_default_model,
        whisper_compute_type=(os.getenv("WHISPER_COMPUTE_TYPE", "int8") or "int8").strip(),
        whisper_device=(os.getenv("WHISPER_DEVICE", "cpu") or "cpu").strip(),
        whisper_beam_size=max(1, _parse_int("WHISPER_BEAM_SIZE", 5)),
        whisper_fallback_language=(os.getenv("WHISPER_FALLBACK_LANGUAGE", "ru") or "ru").strip().lower(),
    )


def _move_tree(source: Path, target: Path) -> None:
    if source.resolve() == target.resolve():
        return
    if not source.exists():
        _ensure_dir(target)
        return
    _ensure_dir(target.parent)
    try:
        shutil.move(str(source), str(target))
    except shutil.Error:
        shutil.copytree(source, target, dirs_exist_ok=True)


MODEL_PATHS = build_model_paths()
apply_model_env(MODEL_PATHS)
SETTINGS = _load_settings()
DEFAULT_SETTINGS = {
    "temperature": SETTINGS.temperature,
    "max_tokens": SETTINGS.max_tokens,
    "num_ctx": SETTINGS.num_ctx,
    "mem_turns": SETTINGS.mem_turns,
    **DEFAULT_RUNTIME_SETTINGS,
}
OLLAMA_ENV = {**os.environ, "OLLAMA_MODELS": str(MODEL_PATHS.ollama)}

TTS_DATA_DIR = _resolve_path(os.getenv("TTS_DATA_DIR"), DATA_DIR / "tts")
TTS_OUTPUT_DIR = _resolve_path(os.getenv("TTS_OUTPUT_DIR"), TTS_DATA_DIR / "output")
TTS_HISTORY_DIR = _resolve_path(os.getenv("TTS_HISTORY_DIR"), TTS_DATA_DIR / "history")
TTS_TEMP_DIR = _resolve_path(os.getenv("TTS_TEMP_DIR"), TTS_DATA_DIR / "temp")

for path in (DATA_DIR, RAG_SOURCE_DIR, TTS_DATA_DIR, TTS_OUTPUT_DIR, TTS_HISTORY_DIR, TTS_TEMP_DIR):
    path.mkdir(parents=True, exist_ok=True)

os.environ["TTS_DATA_DIR"] = str(TTS_DATA_DIR)
os.environ["TTS_OUTPUT_DIR"] = str(TTS_OUTPUT_DIR)
os.environ["TTS_HISTORY_DIR"] = str(TTS_HISTORY_DIR)
os.environ["TTS_TEMP_DIR"] = str(TTS_TEMP_DIR)

MODELS_DIR = MODEL_PATHS.base
WHISPER_MODELS_DIR = MODEL_PATHS.whisper
HF_CACHE_DIR = MODEL_PATHS.hf_cache
CTRANSLATE2_CACHE_DIR = MODEL_PATHS.ctranslate2_cache
TTS_MODELS_DIR = MODEL_PATHS.tts
PIPER_MODELS_DIR = MODEL_PATHS.piper


def update_model_paths(new_base: Path | str, *, move_existing: bool = False) -> ModelPaths:
    global MODEL_PATHS, OLLAMA_ENV, MODELS_DIR, WHISPER_MODELS_DIR, HF_CACHE_DIR, CTRANSLATE2_CACHE_DIR, TTS_MODELS_DIR, PIPER_MODELS_DIR
    old_paths = MODEL_PATHS
    target_paths = build_model_paths(new_base)
    if move_existing:
        for src, dst in zip(
            (
                old_paths.ollama,
                old_paths.whisper,
                old_paths.hf_cache,
                old_paths.ctranslate2_cache,
                old_paths.tts,
            ),
            (
                target_paths.ollama,
                target_paths.whisper,
                target_paths.hf_cache,
                target_paths.ctranslate2_cache,
                target_paths.tts,
            ),
        ):
            _move_tree(src, dst)
    MODEL_PATHS = target_paths.ensure()
    apply_model_env(MODEL_PATHS)
    OLLAMA_ENV = {**os.environ, "OLLAMA_MODELS": str(MODEL_PATHS.ollama)}
    MODELS_DIR = MODEL_PATHS.base
    WHISPER_MODELS_DIR = MODEL_PATHS.whisper
    HF_CACHE_DIR = MODEL_PATHS.hf_cache
    CTRANSLATE2_CACHE_DIR = MODEL_PATHS.ctranslate2_cache
    TTS_MODELS_DIR = MODEL_PATHS.tts
    PIPER_MODELS_DIR = MODEL_PATHS.piper
    return MODEL_PATHS


def log_startup(logger: logging.Logger) -> None:
    logger.info(
        "Models dir: %s (chat=%s, asr=%s, tts=%s, piper=%s, hf_cache=%s, ctranslate2_cache=%s)",
        MODEL_PATHS.base,
        MODEL_PATHS.ollama,
        MODEL_PATHS.whisper,
        MODEL_PATHS.tts,
        MODEL_PATHS.piper,
        MODEL_PATHS.hf_cache,
        MODEL_PATHS.ctranslate2_cache,
    )
    logger.info(
        "Active model: %s • ctx=%s • max_tokens=%s • temp=%s • mem_turns=%s • tts_provider=%s",
        SETTINGS.model,
        SETTINGS.num_ctx,
        SETTINGS.max_tokens,
        SETTINGS.temperature,
        SETTINGS.mem_turns,
        SETTINGS.tts_default_provider,
    )
