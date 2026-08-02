from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from app import config, db

SOURCE_TYPE = "manual_file"
ASR_CONTEXT_SOURCE_TYPE = "asr_context"
VISION_CONTEXT_SOURCE_TYPE = "vision_context"
EMBEDDING_MODEL = "local-hash-v1"
SUPPORTED_SUFFIXES = {".md"}
MAX_FILE_BYTES = 5 * 1024 * 1024
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 180
VECTOR_DIMS = 256
TOKEN_RE = re.compile(r"[\wа-яА-ЯёЁ]{2,}", re.UNICODE)
PRICE_LINE_RE = re.compile(r"(?P<hours>\d+)\s*(?:час|часа|часов)\s*[—-]\s*(?P<price>[\d\s]+)\s*₽", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
KEY_VALUE_RE = re.compile(r"^\s*[-*]?\s*([^:：]{2,80})[:：]\s*(.+)$")


def source_root() -> Path:
    config.RAG_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    return config.RAG_SOURCE_DIR


def _slug(value: str) -> str:
    text = re.sub(r"[^\w.-]+", "_", (value or "").strip(), flags=re.UNICODE).strip("._")
    return text[:80] or "profile"


def profile_source_dir(profile_id: int, *, create: bool = True) -> Path:
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="profile_not_found")
    path = source_root() / f"profile_{profile_id}_{_slug(str(profile.get('name') or 'profile'))}"
    if create:
        path.mkdir(parents=True, exist_ok=True)
        keep = path / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
    return path


def ensure_profile_source_dir(profile_id: int) -> Path:
    return profile_source_dir(profile_id, create=True)


def delete_profile_source_dir(profile_id: int) -> None:
    for path in source_root().glob(f"profile_{profile_id}_*"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)


def source_dir(profile_id: int | None = None) -> Path:
    return profile_source_dir(profile_id) if profile_id is not None else source_root()


def _relative_source_id(path: Path, profile_id: int | None = None) -> str:
    root = source_dir(profile_id).resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="rag_file_outside_source_dir") from exc


def _resolve_source_file(profile_id: int, source_id: str) -> Path:
    clean_source_id = (source_id or "").strip().lstrip("/\\")
    if not clean_source_id:
        raise HTTPException(status_code=422, detail="rag_file_required")
    root = source_dir(profile_id).resolve()
    path = (root / clean_source_id).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="rag_file_outside_source_dir") from exc
    if path.name.startswith(".") or path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=400, detail="rag_file_unsupported")
    return path


def _iter_source_files(profile_id: int) -> list[Path]:
    root = source_dir(profile_id)
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix().lower())


