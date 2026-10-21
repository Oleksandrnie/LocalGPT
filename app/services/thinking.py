"""Settings compatibility and exact Ollama thinking-control values."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from . import models


def resolve_thinking(value: Any) -> bool | str | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if not isinstance(value, str):
        raise invalid_thinking()
    normalized = value.strip().lower()
    if normalized in {"auto", "default", ""}:
        return None
    if normalized in {"on", "true", "1", "yes", "think"}:
        return True
    if normalized in {"off", "false", "0", "no", "nothink"}:
        return False
    if not models.THINKING_VALUE_RE.fullmatch(value):
        raise invalid_thinking()
    return value


def invalid_thinking() -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"code": "invalid_ollama_think", "message": "Unsupported thinking value for this model."},
    )


def validate_thinking(model_name: str, value: bool | str) -> None:
    """New exact values require provider evidence; legacy aliases need no probe.

    /show only reads metadata and never loads a model. Missing metadata retains
    boolean compatibility, but cannot authorize arbitrary named provider values.
    """
    control = models._normalize_thinking(models._show_model_details(model_name).get("thinking"))
    if control is None:
        if isinstance(value, str):
            raise invalid_thinking()
        return
    if not any(type(item) is type(value) and item == value for item in control["values"]):
        raise invalid_thinking()


def normalize_thinking_setting(value: Any, model_name: str) -> str | None:
    if value is None:
        return None
    resolved = resolve_thinking(value)
    if isinstance(value, bool) or isinstance(resolved, str):
        validate_thinking(model_name, resolved)
        if isinstance(resolved, str):
            return resolved
    return "auto" if resolved is None else "on" if resolved else "off"
