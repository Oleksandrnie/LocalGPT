from __future__ import annotations

from pathlib import Path
from typing import Dict

from . import config

ENV_FILE = config.PROJECT_ROOT / ".env"


def _write_env(updates: Dict[str, str]) -> None:
    lines: list[str] = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()

    output: list[str] = []
    seen_keys = set()

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            output.append(raw_line)
            continue
        key, _ = raw_line.split("=", 1)
        key = key.strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen_keys.add(key)
        else:
            output.append(raw_line)

    for key, value in updates.items():
        if key not in seen_keys:
            output.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(output) + "\n", encoding="utf-8")


def describe_paths() -> dict:
    return config.MODEL_PATHS.as_response()


def _to_portable_env_path(path: Path) -> str:
    normalized = path.expanduser().resolve()
    try:
        return str(normalized.relative_to(config.PROJECT_ROOT))
    except ValueError:
        return str(normalized)


def update_models_dir(new_dir: str, *, move_existing: bool = False) -> dict:
    normalized = Path(new_dir).expanduser().resolve()
    paths = config.update_model_paths(normalized, move_existing=move_existing)
    _write_env(
        {
            "MODELS_DIR": _to_portable_env_path(paths.base),
            "OLLAMA_MODELS_DIR": _to_portable_env_path(paths.ollama),
            "WHISPER_MODELS_DIR": _to_portable_env_path(paths.whisper),
            "HF_CACHE_DIR": _to_portable_env_path(paths.hf_cache),
            "CTRANSLATE2_CACHE_DIR": _to_portable_env_path(paths.ctranslate2_cache),
            "TTS_MODELS_DIR": _to_portable_env_path(paths.tts),
            "PIPER_MODELS_DIR": _to_portable_env_path(paths.piper),
        }
    )
    return paths.as_response()
