from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UI_DIR = PROJECT_ROOT / "web_ui"
DATA_DIR = PROJECT_ROOT / "app" / "data"
DEFAULT_TTS_SPEED_OPTIONS = (1.0, 1.25, 1.5, 1.75, 2.0)


def _parse_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", ""}


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


models_dir = _resolve_path(os.getenv("MODELS_DIR"), PROJECT_ROOT / "models")
tts_models_dir = _resolve_path(os.getenv("TTS_MODELS_DIR"), models_dir / "tts")
piper_models_dir = _resolve_path(os.getenv("PIPER_MODELS_DIR"), tts_models_dir / "piper")
tts_data_dir = _resolve_path(os.getenv("TTS_DATA_DIR"), DATA_DIR / "tts")
tts_output_dir = _resolve_path(os.getenv("TTS_OUTPUT_DIR"), tts_data_dir / "output")
tts_history_dir = _resolve_path(os.getenv("TTS_HISTORY_DIR"), tts_data_dir / "history")
tts_temp_dir = _resolve_path(os.getenv("TTS_TEMP_DIR"), tts_data_dir / "temp")

for path in (
    models_dir,
    tts_models_dir,
    piper_models_dir,
    tts_data_dir,
    tts_output_dir,
    tts_history_dir,
    tts_temp_dir,
):
    path.mkdir(parents=True, exist_ok=True)

os.environ["MODELS_DIR"] = str(models_dir)
os.environ["TTS_MODELS_DIR"] = str(tts_models_dir)
os.environ["PIPER_MODELS_DIR"] = str(piper_models_dir)
os.environ["TTS_DATA_DIR"] = str(tts_data_dir)
os.environ["TTS_OUTPUT_DIR"] = str(tts_output_dir)
os.environ["TTS_HISTORY_DIR"] = str(tts_history_dir)
os.environ["TTS_TEMP_DIR"] = str(tts_temp_dir)


@dataclass(frozen=True)
class Settings:
    env: str
    tts_enabled: bool
    tts_default_provider: str
    tts_audio_format: str
    tts_max_text_chars: int
    tts_speed_options: tuple[float, ...]


def _load_settings() -> Settings:
    audio_format = (os.getenv("TTS_AUDIO_FORMAT", "wav") or "wav").strip().lower()
    if audio_format != "wav":
        audio_format = "wav"

    return Settings(
        env=(os.getenv("ENV", "local") or "local").strip(),
        tts_enabled=_parse_bool("TTS_ENABLED", True),
        tts_default_provider=(os.getenv("TTS_DEFAULT_PROVIDER", "piper") or "piper").strip().lower(),
        tts_audio_format=audio_format,
        tts_max_text_chars=max(1, _parse_int("TTS_MAX_TEXT_CHARS", 15000)),
        tts_speed_options=_parse_speed_options(os.getenv("TTS_SPEED_OPTIONS")),
    )


SETTINGS = _load_settings()
MODELS_DIR = models_dir
TTS_MODELS_DIR = tts_models_dir
PIPER_MODELS_DIR = piper_models_dir
TTS_DATA_DIR = tts_data_dir
TTS_OUTPUT_DIR = tts_output_dir
TTS_HISTORY_DIR = tts_history_dir
TTS_TEMP_DIR = tts_temp_dir
