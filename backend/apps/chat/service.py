from __future__ import annotations

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
from backend.apps.chat.prompt_policy import GLOBAL_GUARD_POLICY, data_envelope, profile_persona_envelope
from backend.apps.chat.services import ollama_runtime

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


def _resolve_ollama_think(value: Any) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"on", "true", "1", "yes", "think"}:
        return True
    if normalized in {"off", "false", "0", "no", "nothink"}:
        return False
    return None


def apply_generation_budget_policy(settings: dict[str, Any] | None) -> dict[str, Any]:
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
        int(config.DEFAULT_RUNTIME_SETTINGS.get("thinking_tokens") or 2048),
    )
    think = _resolve_ollama_think(effective.get("ollama_think"))
    if think is True:
        provider_num_predict = min(GENERATION_SAFETY_CAP, output_tokens + thinking_tokens)
        policy = "combined_compatibility_cap"
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
    old_messages = db.get_messages_before_latest(session_id, keep_pairs=mem_turns)
    if len(old_messages) < max(8, mem_turns * 2):
        return None
    source_id = f"chat:{session_id}:messages:{len(old_messages)}"
    existing = db.get_session_summary_by_source(session_id, "chat", source_id)
    if existing:
        return existing
    history_text = "\n".join(f"{item['role']}: {item['content']}" for item in old_messages)
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
                    history_text[: int(settings.get("max_context_chars") or 16000)],
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
        structured_json={"message_count": len(old_messages)},
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
        request_settings = apply_generation_budget_policy(settings)
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
        if result.content.strip():
            return result
        exhausted_after_reasoning = bool(result.reasoning.strip()) and result.done_reason == "length"
        message = (
            "Thinking budget exhausted before the model produced a final answer."
            if exhausted_after_reasoning
            else "The model completed without a final answer."
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": "chat_final_answer_incomplete",
                "message": message,
                "done_reason": result.done_reason,
            },
        )

    def chat_completion_result(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        settings: dict,
    ) -> ollama_runtime.ChatCompletionResult:
        try:
            result = ollama_runtime.chat_completion_result(
                model,
                messages=messages,
                **self._runtime_kwargs(model, settings),
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Local model generation failed.") from exc
        sanitized = replace(result, content=sanitize_reply(result.content))
        return self.require_final_answer(sanitized)

    def chat_completion(self, model: str, messages: list[dict[str, str]], *, settings: dict) -> str:
        return self.chat_completion_result(model, messages, settings=settings).content

    def chat_completion_stream_events(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        settings: dict,
    ) -> Iterator[ollama_runtime.ChatStreamEvent]:
        try:
            yield from ollama_runtime.chat_completion_stream_events(
                model,
                messages=messages,
                **self._runtime_kwargs(model, settings),
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
