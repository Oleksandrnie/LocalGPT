from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from typing import Any, Callable


TOKEN_RE = re.compile(r"[\wа-яА-ЯёЁ]{2,}", re.UNICODE)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})\b")
SUSPICIOUS_INSTRUCTION_RE = re.compile(
    r"(?:ignore|игнорир\w*)\s+(?:the\s+)?(?:system|prompt|инструкц)|"
    r"(?:reveal|раскро\w*|покажи)\s+(?:the\s+)?(?:secret|prompt|секрет)|"
    r"(?:run|execute|запусти|выполни)\s+(?:a\s+)?(?:shell|command|команд)",
    re.IGNORECASE,
)
EXCLUSIVITY_RE = re.compile(r"\b(?:только|исключительно|exclusive\w*|only|must not|нельзя)\b", re.IGNORECASE)
ALTERNATIVE_RE = re.compile(r"\b(?:или|либо|or|допуска\w*|depending)\b", re.IGNORECASE)
SEMANTIC_MIN_SCORE = 0.35
FACET_LEXICAL_MIN_SCORE = 0.34
FACET_SEMANTIC_MIN_SCORE = 0.45
RRF_K = 60
STOPWORDS = {
    "about",
    "and",
    "are",
    "does",
    "for",
    "from",
    "how",
    "is",
    "the",
    "what",
    "which",
    "with",
    "без",
    "вам",
    "ваш",
    "вы",
    "где",
    "для",
    "есть",
    "или",
    "как",
    "какая",
    "какие",
    "какими",
    "какой",
    "когда",
    "кто",
    "можно",
    "на",
    "по",
    "при",
    "про",
    "с",
    "со",
    "что",
    "это",
}


def tokens(text: str, *, significant: bool = False) -> list[str]:
    values = [value.lower() for value in TOKEN_RE.findall(text or "")]
    if significant:
        values = [value for value in values if value not in STOPWORDS]
    return values


def token_matches(left: str, right: str) -> bool:
    if left == right:
        return True
    return min(len(left), len(right)) >= 5 and left[:5] == right[:5]


def split_query_facets(query: str) -> list[dict[str, Any]]:
    compact = re.sub(r"[ \t]+", " ", str(query or "").strip())
    if not compact:
        return []
    raw_parts = re.split(
        r"(?:\n+|[;?]+|\s+(?:и|and)\s+(?=(?:как|где|какие|какими|какой|что|how|where|what|which)\b))",
        compact,
        flags=re.IGNORECASE,
    )
    parts = [part.strip(" ,.-") for part in raw_parts if len(tokens(part, significant=True)) >= 1]
    if len(parts) == 1 and re.search(r"\s+(?:и|and)\s+", parts[0], flags=re.IGNORECASE):
        candidates = re.split(r"\s+(?:и|and)\s+", parts[0], maxsplit=1, flags=re.IGNORECASE)
        if all(len(tokens(part, significant=True)) >= 2 for part in candidates):
            parts = [part.strip(" ,.-") for part in candidates]
    return [
        {"facet_id": f"facet_{index}", "query": part[:240], "tokens": sorted(set(tokens(part, significant=True)))[:32]}
        for index, part in enumerate(parts[:8], start=1)
    ]


def token_coverage(query_tokens: list[str], content_tokens: list[str]) -> float:
    if not query_tokens:
        return 0.0
    content_set = set(content_tokens)
    matched = sum(1 for query_token in set(query_tokens) if any(token_matches(query_token, item) for item in content_set))
    return matched / max(1, len(set(query_tokens)))


def repetition_ratio(text: str) -> float:
    units = [
        re.sub(r"\W+", " ", unit.lower()).strip()
        for unit in re.split(r"\n+|(?<=[.!?])\s+", text or "")
        if len(unit.strip()) >= 24
    ]
    if len(units) < 2:
        return 0.0
    return round(1.0 - (len(set(units)) / len(units)), 4)


def _near_duplicate(left: str, right: str) -> bool:
    left_tokens = set(tokens(left, significant=True))
    right_tokens = set(tokens(right, significant=True))
    if not left_tokens or not right_tokens:
        return False
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens) >= 0.86


def _best_span(text: str, facet_tokens: list[str], *, limit: int = 280) -> str:
    units = [unit.strip() for unit in re.split(r"\n+|(?<=[.!?])\s+", text or "") if unit.strip()]
    if not units:
        return ""
    best = max(units, key=lambda unit: token_coverage(facet_tokens, tokens(unit, significant=True)))
    return best[:limit].rstrip()


