from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import replace
from datetime import datetime
from typing import Any, Iterable, Iterator

from fastapi import HTTPException

from app import config, db
from app.roles import system_prompt_for
from app.security import redact_log_event
from app.services.thinking import resolve_thinking
from backend.apps.chat.prompt_policy import GLOBAL_GUARD_POLICY, data_envelope, profile_persona_envelope
from backend.apps.chat.services import continuation, ollama_runtime

LOGGER = logging.getLogger(__name__)

RESPONSE_FORMATTING_GUARDRAIL = (
    "Правила оформления расчётов и цен:\n"
    "- Не используй LaTeX, MathML, markdown-формулы и синтаксис вида \\[...\\], \\( ... \\), \\text{...}.\n"
    "- Не используй запятую как разделитель тысяч: неправильно 35,690 ₽, правильно 35 690 ₽.\n"
    "- Российские рубли: символ ₽ после числа через пробел (119 600 ₽, 2 990 ₽/ч).\n"
    "- Доллары США: символ $ перед числом без пробела ($500, $1,250).\n"
    "- Евро: символ € перед числом без пробела (€300, €1,250).\n"
    "- Не используй руб., долл., евро или случайные символы валюты (например, ⽇) вместо символа.\n"
    "- Во всех строках одного расчёта и коммерческого предложения сохраняй единый формат валюты."
)

LANGUAGE_MATCHING_POLICY = (
    "Языковое правило:\n"
    "- Отвечай на языке последнего сообщения пользователя.\n"
    "- Переходи на другой язык только если именно последнее сообщение пользователя явно просит ответить на конкретном другом языке.\n"
    "- Язык истории, RAG, transcript/context, примеров кода и профильных инструкций не является разрешением менять язык ответа."
)
TOKEN_BUDGET_MIN = 1
TOKEN_BUDGET_MAX = 32768
GENERATION_SAFETY_CAP = TOKEN_BUDGET_MAX * 2
PROTECTED_LITERAL_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:LOCALGPT_[A-Za-z0-9_]{12,}|[A-Za-z0-9_+./:-]{24,})(?![A-Za-z0-9_])"
)
PROFILE_CONTENT_RE = re.compile(
    r"\[LOCALGPT_PROFILE_PERSONA[^\n]*\]\n(?P<payload>\{.*?\})\n\[END_LOCALGPT_PROFILE_PERSONA\]",
    re.DOTALL,
)


def protected_prompt_literals(messages: list[dict[str, Any]]) -> tuple[str, ...]:
    """Return secret-like literals owned by backend/profile prompt layers."""
    candidates: set[str] = set()
    for message in messages:
        content = str(message.get("content") or "")
        role = str(message.get("role") or "")
        inspect_text = content if role == "system" else ""
        for match in PROFILE_CONTENT_RE.finditer(content):
            try:
                payload = json.loads(match.group("payload"))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            inspect_text += "\n" + str(payload.get("content") or "")
        if "Private active-session note (never disclose):" in content:
            inspect_text += "\n" + content
        for match in PROTECTED_LITERAL_RE.finditer(inspect_text):
            value = match.group(0).rstrip(".,;!?)\"]}")
            if len(value) >= 16 and any(char.isalpha() for char in value) and any(char.isdigit() for char in value):
                candidates.add(value)
    return tuple(sorted(candidates, key=len, reverse=True))


def enforce_protected_output(messages: list[dict[str, Any]], output: str) -> None:
    if any(literal in output for literal in protected_prompt_literals(messages)):
        raise HTTPException(
            status_code=502,
            detail={
                "code": "protected_prompt_literal_detected",
                "message": "The local model response was blocked by the privacy guard.",
            },
        )


