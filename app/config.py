from __future__ import annotations

import logging
import os
import platform
import shlex
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
TRANSCRIBE_LOG_FILE = LOG_DIR / "transcribe.log"
ASR_DIAGNOSTICS_DIR = LOG_DIR / "asr_diagnostics"
DATA_DIR = PROJECT_ROOT / "app" / "data"
CHAT_ATTACHMENTS_DIR = DATA_DIR / "chat_attachments"
RAG_SOURCE_DIR = PROJECT_ROOT / "rag_sources"
DEFAULT_TTS_SPEED_OPTIONS = (1.0, 1.25, 1.5, 1.75, 2.0)
DEFAULT_CORS_ALLOW_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost|127\.0\.0\.1|\[::1\]|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
    r"100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}|"
    r"[a-z0-9.-]+\.local"
    r")(:[0-9]+)?$"
)
ALLOWED_WHISPER_MODELS = (
    "tiny",
    "base",
    "small",
    "medium",
    "large-v3",
    "large-v3-turbo",
)
ASR_STUDIO_DEFAULT_MODEL = "large-v3-turbo"
APPLE_SILICON_PIPELINE_NUM_GPU = 999


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


def _parse_optional_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    value = raw.strip().lower()
    if not value or value in {"auto", "default", "none", "null"}:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _default_pipeline_num_gpu() -> int | None:
    if os.getenv("OLLAMA_PIPELINE_NUM_GPU") is not None:
        return _parse_optional_int("OLLAMA_PIPELINE_NUM_GPU")
    if platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}:
        return APPLE_SILICON_PIPELINE_NUM_GPU
    return None