def _source_bonus(item: dict[str, Any], query_lower: str) -> float:
    metadata = item.get("document_metadata") or {}
    source_kind = str(metadata.get("source_kind") or "")
    bonus = 0.0
    if source_kind == "pricing" and any(
        marker in query_lower for marker in ("тариф", "цен", "стоим", "прайс", "расцен", "час", "депозит", "докуп")
    ):
        bonus += 0.25
    if source_kind == "profile" and any(
        marker in query_lower for marker in ("кто я", "обо мне", "чем занима", "моя роль", "профиль", "интерес", "работаю")
    ):
        bonus += 0.15
    if source_kind == "sla" and any(marker in query_lower for marker in ("sla", "срок", "реакц", "приоритет")):
        bonus += 0.15
    if source_kind == "template" and any(marker in query_lower for marker in ("шаблон", "сообщение", "ответ клиенту")):
        bonus += 0.12
    if metadata.get("source_role") == "source_of_truth":
        bonus += 0.08
    return bonus


def rank_hybrid(
    raw_chunks: list[dict[str, Any]],
    query: str,
    *,
    top_k: int,
    dense_score: Callable[[list[float]], float],
    dense_facet_scores: Callable[[list[float]], dict[str, float]] | None = None,
    strategy: str = "hybrid_v2",
) -> list[dict[str, Any]]:
    facets = split_query_facets(query)
    query_tokens = sorted({token for facet in facets for token in facet["tokens"]})
    if not query_tokens or top_k <= 0:
        return []

    eligible: list[tuple[dict[str, Any], list[str]]] = []
    for chunk in raw_chunks:
        metadata = chunk.get("document_metadata") or {}
        if chunk.get("source_type") == "chat_context" and metadata.get("message_role") == "assistant":
            continue
        content_tokens = tokens(
            " ".join(str(value or "") for value in (chunk.get("content"), chunk.get("source_id"), chunk.get("title"))),
            significant=True,
        )
        eligible.append((chunk, content_tokens))

    document_frequency = Counter()
    for query_token in query_tokens:
        document_frequency[query_token] = sum(
            1 for _, content_tokens in eligible if any(token_matches(query_token, token) for token in set(content_tokens))
        )
    corpus_size = max(1, len(eligible))
    average_length = sum(len(content_tokens) for _, content_tokens in eligible) / corpus_size
    query_lower = query.lower()
    candidates: list[dict[str, Any]] = []

    for chunk, content_tokens in eligible:
        term_counts = Counter(content_tokens)
        bm25 = 0.0
        idf_total = 0.0
        for query_token in query_tokens:
            frequency = sum(count for token, count in term_counts.items() if token_matches(query_token, token))
            document_count = document_frequency[query_token]
            idf = math.log(1.0 + (corpus_size - document_count + 0.5) / (document_count + 0.5))
            idf_total += idf
            if frequency:
                denominator = frequency + 1.2 * (0.25 + 0.75 * (len(content_tokens) / max(1.0, average_length)))
                bm25 += idf * ((frequency * 2.2) / denominator)
        bm25_normalized = bm25 / max(0.0001, idf_total)
        lexical_facet_scores = {
            facet["facet_id"]: token_coverage(facet["tokens"], content_tokens)
            for facet in facets
        }
        overall_coverage = token_coverage(query_tokens, content_tokens)
        repeated = repetition_ratio(str(chunk.get("content") or ""))
        lexical_score = (
            bm25_normalized * 0.56
            + overall_coverage * 0.44
            + (_source_bonus(chunk, query_lower) if overall_coverage > 0 else 0.0)
            - repeated * 0.35
        )
        dense = max(0.0, dense_score(chunk.get("embedding") or []))
        semantic_facet_scores = (
            dense_facet_scores(chunk.get("embedding") or []) if dense_facet_scores else {}
        )
        facet_scores = {
            facet["facet_id"]: max(
                float(lexical_facet_scores.get(facet["facet_id"], 0.0)),
                float(semantic_facet_scores.get(facet["facet_id"], 0.0)),
            )
            for facet in facets
        }
        item = {
            "score": 0.0,
            "chunk_id": chunk.get("chunk_id"),
            "document_id": chunk.get("document_id"),
            "source_type": chunk.get("source_type"),
            "source_id": chunk.get("source_id"),
            "title": chunk.get("title"),
            "chunk_index": chunk.get("chunk_index"),
            "content": chunk.get("content"),
            "metadata": chunk.get("chunk_metadata") or {},
            "document_metadata": chunk.get("document_metadata") or {},
            "retrieval": {
                "strategy": strategy,
                "bm25": round(bm25_normalized, 4),
                "dense": round(dense, 4),
                "query_coverage": round(overall_coverage, 4),
                "repetition_ratio": repeated,
                "lexical_score": round(max(0.0, lexical_score), 4),
                "semantic_score": round(dense, 4),
            },
            "matched_facets": [
                facet["facet_id"]
                for facet in facets
                if lexical_facet_scores.get(facet["facet_id"], 0.0) >= FACET_LEXICAL_MIN_SCORE
                or semantic_facet_scores.get(facet["facet_id"], 0.0) >= FACET_SEMANTIC_MIN_SCORE
            ],
            "facet_scores": {key: round(value, 4) for key, value in facet_scores.items()},
            "evidence_status": "supported",
            "provenance": {
                "source_id": chunk.get("source_id"),
                "chunk_id": chunk.get("chunk_id"),
                "chunk_index": chunk.get("chunk_index"),
            },
        }
        candidates.append(item)

    pool_size = min(len(candidates), max(20, top_k * 4))
    lexical_pool = sorted(
        (
            item
            for item in candidates
            if float((item.get("retrieval") or {}).get("query_coverage") or 0.0) > 0
            and float((item.get("retrieval") or {}).get("lexical_score") or 0.0) > 0
        ),
        key=lambda item: (
            -float((item.get("retrieval") or {}).get("lexical_score") or 0.0),
            str(item.get("source_id") or ""),
            int(item.get("chunk_index") or 0),
        ),
    )[:pool_size]
    semantic_pool = [] if strategy == "lexical_v1" else sorted(
        (
            item
            for item in candidates
            if float((item.get("retrieval") or {}).get("semantic_score") or 0.0) >= SEMANTIC_MIN_SCORE
        ),
        key=lambda item: (
            -float((item.get("retrieval") or {}).get("semantic_score") or 0.0),
            str(item.get("source_id") or ""),
            int(item.get("chunk_index") or 0),
        ),
    )[:pool_size]
    lexical_ranks = {int(item["chunk_id"]): rank for rank, item in enumerate(lexical_pool, start=1)}
    semantic_ranks = {int(item["chunk_id"]): rank for rank, item in enumerate(semantic_pool, start=1)}
    candidate_by_id = {
        int(item["chunk_id"]): item for item in [*lexical_pool, *semantic_pool]
    }
    for chunk_id, item in candidate_by_id.items():
        lexical_rank = lexical_ranks.get(chunk_id)
        semantic_rank = semantic_ranks.get(chunk_id)
        rrf_lexical = (1.0 / (RRF_K + lexical_rank)) if lexical_rank else 0.0
        rrf_semantic = (1.0 / (RRF_K + semantic_rank)) if semantic_rank else 0.0
        raw_fusion = rrf_lexical + rrf_semantic
        maximum = 2.0 / (RRF_K + 1) if strategy != "lexical_v1" else 1.0 / (RRF_K + 1)
        score = raw_fusion / maximum if maximum else 0.0
        item["score"] = round(score, 4)
        item["retrieval"].update(
            {
                "fusion": "rrf_v1",
                "lexical_rank": lexical_rank,
                "semantic_rank": semantic_rank,
                "candidate_pools": [
                    pool
                    for pool, rank in (("lexical", lexical_rank), ("semantic", semantic_rank))
                    if rank is not None
                ],
            }
        )
    candidates = sorted(
        candidate_by_id.values(),
        key=lambda item: (
            -float(item["score"]),
            str(item.get("source_id") or ""),
            int(item.get("chunk_index") or 0),
        ),
    )
    selected: list[dict[str, Any]] = []
    selected_sources: set[str] = set()

    def can_select(candidate: dict[str, Any], *, require_new_source: bool) -> bool:
        source_id = str(candidate.get("source_id") or "")
        if require_new_source and source_id in selected_sources:
            return False
        return not any(_near_duplicate(str(candidate.get("content") or ""), str(item.get("content") or "")) for item in selected)

    for facet in facets:
        if len(selected) >= top_k:
            break
        ranked_for_facet = sorted(
            candidates,
            key=lambda item: (
                -float((item.get("facet_scores") or {}).get(facet["facet_id"], 0.0)),
                -float(item.get("score") or 0.0),
            ),
        )
        best = next(
            (
                item
                for item in ranked_for_facet
                if item not in selected
                and facet["facet_id"] in (item.get("matched_facets") or [])
                and can_select(item, require_new_source=True)
            ),
            None,
        )
        if best:
            selected.append(best)
            selected_sources.add(str(best.get("source_id") or ""))

    for require_new_source in (True, False):
        for candidate in candidates:
            if len(selected) >= top_k:
                break
            if candidate in selected or not can_select(candidate, require_new_source=require_new_source):
                continue
            selected.append(candidate)
            selected_sources.add(str(candidate.get("source_id") or ""))

    return selected[:top_k]