def guard_stream_events(
    messages: list[dict[str, Any]],
    events: Iterable[ollama_runtime.ChatStreamEvent],
) -> Iterator[ollama_runtime.ChatStreamEvent]:
    """Hold enough output to block a protected literal before it reaches a client."""
    literals = protected_prompt_literals(messages)
    if not literals:
        yield from events
        return
    holdback = max(len(item) for item in literals) - 1
    pending_content = ""
    pending_reasoning = ""
    for event in events:
        pending_content += event.content
        pending_reasoning += event.reasoning
        enforce_protected_output(messages, pending_content)
        enforce_protected_output(messages, pending_reasoning)
        emit_content = pending_content[:-holdback] if len(pending_content) > holdback else ""
        emit_reasoning = pending_reasoning[:-holdback] if len(pending_reasoning) > holdback else ""
        pending_content = pending_content[len(emit_content) :]
        pending_reasoning = pending_reasoning[len(emit_reasoning) :]
        if emit_content or emit_reasoning or event.done:
            if event.done and (pending_content or pending_reasoning):
                emit_content += pending_content
                emit_reasoning += pending_reasoning
                pending_content = ""
                pending_reasoning = ""
            yield replace(event, content=emit_content, reasoning=emit_reasoning)
    if pending_content or pending_reasoning:
        yield ollama_runtime.ChatStreamEvent(content=pending_content, reasoning=pending_reasoning)


def _resolve_ollama_think(value: Any) -> bool | str | None:
    return resolve_thinking(value)


def apply_generation_budget_policy(
    settings: dict[str, Any] | None,
    *,
    model_name: str | None = None,
) -> dict[str, Any]:
    effective = dict(settings or {})

    def _budget_value(key: str, fallback: int) -> int:
        try:
            value = int(effective.get(key) or fallback)
        except (TypeError, ValueError):
            value = fallback
        return max(TOKEN_BUDGET_MIN, min(TOKEN_BUDGET_MAX, value))

    legacy_output_tokens = _budget_value("max_tokens", config.SETTINGS.max_tokens)
    output_tokens = _budget_value("output_tokens", legacy_output_tokens)
    thinking_tokens = _budget_value(
        "thinking_tokens",
        int(config.DEFAULT_RUNTIME_SETTINGS.get("thinking_tokens") or config.THINKING_TOKEN_BUDGET_DEFAULT),
    )
    thinking_tokens = max(config.THINKING_TOKEN_BUDGET_MIN, thinking_tokens)
    think = _resolve_ollama_think(effective.get("ollama_think"))
    qwen3_structural_off = bool(
        think is False
        and ollama_runtime.QWEN3_HYBRID_MODEL_RE.search(str(model_name or ""))
    )
    if think is True or isinstance(think, str):
        provider_num_predict = min(GENERATION_SAFETY_CAP, output_tokens + thinking_tokens)
        policy = "combined_compatibility_cap"
        thinking_budget_applied = True
    elif qwen3_structural_off:
        provider_num_predict = min(GENERATION_SAFETY_CAP, output_tokens + thinking_tokens)
        policy = "qwen3_off_structural_compatibility_cap"
        thinking_budget_applied = True
    elif think is False:
        provider_num_predict = output_tokens
        policy = "output_only"
        thinking_budget_applied = False
    else:
        provider_num_predict = output_tokens
        policy = "provider_default_output_cap"
        thinking_budget_applied = False
    return {
        **effective,
        "max_tokens": output_tokens,
        "output_tokens": output_tokens,
        "thinking_tokens": thinking_tokens,
        "provider_num_predict": provider_num_predict,
        "generation_budget_policy": policy,
        "thinking_budget_applied": thinking_budget_applied,
        "native_reasoning_budget_supported": False,
        "generation_safety_cap": GENERATION_SAFETY_CAP,
    }

