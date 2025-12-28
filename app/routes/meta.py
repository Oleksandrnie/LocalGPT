from __future__ import annotations

from fastapi import APIRouter

from .. import config
from ..roles import DEFAULT_ROLE, list_roles

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "env": config.SETTINGS.env,
        "model": config.SETTINGS.model,
        "num_ctx": config.SETTINGS.num_ctx,
        "max_tokens": config.SETTINGS.max_tokens,
        "mem_turns": config.SETTINGS.mem_turns,
        "temperature": config.SETTINGS.temperature,
        "models_dir": str(config.MODEL_PATHS.base),
        "ollama_models_dir": str(config.MODEL_PATHS.ollama),
        "whisper_models_dir": str(config.MODEL_PATHS.whisper),
    }


@router.get("/version")
def version():
    return {"env": config.SETTINGS.env, "model": config.SETTINGS.model, "base_url": config.SETTINGS.base_url}


@router.get("/roles")
def roles():
    return {"roles": list_roles(), "default": DEFAULT_ROLE}