def evidence_diagnostics(
    query: str,
    chunks: list[dict[str, Any]],
    *,
    strategy: str = "hybrid_v2",
) -> dict[str, Any]:
    facets = split_query_facets(query)
    facet_results: list[dict[str, Any]] = []
    for facet in facets:
        supporting = [
            item
            for item in chunks
            if facet["facet_id"] in (item.get("matched_facets") or [])
        ]
        years = sorted(
            {
                int(year)
                for item in supporting
                for year in YEAR_RE.findall(str(item.get("content") or ""))
            }
        )
        exclusive_years = {
            int(year)
            for item in supporting
            if EXCLUSIVITY_RE.search(str(item.get("content") or ""))
            for year in YEAR_RE.findall(str(item.get("content") or ""))
        }
        alternative_years = {
            int(year)
            for item in supporting
            if ALTERNATIVE_RE.search(str(item.get("content") or ""))
            for year in YEAR_RE.findall(str(item.get("content") or ""))
        }
        conflict = bool(exclusive_years and alternative_years and exclusive_years != alternative_years)
        status = "conflict" if conflict else ("supported" if supporting else "not_found")
        evidence = [
            {
                "source_id": item.get("source_id"),
                "chunk_id": item.get("chunk_id"),
                "evidence_span": _best_span(str(item.get("content") or ""), facet["tokens"]),
            }
            for item in supporting[:3]
        ]
        facet_results.append(
            {
                "facet_id": facet["facet_id"],
                "query": facet["query"],
                "status": status,
                "evidence": evidence,
                "conflict_years": years if conflict else [],
            }
        )

    statuses = {item["status"] for item in facet_results}
    if not facet_results or statuses == {"not_found"}:
        overall = "not_found"
    elif "conflict" in statuses:
        overall = "conflict"
    elif "not_found" in statuses:
        overall = "partial"
    else:
        overall = "supported"
    return {
        "strategy": strategy,
        "overall_status": overall,
        "facet_coverage": facet_results,
        "selected_chunks": len(chunks),
        "selected_sources": len({str(item.get("source_id") or "") for item in chunks}),
    }