EXPLICIT_RESPONSE_LANGUAGE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:answer|respond|reply|write)\s+(?:in|with)\s+english\b", re.IGNORECASE), "английском"),
    (re.compile(r"\b(?:answer|respond|reply|write)\s+(?:in|with)\s+russian\b", re.IGNORECASE), "русском"),
    (re.compile(r"\b(?:answer|respond|reply|write)\s+(?:in|with)\s+spanish\b", re.IGNORECASE), "испанском"),
    (re.compile(r"\b(?:answer|respond|reply|write)\s+(?:in|with)\s+french\b", re.IGNORECASE), "французском"),
    (re.compile(r"\b(?:answer|respond|reply|write)\s+(?:in|with)\s+german\b", re.IGNORECASE), "немецком"),
    (re.compile(r"\b(?:answer|respond|reply|write)\s+(?:in|with)\s+ukrainian\b", re.IGNORECASE), "украинском"),
    (re.compile(r"(?:ответь|отвечай|напиши|дай\s+ответ)\s+(?:на|по-)\s*английск", re.IGNORECASE), "английском"),
    (re.compile(r"(?:ответь|отвечай|напиши|дай\s+ответ)\s+(?:на|по-)\s*русск", re.IGNORECASE), "русском"),
    (re.compile(r"(?:ответь|отвечай|напиши|дай\s+ответ)\s+(?:на|по-)\s*испанск", re.IGNORECASE), "испанском"),
    (re.compile(r"(?:ответь|отвечай|напиши|дай\s+ответ)\s+(?:на|по-)\s*французск", re.IGNORECASE), "французском"),
    (re.compile(r"(?:ответь|отвечай|напиши|дай\s+ответ)\s+(?:на|по-)\s*немецк", re.IGNORECASE), "немецком"),
    (re.compile(r"(?:ответь|отвечай|напиши|дай\s+ответ)\s+(?:на|по-)\s*украинск", re.IGNORECASE), "украинском"),
)
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
LATIN_RE = re.compile(r"[A-Za-z]")
COMMON_ENGLISH_RE = re.compile(
    r"\b(?:the|what|how|why|where|when|who|is|are|do|does|did|can|could|please|you|your|tell|explain|write|create|fix)\b",
    re.IGNORECASE,
)