def _read_text_file(path: Path) -> str:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("file_too_large")
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_sections(text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    intro: list[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        heading = HEADING_RE.match(line)
        if heading:
            if current is None and intro:
                sections.append({"level": 1, "title": "Основной текст", "bullets": [], "text": intro})
                intro = []
            current = {
                "level": len(heading.group(1)),
                "title": heading.group(2).strip(),
                "bullets": [],
                "text": [],
            }
            sections.append(current)
            continue
        if current is None:
            if line:
                intro.append(line[2:].strip() if line.startswith(("- ", "* ")) else line)
            continue
        if line.startswith(("- ", "* ")):
            current["bullets"].append(line[2:].strip())
        elif line:
            current["text"].append(line)
    if current is None and intro:
        sections.append({"level": 1, "title": "Основной текст", "bullets": [], "text": intro})
    return sections


def _pricing_facts(text: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    current_line = ""
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        heading = HEADING_RE.match(line)
        if heading and len(heading.group(1)) >= 3:
            title = heading.group(2).strip()
            if title.lower() in {"базовый", "оптимальный", "премиальный", "максимальный / премиальный"}:
                current_line = title
            continue
        if not current_line:
            continue
        match = PRICE_LINE_RE.search(line)
        if not match:
            continue
        facts.append(
            {
                "line": current_line,
                "hours": int(match.group("hours")),
                "price": int(re.sub(r"\D+", "", match.group("price"))),
            }
        )
    return facts


def _source_kind(path: Path) -> str:
    name = path.name.lower()
    if "pricing" in name or "price" in name or "tariff" in name:
        return "pricing"
    if "sla" in name:
        return "sla"
    if "template" in name:
        return "template"
    if "profile" in name or "persona" in name or "career" in name:
        return "profile"
    if "link" in name:
        return "links"
    if "system prompt" in name or "prompt" in name:
        return "system_prompt"
    if "index" in name:
        return "index"
    return "knowledge_base"


def _flatten_section_facts(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for section in sections:
        title = str(section.get("title") or "").strip()
        for bullet in section.get("bullets") or []:
            text = str(bullet or "").strip()
            if not text:
                continue
            match = KEY_VALUE_RE.match(text)
            fact: dict[str, Any] = {"section": title, "text": text}
            if match:
                fact["key"] = match.group(1).strip()
                fact["value"] = match.group(2).strip()
            facts.append(fact)
        for line in section.get("text") or []:
            text = str(line or "").strip()
            if not text:
                continue
            match = KEY_VALUE_RE.match(text)
            if match:
                facts.append(
                    {
                        "section": title,
                        "key": match.group(1).strip(),
                        "value": match.group(2).strip(),
                        "text": text,
                    }
                )
            else:
                facts.append({"section": title, "text": text})
    return facts[:250]


def _constraint_lines(sections: list[dict[str, Any]]) -> list[dict[str, str]]:
    markers = ("важно", "нельзя", "только", "если", "не ", "нет ", "всегда", "обязательно", "источник истины")
    constraints: list[dict[str, str]] = []
    for section in sections:
        title = str(section.get("title") or "").strip()
        for raw in [*(section.get("bullets") or []), *(section.get("text") or [])]:
            text = str(raw or "").strip()
            lowered = text.lower()
            if text and any(marker in lowered for marker in markers):
                constraints.append({"section": title, "text": text})
    return constraints[:120]


def structured_payload_for_markdown(path: Path) -> dict[str, Any]:
    text = _read_text_file(path)
    sections = _extract_sections(text)
    title = sections[0]["title"] if sections else path.stem
    facts = _flatten_section_facts(sections)
    payload: dict[str, Any] = {
        "schema": "localgpt.rag.structured.v1",
        "generated_by": "localgpt_auto_structurer",
        "source_file": path.name,
        "title": title,
        "source_kind": _source_kind(path),
        "source_priority": "json_is_source_of_truth_md_is_explanation",
        "rules": [
            "If this JSON conflicts with the Markdown file, use this JSON.",
            "Use Markdown only as explanatory context.",
            "Prefer exact structured fields, facts, constraints, tables, and explicit values from JSON.",
            "If a value is absent, answer that it is not specified instead of guessing.",
        ],
        "lookup_terms": sorted(
            {
                path.stem,
                *[str(section.get("title") or "").strip() for section in sections if section.get("title")],
            }
        ),
        "facts": facts,
        "constraints": _constraint_lines(sections),
        "sections": sections,
    }
    if "pricing" in path.name.lower():
        payload["pricing"] = {
            "support_tariffs": _pricing_facts(text),
            "interpretation_rules": [
                "The minimum/cheapest/smallest-by-hours technical support tariff is the lowest numeric price/hours item in support_tariffs.",
                "Базовый is a tariff line with only 3, 5, and 7 hour variants.",
                "The maximum variant inside Базовый is 7 hours / 23730 RUB.",
                "Оптимальный is a tariff line with only 8, 11, and 15 hour variants.",
                "Премиальный (legacy name: Максимальный / Премиальный) is a separate tariff line, not a Базовый variant.",
                "Do not move 16, 24, or 40 hour variants into Базовый.",
                "For plural cheapest/middle/highest grid requests, return one matching variant from each tariff line.",
                "For singular cheapest/most-expensive grid requests, return one absolute item across the whole grid.",
            ],
        }
    return payload


def _clean_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in (text or "").splitlines()]
    compact = "\n".join(line for line in lines if line)
    return compact.strip()


def _chunk_text(text: str) -> list[str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + CHUNK_CHARS)
        if end < len(cleaned):
            split_at = max(cleaned.rfind("\n", start, end), cleaned.rfind(". ", start, end))
            if split_at > start + 300:
                end = split_at + 1
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(0, end - CHUNK_OVERLAP)
    return chunks


def embed_text(text: str) -> list[float]:
    vector = [0.0] * VECTOR_DIMS
    for token in TOKEN_RE.findall((text or "").lower()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        index = value % VECTOR_DIMS
        sign = 1.0 if (value >> 8) & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    return sum(left[idx] * right[idx] for idx in range(size))


def _existing_documents(profile_id: int, source_type: str = SOURCE_TYPE) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("source_id") or ""): item
        for item in db.list_source_documents(profile_id=profile_id, source_type=source_type)
    }


def _index_text_document(
    *,
    profile_id: int,
    session_id: str | None,
    source_type: str,
    source_id: str,
    title: str,
    text: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    chunks = _chunk_text(text)
    if not chunks:
        raise HTTPException(status_code=422, detail="rag_context_empty")

    db.delete_source_document(profile_id, source_type, source_id)
    document = db.create_source_document(
        profile_id=profile_id,
        session_id=session_id,
        source_type=source_type,
        source_id=source_id,
        title=title,
        content=text,
        metadata={**metadata, "embedding_model": EMBEDDING_MODEL},
    )
    document_id = int(document["id"])
    for idx, chunk in enumerate(chunks):
        chunk_id = db.create_document_chunk(
            document_id=document_id,
            profile_id=profile_id,
            session_id=session_id,
            chunk_index=idx,
            content=chunk,
            metadata={"source_id": source_id, "chunk_index": idx, "source_type": source_type},
        )
        db.create_document_embedding(
            chunk_id=chunk_id,
            profile_id=profile_id,
            embedding_model=EMBEDDING_MODEL,
            embedding=embed_text(chunk),
            metadata={"source_id": source_id, "chunk_index": idx, "source_type": source_type},
        )
    return {
        "indexed": True,
        "document_id": document_id,
        "source_type": source_type,
        "source_id": source_id,
        "title": title,
        "chunks_indexed": len(chunks),
        "embedding_model": EMBEDDING_MODEL,
    }


def asr_context_source_id(transcript_id: int | str) -> str:
    return f"transcript:{int(transcript_id)}"


def index_asr_context_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    transcript_id = transcript.get("id")
    profile_id = transcript.get("profile_id")
    if transcript_id is None or profile_id is None:
        raise HTTPException(status_code=422, detail="asr_context_transcript_invalid")
    title = str(transcript.get("name") or f"ASR context #{transcript_id}").strip()
    source_id = asr_context_source_id(transcript_id)
    metadata = {
        "source_kind": "asr_context",
        "source_role": "source_of_truth",
        "truth_priority": 80,
        "transcript_id": int(transcript_id),
        "origin": "asr_context",
        "labels": transcript.get("labels") or {},
    }
    return _index_text_document(
        profile_id=int(profile_id),
        session_id=transcript.get("session_id"),
        source_type=ASR_CONTEXT_SOURCE_TYPE,
        source_id=source_id,
        title=title,
        text=str(transcript.get("content") or ""),
        metadata=metadata,
    )


def vision_context_source_id(message_id: int | str) -> str:
    return f"message:{int(message_id)}"


def index_vision_context(
    *,
    profile_id: int,
    session_id: str,
    message_id: int,
    title: str | None,
    text: str,
) -> dict[str, Any]:
    profile = db.get_profile(profile_id)
    if not profile or not profile.get("is_active", 1):
        raise HTTPException(status_code=404, detail="profile_not_found")
    session = db.get_session(session_id)
    if not session or int(session.get("profile_id") or 0) != int(profile_id):
        raise HTTPException(status_code=403, detail="vision_context_session_mismatch")
    message = db.get_message(message_id)
    if (
        not message
        or str(message.get("session_id") or "") != str(session_id)
        or str(message.get("role") or "") != "user"
    ):
        raise HTTPException(status_code=403, detail="vision_context_message_mismatch")
    attachments = db.list_chat_attachments(
        profile_id=int(profile_id),
        session_id=str(session_id),
        message_id=int(message_id),
    )
    if not attachments:
        raise HTTPException(status_code=422, detail="vision_context_attachments_required")

    edited_text = str(text or "").strip()
    if not edited_text:
        raise HTTPException(status_code=422, detail="vision_context_empty")
    if len(edited_text) > 100_000:
        raise HTTPException(status_code=413, detail="vision_context_too_large")
    if re.search(r"data:image/[^;]+;base64,", edited_text, flags=re.IGNORECASE):
        raise HTTPException(status_code=422, detail="vision_context_binary_forbidden")

    source_id = vision_context_source_id(message_id)
    clean_title = str(title or "").strip()[:160] or f"Vision context: {message.get('content') or source_id}"
    metadata = {
        "source_kind": "vision_context",
        "source_role": "derived_context",
        "truth_priority": 50,
        "origin": "explicit_chat_export",
        "message_id": int(message_id),
        "session_id": str(session_id),
        "attachment_ids": [str(item.get("id")) for item in attachments],
        "editable": True,
        "binary_ingested": False,
    }
    return _index_text_document(
        profile_id=int(profile_id),
        session_id=str(session_id),
        source_type=VISION_CONTEXT_SOURCE_TYPE,
        source_id=source_id,
        title=clean_title,
        text=edited_text,
        metadata=metadata,
    )


def _context_items(profile_id: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for document in db.list_source_documents(profile_id=profile_id, source_type=ASR_CONTEXT_SOURCE_TYPE):
        metadata = document.get("metadata") or {}
        items.append(
            {
                "source_type": ASR_CONTEXT_SOURCE_TYPE,
                "source_id": document.get("source_id") or "",
                "title": document.get("title") or "ASR context",
                "session_id": document.get("session_id"),
                "transcript_id": metadata.get("transcript_id"),
                "created_at": document.get("created_at"),
                "updated_at": document.get("updated_at"),
            }
        )
    for document in db.list_source_documents(profile_id=profile_id, source_type=VISION_CONTEXT_SOURCE_TYPE):
        metadata = document.get("metadata") or {}
        items.append(
            {
                "source_type": VISION_CONTEXT_SOURCE_TYPE,
                "source_id": document.get("source_id") or "",
                "title": document.get("title") or "Vision context",
                "session_id": document.get("session_id"),
                "message_id": metadata.get("message_id"),
                "attachment_ids": metadata.get("attachment_ids") or [],
                "created_at": document.get("created_at"),
                "updated_at": document.get("updated_at"),
            }
        )
    return items


def delete_asr_context_source(profile_id: int, source_id: str) -> dict[str, Any]:
    target = str(source_id or "").strip()
    if not target:
        raise HTTPException(status_code=422, detail="rag_context_required")
    document = next(
        (
            item
            for item in db.list_source_documents(profile_id=profile_id, source_type=ASR_CONTEXT_SOURCE_TYPE)
            if str(item.get("source_id") or "") == target
        ),
        None,
    )
    if not document:
        raise HTTPException(status_code=404, detail="rag_context_not_found")

    metadata = document.get("metadata") or {}
    transcript_id = metadata.get("transcript_id")
    deleted_docs = db.delete_source_document(profile_id, ASR_CONTEXT_SOURCE_TYPE, target)
    deleted_transcript = False
    if transcript_id is not None:
        transcript = db.get_transcript(int(transcript_id))
        if transcript and int(transcript.get("profile_id") or 0) == int(profile_id):
            db.delete_transcript(int(transcript_id))
            deleted_transcript = True
    return {
        "profile_id": profile_id,
        "deleted": [target] if deleted_docs else [],
        "deleted_transcript": deleted_transcript,
        "status": status(profile_id),
    }


def delete_context_source(profile_id: int, source_id: str) -> dict[str, Any]:
    target = str(source_id or "").strip()
    if not target:
        raise HTTPException(status_code=422, detail="rag_context_required")
    vision_document = next(
        (
            item
            for item in db.list_source_documents(profile_id=profile_id, source_type=VISION_CONTEXT_SOURCE_TYPE)
            if str(item.get("source_id") or "") == target
        ),
        None,
    )
    if not vision_document:
        return delete_asr_context_source(profile_id, target)
    deleted_docs = db.delete_source_document(profile_id, VISION_CONTEXT_SOURCE_TYPE, target)
    return {
        "profile_id": profile_id,
        "deleted": [target] if deleted_docs else [],
        "deleted_transcript": False,
        "status": status(profile_id),
    }


def delete_asr_context_for_transcript(profile_id: int, transcript_id: int | str) -> int:
    return db.delete_source_document(profile_id, ASR_CONTEXT_SOURCE_TYPE, asr_context_source_id(transcript_id))


def ingest_sources(profile_id: int, *, force: bool = False) -> dict[str, Any]:
    if not db.get_profile(profile_id):
        raise HTTPException(status_code=404, detail="profile_not_found")

    existing = _existing_documents(profile_id)
    scanned = 0
    indexed = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    total_chunks = 0
    seen_source_ids: set[str] = set()

    for path in _iter_source_files(profile_id):
        scanned += 1
        source_id = _relative_source_id(path, profile_id)
        seen_source_ids.add(source_id)
        stat = path.stat()
        metadata = {
            "path": source_id,
            "suffix": path.suffix.lower(),
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "embedding_model": EMBEDDING_MODEL,
            "source_kind": _source_kind(path),
            "truth_priority": 10,
            "source_role": "source",
        }
        current = existing.get(source_id)
        current_meta = current.get("metadata") if isinstance(current, dict) else {}
        if (
            not force
            and current
            and current_meta.get("size") == metadata["size"]
            and current_meta.get("mtime") == metadata["mtime"]
            and current_meta.get("embedding_model") == EMBEDDING_MODEL
        ):
            skipped += 1
            continue

        try:
            text = _read_text_file(path)
            chunks = _chunk_text(text)
            if not chunks:
                skipped += 1
                continue
        except Exception as exc:
            errors.append({"path": source_id, "error": str(exc)})
            continue

        db.delete_source_document(profile_id, SOURCE_TYPE, source_id)
        document = db.create_source_document(
            profile_id=profile_id,
            session_id=None,
            source_type=SOURCE_TYPE,
            source_id=source_id,
            title=path.name,
            content=None,
            metadata=metadata,
        )
        document_id = int(document["id"])
        for idx, chunk in enumerate(chunks):
            chunk_id = db.create_document_chunk(
                document_id=document_id,
                profile_id=profile_id,
                session_id=None,
                chunk_index=idx,
                content=chunk,
                metadata={"path": source_id, "chunk_index": idx},
            )
            db.create_document_embedding(
                chunk_id=chunk_id,
                profile_id=profile_id,
                embedding_model=EMBEDDING_MODEL,
                embedding=embed_text(chunk),
                metadata={"path": source_id, "chunk_index": idx},
            )
        indexed += 1
        total_chunks += len(chunks)

    removed_stale = 0
    for source_id in set(existing) - seen_source_ids:
        db.delete_source_document(profile_id, SOURCE_TYPE, source_id)
        removed_stale += 1

    stats = db.rag_stats(profile_id)
    return {
        "profile_id": profile_id,
        "source_dir": str(source_dir(profile_id)),
        "profile_source_dir": str(source_dir(profile_id)),
        "embedding_model": EMBEDDING_MODEL,
        "supported_suffixes": sorted(SUPPORTED_SUFFIXES),
        "scanned": scanned,
        "indexed": indexed,
        "skipped": skipped,
        "chunks_indexed": total_chunks,
        "removed_stale": removed_stale,
        "errors": errors,
        "stats": stats,
    }


def status(profile_id: int | None = None) -> dict[str, Any]:
    root = source_dir(profile_id)
    files = _iter_source_files(profile_id) if profile_id is not None else []
    if profile_id is not None:
        valid_source_ids = {_relative_source_id(path, profile_id) for path in files}
        for document in db.list_source_documents(profile_id=profile_id, source_type=SOURCE_TYPE):
            source_id = str(document.get("source_id") or "")
            if source_id and source_id not in valid_source_ids:
                db.delete_source_document(profile_id, SOURCE_TYPE, source_id)
    return {
        "source_dir": str(root),
        "root_source_dir": str(source_root()),
        "embedding_model": EMBEDDING_MODEL,
        "supported_suffixes": sorted(SUPPORTED_SUFFIXES),
        "file_count": len(files),
        "files": [_relative_source_id(path, profile_id) for path in files[:100]],
        "contexts": _context_items(profile_id) if profile_id is not None else [],
        "stats": db.rag_stats(profile_id),
    }


def search(profile_id: int, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
    cleaned_query = (query or "").strip()
    if not cleaned_query or top_k <= 0:
        return []
    query_vector = embed_text(cleaned_query)
    query_tokens = set(TOKEN_RE.findall(cleaned_query.lower()))
    query_lower = cleaned_query.lower()
    scored: list[dict[str, Any]] = []
    for chunk in db.list_rag_chunks(profile_id, embedding_model=EMBEDDING_MODEL):
        score = _cosine(query_vector, chunk.get("embedding") or [])
        haystack = " ".join(
            str(value or "")
            for value in (chunk.get("content"), chunk.get("source_id"), chunk.get("title"))
        ).lower()
        content_tokens = set(TOKEN_RE.findall(haystack))
        lexical = len(query_tokens & content_tokens) / max(1, len(query_tokens)) if query_tokens else 0.0
        score += min(0.18, lexical * 0.18)
        if score <= 0:
            continue
        document_meta = chunk.get("document_metadata") or {}
        source_kind = document_meta.get("source_kind") or _source_kind(Path(str(chunk.get("source_id") or "")))
        if source_kind == "pricing" and any(
            marker in query_lower
            for marker in ("тариф", "цена", "стоим", "прайс", "час", "депозит", "докуп")
        ):
            score += 0.35
        if source_kind == "profile" and any(
            marker in query_lower
            for marker in ("кто я", "обо мне", "чем занима", "моя роль", "профиль", "интерес", "работаю")
        ):
            score += 0.25
        if source_kind == "sla" and any(marker in query_lower for marker in ("sla", "срок", "реакц", "приоритет")):
            score += 0.25
        if source_kind == "template" and any(marker in query_lower for marker in ("шаблон", "сообщение", "ответ клиенту")):
            score += 0.2
        score += 0.08 if document_meta.get("source_role") == "source_of_truth" else 0.0
        scored.append(
            {
                "score": round(score, 4),
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "source_type": chunk["source_type"],
                "source_id": chunk["source_id"],
                "title": chunk["title"],
                "chunk_index": chunk["chunk_index"],
                "content": chunk["content"],
                "metadata": chunk.get("chunk_metadata") or {},
                "document_metadata": document_meta,
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def build_context(chunks: list[dict[str, Any]], *, max_chars: int = 6000) -> str:
    parts: list[str] = [
        "RAG rules: use the retrieved Markdown sources as authoritative local context. "
        "Do not invent facts that are not present in the retrieved chunks. "
        "If the source does not define an ambiguous value, ask a short clarifying question."
    ]
    total = len(parts[0]) + 2
    for item in chunks:
        source = item.get("source_id") or item.get("title") or "unknown"
        meta = item.get("document_metadata") or {}
        role = meta.get("source_role") or "context"
        block = f"[{source} | {role} | score={item.get('score')}]\n{item.get('content') or ''}".strip()
        if not block:
            continue
        if total + len(block) + 2 > max_chars:
            break
        parts.append(block)
        total += len(block) + 2
    return "\n\n".join(parts).strip()


def save_uploaded_files(profile_id: int, files: list[UploadFile]) -> dict[str, Any]:
    target_dir = source_dir(profile_id)
    saved: list[str] = []
    errors: list[dict[str, str]] = []
    for upload in files:
        original_name = Path(upload.filename or "").name
        if not original_name:
            continue
        suffix = Path(original_name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            errors.append({"file": original_name, "error": "unsupported_file_type"})
            continue
        safe_name = _slug(Path(original_name).stem) + suffix
        target = target_dir / safe_name
        data = upload.file.read()
        if len(data) > MAX_FILE_BYTES:
            errors.append({"file": original_name, "error": "file_too_large"})
            continue
        target.write_bytes(data)
        saved.append(_relative_source_id(target, profile_id))
    return {
        "profile_id": profile_id,
        "source_dir": str(target_dir),
        "saved": saved,
        "errors": errors,
        "status": status(profile_id),
    }


def delete_file(profile_id: int, source_id: str) -> dict[str, Any]:
    target = _resolve_source_file(profile_id, source_id)
    deleted: list[str] = []
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="rag_file_not_found")

    source = _relative_source_id(target, profile_id)
    try:
        target.unlink()
    except FileNotFoundError:
        pass
    db.delete_source_document(profile_id, SOURCE_TYPE, source)
    deleted.append(source)

    return {"profile_id": profile_id, "deleted": deleted, "status": status(profile_id)}


def migrate_legacy_root_files(profile_id: int) -> dict[str, Any]:
    root = source_root()
    target_dir = source_dir(profile_id)
    moved: list[str] = []
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.name.startswith(".") or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        target = target_dir / path.name
        if target.exists():
            continue
        shutil.move(str(path), str(target))
        moved.append(_relative_source_id(target, profile_id))
    return {"moved": moved, "status": status(profile_id)}