def corpus_audit(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in chunks:
        by_source[str(item.get("source_id") or "unknown")].append(item)
    fingerprints: dict[str, list[str]] = defaultdict(list)
    source_text: dict[str, str] = {}
    for source_id, items in by_source.items():
        text = "\n".join(str(item.get("content") or "") for item in sorted(items, key=lambda row: row.get("chunk_index") or 0))
        source_text[source_id] = text
        normalized = " ".join(tokens(text, significant=True))
        fingerprints[hashlib.sha256(normalized.encode("utf-8")).hexdigest()].append(source_id)

    exact_groups = [sorted(set(group)) for group in fingerprints.values() if len(set(group)) > 1]
    source_ids = sorted(source_text)
    near_pairs: list[list[str]] = []
    for index, left in enumerate(source_ids):
        for right in source_ids[index + 1 :]:
            if _near_duplicate(source_text[left], source_text[right]):
                near_pairs.append([left, right])
    years_by_source = {
        source_id: sorted({int(value) for value in YEAR_RE.findall(text)})
        for source_id, text in source_text.items()
    }
    latest_year = max((year for values in years_by_source.values() for year in values), default=None)
    stale_sources = sorted(
        source_id
        for source_id, values in years_by_source.items()
        if latest_year is not None and values and max(values) <= latest_year - 3
    )
    suspicious = sorted(source_id for source_id, text in source_text.items() if SUSPICIOUS_INSTRUCTION_RE.search(text))
    boilerplate = sorted(source_id for source_id, text in source_text.items() if repetition_ratio(text) >= 0.3)
    oversized = sorted(source_id for source_id, text in source_text.items() if len(text) > 20_000)
    missing_headings = sorted(source_id for source_id, text in source_text.items() if not re.search(r"^#{1,6}\s+", text, re.MULTILINE))
    conflict_sources = sorted(
        source_id
        for source_id, text in source_text.items()
        if YEAR_RE.search(text) and (EXCLUSIVITY_RE.search(text) or ALTERNATIVE_RE.search(text))
    )
    duplicate_sources = (
        {source for group in exact_groups for source in group}
        | {source for pair in near_pairs for source in pair}
        | set(boilerplate)
    )
    return {
        "preview_only": True,
        "source_count": len(source_ids),
        "duplicate_ratio": round(len(duplicate_sources) / max(1, len(source_ids)), 4),
        "duplicate_or_boilerplate_sources": sorted(duplicate_sources),
        "exact_duplicate_groups": exact_groups,
        "near_duplicate_pairs": near_pairs,
        "boilerplate_sources": boilerplate,
        "oversized_sources": oversized,
        "missing_heading_sources": missing_headings,
        "stale_sources": stale_sources,
        "potential_conflict_sources": conflict_sources,
        "suspicious_instruction_sources": suspicious,
        "mutations_performed": 0,
    }