def sanitize_reply(text: str) -> str:
    """Убирает повторы и случайные мусорные блоки из ответа модели."""
    text = re.sub(r"[\u4e00-\u9fff]{2,}.*?(?:[.!?。！？]|$)", "", text)
    text = re.sub(r"\\\[(.*?)\\\]", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.*?)\\\)", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"\\text\{([^{}]+)\}", r"\1", text)
    text = text.replace(r"\,", " ")
    text = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", " ", text)
    text = re.sub(r"(\d)\s+₽", r"\1 ₽", text)
    text = re.sub(r"(\d)\s*⽇", r"\1 ₽", text)

    def _drop_section(src: str, heading: str) -> str:
        pattern = re.compile(rf"(^##\s*{heading}.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
        return re.sub(pattern, "", src)

    for meta_heading in (
        "Минимальный набор фактов",
        "Чеклист перед отправкой",
        "Checklist before sending",
    ):
        text = _drop_section(text, meta_heading)

    text = re.sub(r"^.*Теперь вы можете.*$", "", text, flags=re.MULTILINE)

    lines: list[str] = []
    seen_headings: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            if lines and lines[-1] == "":
                continue
            lines.append("")
            continue

        if stripped.startswith("### "):
            key = stripped.lower()
            if key in seen_headings:
                continue
            seen_headings.add(key)

        if lines and lines[-1].strip() == stripped:
            continue

        lines.append(line)

    return "\n".join(lines).strip()


def response_language_instruction(user_query: str) -> str:
    query = str(user_query or "")
    for pattern, language_name in EXPLICIT_RESPONSE_LANGUAGE_PATTERNS:
        if pattern.search(query):
            return (
                f"{LANGUAGE_MATCHING_POLICY}\n"
                f"Последнее сообщение пользователя явно просит ответить на {language_name}. Ответь на {language_name}."
            )

    cyrillic_count = len(CYRILLIC_RE.findall(query))
    latin_count = len(LATIN_RE.findall(query))
    if cyrillic_count >= max(2, latin_count):
        detected = "Последнее сообщение пользователя выглядит русскоязычным. Ответь на русском."
    elif latin_count >= 2 and COMMON_ENGLISH_RE.search(query):
        detected = "Последнее сообщение пользователя выглядит англоязычным. Ответь на английском."
    elif latin_count >= 2:
        detected = "Последнее сообщение пользователя написано латиницей. Ответь на том же естественном языке этого сообщения."
    else:
        detected = "Если язык последнего сообщения неоднозначен, сохрани язык и стиль последнего сообщения пользователя."

    return f"{LANGUAGE_MATCHING_POLICY}\n{detected}"


def build_messages(
    *,
    role: str,
    user_query: str,
    context: str | None,
    profile_system_prompt: str | None,
    transcript: str | None,
    criteria: Iterable[str],
    history: list[dict[str, str]],
    summary_memory: Iterable[dict[str, Any]] | None = None,
    rag_context: str | None = None,
    processed_transcript: str | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt_for(role)}]
    if profile_system_prompt:
        messages.append({"role": "system", "content": profile_persona_envelope(profile_system_prompt)})
    if context:
        messages.append(
            {
                "role": "user",
                "content": data_envelope(
                    "request_context",
                    context,
                    provenance={"owner": "request_caller", "scope": "active_profile_request"},
                ),
            }
        )
    memory_items = [item for item in (summary_memory or []) if item and item.get("summary")]
    if memory_items:
        memory_block = "\n\n".join(
            f"- [{item.get('source_type') or 'memory'}] {item.get('summary')}" for item in memory_items
        )
        messages.append(
            {
                "role": "user",
                "content": data_envelope(
                    "summary_memory",
                    f"Summary memory:\n{memory_block}",
                    provenance={"owner": "active_profile_session", "items": len(memory_items)},
                ),
            }
        )
    if rag_context:
        messages.append(
            {
                "role": "user",
                "content": data_envelope(
                    "rag_context",
                    f"Relevant RAG context:\n{rag_context}",
                    provenance={"owner": "active_profile", "retrieval": "current_request"},
                    allowed_influence="factual_evidence_only",
                ),
            }
        )
    if processed_transcript:
        messages.append(
            {
                "role": "user",
                "content": data_envelope(
                    "processed_transcript",
                    processed_transcript,
                    provenance={"owner": "active_profile_session", "derived": True},
                ),
            }
        )
    elif transcript:
        messages.append(
            {
                "role": "user",
                "content": data_envelope(
                    "request_transcript",
                    transcript,
                    provenance={"owner": "request_caller", "derived": False},
                ),
            }
        )
    criteria_list = [c for c in criteria if c]
    if criteria_list:
        criteria_block = "\n".join(f"- {item}" for item in criteria_list)
        messages.append(
            {
                "role": "user",
                "content": data_envelope(
                    "evaluation_criteria",
                    criteria_block,
                    provenance={"owner": "active_profile_session", "items": len(criteria_list)},
                    allowed_influence="answer_quality_and_format_only",
                ),
            }
        )
    messages.append(
        {
            "role": "system",
            "content": (
                "Отвечай на последний вопрос пользователя, без повторения уже выданных ответов и без пересказа предыдущего анализа. "
                f"{response_language_instruction(user_query)}\n\n"
                f"{RESPONSE_FORMATTING_GUARDRAIL}"
            ),
        }
    )
    messages.append({"role": "system", "content": GLOBAL_GUARD_POLICY})
    if history:
        messages.extend(
            {
                "role": str(item.get("role") or "user"),
                "content": data_envelope(
                    "chat_history",
                    str(item.get("content") or ""),
                    provenance={
                        "owner": "active_profile_session",
                        "original_role": str(item.get("role") or "unknown"),
                    },
                    allowed_influence="conversation_continuity_only",
                ),
            }
            for item in history
            if str(item.get("content") or "").strip()
        )
    messages.append({"role": "user", "content": user_query})
    return messages


