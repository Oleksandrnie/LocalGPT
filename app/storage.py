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


def update_models_dir(new_dir: str, *, move_existing: bool = False) -> dict:
    normalized = Path(new_dir).expanduser().resolve()
    paths = config.update_model_paths(normalized, move_existing=move_existing)
    relative_base = normalized
    try:
        relative_base = normalized.relative_to(config.PROJECT_ROOT)
    except ValueError:
        relative_base = normalized

    base_value = str(relative_base)
    _write_env(
        {
            "MODELS_DIR": base_value,
            "OLLAMA_MODELS_DIR": str(paths.ollama),
            "WHISPER_MODELS_DIR": str(paths.whisper),
            "HF_CACHE_DIR": str(paths.hf_cache),
            "CTRANSLATE2_CACHE_DIR": str(paths.ctranslate2_cache),
        }
    )
    return paths.as_response()
