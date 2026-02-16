from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ALLOWED_WHISPER_MODELS = (
    "tiny",
    "base",
    "small",
    "medium",
    "large-v3",
    "large-v3-turbo",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UI_DIR = PROJECT_ROOT / "web_ui"
DATA_DIR = PROJECT_ROOT / "app" / "data"


def _parse_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _resolve_path(raw: str | None, fallback: Path) -> Path:
    if not raw:
        return fallback.resolve()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


models_dir = _resolve_path(os.getenv("MODELS_DIR"), PROJECT_ROOT / "models")
whisper_models_dir = _resolve_path(os.getenv("WHISPER_MODELS_DIR"), models_dir)
default_hf_home_dir = models_dir / "huggingface"
hf_home_dir = _resolve_path(os.getenv("HF_HOME"), default_hf_home_dir)
hf_hub_cache_dir = _resolve_path(
    os.getenv("HUGGINGFACE_HUB_CACHE") or os.getenv("HF_CACHE_DIR"),
    hf_home_dir / "hub",
)
ctranslate2_cache_dir = _resolve_path(
    os.getenv("CTRANSLATE2_CACHE_DIR") or os.getenv("CT2_TRANSLATORS_CACHE"),
    models_dir / "ctranslate2_cache",
)
transcripts_dir = _resolve_path(os.getenv("TRANSCRIPTS_DIR"), DATA_DIR / "transcripts")

for path in (models_dir, whisper_models_dir, hf_home_dir, hf_hub_cache_dir, ctranslate2_cache_dir, transcripts_dir):
    path.mkdir(parents=True, exist_ok=True)

for model_name in ALLOWED_WHISPER_MODELS:
    (whisper_models_dir / model_name).mkdir(parents=True, exist_ok=True)

os.environ["MODELS_DIR"] = str(models_dir)
os.environ["WHISPER_MODELS_DIR"] = str(whisper_models_dir)
os.environ["HF_HOME"] = str(hf_home_dir)
os.environ["HUGGINGFACE_HUB_CACHE"] = str(hf_hub_cache_dir)
os.environ["HF_CACHE_DIR"] = str(hf_hub_cache_dir)
os.environ["CTRANSLATE2_CACHE_DIR"] = str(ctranslate2_cache_dir)
os.environ["CT2_TRANSLATORS_CACHE"] = str(ctranslate2_cache_dir)
os.environ["TRANSCRIPTS_DIR"] = str(transcripts_dir)


@dataclass(frozen=True)
class Settings:
    env: str
    whisper_default_model: str
    whisper_compute_type: str
    whisper_device: str
    whisper_beam_size: int
    whisper_fallback_language: str


def _load_settings() -> Settings:
    raw_default_model = (os.getenv("WHISPER_MODEL_SIZE", "small") or "small").strip()
    default_model = raw_default_model if raw_default_model in ALLOWED_WHISPER_MODELS else "small"

    return Settings(
        env=(os.getenv("ENV", "local") or "local").strip(),
        whisper_default_model=default_model,
        whisper_compute_type=(os.getenv("WHISPER_COMPUTE_TYPE", "auto") or "auto").strip(),
        whisper_device=(os.getenv("WHISPER_DEVICE", "auto") or "auto").strip(),
        whisper_beam_size=max(1, _parse_int("WHISPER_BEAM_SIZE", 5)),
        whisper_fallback_language=(os.getenv("WHISPER_FALLBACK_LANGUAGE", "ru") or "ru").strip().lower(),
    )


SETTINGS = _load_settings()
MODELS_DIR = models_dir
WHISPER_MODELS_DIR = whisper_models_dir
HF_HOME_DIR = hf_home_dir
HF_CACHE_DIR = hf_hub_cache_dir
CTRANSLATE2_CACHE_DIR = ctranslate2_cache_dir
TRANSCRIPTS_DIR = transcripts_dir
