from __future__ import annotations

import hmac
from typing import Any

from fastapi import HTTPException

from . import config


ADMIN_TOKEN_HEADER = "X-LocalGPT-Admin-Token"
_LOG_TEXT_FIELDS = frozenset({"query", "reply", "error", "prompt", "messages", "profile_system_prompt"})
_LOG_SAFE_FIELDS = frozenset(
    {
        "ts",
        "status",
        "session_id",
        "profile_id",
        "model",
        "role",
        "criteria_count",
        "transcript_chars",
        "elapsed_ms",
        "error_code",
        "event",
        "task_id",
    }
)


def admin_token_matches(provided: str | None) -> bool:
    expected = str(config.SETTINGS.admin_token or "")
    candidate = str(provided or "")
    return bool(expected and candidate and hmac.compare_digest(candidate, expected))


def require_admin_token(provided: str | None) -> None:
    if not str(config.SETTINGS.admin_token or ""):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "admin_token_not_configured",
                "message": "Set ADMIN_TOKEN before using privileged LocalGPT operations.",
            },
        )
    if not admin_token_matches(provided):
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "Administrator authorization is required."},
        )


def redact_log_event(payload: dict[str, object]) -> dict[str, Any]:
    event: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _LOG_TEXT_FIELDS:
            event[f"{key}_chars"] = len(str(value or ""))
        elif key in _LOG_SAFE_FIELDS and isinstance(value, (str, int, float, bool, type(None))):
            event[key] = value
    event.setdefault("event", "chat")
    return event


def public_error_detail(code: str, message: str) -> dict[str, str]:
    return {"code": str(code or "operation_failed"), "message": str(message or "Operation failed.")}