def prompt_blocks(
    *,
    context: str | None,
    profile_system_prompt: str | None,
    summary_memory: Iterable[dict[str, Any]] | None,
    rag_context: str | None,
    processed_transcript: str | None,
    transcript: str | None,
    criteria: Iterable[str],
    history: list[dict[str, str]],
    user_query: str,
) -> list[dict[str, Any]]:
    return [
        {"name": "global_system_policy", "included": True, "trust_class": "L1", "role": "system", "owner": "backend"},
        {
            "name": "profile_persona",
            "included": bool(profile_system_prompt),
            "chars": len(profile_system_prompt or ""),
            "trust_class": "L2",
            "role": "system",
            "owner": "active_profile",
        },
        {
            "name": "request_context",
            "included": bool(context),
            "chars": len(context or ""),
            "trust_class": "L4",
            "role": "user",
            "owner": "request_caller",
        },
        {
            "name": "summary_memory",
            "included": bool([item for item in (summary_memory or []) if item.get("summary")]),
            "items": len([item for item in (summary_memory or []) if item.get("summary")]),
            "trust_class": "L4",
            "role": "user",
            "owner": "active_profile_session",
        },
        {
            "name": "rag_context",
            "included": bool(rag_context),
            "chars": len(rag_context or ""),
            "trust_class": "L4",
            "role": "user",
            "owner": "active_profile",
        },
        {
            "name": "processed_transcript",
            "included": bool(processed_transcript),
            "chars": len(processed_transcript or ""),
            "trust_class": "L4",
            "role": "user",
            "owner": "active_profile_session",
        },
        {
            "name": "raw_transcript_fallback",
            "included": bool(transcript and not processed_transcript),
            "chars": len(transcript or ""),
            "trust_class": "L4",
            "role": "user",
            "owner": "request_caller",
        },
        {
            "name": "evaluation_criteria",
            "included": bool([item for item in criteria if item]),
            "items": len([item for item in criteria if item]),
            "trust_class": "L4",
            "role": "user",
            "owner": "active_profile_session",
        },
        {"name": "immutable_guard", "included": True, "trust_class": "L1", "role": "system", "owner": "backend"},
        {
            "name": "chat_history",
            "included": bool(history),
            "messages": len(history),
            "trust_class": "L4/L5",
            "role": "original_wrapped",
            "owner": "active_profile_session",
        },
        {
            "name": "current_user_query",
            "included": bool(user_query),
            "chars": len(user_query or ""),
            "trust_class": "L3",
            "role": "user",
            "owner": "request_caller",
        },
    ]


def estimate_messages_chars(messages: list[dict[str, str]]) -> int:
    return sum(len(item.get("role", "")) + len(item.get("content", "")) for item in messages)


ANSWER_TRACE_TOKEN_RE = re.compile(r"(?iu)[^\W_](?:[\w:-]*[^\W_])?")
ANSWER_TRACE_STOP_WORDS = {
    "about", "answer", "every", "from", "have", "information", "that", "there", "these", "this", "with",
    "будет", "данные", "информация", "котор", "ответ", "этого", "этот",
}


def assess_rag_answer(
    answer: str,
    evidence_manifest: Iterable[dict[str, Any]] | None,
    rag_diagnostics: dict[str, Any] | None,
) -> dict[str, Any]:
    """Trace an answer only to evidence content spans actually sent to the model."""
    included_evidence = [
        item
        for item in (evidence_manifest or [])
        if item and str(item.get("content") or "").strip()
    ]
    retrieval_status = str(
        (rag_diagnostics or {}).get("overall_status")
        or ("supported" if included_evidence else "disabled")
    )
    evidence_text = "\n".join(str(item.get("content") or "") for item in included_evidence)
    source_ids = list(
        dict.fromkeys(str(item.get("source_id") or "unknown") for item in included_evidence)
    )
    chunk_ids = list(
        dict.fromkeys(
            item.get("chunk_id")
            for item in included_evidence
            if item.get("chunk_id") is not None
        )
    )
    if retrieval_status == "disabled":
        answer_status = "retrieval_disabled"
        matched_terms = []
    elif not included_evidence:
        answer_status = "evidence_not_found"
        matched_terms = []
    else:
        def trace_terms(text: str) -> set[str]:
            return {
                normalized
                for token in ANSWER_TRACE_TOKEN_RE.findall(text)
                if (normalized := token.casefold()) not in ANSWER_TRACE_STOP_WORDS
                and (len(normalized) >= 4 or any(char.isdigit() for char in normalized))
            }

        answer_terms = trace_terms(str(answer or ""))
        evidence_terms = trace_terms(evidence_text)
        matched_terms = sorted(answer_terms.intersection(evidence_terms))[:20]
        answer_status = "evidence_traceable" if matched_terms else "evidence_found_answer_not_traceable"
    return {
        "retrieval_status": retrieval_status,
        "answer_status": answer_status,
        "source_ids": source_ids,
        "chunk_ids": chunk_ids,
        "matched_term_count": len(matched_terms),
        "method": "lexical_evidence_span_trace_v2",
    }


