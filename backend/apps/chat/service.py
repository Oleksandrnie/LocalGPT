from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Iterable, Iterator

from fastapi import HTTPException

from app import config, db
from app.roles import system_prompt_for
from backend.apps.chat.services import ollama_runtime

LOGGER = logging.getLogger(__name__)

RESPONSE_FORMATTING_GUARDRAIL = (
    "Правила оформления расчётов и цен:\n"
    "- Не используй LaTeX, MathML, markdown-формулы и синтаксис вида \\[...\\], \\( ... \\), \\text{...}.\n"
    "- Не используй запятую как разделитель тысяч: неправильно 35,690 ₽, правильно 35 690 ₽.\n"
    "- Денежные суммы пиши обычным текстом в человекочитаемом русском формате."
)

LANGUAGE_MATCHING_POLICY = (
    "Языковое правило:\n"
    "- Отвечай на языке последнего сообщения пользователя.\n"
    "- Переходи на другой язык только если именно последнее сообщение пользователя явно просит ответить на конкретном другом языке.\n"
    "- Язык истории, RAG, transcript/context, примеров кода и профильных инструкций не является разрешением менять язык ответа."
)

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
        messages.append({"role": "system", "content": f"Профильный system prompt:\n{profile_system_prompt}"})
    if context:
        messages.append({"role": "user", "content": f"Контекст профиля/пользователя:\n{context}"})
    memory_items = [item for item in (summary_memory or []) if item and item.get("summary")]
    if memory_items:
        memory_block = "\n\n".join(
            f"- [{item.get('source_type') or 'memory'}] {item.get('summary')}" for item in memory_items
        )
        messages.append({"role": "user", "content": f"Summary memory:\n{memory_block}"})
    if rag_context:
        messages.append(
            {
                "role": "system",
                "content": (
                    "Authoritative local RAG context for the active profile follows. "
                    "Use it when answering questions about the user's profile, company, tariffs, templates, rules, or local documents. "
                    "If the answer is not present in this context, say that the local RAG context does not contain enough data instead of inventing facts.\n\n"
                    f"Relevant RAG context:\n{rag_context}"
                ),
            }
        )
    if processed_transcript:
        messages.append({"role": "user", "content": f"Обработанный transcript/context:\n{processed_transcript}"})
    elif transcript:
        messages.append({"role": "user", "content": f"Короткий transcript/context:\n{transcript}"})
    criteria_list = [c for c in criteria if c]
    if criteria_list:
        criteria_block = "\n".join(f"- {item}" for item in criteria_list)
        messages.append({"role": "user", "content": f"Критерии оценки:\n{criteria_block}"})
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
    if history:
        messages.extend(history)
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
        {"name": "profile_system_prompt", "included": bool(profile_system_prompt), "chars": len(profile_system_prompt or "")},
        {"name": "profile_context", "included": bool(context), "chars": len(context or "")},
        {
            "name": "summary_memory",
            "included": bool([item for item in (summary_memory or []) if item.get("summary")]),
            "items": len([item for item in (summary_memory or []) if item.get("summary")]),
        },
        {"name": "rag_context", "included": bool(rag_context), "chars": len(rag_context or "")},
        {"name": "processed_transcript", "included": bool(processed_transcript), "chars": len(processed_transcript or "")},
        {"name": "raw_transcript_fallback", "included": bool(transcript and not processed_transcript), "chars": len(transcript or "")},
        {"name": "criteria", "included": bool([item for item in criteria if item]), "items": len([item for item in criteria if item])},
        {"name": "short_raw_history", "included": bool(history), "messages": len(history)},
        {"name": "current_user_query", "included": bool(user_query), "chars": len(user_query or "")},
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
    mem_turns = max(1, int(settings.get("mem_turns") or config.SETTINGS.mem_turns))
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
        {
            "role": "user",
            "content": (
                "Сохрани решения, задачи, предпочтения пользователя и важный контекст. "
                "Не пересказывай малозначимые реплики.\n\n"
                f"{history_text[: int(settings.get('max_context_chars') or 16000)]}"
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
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover - лог только для диагностики
            LOGGER.warning("Failed to write chat log: %s", exc)

    def _runtime_kwargs(self, model: str, settings: dict) -> dict[str, Any]:
        request_settings = dict(settings or {})
        request_settings["num_ctx_requested"] = request_settings.get("num_ctx")
        request_settings["num_ctx_applied"] = False
        request_settings["num_ctx_apply_method"] = "openai_compatible_not_supported"
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
            "max_tokens": request_settings.get("max_tokens", config.SETTINGS.max_tokens),
            "keep_alive": keep_alive,
        }
        if num_gpu is not None:
            runtime_kwargs["num_gpu"] = num_gpu
        return runtime_kwargs

    def chat_completion(self, model: str, messages: list[dict[str, str]], *, settings: dict) -> str:
        try:
            text = ollama_runtime.chat_completion(model, messages=messages, **self._runtime_kwargs(model, settings))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc
        return sanitize_reply(text)

    def chat_completion_stream(self, model: str, messages: list[dict[str, str]], *, settings: dict) -> Iterator[str]:
        try:
            yield from ollama_runtime.chat_completion_stream(model, messages=messages, **self._runtime_kwargs(model, settings))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc


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
