from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from secrets import token_hex
from tempfile import NamedTemporaryFile
from typing import Any

from . import config

TRANSCRIPTS_DIR = config.TRANSCRIPTS_DIR
ALLOWED_SOURCE_TYPES = {"upload", "recording", "manual"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_source_type(source_type: str | None) -> str:
    value = (source_type or "manual").strip().lower()
    if value in ALLOWED_SOURCE_TYPES:
        return value
    return "manual"


def _normalize_source_name(source_name: str | None, source_type: str) -> str:
    name = (source_name or "").strip()
    if name:
        return name
    return {
        "upload": "uploaded_file",
        "recording": "voice_recording",
        "manual": "manual_edit",
    }.get(source_type, "manual_edit")


def _normalize_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    return normalized


def _build_preview(text: str, limit_words: int = 12, max_chars: int = 90) -> str:
    clean = _normalize_text(text)
    if not clean:
        return ""
    words = clean.split(" ")
    preview = " ".join(words[:limit_words])
    if len(preview) > max_chars:
        preview = preview[: max_chars - 1].rstrip() + "…"
    elif len(words) > limit_words:
        preview = preview.rstrip() + "…"
    return preview


def _record_path(transcript_id: str) -> Path:
    return TRANSCRIPTS_DIR / f"{transcript_id}.json"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp_file:
        json.dump(payload, tmp_file, ensure_ascii=False, indent=2)
        tmp_file.flush()
        temp_name = tmp_file.name
    Path(temp_name).replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _generate_id() -> str:
    now = datetime.now(timezone.utc)
    return f"tr_{now:%Y%m%d_%H%M%S}_{token_hex(3)}"


def _sanitize_duration(duration_sec: float | int | None) -> float | None:
    if duration_sec is None:
        return None
    try:
        value = float(duration_sec)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return round(value, 3)


def _metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "source_type": record.get("source_type"),
        "source_name": record.get("source_name"),
        "model": record.get("model"),
        "language": record.get("language"),
        "duration_sec": record.get("duration_sec"),
        "preview": record.get("preview", ""),
    }


def create_transcript(
    *,
    text: str,
    source_type: str = "manual",
    source_name: str | None = None,
    model: str | None = None,
    language: str | None = None,
    duration_sec: float | int | None = None,
) -> dict[str, Any]:
    normalized_text = (text or "").strip()
    if not normalized_text:
        raise ValueError("text_required")

    now = _utc_now()
    normalized_source_type = _normalize_source_type(source_type)
    transcript_id = _generate_id()

    record: dict[str, Any] = {
        "id": transcript_id,
        "created_at": now,
        "updated_at": now,
        "source_type": normalized_source_type,
        "source_name": _normalize_source_name(source_name, normalized_source_type),
        "model": (model or "").strip() or None,
        "language": (language or "").strip() or None,
        "duration_sec": _sanitize_duration(duration_sec),
        "preview": _build_preview(normalized_text),
        "text": normalized_text,
    }

    _atomic_write_json(_record_path(transcript_id), record)
    return record


def list_transcripts() -> list[dict[str, Any]]:
    if not TRANSCRIPTS_DIR.exists():
        return []

    items: list[dict[str, Any]] = []
    for path in TRANSCRIPTS_DIR.glob("tr_*.json"):
        payload = _read_json(path)
        if not payload:
            continue
        items.append(_metadata(payload))

    items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return items


def get_transcript(transcript_id: str) -> dict[str, Any] | None:
    if not transcript_id:
        return None
    path = _record_path(transcript_id)
    if not path.exists():
        return None
    return _read_json(path)


def update_transcript(
    transcript_id: str,
    *,
    text: str | None = None,
    source_name: str | None = None,
) -> dict[str, Any] | None:
    existing = get_transcript(transcript_id)
    if not existing:
        return None

    if text is not None:
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("text_required")
        existing["text"] = normalized_text
        existing["preview"] = _build_preview(normalized_text)

    if source_name is not None:
        normalized_source = source_name.strip()
        if normalized_source:
            existing["source_name"] = normalized_source

    existing["updated_at"] = _utc_now()
    _atomic_write_json(_record_path(transcript_id), existing)
    return existing