def _chat_summary_snapshot(
    session_id: str,
    *,
    mem_turns: int,
    max_context_chars: int,
) -> tuple[str, list[dict[str, Any]]]:
    old_messages = db.get_messages_before_latest(session_id, keep_pairs=mem_turns)
    identity = [
        {"id": item.get("id"), "role": item.get("role"), "content": str(item.get("content") or "")}
        for item in old_messages
    ]
    digest = hashlib.sha256(
        json.dumps(
            {
                "version": 2,
                "mem_turns": mem_turns,
                "max_context_chars": max_context_chars,
                "messages": identity,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:24]
    return f"chat:{session_id}:snapshot-v2:{digest}", old_messages


def current_session_summary_memory(
    session_id: str,
    *,
    mem_turns: int,
    max_context_chars: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Keep non-chat memories and only the chat summary for the current completed-turn snapshot."""
    bounded_limit = max(1, int(limit or 1))
    current_chat_source, _ = _chat_summary_snapshot(
        session_id,
        mem_turns=max(0, int(mem_turns or 0)),
        max_context_chars=max(1, int(max_context_chars or 1)),
    )
    current_chat_summary = db.get_session_summary_by_source(session_id, "chat", current_chat_source)
    candidates = db.list_session_summaries(session_id, limit=100)
    selected: list[dict[str, Any]] = []
    seen_sources: set[tuple[str, str]] = set()
    legacy_prefix = f"chat:{session_id}:messages:"
    snapshot_prefix = f"chat:{session_id}:snapshot-v2:"
    for item in reversed(candidates):
        source_type = str(item.get("source_type") or "")
        source_id = str(item.get("source_id") or "")
        automatic_chat_summary = source_type == "chat" and source_id.startswith((legacy_prefix, snapshot_prefix))
        if automatic_chat_summary and source_id != current_chat_source:
            continue
        source_key = (source_type, source_id)
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        selected.append(item)
    selected.reverse()
    if not current_chat_summary:
        return selected[-bounded_limit:]
    without_current = [item for item in selected if item.get("id") != current_chat_summary.get("id")]
    if bounded_limit == 1:
        return [current_chat_summary]
    result = [*without_current[-(bounded_limit - 1) :], current_chat_summary]
    return sorted(result, key=lambda item: (str(item.get("updated_at") or ""), int(item.get("id") or 0)))


def _bounded_summary_history(
    messages: list[dict[str, Any]],
    *,
    max_chars: int,
) -> tuple[str, int]:
    """Serialize complete user/assistant turns without slicing either message."""
    included: list[str] = []
    used = 0
    for index in range(0, len(messages) - 1, 2):
        turn = messages[index : index + 2]
        block = "\n".join(f"{item['role']}: {item['content']}" for item in turn)
        added = len(block) + (1 if included else 0)
        if used + added > max_chars:
            break
        included.append(block)
        used += added
    return "\n".join(included), len(included) * 2


def processed_transcript_context(transcript: dict[str, Any] | None, max_chars: int) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if not transcript:
        return "", warnings
    run = db.get_latest_pipeline_run(int(transcript["id"])) if transcript.get("id") is not None else None
    parts: list[str] = []
    if run:
        if run.get("summary"):
            parts.append(f"Summary:\n{run['summary']}")
        if run.get("structured_json"):
            parts.append("Structured data:\n" + json.dumps(run["structured_json"], ensure_ascii=False, indent=2))
        elif run.get("cleaned_transcript"):
            parts.append(f"Cleaned transcript:\n{run['cleaned_transcript']}")
    if not parts:
        warnings.append("processed_transcript_missing")
        return "", warnings
    text = "\n\n".join(parts).strip()
    if len(text) > max_chars:
        warnings.append("processed_transcript_truncated")
        text = text[:max_chars].rstrip()
    return text, warnings


def maybe_compress_session_history(
    *,
    service: "ChatService",
    session_id: str,
    profile_id: int,
    model_name: str,
    settings: dict[str, Any],
) -> dict[str, Any] | None:
    if not settings.get("summary_memory_enabled", True):
        return None
    configured_mem_turns = settings.get("mem_turns")
    mem_turns = max(0, int(config.SETTINGS.mem_turns if configured_mem_turns is None else configured_mem_turns))
    max_context_chars = max(1, int(settings.get("max_context_chars") or 16000))
    source_id, old_messages = _chat_summary_snapshot(
        session_id,
        mem_turns=mem_turns,
        max_context_chars=max_context_chars,
    )
    if len(old_messages) < max(8, mem_turns * 2):
        return None
    existing = db.get_session_summary_by_source(session_id, "chat", source_id)
    if existing:
        return existing
    history_text, summarized_message_count = _bounded_summary_history(
        old_messages,
        max_chars=max_context_chars,
    )
    if not history_text:
        return None
    prompt = [
        {
            "role": "system",
            "content": "Сожми старую часть диалога в краткую summary memory. Не добавляй факты от себя.",
        },
        {"role": "system", "content": GLOBAL_GUARD_POLICY},
        {
            "role": "user",
            "content": (
                "Сохрани решения, задачи, предпочтения пользователя и важный контекст. "
                "Не пересказывай малозначимые реплики.\n\n"
                + data_envelope(
                    "chat_history_for_summary",
                    history_text,
                    provenance={"owner": "active_profile_session", "session_id": session_id},
                    allowed_influence="conversation_memory_only",
                )
            ),
        },
    ]
    stage_settings = {
        "temperature": 0.2,
        "max_tokens": min(int(settings.get("max_tokens") or config.SETTINGS.max_tokens), 900),
    }
    summary = service.chat_completion(model_name, prompt, settings=stage_settings)
    if not summary.strip():
        return None
    return db.create_session_summary(
        profile_id=profile_id,
        session_id=session_id,
        source_type="chat",
        source_id=source_id,
        summary=summary.strip(),
        structured_json={
            "message_count": len(old_messages),
            "source_message_count": len(old_messages),
            "summarized_message_count": summarized_message_count,
            "truncated": summarized_message_count < len(old_messages),
            "mem_turns": mem_turns,
            "max_context_chars": max_context_chars,
            "snapshot_version": 2,
        },
    )


class ChatService:
    def __init__(self) -> None:
        pass

    def log_chat_event(self, payload: dict[str, object]) -> None:
        try:
            config.LOG_DIR.mkdir(parents=True, exist_ok=True)
            with config.CHAT_LOG_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(redact_log_event(payload), ensure_ascii=False, separators=(",", ":")) + "\n")
        except Exception as exc:  # pragma: no cover - лог только для диагностики
            LOGGER.warning("Failed to write chat log: %s", type(exc).__name__)

    def _runtime_kwargs(self, model: str, settings: dict, *, vision: bool = False) -> dict[str, Any]:
        request_settings = apply_generation_budget_policy(settings, model_name=model)
        request_settings["num_ctx_requested"] = request_settings.get("num_ctx")
        request_settings["num_ctx_applied"] = request_settings.get("num_ctx") is not None
        request_settings["num_ctx_apply_method"] = "native_ollama_options"
        keep_alive = ollama_runtime.resolve_keep_alive(model, request_settings)
        raw_num_gpu = request_settings.get("ollama_num_gpu", request_settings.get("num_gpu"))
        num_gpu = None
        if raw_num_gpu is not None:
            try:
                num_gpu = int(raw_num_gpu)
            except (TypeError, ValueError):
                num_gpu = None
        runtime_kwargs = {
            "temperature": request_settings.get("temperature", config.SETTINGS.temperature),
            "max_tokens": request_settings["provider_num_predict"],
            "keep_alive": keep_alive,
        }
        context_key = "vision_num_ctx" if vision else "num_ctx"
        raw_num_ctx = request_settings.get(context_key)
        if raw_num_ctx is not None:
            try:
                runtime_kwargs["num_ctx"] = max(1, int(raw_num_ctx))
            except (TypeError, ValueError):
                pass
        if num_gpu is not None:
            runtime_kwargs["num_gpu"] = num_gpu
        if "ollama_allow_cpu_fallback" in request_settings:
            runtime_kwargs["allow_cpu_fallback"] = bool(request_settings.get("ollama_allow_cpu_fallback"))
        think = _resolve_ollama_think(request_settings.get("ollama_think"))
        if think is not None:
            runtime_kwargs["think"] = think
        return runtime_kwargs

    @staticmethod
    def require_final_answer(result: ollama_runtime.ChatCompletionResult) -> ollama_runtime.ChatCompletionResult:
        if result.done_reason == "length":
            exhausted_after_reasoning = bool(result.reasoning.strip())
            message = (
                "Thinking budget exhausted before the model produced a final answer."
                if exhausted_after_reasoning and not result.content.strip()
                else "The model response reached its token limit before completion."
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "chat_final_answer_incomplete",
                    "message": message,
                    "done_reason": result.done_reason,
                },
            )
        if result.content.strip():
            return result
        raise HTTPException(
            status_code=502,
            detail={
                "code": "chat_final_answer_incomplete",
                "message": "The model completed without a final answer.",
                "done_reason": result.done_reason,
            },
        )

    @classmethod
    def apply_stream_completion_policy(
        cls,
        events: Iterable[ollama_runtime.ChatStreamEvent],
        *,
        think: bool | str | None,
    ) -> Iterator[ollama_runtime.ChatStreamEvent]:
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        for event in events:
            if event.content:
                content_parts.append(event.content)
            if event.reasoning:
                reasoning_parts.append(event.reasoning)
            if event.done:
                cls.require_final_answer(
                    ollama_runtime.ChatCompletionResult(
                        content="".join(content_parts),
                        reasoning="".join(reasoning_parts),
                        done_reason=event.done_reason,
                        eval_count=event.eval_count,
                    )
                )
            yield replace(event, reasoning="" if think is False else event.reasoning)

    def chat_completion_result(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        settings: dict,
    ) -> ollama_runtime.ChatCompletionResult:
        try:
            result = continuation.complete(
                messages,
                lambda pass_messages: ollama_runtime.chat_completion_result(
                    model, messages=pass_messages, **self._runtime_kwargs(model, settings)
                ),
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Local model generation failed.") from exc
        think = _resolve_ollama_think(settings.get("ollama_think"))
        sanitized = replace(result, content=sanitize_reply(result.content))
        enforce_protected_output(messages, sanitized.content)
        enforce_protected_output(messages, sanitized.reasoning)
        completed = self.require_final_answer(sanitized)
        return replace(completed, reasoning="") if think is False else completed

    def chat_completion(self, model: str, messages: list[dict[str, str]], *, settings: dict) -> str:
        return self.chat_completion_result(model, messages, settings=settings).content

    def chat_completion_stream_events(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        settings: dict,
    ) -> Iterator[ollama_runtime.ChatStreamEvent]:
        think = _resolve_ollama_think(settings.get("ollama_think"))
        try:
            yield from self.apply_stream_completion_policy(
                guard_stream_events(
                    messages,
                    continuation.stream(
                        messages,
                        lambda pass_messages: ollama_runtime.chat_completion_stream_events(
                            model, messages=pass_messages, **self._runtime_kwargs(model, settings)
                        ),
                    ),
                ),
                think=think,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Local model generation failed.") from exc

    def chat_completion_stream(self, model: str, messages: list[dict[str, str]], *, settings: dict) -> Iterator[str]:
        for event in self.chat_completion_stream_events(model, messages, settings=settings):
            if event.content:
                yield event.content


def session_title_hint(raw_title: str | None, query: str | None) -> str:
    if raw_title and raw_title.strip():
        return raw_title.strip()
    prompt = (query or "").strip()
    if prompt:
        return (prompt[:60] + ("…" if len(prompt) > 60 else "")).strip()
    return "Новая сессия"


def normalize_model_name(model_name: str | None, fallback: str | None = None) -> str:
    base = fallback or config.SETTINGS.model
    return (model_name or base).strip() or base