def _parse_args(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return ()
    try:
        return tuple(shlex.split(raw))
    except ValueError:
        return ()


def _parse_csv(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return ()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _parse_keep_alive(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    return value if value else default


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
    whisper_cpp: Path
    hf_cache: Path
    ctranslate2_cache: Path
    tts: Path
    piper: Path

    def ensure(self) -> "ModelPaths":
        for path in (
            self.base,
            self.ollama,
            self.whisper,
            self.whisper_cpp,
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
            "whisper_cpp": str(self.whisper_cpp),
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
    ollama_chat_keep_alive: str
    ollama_auto_target_keep_alive: str
    ollama_manual_keep_alive: str
    ollama_code_keep_alive: str
    ollama_router_keep_alive: str
    ollama_heavy_keep_alive: str
    ollama_pipeline_keep_alive: str
    ollama_pipeline_num_gpu: int | None
    max_resident_target_models: int
    allow_light_with_heavy: bool
    single_large_target_model: bool
    preload_model_on_manual_select: bool
    admin_token: str
    tts_enabled: bool
    tts_default_provider: str
    tts_audio_format: str
    tts_max_text_chars: int
    tts_speed_options: tuple[float, ...]
    whisper_default_model: str
    whisper_backend: str
    whisper_compute_type: str
    whisper_device: str
    whisper_beam_size: int
    whisper_fallback_language: str
    whisper_cpp_binary: str
    whisper_cpp_models_dir: Path
    whisper_cpp_model_path: str
    whisper_cpp_threads: int
    whisper_cpp_extra_args: tuple[str, ...]
    whisper_cpp_convert_audio: bool
    whisper_cpp_ffmpeg_binary: str
    whisper_cpp_download_coreml: bool
    cors_allow_origins: tuple[str, ...]
    cors_allow_origin_regex: str


MODEL_CATALOG = [
    {
        "id": "qwen2.5:3b-instruct",
        "title": "Qwen 2.5 3B Instruct",
        "category": "fast_rag",
        "weight": "light",
        "recommended": True,
        "experimental": False,
        "description": (
            "Быстрый слой: RAG, короткие ответы и быстрые уточнения. Для ASR pipeline использовать "
            "как fallback, когда важна скорость, а не качество длинной встречи."
        ),
    },
    {
        "id": "qwen2.5:7b-instruct",
        "title": "Qwen 2.5 7B Instruct",
        "category": "default_chat",
        "weight": "medium",
        "recommended": True,
        "experimental": False,
        "description": (
            "Основная рабочая модель: обычный чат, RAG с нормальным качеством, рабочие формулировки, "
            "summary среднего размера."
        ),
    },
    {
        "id": "qwen3:8b",
        "title": "Qwen 3 8B",
        "category": "thinking",
        "weight": "medium",
        "recommended": True,
        "experimental": False,
        "description": (
            "Thinking/reasoning-модель: сложные вопросы, анализ, проверка логики, ситуации где нужно "
            "подумать, а не быстро ответить."
        ),
    },
    {
        "id": "mistral-nemo:12b",
        "title": "Mistral Nemo 12B",
        "category": "pipeline_heavy",
        "weight": "heavy",
        "recommended": True,
        "experimental": False,
        "description": (
            "Тяжёлая модель для pipeline: summary, structuring, выделение decisions/tasks/risks/open "
            "questions. На M1 Pro 16GB может работать медленнее."
        ),
    },
    {
        "id": "qwen2.5-coder:7b",
        "title": "Qwen 2.5 Coder 7B",
        "category": "code",
        "weight": "medium",
        "recommended": True,
        "experimental": False,
        "description": (
            "Основная модель для кода: Python, FastAPI, JavaScript, Docker, отладка, рефакторинг и "
            "анализ ошибок."
        ),
    },
    {
        "id": "deepseek-coder:6.7b",
        "title": "DeepSeek Coder 6.7B",
        "category": "code_alt",
        "weight": "medium",
        "recommended": True,
        "experimental": False,
        "description": (
            "Альтернативная кодовая модель для сравнения с Qwen Coder. Полезна для проверки решений, "
            "генерации патчей и разбора ошибок."
        ),
    },
    {
        "id": "qwen3:4b",
        "title": "Qwen 3 4B",
        "category": "experimental",
        "weight": "light_medium",
        "recommended": False,
        "experimental": True,
        "description": (
            "Экспериментальная модель: компромисс между qwen2.5 3B и qwen3 8B. Проверить как быстрый "
            "reasoning/RAG fallback."
        ),
    },
]

VISION_MODEL_CATALOG = [
    {
        "id": "qwen2.5vl:3b",
        "title": "Qwen 2.5 VL 3B",
        "category": "vision",
        "weight": "light_medium",
        "recommended": True,
        "experimental": False,
        "capabilities": ["text", "vision"],
        "description": (
            "Основная локальная vision-модель для изображений, документов, схем и интерфейсов. "
            "Рекомендуемый первый вариант для M1 Pro 16GB; загружается только по явному действию пользователя."
        ),
    },
    {
        "id": "qwen2.5vl:7b",
        "title": "Qwen 2.5 VL 7B",
        "category": "vision_quality",
        "weight": "medium_heavy",
        "recommended": False,
        "experimental": False,
        "capabilities": ["text", "vision"],
        "description": (
            "Более качественный vision-профиль для сложных документов и диаграмм. "
            "Требует больше памяти и не выбирается автоматически, пока 3B доступна."
        ),
    },
    {
        "id": "gemma3:4b",
        "title": "Gemma 3 4B Vision",
        "category": "vision_alt",
        "weight": "light_medium",
        "recommended": False,
        "experimental": True,
        "capabilities": ["text", "vision"],
        "description": (
            "Альтернативная multimodal-модель для сравнительной проверки качества. "
            "Не загружается и не выбирается автоматически без явного действия пользователя."
        ),
    },
]

UTILITY_MODEL_CATALOG = [
    {
        "id": "qwen3:0.6b",
        "title": "Qwen 3 0.6B Router",
        "category": "utility_router",
        "weight": "ultra_light",
        "recommended": False,
        "experimental": False,
        "utility": True,
        "description": (
            "Служебная router-модель для режима Auto / Smart Router. Используется только для классификации "
            "chat-запроса и выбора target-модели, не как обычная модель ответа."
        ),
    },
]

# Backward-compatible response key for older UI modules; the content is the new catalog.
MODEL_RECOMMENDATIONS = MODEL_CATALOG

DEFAULT_PIPELINE = {
    "cleaner": {
        "enabled": False,
        "model": "qwen2.5:7b-instruct",
        "temperature": 0,
        "max_tokens": 6000,
    },
    "segmenter": {
        "enabled": False,
        "model": "qwen2.5:7b-instruct",
        "temperature": 0.05,
        "max_tokens": 6000,
    },
    "speaker_resolver": {
        "enabled": False,
        "model": "qwen2.5:7b-instruct",
        "temperature": 0,
        "max_tokens": 3000,
    },
    "structurer": {
        "enabled": True,
        "model": "qwen3:8b",
        "temperature": 0.05,
        "max_tokens": 6000,
    },
    "summary": {
        "enabled": True,
        "model": "qwen3:8b",
        "temperature": 0.05,
        "max_tokens": 7000,
    },
}

DEFAULT_RUNTIME_SETTINGS = {
    "streaming_enabled": True,
    "pipeline_enabled": True,
    "asr_full_analysis_enabled": False,
    "summary_memory_enabled": True,
    "rag_enabled": False,
    "default_pipeline_preset": "balanced",
    "max_transcript_chars": 24000,
    "max_context_chars": 16000,
    "summary_memory_limit": 5,
    "rag_top_k": 5,
    "rag_max_context_chars": 6000,
    "chat_images_enabled": True,
    "max_images_per_message": 1,
    "chat_image_max_file_bytes": 20 * 1024 * 1024,
    "chat_image_max_total_bytes": 40 * 1024 * 1024,
    "chat_image_max_pixels": 16_000_000,
    "chat_image_max_side": 4096,
    "vision_model": "auto",
    "ocr_assist": "auto",
    "ollama_think": "auto",
    "show_router_thinking_toggle": False,
    "pipeline": DEFAULT_PIPELINE,
}


def build_model_paths(base_dir: Path | str | None = None) -> ModelPaths:
    use_env_overrides = base_dir is None
    base = _resolve_path(str(base_dir), PROJECT_ROOT / "models") if base_dir else _resolve_path(os.getenv("MODELS_DIR"), PROJECT_ROOT / "models")
    ollama_env = (os.getenv("OLLAMA_MODELS_DIR") or os.getenv("OLLAMA_MODELS")) if use_env_overrides else None
    whisper_env = os.getenv("WHISPER_MODELS_DIR") if use_env_overrides else None
    whisper_cpp_env = os.getenv("WHISPER_CPP_MODELS_DIR") if use_env_overrides else None
    hf_env = (os.getenv("HF_CACHE_DIR") or os.getenv("HUGGINGFACE_HUB_CACHE") or os.getenv("HF_HOME")) if use_env_overrides else None
    ct2_env = (os.getenv("CTRANSLATE2_CACHE_DIR") or os.getenv("CT2_TRANSLATORS_CACHE")) if use_env_overrides else None
    tts_env = os.getenv("TTS_MODELS_DIR") if use_env_overrides else None
    piper_env = os.getenv("PIPER_MODELS_DIR") if use_env_overrides else None

    paths = ModelPaths(
        base=base,
        ollama=_resolve_path(ollama_env, base / "ollama"),
        whisper=_resolve_path(whisper_env, base / "whisper"),
        whisper_cpp=_resolve_path(whisper_cpp_env, base / "whisper_cpp"),
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
    os.environ["WHISPER_CPP_MODELS_DIR"] = str(paths.whisper_cpp)
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
    raw_whisper_model = (os.getenv("WHISPER_MODEL_SIZE", ASR_STUDIO_DEFAULT_MODEL) or ASR_STUDIO_DEFAULT_MODEL).strip()
    whisper_default_model = raw_whisper_model if raw_whisper_model in ALLOWED_WHISPER_MODELS else ASR_STUDIO_DEFAULT_MODEL
    whisper_backend = (os.getenv("WHISPER_BACKEND", "whisper_cpp") or "whisper_cpp").strip().lower()
    whisper_backend = whisper_backend.replace("-", "_")
    if whisper_backend not in {"auto", "faster_whisper", "whisper_cpp"}:
        whisper_backend = "faster_whisper"

    return Settings(
        env=os.getenv("ENV", "local"),
        base_url=os.getenv("LOCAL_BASE_URL", "http://localhost:11434/v1"),
        api_key=os.getenv("LOCAL_API_KEY", "LOCAL-KEY"),
        model=(os.getenv("LOCAL_MODEL") or "").strip(),
        temperature=_parse_float("TEMP", 0.25),
        max_tokens=_parse_int("MAX_TOKENS", 512),
        num_ctx=_parse_int("NUM_CTX", 32768),
        mem_turns=_parse_int("MEM_TURNS", 6),
        ollama_chat_keep_alive=_parse_keep_alive("OLLAMA_CHAT_KEEP_ALIVE", "4m"),
        ollama_auto_target_keep_alive=_parse_keep_alive(
            "OLLAMA_AUTO_TARGET_KEEP_ALIVE",
            _parse_keep_alive("OLLAMA_CHAT_KEEP_ALIVE", "4m"),
        ),
        ollama_manual_keep_alive=_parse_keep_alive(
            "OLLAMA_MANUAL_KEEP_ALIVE",
            "5m",
        ),
        ollama_code_keep_alive=_parse_keep_alive("OLLAMA_CODE_KEEP_ALIVE", "2m"),
        ollama_router_keep_alive=_parse_keep_alive("OLLAMA_ROUTER_KEEP_ALIVE", "2m"),
        ollama_heavy_keep_alive=_parse_keep_alive("OLLAMA_HEAVY_KEEP_ALIVE", "60s"),
        ollama_pipeline_keep_alive=_parse_keep_alive("OLLAMA_PIPELINE_KEEP_ALIVE", "0"),
        ollama_pipeline_num_gpu=_default_pipeline_num_gpu(),
        max_resident_target_models=_parse_int("MAX_RESIDENT_TARGET_MODELS", 1),
        allow_light_with_heavy=_parse_bool("ALLOW_LIGHT_WITH_HEAVY", False),
        single_large_target_model=_parse_bool("SINGLE_LARGE_TARGET_MODEL", True),
        preload_model_on_manual_select=_parse_bool("PRELOAD_MODEL_ON_MANUAL_SELECT", False),
        admin_token=os.getenv("ADMIN_TOKEN", ""),
        tts_enabled=_parse_bool("TTS_ENABLED", True),
        tts_default_provider=(os.getenv("TTS_DEFAULT_PROVIDER", "piper") or "piper").strip().lower(),
        tts_audio_format=audio_format,
        tts_max_text_chars=max(1, _parse_int("TTS_MAX_TEXT_CHARS", 15000)),
        tts_speed_options=_parse_speed_options(os.getenv("TTS_SPEED_OPTIONS")),
        whisper_default_model=whisper_default_model,
        whisper_backend=whisper_backend,
        whisper_compute_type=(os.getenv("WHISPER_COMPUTE_TYPE", "int8") or "int8").strip(),
        whisper_device=(os.getenv("WHISPER_DEVICE", "cpu") or "cpu").strip(),
        whisper_beam_size=max(1, _parse_int("WHISPER_BEAM_SIZE", 5)),
        whisper_fallback_language=(os.getenv("WHISPER_FALLBACK_LANGUAGE", "ru") or "ru").strip().lower(),
        whisper_cpp_binary=(
            os.getenv("WHISPER_CPP_BINARY", str(MODEL_PATHS.whisper_cpp / "bin" / "whisper-cli"))
            or str(MODEL_PATHS.whisper_cpp / "bin" / "whisper-cli")
        ).strip(),
        whisper_cpp_models_dir=MODEL_PATHS.whisper_cpp,
        whisper_cpp_model_path=(os.getenv("WHISPER_CPP_MODEL_PATH", "") or "").strip(),
        whisper_cpp_threads=max(0, _parse_int("WHISPER_CPP_THREADS", 4)),
        whisper_cpp_extra_args=_parse_args("WHISPER_CPP_EXTRA_ARGS"),
        whisper_cpp_convert_audio=_parse_bool("WHISPER_CPP_CONVERT_AUDIO", True),
        whisper_cpp_ffmpeg_binary=(os.getenv("WHISPER_CPP_FFMPEG_BINARY", "ffmpeg") or "ffmpeg").strip(),
        whisper_cpp_download_coreml=_parse_bool("WHISPER_CPP_DOWNLOAD_COREML", True),
        cors_allow_origins=_parse_csv("LOCALGPT_CORS_ALLOW_ORIGINS"),
        cors_allow_origin_regex=(
            os.getenv("LOCALGPT_CORS_ALLOW_ORIGIN_REGEX", DEFAULT_CORS_ALLOW_ORIGIN_REGEX)
            or ""
        ).strip(),
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
DEFAULT_RUNTIME_SETTINGS.update(
    {
        "mem_turns": SETTINGS.mem_turns,
        "max_resident_target_models": max(1, min(5, SETTINGS.max_resident_target_models)),
        "allow_light_with_heavy": SETTINGS.allow_light_with_heavy,
        "single_large_target_model": SETTINGS.single_large_target_model,
        "preload_model_on_manual_select": SETTINGS.preload_model_on_manual_select,
        "auto_target_keep_alive": SETTINGS.ollama_auto_target_keep_alive,
        "manual_keep_alive": SETTINGS.ollama_manual_keep_alive,
        "code_model_keep_alive": SETTINGS.ollama_code_keep_alive,
        "heavy_model_keep_alive": SETTINGS.ollama_heavy_keep_alive,
        "router_keep_alive": SETTINGS.ollama_router_keep_alive,
        "pipeline_keep_alive": SETTINGS.ollama_pipeline_keep_alive,
        "pipeline_num_gpu": SETTINGS.ollama_pipeline_num_gpu,
    }
)
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

for path in (
    DATA_DIR,
    CHAT_ATTACHMENTS_DIR,
    RAG_SOURCE_DIR,
    TTS_DATA_DIR,
    TTS_OUTPUT_DIR,
    TTS_HISTORY_DIR,
    TTS_TEMP_DIR,
):
    path.mkdir(parents=True, exist_ok=True)
SETTINGS.whisper_cpp_models_dir.mkdir(parents=True, exist_ok=True)

os.environ["TTS_DATA_DIR"] = str(TTS_DATA_DIR)
os.environ["TTS_OUTPUT_DIR"] = str(TTS_OUTPUT_DIR)
os.environ["TTS_HISTORY_DIR"] = str(TTS_HISTORY_DIR)
os.environ["TTS_TEMP_DIR"] = str(TTS_TEMP_DIR)

MODELS_DIR = MODEL_PATHS.base
WHISPER_MODELS_DIR = MODEL_PATHS.whisper
WHISPER_CPP_MODELS_DIR = MODEL_PATHS.whisper_cpp
HF_CACHE_DIR = MODEL_PATHS.hf_cache
CTRANSLATE2_CACHE_DIR = MODEL_PATHS.ctranslate2_cache
TTS_MODELS_DIR = MODEL_PATHS.tts
PIPER_MODELS_DIR = MODEL_PATHS.piper


def update_model_paths(new_base: Path | str, *, move_existing: bool = False) -> ModelPaths:
    global MODEL_PATHS, OLLAMA_ENV, MODELS_DIR, WHISPER_MODELS_DIR, WHISPER_CPP_MODELS_DIR, HF_CACHE_DIR, CTRANSLATE2_CACHE_DIR, TTS_MODELS_DIR, PIPER_MODELS_DIR
    old_paths = MODEL_PATHS
    target_paths = build_model_paths(new_base)
    if move_existing:
        for src, dst in zip(
            (
                old_paths.ollama,
                old_paths.whisper,
                old_paths.whisper_cpp,
                old_paths.hf_cache,
                old_paths.ctranslate2_cache,
                old_paths.tts,
            ),
            (
                target_paths.ollama,
                target_paths.whisper,
                target_paths.whisper_cpp,
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
    WHISPER_CPP_MODELS_DIR = MODEL_PATHS.whisper_cpp
    HF_CACHE_DIR = MODEL_PATHS.hf_cache
    CTRANSLATE2_CACHE_DIR = MODEL_PATHS.ctranslate2_cache
    TTS_MODELS_DIR = MODEL_PATHS.tts
    PIPER_MODELS_DIR = MODEL_PATHS.piper
    return MODEL_PATHS


def log_startup(logger: logging.Logger) -> None:
    logger.info(
        "Models dir: %s (chat=%s, asr=%s, whisper_cpp=%s, tts=%s, piper=%s, hf_cache=%s, ctranslate2_cache=%s)",
        MODEL_PATHS.base,
        MODEL_PATHS.ollama,
        MODEL_PATHS.whisper,
        MODEL_PATHS.whisper_cpp,
        MODEL_PATHS.tts,
        MODEL_PATHS.piper,
        MODEL_PATHS.hf_cache,
        MODEL_PATHS.ctranslate2_cache,
    )
    logger.info(
        "Active model: %s • ctx=%s • max_tokens=%s • temp=%s • mem_turns=%s • tts_provider=%s",
        SETTINGS.model or "not loaded",
        SETTINGS.num_ctx,
        SETTINGS.max_tokens,
        SETTINGS.temperature,
        SETTINGS.mem_turns,
        SETTINGS.tts_default_provider,
    )
    logger.info(
        "CORS: origins=%s regex=%s",
        ",".join(SETTINGS.cors_allow_origins) or "none",
        SETTINGS.cors_allow_origin_regex or "none",
    )
