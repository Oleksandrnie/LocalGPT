from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UI_DIR = PROJECT_ROOT / "web_ui"
PROMPTS_DIR = Path(__file__).with_name("prompts")
LOG_DIR = PROJECT_ROOT / "tmp_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
CHAT_LOG_FILE = LOG_DIR / "chat.log"


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


def _resolve_models_base() -> Path:
    return _resolve_path(os.getenv("MODELS_DIR"), PROJECT_ROOT / "models")


@dataclass
class ModelPaths:
    base: Path
    ollama: Path
    whisper: Path
    hf_cache: Path
    ctranslate2_cache: Path

    def ensure(self) -> "ModelPaths":
        for path in (self.base, self.ollama, self.whisper, self.hf_cache, self.ctranslate2_cache):
            _ensure_dir(path)
        return self

    def as_response(self) -> dict:
        return {
            "base": str(self.base),
            "ollama": str(self.ollama),
            "whisper": str(self.whisper),
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


MODEL_RECOMMENDATIONS = [
    {"name": "qwen2.5:3b", "label": "Лёгкая (≈3B)"},
    {"name": "qwen2.5:7b-instruct", "label": "Инструкционная 7B"},
    {"name": "qwen2.5-7b-long", "label": "Длинный контекст 7B"},
    {"name": "llama3:8b", "label": "LLaMA 3 8B"},
    {"name": "mistral:7b", "label": "Mistral 7B"},
]


def build_model_paths(base_dir: Path | str | None = None) -> ModelPaths:
    base = _resolve_path(str(base_dir), PROJECT_ROOT / "models") if base_dir else _resolve_models_base()
    whisper_env = os.getenv("WHISPER_MODELS_DIR")
    ollama_env = os.getenv("OLLAMA_MODELS_DIR") or os.getenv("OLLAMA_MODELS")
    hf_env = os.getenv("HF_CACHE_DIR") or os.getenv("HUGGINGFACE_HUB_CACHE") or os.getenv("HF_HOME")
    ct2_env = os.getenv("CTRANSLATE2_CACHE_DIR") or os.getenv("CT2_TRANSLATORS_CACHE")

    paths = ModelPaths(
        base=base,
        ollama=_resolve_path(ollama_env, base / "ollama"),
        whisper=_resolve_path(whisper_env, base / "whisper"),
        hf_cache=_resolve_path(hf_env, base / "hf_cache"),
        ctranslate2_cache=_resolve_path(ct2_env, base / "ctranslate2_cache"),
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


def _load_settings() -> Settings:
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
        # shutil.move fails if target is inside source or already exists — fallback to merge copy
        shutil.copytree(source, target, dirs_exist_ok=True)


MODEL_PATHS = build_model_paths()
apply_model_env(MODEL_PATHS)
SETTINGS = _load_settings()
DEFAULT_SETTINGS = {
    "temperature": SETTINGS.temperature,
    "max_tokens": SETTINGS.max_tokens,
    "num_ctx": SETTINGS.num_ctx,
    "mem_turns": SETTINGS.mem_turns,
}
OLLAMA_ENV = {**os.environ, "OLLAMA_MODELS": str(MODEL_PATHS.ollama)}


def update_model_paths(new_base: Path | str, *, move_existing: bool = False) -> ModelPaths:
    global MODEL_PATHS, OLLAMA_ENV
    old_paths = MODEL_PATHS
    target_paths = build_model_paths(new_base)
    if move_existing:
        for src, dst in zip(
            (old_paths.ollama, old_paths.whisper, old_paths.hf_cache, old_paths.ctranslate2_cache),
            (target_paths.ollama, target_paths.whisper, target_paths.hf_cache, target_paths.ctranslate2_cache),
        ):
            _move_tree(src, dst)
    MODEL_PATHS = target_paths.ensure()
    apply_model_env(MODEL_PATHS)
    OLLAMA_ENV = {**os.environ, "OLLAMA_MODELS": str(MODEL_PATHS.ollama)}
    return MODEL_PATHS


def log_startup(logger: logging.Logger) -> None:
    logger.info(
        "Models dir: %s (ollama=%s, whisper=%s, hf_cache=%s, ctranslate2_cache=%s)",
        MODEL_PATHS.base,
        MODEL_PATHS.ollama,
        MODEL_PATHS.whisper,
        MODEL_PATHS.hf_cache,
        MODEL_PATHS.ctranslate2_cache,
    )
    logger.info(
        "Active model: %s • ctx=%s • max_tokens=%s • temp=%s • mem_turns=%s",
        SETTINGS.model,
        SETTINGS.num_ctx,
        SETTINGS.max_tokens,
        SETTINGS.temperature,
        SETTINGS.mem_turns,
    )
