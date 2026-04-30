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
EMBEDDING_MODEL = "local-hash-v1"
SUPPORTED_SUFFIXES = {".txt", ".md", ".json"}
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
    return sorted(
        files,
        key=lambda item: (0 if item.suffix.lower() == ".json" else 1, item.relative_to(root).as_posix().lower()),
    )


def _read_text_file(path: Path) -> str:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("file_too_large")
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            parsed = json.loads(raw)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return raw
    return raw


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
            if title.lower() in {"базовый", "оптимальный", "максимальный / премиальный"}:
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
                "Максимальный / Премиальный is a separate tariff line, not a Базовый variant.",
                "Do not move 16, 24, or 40 hour variants into Базовый.",
            ],
        }
    return payload


def ensure_structured_json_files(profile_id: int, *, force: bool = False) -> list[str]:
    created: list[str] = []
    for md_path in _iter_source_files(profile_id):
        if md_path.suffix.lower() != ".md":
            continue
        json_path = md_path.with_suffix(".json")
        if json_path.exists():
            if not force:
                continue
            try:
                existing = json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = None
            if not isinstance(existing, dict) or existing.get("generated_by") != "localgpt_auto_structurer":
                continue
        payload = structured_payload_for_markdown(md_path)
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        created.append(_relative_source_id(json_path, profile_id))
    return created


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


def _existing_documents(profile_id: int) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("source_id") or ""): item
        for item in db.list_source_documents(profile_id=profile_id, source_type=SOURCE_TYPE)
    }


def ingest_sources(profile_id: int, *, force: bool = False) -> dict[str, Any]:
    if not db.get_profile(profile_id):
        raise HTTPException(status_code=404, detail="profile_not_found")

    generated_json = ensure_structured_json_files(profile_id, force=force)
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
            "truth_priority": 100 if path.suffix.lower() == ".json" else 10,
            "source_role": "source_of_truth" if path.suffix.lower() == ".json" else "explanation",
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
        "generated_json": generated_json,
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
        "RAG rules: JSON chunks are source of truth. If JSON conflicts with Markdown, use JSON. "
        "Markdown chunks are explanatory context. Do not invent facts not present in retrieved chunks. "
        "For pricing questions, use explicit structured values and distinguish a minimum tariff from a maximum variant inside a tariff line."
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
    generated_json = ensure_structured_json_files(profile_id)
    return {
        "profile_id": profile_id,
        "source_dir": str(target_dir),
        "saved": saved,
        "generated_json": generated_json,
        "errors": errors,
        "status": status(profile_id),
    }


def delete_file(profile_id: int, source_id: str) -> dict[str, Any]:
    target = _resolve_source_file(profile_id, source_id)
    deleted: list[str] = []
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="rag_file_not_found")

    delete_targets = [target]
    if target.suffix.lower() == ".md":
        companion = target.with_suffix(".json")
        if companion.exists() and companion.is_file():
            try:
                companion_payload = json.loads(companion.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                companion_payload = None
            if isinstance(companion_payload, dict) and companion_payload.get("generated_by") == "localgpt_auto_structurer":
                delete_targets.append(companion)

    for path in delete_targets:
        source = _relative_source_id(path, profile_id)
        try:
            path.unlink()
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
    generated_json = ensure_structured_json_files(profile_id)
    return {"moved": moved, "generated_json": generated_json, "status": status(profile_id)}
