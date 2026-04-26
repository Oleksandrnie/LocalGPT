from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app import config, db

SOURCE_TYPE = "manual_file"
EMBEDDING_MODEL = "local-hash-v1"
SUPPORTED_SUFFIXES = {".txt", ".md", ".json"}
MAX_FILE_BYTES = 5 * 1024 * 1024
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 180
VECTOR_DIMS = 256
TOKEN_RE = re.compile(r"[\wа-яА-ЯёЁ]{2,}", re.UNICODE)


def source_dir() -> Path:
    config.RAG_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    return config.RAG_SOURCE_DIR


def _relative_source_id(path: Path) -> str:
    root = source_dir().resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="rag_file_outside_source_dir") from exc


def _iter_source_files() -> list[Path]:
    root = source_dir()
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
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            parsed = json.loads(raw)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return raw
    return raw


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

    existing = _existing_documents(profile_id)
    scanned = 0
    indexed = 0
    skipped = 0
    errors: list[dict[str, str]] = []
    total_chunks = 0

    for path in _iter_source_files():
        scanned += 1
        source_id = _relative_source_id(path)
        stat = path.stat()
        metadata = {
            "path": source_id,
            "suffix": path.suffix.lower(),
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "embedding_model": EMBEDDING_MODEL,
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

    stats = db.rag_stats(profile_id)
    return {
        "profile_id": profile_id,
        "source_dir": str(source_dir()),
        "embedding_model": EMBEDDING_MODEL,
        "supported_suffixes": sorted(SUPPORTED_SUFFIXES),
        "scanned": scanned,
        "indexed": indexed,
        "skipped": skipped,
        "chunks_indexed": total_chunks,
        "errors": errors,
        "stats": stats,
    }


def status(profile_id: int | None = None) -> dict[str, Any]:
    files = _iter_source_files()
    return {
        "source_dir": str(source_dir()),
        "embedding_model": EMBEDDING_MODEL,
        "supported_suffixes": sorted(SUPPORTED_SUFFIXES),
        "file_count": len(files),
        "files": [_relative_source_id(path) for path in files[:50]],
        "stats": db.rag_stats(profile_id),
    }


def search(profile_id: int, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
    cleaned_query = (query or "").strip()
    if not cleaned_query or top_k <= 0:
        return []
    query_vector = embed_text(cleaned_query)
    scored: list[dict[str, Any]] = []
    for chunk in db.list_rag_chunks(profile_id, embedding_model=EMBEDDING_MODEL):
        score = _cosine(query_vector, chunk.get("embedding") or [])
        if score <= 0:
            continue
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
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def build_context(chunks: list[dict[str, Any]], *, max_chars: int = 6000) -> str:
    parts: list[str] = []
    total = 0
    for item in chunks:
        source = item.get("source_id") or item.get("title") or "unknown"
        block = f"[{source} | score={item.get('score')}]\n{item.get('content') or ''}".strip()
        if not block:
            continue
        if total + len(block) + 2 > max_chars:
            break
        parts.append(block)
        total += len(block) + 2
    return "\n\n".join(parts).strip()
