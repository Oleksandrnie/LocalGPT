"""Deterministic, local evidence lookup. This path never invokes a chat model."""
from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from backend.apps.rag import service as rag

MAX_EVIDENCE_CHARS = 16_000


def search(profile_id: int, query: str, *, session_id: str | None, top_k: int) -> dict[str, Any]:
    # Reject before retrieval: even a configured remote embedding provider must
    # never receive the query. lexical_v1 also avoids embedding calls entirely.
    provider = rag._embedding_provider()
    if provider.descriptor.provider != "local_hash":
        raise HTTPException(409, {
            "code": "knowledge_search_requires_local_hash",
            "message": "Поиск в базе требует локального local_hash. Измените embedding provider и переиндексируйте базу.",
        })
    indexed = rag._current_generation_chunks(profile_id, provider, session_id=session_id)
    result = rag.search_with_diagnostics(
        profile_id, query, top_k=top_k, strategy="lexical_v1", session_id=session_id,
    )
    snapshot = rag.build_context_snapshot(result["results"], max_chars=MAX_EVIDENCE_CHARS)
    evidence = snapshot["evidence_manifest"]
    titles = {item.get("chunk_id"): item.get("title") for item in result["results"]}
    for item in evidence:
        item["title"] = titles.get(item.get("chunk_id"))
    status = "matches" if evidence else ("no_matches" if indexed else "empty_index")
    limits = (
        f"Не более {top_k} фрагментов, до {MAX_EVIDENCE_CHARS} символов исходного текста и метаданных. "
        "Локальный поиск по словам; кандидаты требуют проверки по цитате. "
        "Выборка не является полным аудитом базы и не доказывает отсутствие других сообщений."
    )
    if status == "empty_index":
        reply = "Поиск в базе: индекс пуст. Добавьте источники и выполните индексацию в разделе «Знания»."
    elif status == "no_matches":
        reply = "Поиск в базе: совпадений не найдено. Уточните слова, даты или ID сообщения."
    else:
        reply = "Поиск в базе: исходные фрагменты без пересказа LLM."
    parts = [reply, limits]
    for index, item in enumerate(evidence, 1):
        meta = item.get("provenance") or {}
        source = str(item.get("source_id") or item.get("title") or "Источник")
        locator = f"фрагмент {item.get('chunk_index')}; chunk ID: {item.get('chunk_id')}"
        header = f"{index}. Источник: {source} · {locator}"
        if meta.get("message_id"):
            header += f"\nID: {meta['message_id']}"
            if meta.get("timestamp"):
                header += f" · Дата: {meta['timestamp']}"
            if meta.get("author"):
                header += f" · Автор: {meta['author']}"
        content = str(item.get("content") or "")
        fence = "`" * max(3, max((len(v) + 1 for v in re.findall(r"`+", content)), default=3))
        parts.append(f"{header}\n{fence}text\n{content}\n{fence}"
                     + ("\nФрагмент сокращён по лимиту выдачи." if item.get("truncated") else ""))
    return {
        "mode": "knowledge_search", "status": status, "reply": "\n\n".join(parts),
        "results": evidence, "diagnostics": result["diagnostics"],
        "limits": {"top_k": top_k, "max_context_chars": MAX_EVIDENCE_CHARS,
                   "indexed_chunks": len(indexed), "exhaustive": False, "strategy": "lexical_v1"},
    }
