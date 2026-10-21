from __future__ import annotations

import json
import logging
import re
import threading
import time
from copy import deepcopy
from typing import Any

from fastapi import HTTPException

from app import config, db
from app.services import models as model_service
from app.services.thinking import resolve_thinking
from backend.apps.chat.prompt_policy import GLOBAL_GUARD_POLICY, data_envelope, profile_configuration_envelope
from backend.apps.chat.service import ChatService
from backend.apps.chat.services import model_residency, ollama_runtime

LOGGER = logging.getLogger(__name__)
_PIPELINE_STOP_EVENT = threading.Event()
_ACTIVE_PIPELINE_MODELS_LOCK = threading.Lock()
_ACTIVE_PIPELINE_MODELS: set[str] = set()
ASR_PIPELINE_SETTINGS_MODEL_ID = "__asr_pipeline__"

PIPELINE_PRESETS: dict[str, dict[str, Any]] = {
    "fast": {
        "cleaner": True,
        "segmenter": False,
        "speaker_resolver": False,
        "structurer": False,
        "summary": True,
        "memory_save": False,
        "debug_artifacts": False,
    },
    "balanced": {
        "cleaner": True,
        "segmenter": True,
        "speaker_resolver": True,
        "structurer": True,
        "summary": True,
        "memory_save": False,
        "debug_artifacts": False,
    },
    "deep": {
        "cleaner": True,
        "segmenter": True,
        "speaker_resolver": True,
        "structurer": True,
        "summary": True,
        "memory_save": True,
        "debug_artifacts": True,
    },
}

VALID_ACTIONS = {"clean", "summary", "smart_summary", "tasks", "full"}
SUMMARY_ACTIONS = {"summary", "smart_summary", "full"}
SPEAKER_RE = re.compile(r"^Speaker_\d+$")
MIN_TRANSCRIPT_CHUNK_CHARS = 500
DEFAULT_TRANSCRIPT_CHUNK_CHARS = 24000
SUMMARY_INLINE_TRANSCRIPT_CHARS = 24000
SUMMARY_SEGMENT_DIGEST_CHARS = 18000
INCOMPLETE_SUMMARY_HEADING = "## Неполное summary: не удалось покрыть следующие темы"
ASR_SUMMARY_GUARDRAILS_RU = (
    "Сохраняй различия и термины из evidence. Не подменяй архитектуру, названия систем, интеграции, "
    "ответственных или статусы задач своими предположениями. Если источник противоречивый, помести "
    "спорный пункт в вопросы для уточнения. Не повышай варианты и гипотезы до подтверждённых решений. "
    "Не назначай ответственных, если они явно не подтверждены."
)
ASR_SUMMARY_GUARDRAILS_EN = (
    "Preserve distinctions and source terms from evidence. Do not replace architecture, system names, integrations, "
    "owners or task statuses with assumptions. If evidence conflicts, put the disputed item into Questions to Clarify. "
    "Do not upgrade options or hypotheses into confirmed decisions. Do not assign owners unless they are explicitly confirmed."
)
NO_DECISIONS_RE = re.compile(
    r"(?:не\s+(?:зафиксировано|выявлено|обнаружено)|нет\s+(?:решени[йя]|договор[её]нност))",
    re.IGNORECASE,
)
TOKEN_RE = re.compile(r"[a-zа-яё0-9][a-zа-яё0-9_-]{2,}", re.IGNORECASE)
CYRILLIC_RE = re.compile(r"[а-яё]", re.IGNORECASE)
LATIN_RE = re.compile(r"[a-z]", re.IGNORECASE)
TOPIC_STOPWORDS = {
    "это",
    "как",
    "что",
    "для",
    "или",
    "если",
    "при",
    "над",
    "под",
    "без",
    "все",
    "ещё",
    "еще",
    "уже",
    "нужно",
    "надо",
    "будет",
    "были",
    "было",
    "быть",
    "есть",
    "нет",
    "там",
    "тут",
    "про",
    "они",
    "она",
    "оно",
    "его",
    "это",
    "того",
    "этого",
    "когда",
    "который",
    "которая",
    "которые",
    "можно",
    "раз",
    "только",
    "тоже",
    "так",
    "вот",
    "the",
    "and",
    "for",
    "with",
    "not",
    "none",
    "summary",
    "chunk",
    "context",
    "status",
    "task",
    "topic",
}
SUMMARY_INVALID_PATTERNS = (
    re.compile(r"\bthe\s+task\s+is\s+to\s+summari[sz]e\b", re.IGNORECASE),
    re.compile(r"\bthe\s+provided\s+text\s+appears\s+to\s+be\b", re.IGNORECASE),
    re.compile(r"\bfollowing\s+conversation\s+in\s+english\b", re.IGNORECASE),
    re.compile(r"\bcreate\s+the\s+summary\s+strictly\s+in\s+this\s+markdown\s+format\b", re.IGNORECASE),
    re.compile(r"\boutput\s+language:\s*(?:english|russian)\b", re.IGNORECASE),
    re.compile(r"\bevidence_json\b", re.IGNORECASE),
)
SUMMARY_OVERVIEW_ARTIFACT_PATTERNS = (
    re.compile(r"\bSpeaker[_\s-]*\d+\b", re.IGNORECASE),
    re.compile(r"(?im)^\s*(?:\d+\.\s*)?\*\*?\s*(?:участники|participants)\s*[:：]"),
    re.compile(r"(?im)^\s*(?:\d+\.\s*)?\*\*?\s*(?:язык|language)\s*[:：]\s*(?:русский|english|английский|russian)\b"),
    re.compile(r"\bкратк(?:ий|ого)\s+обзор(?:а)?\s+диалога\b", re.IGNORECASE),
    re.compile(r"\bbrief\s+overview\s+of\s+(?:the\s+)?(?:dialogue|conversation)\b", re.IGNORECASE),
    re.compile(r"\bиз-за\s+отсутствия\s+контекста\b", re.IGNORECASE),
    re.compile(r"\bне\s+могу\s+предоставить\s+более\s+подробн", re.IGNORECASE),
    re.compile(r"\bdue\s+to\s+(?:the\s+)?lack\s+of\s+context\b", re.IGNORECASE),
    re.compile(r"\bi\s+cannot\s+provide\s+(?:a\s+)?more\s+detailed\b", re.IGNORECASE),
)


def _json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _merge_dict(target: dict[str, Any], updates: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(updates, dict):
        return target
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_dict(target[key], value)
        elif value is not None:
            target[key] = value
    return target


def _extract_json(text: str, fallback: Any) -> Any:
    raw = (text or "").strip()
    if not raw:
        return fallback
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    candidates = [raw]
    start = raw.find("[")
    end = raw.rfind("]")
    if start >= 0 and end > start:
        candidates.append(raw[start : end + 1])
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        candidates.append(raw[start : end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return fallback


def _normalize_preset(value: str | None, fallback: str = "balanced") -> str:
    preset = (value or fallback or "balanced").strip().lower()
    if preset not in PIPELINE_PRESETS:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_pipeline_preset", "message": "Pipeline preset must be fast, balanced or deep."},
        )
    return preset


def _normalize_action(value: str | None) -> str:
    action = (value or "full").strip().lower()
    if action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_pipeline_action", "message": "Pipeline action must be clean, summary, smart_summary, tasks or full."},
        )
    return action


def _stage_enabled(stage: str, action: str, preset: str, pipeline: dict[str, Any]) -> bool:
    preset_cfg = PIPELINE_PRESETS[preset]
    if action == "clean":
        desired = stage == "cleaner"
    elif action == "summary":
        desired = stage == "summary"
    elif action == "smart_summary":
        desired = stage in {"structurer", "summary"}
    elif action == "tasks":
        desired = stage in {"segmenter", "structurer"}
    elif action == "full":
        desired = stage in {"segmenter", "speaker_resolver", "structurer", "summary"}
    else:
        desired = bool(preset_cfg.get(stage))
    stage_cfg = pipeline.get(stage) or {}
    return desired and bool(stage_cfg.get("enabled", True))


def _stage_settings(settings: dict[str, Any], stage: str) -> dict[str, Any]:
    stage_cfg = ((settings.get("pipeline") or {}).get(stage) or {}).copy()
    default_stage_model = ((config.DEFAULT_PIPELINE.get(stage) or {}).get("model") or "").strip()
    fallback_model = str(settings.get("_fallback_model") or "").strip()
    if fallback_model == ASR_PIPELINE_SETTINGS_MODEL_ID:
        fallback_model = default_stage_model or config.SETTINGS.model
    model = str(stage_cfg.get("model") or fallback_model or default_stage_model or config.SETTINGS.model).strip()
    if fallback_model and fallback_model != model:
        try:
            if not model_service.is_model_installed(model) and model_service.is_model_installed(fallback_model):
                model = fallback_model
        except Exception:
            pass
    return {
        "model": model,
        "temperature": stage_cfg.get("temperature", 0.2),
        "max_tokens": stage_cfg.get("max_tokens", config.SETTINGS.max_tokens),
    }


def _pipeline_keep_alive(settings: dict[str, Any] | None) -> str | None:
    value = (settings or {}).get("pipeline_keep_alive", config.SETTINGS.ollama_pipeline_keep_alive)
    text = str(value if value is not None else "").strip()
    return text or None


def _pipeline_num_gpu(settings: dict[str, Any] | None) -> int | None:
    value = (settings or {}).get("pipeline_num_gpu", config.SETTINGS.ollama_pipeline_num_gpu)
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "auto", "default", "none", "null"}:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _pipeline_ollama_think(settings: dict[str, Any] | None) -> bool | str | None:
    return resolve_thinking((settings or {}).get("ollama_think"))


def _clean_text_fallback(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"\b(\w+)(?:\s+\1\b){2,}", r"\1", text, flags=re.IGNORECASE)
    return text


def _segment_fallback(text: str) -> list[dict[str, Any]]:
    chunks = [item.strip() for item in re.split(r"(?<=[.!?。！？])\s+", text or "") if item.strip()]
    if not chunks and text.strip():
        chunks = [text.strip()]
    segments: list[dict[str, Any]] = []
    current = ""
    for chunk in chunks:
        if len(current) + len(chunk) + 1 <= 700:
            current = f"{current} {chunk}".strip()
            continue
        if current:
            segments.append({"segment_id": len(segments) + 1, "text": current})
        current = chunk
    if current:
        segments.append({"segment_id": len(segments) + 1, "text": current})
    return segments


def _append_warning_once(warnings: list[str], warning: str) -> None:
    if warning not in warnings:
        warnings.append(warning)


def _pipeline_stop_detail(stage: str | None = None) -> dict[str, Any]:
    return {
        "code": "pipeline_cancelled",
        "stage": stage,
        "message": "ASR pipeline stop requested.",
    }


def _raise_if_pipeline_stop_requested(stage: str | None = None) -> None:
    if _PIPELINE_STOP_EVENT.is_set():
        raise HTTPException(status_code=499, detail=_pipeline_stop_detail(stage))


def _configured_pipeline_models() -> set[str]:
    models: set[str] = set()
    for source in (config.DEFAULT_PIPELINE,):
        for stage_cfg in (source or {}).values():
            if isinstance(stage_cfg, dict):
                model = str(stage_cfg.get("model") or "").strip()
                if model:
                    models.add(model)
    return models


def request_pipeline_stop() -> dict[str, Any]:
    _PIPELINE_STOP_EVENT.set()
    with _ACTIVE_PIPELINE_MODELS_LOCK:
        models = set(_ACTIVE_PIPELINE_MODELS)
    models.update(_configured_pipeline_models())

    unload_result = ollama_runtime.force_unload_models(
        models,
        unload_timeout=1.0,
        wait_timeout=1.5,
        terminate_stuck_runners=True,
    )
    return {
        "pipeline_stop_requested": True,
        "active_models": sorted(models),
        **unload_result,
    }


def reset_pipeline_stop_request() -> None:
    _PIPELINE_STOP_EVENT.clear()


def _transcript_chunk_chars(settings: dict[str, Any]) -> int:
    try:
        value = int(settings.get("max_transcript_chars") or DEFAULT_TRANSCRIPT_CHUNK_CHARS)
    except (TypeError, ValueError):
        value = DEFAULT_TRANSCRIPT_CHUNK_CHARS
    return max(MIN_TRANSCRIPT_CHUNK_CHARS, value)


def _split_text_chunks(text: str, max_chars: int) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return [""]
    if len(raw) <= max_chars:
        return [raw]

    chunks: list[str] = []
    start = 0
    total = len(raw)
    min_boundary = max(1, int(max_chars * 0.45))
    while start < total:
        hard_end = min(total, start + max_chars)
        end = hard_end
        if hard_end < total:
            search_start = min(total, start + min_boundary)
            boundaries = [
                raw.rfind("\n\n", search_start, hard_end),
                raw.rfind("\n", search_start, hard_end),
                raw.rfind(". ", search_start, hard_end),
                raw.rfind("? ", search_start, hard_end),
                raw.rfind("! ", search_start, hard_end),
                raw.rfind("; ", search_start, hard_end),
            ]
            boundary = max(boundaries)
            if boundary > start:
                end = boundary + 1
        chunk = raw[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
        while start < total and raw[start].isspace():
            start += 1
    return chunks or [raw]


def _debug_stage_input(debug: dict[str, Any] | None, stage: str, prompt: list[dict[str, str]], chunk_id: int | None = None) -> None:
    if not debug:
        return
    key = stage if chunk_id is None else f"{stage}_chunk_{chunk_id}"
    debug.setdefault("stage_inputs", {})[key] = prompt


def _reindex_segments(items: list[dict[str, Any]], *, chunk_id: int, next_segment_id: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for local_idx, item in enumerate(items, start=1):
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        result.append(
            {
                "segment_id": next_segment_id + len(result),
                "chunk_id": chunk_id,
                "local_segment_id": int(item.get("segment_id") or local_idx),
                "text": text,
            }
        )
    return result


def _attach_chunk_to_mapping(mapping: list[dict[str, Any]], segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chunk_by_segment_id = {int(item.get("segment_id") or 0): item.get("chunk_id") for item in segments}
    result: list[dict[str, Any]] = []
    for item in mapping:
        next_item = dict(item)
        chunk_id = chunk_by_segment_id.get(int(next_item.get("segment_id") or 0))
        if chunk_id is not None:
            next_item["chunk_id"] = chunk_id
        result.append(next_item)
    return result


def _empty_structure() -> dict[str, Any]:
    return {
        "topic": "не указано",
        "summary": "",
        "current_state": "не указано",
        "target_state": "не указано",
        "tasks": [],
        "decisions": [],
        "proposals": [],
        "agreements": [],
        "risks": [],
        "open_questions": [],
        "next_steps": [],
        "owners": "не указано",
        "deadlines": "не указано",
    }


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized or normalized.lower() in {"no specific agreement found", "none", "not specified"}:
            return []
        return [normalized]
    return [value]


def _normalize_structured_output(value: Any, warnings: list[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return _empty_structure()
    result = _empty_structure()
    source_context = _context_text(value)
    aliases = {
        "topic": ("topic", "theme", "тема"),
        "summary": ("summary", "резюме", "суть"),
        "current_state": ("current_state", "current", "текущее_состояние", "as_is", "as-is"),
        "target_state": ("target_state", "target", "целевое_состояние", "to_be", "to-be"),
        "decisions": ("decisions", "решения", "confirmed_decisions"),
        "proposals": ("proposals", "solutions", "предложения", "варианты"),
        "agreements": ("agreements", "договоренности", "договорённости"),
        "tasks": ("tasks", "задачи"),
        "risks": ("risks", "риски"),
        "open_questions": ("open_questions", "questions", "вопросы", "открытые_вопросы"),
        "next_steps": ("next_steps", "следующие_действия"),
        "owners": ("owners", "responsible", "ответственные", "ответственность"),
        "deadlines": ("deadlines", "schedules", "сроки", "графики"),
    }
    for target, keys in aliases.items():
        for key in keys:
            if key in value:
                result[target] = value.get(key)
                break

    result["topic"] = _normalize_pipeline_text(result.get("topic") or "не указано", source_context, warnings) or "не указано"
    result["summary"] = _normalize_pipeline_text(result.get("summary") or "", source_context, warnings)
    result["current_state"] = (
        _normalize_pipeline_text(result.get("current_state") or "не указано", source_context, warnings) or "не указано"
    )
    result["target_state"] = (
        _normalize_pipeline_text(result.get("target_state") or "не указано", source_context, warnings) or "не указано"
    )
    for key in ("decisions", "agreements", "risks", "open_questions", "next_steps"):
        result[key] = _dedupe_strings(
            [_normalize_pipeline_text(item, source_context, warnings) for item in _as_list(result.get(key))]
        )
    proposals = [_normalize_pipeline_text(item, source_context, warnings) for item in _as_list(result.get("proposals"))]
    confirmed_decisions: list[str] = []
    for item in result["decisions"]:
        if _looks_unconfirmed_or_proposed(item):
            proposals.append(item)
        else:
            confirmed_decisions.append(item)
    result["decisions"] = _dedupe_strings(confirmed_decisions)
    result["proposals"] = _dedupe_strings(proposals)
    result["owners"] = [_normalize_responsible(item) for item in _as_list(result.get("owners"))]
    result["owners"] = _dedupe_strings(result["owners"]) or ["не указано"]
    result["deadlines"] = _dedupe_strings(
        [_normalize_pipeline_text(item, source_context, warnings) for item in _as_list(result.get("deadlines"))]
    ) or ["не указано"]

    tasks: list[dict[str, Any]] = []
    for item in _as_list(result.get("tasks")):
        if isinstance(item, dict):
            task_context = _context_text(source_context, item)
            task_text = _normalize_pipeline_text(
                item.get("task") or item.get("title") or item.get("name") or item.get("text") or "",
                task_context,
                warnings,
            )
            context = _normalize_pipeline_text(
                item.get("context") or item.get("details") or item.get("description") or item.get("evidence") or "",
                task_context,
                warnings,
            )
            responsible = _normalize_responsible(item.get("responsible") or item.get("owner") or "не указано")
            status = str(item.get("status") or "open").strip() or "open"
        else:
            task_text = _normalize_pipeline_text(item, source_context, warnings)
            context = ""
            responsible = "не указано"
            status = "open"
        if not task_text:
            continue
        status = _normalize_task_status(task_text, context, status)
        tasks.append({"task": task_text, "context": context, "responsible": responsible, "status": status})
    result["tasks"] = tasks
    return result


def _is_empty_marker(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {
        "",
        "none",
        "not specified",
        "no specific agreement found",
        "не указано",
        "не зафиксировано",
        "требует уточнения",
    }


def _short_text(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip(" .,;:-") + "..."


def _context_text(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            parts.append(value)
        else:
            try:
                parts.append(json.dumps(value, ensure_ascii=False))
            except TypeError:
                parts.append(str(value))
    return "\n".join(parts)


def _normalize_pipeline_text(text: Any, context: str = "", warnings: list[str] | None = None) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _normalize_responsible(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text or _is_empty_marker(text):
        return "не указано"
    if text.lower() in {"unknown speaker", "unknown", "speaker_1", "speaker_2"}:
        return "не указано"
    return text[:80]


def _looks_unconfirmed_or_proposed(text: str) -> bool:
    lowered = str(text or "").lower()
    if _has_confirmation_marker(lowered):
        return False
    if re.search(r"\b(?:вариант|предлож|обсуд|может|можно|возможно|уточнить|проверить|спросить)\w*", lowered):
        return True
    if re.search(
        r"\b(?:создать|создание|сделать|подготовить|разработать|разработка|использовать|перейти|развернуть|"
        r"настроить|проверить|уточнить|нужно|надо|требуется|планируется|задача)\w*",
        lowered,
    ):
        return True
    return False


def _has_confirmation_marker(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:решили|решено|договорились|согласовали|утвердили|подтвердили|зафиксировали|"
            r"принято\s+решение|agreed|confirmed|approved)\b",
            str(text or "").lower(),
        )
    )


def _normalize_task_status(task_text: str, context: str, status: str) -> str:
    normalized = (status or "open").strip().lower()
    if normalized not in {"open", "proposed", "agreed", "blocked"}:
        normalized = "open"
    if _looks_unconfirmed_or_proposed(_context_text(task_text, context)):
        return "proposed"
    return normalized


def _dedupe_strings(items: list[Any], *, limit: int | None = None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _short_text(item, 320)
        if _is_empty_marker(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
        if limit is not None and len(result) >= limit:
            break
    return result


def _task_key(item: dict[str, Any]) -> str:
    return " ".join(
        [
            str(item.get("task") or "").strip().lower(),
            str(item.get("context") or "").strip().lower(),
            str(item.get("responsible") or "").strip().lower(),
        ]
    ).strip()


def _merge_structured_outputs(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return _empty_structure()
    if len(items) == 1:
        result = dict(items[0])
        result.setdefault("coverage_topics", _coverage_topics_from_structure(result))
        result.setdefault("chunk_count", 1)
        return result

    merged = _empty_structure()
    topics: list[str] = []
    summaries: list[str] = []
    current_states: list[str] = []
    target_states: list[str] = []
    coverage_topics: list[str] = []
    chunk_summaries: list[dict[str, Any]] = []
    list_fields = ("decisions", "proposals", "agreements", "risks", "open_questions", "next_steps")
    collected: dict[str, list[Any]] = {field: [] for field in list_fields}
    owners: list[Any] = []
    deadlines: list[Any] = []
    tasks: list[dict[str, Any]] = []
    task_seen: set[str] = set()

    for idx, item in enumerate(items, start=1):
        topic = str(item.get("topic") or "").strip()
        summary = str(item.get("summary") or "").strip()
        current_state = str(item.get("current_state") or "").strip()
        target_state = str(item.get("target_state") or "").strip()
        if not _is_empty_marker(topic):
            topics.append(topic)
            coverage_topics.append(topic)
        if summary:
            summaries.append(f"Chunk {idx}: {summary}")
            coverage_topics.append(summary)
        if not _is_empty_marker(current_state):
            current_states.append(current_state)
            coverage_topics.append(f"Текущее состояние: {current_state}")
        if not _is_empty_marker(target_state):
            target_states.append(target_state)
            coverage_topics.append(f"Целевое состояние: {target_state}")
        chunk_summaries.append({"chunk_id": item.get("chunk_id") or idx, "topic": topic, "summary": summary})
        for field in list_fields:
            field_values = _as_list(item.get(field))
            collected[field].extend(field_values)
            coverage_topics.extend(field_values)
        owners.extend(_as_list(item.get("owners")))
        deadlines.extend(_as_list(item.get("deadlines")))
        for task in item.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            key = _task_key(task)
            if not key or key in task_seen:
                continue
            task_seen.add(key)
            tasks.append(task)
            coverage_topics.append(task.get("task") or "")
            coverage_topics.append(task.get("context") or "")

    merged["topic"] = "; ".join(_dedupe_strings(topics, limit=12)) or "не указано"
    merged["summary"] = "\n".join(_dedupe_strings(summaries)) or ""
    merged["current_state"] = "\n".join(_dedupe_strings(current_states, limit=12)) or "не указано"
    merged["target_state"] = "\n".join(_dedupe_strings(target_states, limit=12)) or "не указано"
    for field in list_fields:
        merged[field] = _dedupe_strings(collected[field])
    merged["tasks"] = tasks
    merged["owners"] = _dedupe_strings(owners) or ["не указано"]
    merged["deadlines"] = _dedupe_strings(deadlines) or ["не указано"]
    merged["coverage_topics"] = _dedupe_strings(coverage_topics, limit=80)
    merged["chunk_summaries"] = chunk_summaries
    merged["chunk_count"] = len(items)
    return merged


def _coverage_topics_from_structure(structured: Any) -> list[str]:
    if not isinstance(structured, dict):
        return []
    explicit = _dedupe_strings(_as_list(structured.get("coverage_topics")), limit=80)
    if explicit:
        return explicit
    topics: list[Any] = []
    topics.append(structured.get("current_state") or "")
    topics.append(structured.get("target_state") or "")
    for key in ("decisions", "proposals", "agreements", "risks", "open_questions", "next_steps"):
        topics.extend(_as_list(structured.get(key)))
    for task in structured.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        topics.append(task.get("task") or "")
        topics.append(task.get("context") or "")
    return _dedupe_strings(topics, limit=80)


def _derive_transcript_name(summary: str | None, structured: Any, cleaned: str | None) -> str:
    candidates: list[str] = []
    if isinstance(structured, dict):
        candidates.extend([str(structured.get("topic") or ""), str(structured.get("summary") or "")])
    candidates.append(str(summary or ""))
    candidates.append(str(cleaned or ""))
    for candidate in candidates:
        text = re.sub(r"^#+\s*", "", candidate.strip())
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"^[*-]\s*", "", text)
        if len(text) >= 8 and text.lower() not in {"не указано", "не зафиксировано"}:
            return text[:86].rstrip(" .,;:-") or "ASR transcript"
    return "ASR transcript"


def _sync_transcript_pipeline_fields(transcript_id: int, run: dict[str, Any]) -> None:
    structured = run.get("structured_json")
    summary = str(run.get("summary") or "").strip()
    if not summary and isinstance(structured, dict):
        summary = str(structured.get("summary") or "").strip()
    name = _derive_transcript_name(summary, structured, run.get("cleaned_transcript"))
    labels = dict((db.get_transcript(transcript_id) or {}).get("labels") or {})
    labels.update(
        {
            "latest_pipeline_run_id": run.get("id"),
            "latest_pipeline_action": run.get("action"),
            "latest_pipeline_preset": run.get("preset"),
            "has_summary": bool(summary),
            "has_structured_json": bool(structured),
        }
    )
    db.update_transcript(
        transcript_id,
        name=name,
        summary=summary,
        structured_json=structured,
        latest_pipeline_run_id=int(run["id"]),
        labels=labels,
    )


def _speaker_name(value: Any) -> str:
    raw = str(value or "").strip()
    if SPEAKER_RE.fullmatch(raw):
        return raw
    if raw.lower() in {"unknown", "unknown speaker", "неизвестно", "не указан"}:
        return "Unknown speaker"
    return "Unknown speaker"


def _manual_speaker_name(value: Any) -> str:
    raw = " ".join(str(value or "").strip().split())
    if not raw:
        return "Unknown speaker"
    return raw[:80]


def _sanitize_speaker_mapping(items: Any, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[int, dict[str, Any]] = {}
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                segment_id = int(item.get("segment_id"))
            except (TypeError, ValueError):
                continue
            confidence = item.get("confidence")
            try:
                confidence_float = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                confidence_float = 0.0
            speaker = _speaker_name(item.get("speaker"))
            by_id[segment_id] = {
                "segment_id": segment_id,
                "speaker": speaker,
                "confidence": confidence_float,
                "uncertain": speaker == "Unknown speaker" or confidence_float < 0.7,
                "text": str(item.get("text") or ""),
            }
    result: list[dict[str, Any]] = []
    for segment in segments:
        segment_id = int(segment.get("segment_id") or len(result) + 1)
        item = by_id.get(segment_id) or {}
        speaker = _speaker_name(item.get("speaker"))
        confidence = float(item.get("confidence") or 0.0)
        result.append(
            {
                "segment_id": segment_id,
                "speaker": speaker,
                "confidence": confidence,
                "uncertain": speaker == "Unknown speaker" or confidence < 0.7,
                "text": str(item.get("text") or segment.get("text") or ""),
            }
        )
    return result


def apply_speaker_overrides(
    speaker_mapping: list[dict[str, Any]],
    overrides: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(overrides, dict) or not overrides:
        return speaker_mapping
    result: list[dict[str, Any]] = []
    for item in speaker_mapping:
        segment_id = str(item.get("segment_id"))
        next_item = dict(item)
        if segment_id in overrides:
            next_item["speaker"] = _manual_speaker_name(overrides[segment_id])
            next_item["confidence"] = 1.0
            next_item["uncertain"] = False
            next_item["manual_override"] = True
        result.append(next_item)
    return result


def _call_stage(
    *,
    service: ChatService,
    stage: str,
    model: str,
    temperature: float,
    max_tokens: int,
    messages: list[dict[str, str]],
    timings: dict[str, Any],
    warnings: list[str],
    runtime_settings: dict[str, Any] | None = None,
) -> str:
    _raise_if_pipeline_stop_requested(stage)
    started = time.perf_counter()
    try:
        if not model_service.is_model_installed(model):
            raise HTTPException(
                status_code=424,
                detail={
                    "code": "pipeline_model_missing",
                    "model": model,
                    "stage": stage,
                    "message": f"Pipeline model {model} is not installed.",
                },
            )
        request_settings: dict[str, Any] = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "ollama_allow_cpu_fallback": False,
        }
        think = _pipeline_ollama_think(runtime_settings)
        if think is not None:
            request_settings["ollama_think"] = think
        try:
            residency_settings = model_residency.apply_target_settings(model, runtime_settings or {}, mode="manual")
            keep_alive = residency_settings.get("ollama_keep_alive_effective")
            if keep_alive is not None:
                request_settings["ollama_keep_alive_effective"] = keep_alive
        except Exception as exc:
            LOGGER.warning("Failed to apply pipeline model residency for %s/%s: %s", stage, model, exc)
            warnings.append(f"{stage}_residency_warning: {exc}")
        keep_alive = _pipeline_keep_alive(runtime_settings)
        if keep_alive is not None:
            request_settings["ollama_keep_alive_effective"] = keep_alive
        num_gpu = _pipeline_num_gpu(runtime_settings)
        if num_gpu is not None:
            request_settings["ollama_num_gpu"] = num_gpu
        with _ACTIVE_PIPELINE_MODELS_LOCK:
            _ACTIVE_PIPELINE_MODELS.add(model)
        try:
            result = service.chat_completion(model, messages, settings=request_settings)
        finally:
            with _ACTIVE_PIPELINE_MODELS_LOCK:
                _ACTIVE_PIPELINE_MODELS.discard(model)
        _raise_if_pipeline_stop_requested(stage)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        if _PIPELINE_STOP_EVENT.is_set():
            raise HTTPException(status_code=499, detail=_pipeline_stop_detail(stage)) from exc
        warnings.append(f"{stage}_failed: {exc}")
        raise HTTPException(status_code=502, detail={"code": f"{stage}_failed", "message": str(exc)}) from exc
    finally:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        existing = timings.get(stage)
        if isinstance(existing, dict):
            existing["elapsed_ms"] = int(existing.get("elapsed_ms") or 0) + elapsed_ms
            existing["calls"] = int(existing.get("calls") or 1) + 1
            if existing.get("model") != model:
                models = list(existing.get("models") or [existing.get("model")])
                if model not in models:
                    models.append(model)
                existing["models"] = [item for item in models if item]
                existing["model"] = ",".join(existing["models"])
        else:
            timings[stage] = {"elapsed_ms": elapsed_ms, "model": model}


def _log_pipeline_event(payload: dict[str, Any]) -> None:
    try:
        config.PIPELINE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with config.PIPELINE_LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("Failed to write pipeline log: %s", exc)


def _asr_diagnostics_enabled(settings: dict[str, Any] | None) -> bool:
    return bool((settings or {}).get("_asr_diagnostics_enabled"))


def _log_asr_diagnostic_event(settings: dict[str, Any], profile_id: int, payload: dict[str, Any]) -> None:
    if not _asr_diagnostics_enabled(settings):
        return
    try:
        path = config.ASR_DIAGNOSTICS_DIR / f"profile_{int(profile_id)}"
        path.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": int(time.time()),
            **payload,
        }
        with (path / "pipeline_runs.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("Failed to write ASR diagnostics log: %s", exc)


def _asr_analysis_context(settings: dict[str, Any]) -> str:
    return str((settings or {}).get("_asr_analysis_prompt") or "").strip()


def _normalize_asr_analysis_language(value: Any) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized in {"", "none"}:
        return "auto"
    return normalized if normalized in {"auto", "ru", "en"} else "auto"


def _language_from_transcript_metadata(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("ru"):
        return "ru"
    if normalized.startswith("en"):
        return "en"
    return None


def _detect_transcript_language(text: str) -> str | None:
    raw = str(text or "")
    cyrillic_count = len(CYRILLIC_RE.findall(raw))
    latin_count = len(LATIN_RE.findall(raw))
    if cyrillic_count >= 20 and cyrillic_count >= latin_count * 0.35:
        return "ru"
    if latin_count >= 20 and latin_count > cyrillic_count * 2:
        return "en"
    if cyrillic_count and not latin_count:
        return "ru"
    if latin_count and not cyrillic_count:
        return "en"
    return None


def _language_counts(text: str) -> tuple[int, int]:
    raw = str(text or "")
    return len(CYRILLIC_RE.findall(raw)), len(LATIN_RE.findall(raw))


def _resolve_asr_output_language(settings: dict[str, Any], transcript: dict[str, Any], raw_text: str) -> str:
    preferred = _normalize_asr_analysis_language(settings.get("_asr_analysis_language"))
    if preferred in {"ru", "en"}:
        return preferred
    return (
        _detect_transcript_language(raw_text)
        or _language_from_transcript_metadata(transcript.get("language"))
        or "ru"
    )


def _asr_output_language(settings: dict[str, Any]) -> str:
    language = _normalize_asr_analysis_language(settings.get("_asr_output_language")) if settings else "ru"
    return language if language in {"ru", "en"} else "ru"


def _language_name(language: str) -> str:
    return "English" if language == "en" else "Russian"


def _summary_guardrails(language: str) -> str:
    return ASR_SUMMARY_GUARDRAILS_EN if language == "en" else ASR_SUMMARY_GUARDRAILS_RU


def _summary_grounding_rules(language: str) -> str:
    if language == "en":
        return (
            "Use only EVIDENCE_JSON. Do not restate this task. Do not create examples. "
            "Do not invent sample speakers, greetings, places, plans, meetings, or dialogue. "
            "Do not write a generic overview of the dialogue, participant metadata, language metadata, or limitation disclaimer. "
            "Do not use Speaker 1, Speaker 2, Unknown speaker, or similar placeholder participants as factual identities. "
            "If evidence is insufficient, write that evidence is insufficient instead of fabricating content."
        )
    return (
        "Используй только EVIDENCE_JSON. Не пересказывай инструкцию. Не создавай примеры. "
        "Не придумывай учебных спикеров, приветствия, места, планы, встречи или диалог. "
        "Не пиши общий обзор диалога, метаданные участников, метаданные языка или дисклеймер об ограниченном контексте. "
        "Не используй Speaker 1, Speaker 2, Unknown speaker и похожие placeholder-участники как фактические личности. "
        "Если evidence недостаточно, напиши, что данных недостаточно, а не выдумывай содержание."
    )


def _json_language_instruction(language: str) -> str:
    if language == "en":
        return (
            "Output language: English. Keep JSON keys exactly as requested, but write all human-readable JSON values "
            "in English. Keep product names, domains, IDs, commands and quoted source terms unchanged."
        )
    return (
        "Output language: Russian. Keep JSON keys exactly as requested, but write all human-readable JSON values "
        "in Russian. Keep product names, domains, IDs, commands and quoted source terms unchanged."
    )


def _summary_format_instruction(language: str) -> str:
    if language == "en":
        return (
            "Create the summary strictly in this markdown format:\n"
            "## Brief Summary\n...\n## Key Decisions\n- ...\n## Tasks\n- ...\n"
            "## Proposals / Options\n- ...\n"
            "## Risks\n- ...\n## Questions to Clarify\n- ...\n## Next Steps\n- ...\n\n"
            "Put only confirmed decisions in 'Key Decisions'. If there were only options, leave decisions empty or write 'not recorded'. "
            "If structured contains decisions or agreements, do not say that decisions were not recorded. "
            "Cover all major topics from coverage_topics; do not limit the summary to the start of the transcript. "
            "If structured contains current_state/target_state, clearly separate current state from target state. "
            "If an important point is repeated in different words, reflect it as a significant topic/task/question. "
            "If a technical term looks like an ASR error or a concept mix-up, put it into Questions to Clarify. "
            "Do not assign owners unless explicitly confirmed. "
            "Start with '## Brief Summary'. Do not add a preamble, participants/language metadata, or limitation note."
        )
    return (
        "Сформируй summary строго в формате:\n"
        "## Краткое резюме\n...\n## Ключевые решения\n- ...\n## Задачи\n- ...\n"
        "## Предложения / варианты дальнейших действий\n- ...\n"
        "## Риски\n- ...\n## Вопросы для уточнения\n- ...\n## Следующие действия\n- ...\n\n"
        "В 'Ключевые решения' помещай только подтверждённые решения. "
        "Если были только варианты, оставь решения пустыми или напиши 'не зафиксировано'. "
        "Но если в structured есть decisions или agreements, не пиши, что решения не зафиксированы. "
        "Покрой все крупные темы из coverage_topics; не ограничивайся началом transcript. "
        "Если structured содержит current_state/target_state, явно отдели текущее состояние от целевого. "
        "Если важный пункт повторяется разными словами, отрази его как значимую тему/задачу/уточнение. "
        "Если технический термин выглядит как ошибка ASR или смешение понятий, вынеси его в вопросы для уточнения. "
        "Не назначай ответственных, если они не подтверждены явно. "
        "Начни с '## Краткое резюме'. Не добавляй вводную фразу, метаданные участников/языка или примечание об ограниченном контексте."
    )


def _structurer_task_instruction(language: str, chunk_id: int, chunk_count: int) -> str:
    if language == "en":
        return (
            f"Analyze transcript chunk {chunk_id}/{chunk_count} for task planning.\n"
            "Return exactly this JSON schema:\n"
            "{\n"
            '  "topic": "short topic",\n'
            '  "summary": "1-2 sentences with the point",\n'
            '  "current_state": "current state/how it works now, if discussed",\n'
            '  "target_state": "target state/where they want to get, if discussed",\n'
            '  "decisions": ["confirmed decisions only"],\n'
            '  "proposals": ["what was proposed or discussed as an option"],\n'
            '  "agreements": ["recorded agreements only"],\n'
            '  "tasks": [{"task":"what to do","context":"context/why this is a task from the conversation","responsible":"not specified|name/role if explicit","status":"open|proposed|agreed|blocked"}],\n'
            '  "risks": ["consequences of uncertainty, not questions"],\n'
            '  "open_questions": ["questions to clarify"],\n'
            '  "next_steps": ["next actions"],\n'
            '  "owners": ["owners, if explicitly stated"],\n'
            '  "deadlines": ["deadlines, if explicitly stated"]\n'
            "}\n"
            "Tasks must be actionable: short action plus separate context/reason. "
            "If there is a contrast between 'now' and 'target', do not mix them: fill current_state and target_state. "
            "Do not put proposals, hypotheses or items requiring confirmation into decisions. "
            "If an important point is repeated in different words, keep it as a significant topic/task/question rather than removing it as noise. "
            "If data is missing, write 'not specified', 'not recorded' or 'requires clarification'."
        )
    return (
        f"Разбери transcript chunk {chunk_id}/{chunk_count} для постановки задачи.\n"
        "Верни строго такую JSON-схему:\n"
        "{\n"
        '  "topic": "краткая тема",\n'
        '  "summary": "1-2 предложения о сути",\n'
        '  "current_state": "текущее состояние/как устроено сейчас, если обсуждалось",\n'
        '  "target_state": "целевое состояние/к чему хотят прийти, если обсуждалось",\n'
        '  "decisions": ["только подтверждённые решения"],\n'
        '  "proposals": ["то, что было предложено или обсуждалось как вариант"],\n'
        '  "agreements": ["только зафиксированные договорённости"],\n'
        '  "tasks": [{"task":"что сделать","context":"контекст/почему это задача из разговора","responsible":"не указано|имя/роль если явно указано","status":"open|proposed|agreed|blocked"}],\n'
        '  "risks": ["последствия неопределённости, не вопросы"],\n'
        '  "open_questions": ["вопросы, которые нужно уточнить"],\n'
        '  "next_steps": ["следующие действия"],\n'
        '  "owners": ["ответственные, если явно указаны"],\n'
        '  "deadlines": ["сроки, если явно указаны"]\n'
        "}\n"
        "Поле tasks должно быть пригодно для постановки задачи: короткое действие + отдельный контекст/основание. "
        "Если есть противопоставление 'сейчас' и 'цель', не смешивай их: заполни current_state и target_state. "
        "Не помещай в decisions то, что было только предложено, обсуждалось как гипотеза или требует подтверждения. "
        "Если важный пункт повторяется разными словами, сохрани его как значимую тему/задачу/уточнение, а не удаляй как шум. "
        "Если данных нет, пиши 'не указано', 'не зафиксировано' или 'требует уточнения'."
    )


def _resolve_settings(profile_id: int, model_name: str | None = None) -> dict[str, Any]:
    model = model_name or ASR_PIPELINE_SETTINGS_MODEL_ID
    settings_bundle = db.effective_settings(profile_id, model, config.DEFAULT_SETTINGS)
    settings = settings_bundle.get("effective") or {}
    overrides = settings_bundle.get("overrides") or {}
    if model == ASR_PIPELINE_SETTINGS_MODEL_ID and overrides.get("ollama_think") is None:
        settings["ollama_think"] = "off"
    profile = db.get_profile(profile_id) or {}
    asr_preferences = ((profile.get("preferences") or {}).get("asr") or {}) if isinstance(profile, dict) else {}
    settings["_settings_model"] = model
    settings["_fallback_model"] = model
    settings["_asr_analysis_prompt"] = str(asr_preferences.get("analysis_prompt") or "").strip()[:4000]
    settings["_asr_analysis_language"] = _normalize_asr_analysis_language(asr_preferences.get("analysis_language"))
    settings["_asr_diagnostics_enabled"] = bool(asr_preferences.get("diagnostics_enabled"))
    return settings


def run_transcript_pipeline(
    *,
    transcript_id: int,
    preset: str | None = None,
    action: str | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    reset_pipeline_stop_request()
    transcript = db.get_transcript(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="transcript_not_found")
    profile_id = int(transcript["profile_id"])
    settings = _resolve_settings(profile_id, model_name)
    if not settings.get("pipeline_enabled", True):
        raise HTTPException(status_code=409, detail={"code": "pipeline_disabled", "message": "Pipeline is disabled."})
    preset_value = _normalize_preset(preset, settings.get("default_pipeline_preset") or "balanced")
    action_value = _normalize_action(action)
    if action_value == "full" and not bool(settings.get("asr_full_analysis_enabled", False)):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "asr_full_analysis_disabled",
                "message": "Full ASR analysis is disabled for this profile.",
            },
        )
    pipeline_cfg = _json_clone(settings.get("pipeline") or config.DEFAULT_PIPELINE)
    raw = str(transcript.get("content") or "")
    output_language = _resolve_asr_output_language(settings, transcript, raw)
    settings["_asr_output_language"] = output_language
    max_chars = _transcript_chunk_chars(settings)
    raw_chunks = _split_text_chunks(raw, max_chars)
    warnings: list[str] = []
    if len(raw_chunks) > 1:
        _append_warning_once(warnings, f"raw_transcript_chunked:{len(raw_chunks)}")

    service = ChatService()
    timings: dict[str, Any] = {}
    debug: dict[str, Any] = {"stage_inputs": {}} if PIPELINE_PRESETS[preset_value].get("debug_artifacts") else {}
    if debug:
        debug["chunking"] = {
            "raw_chars": len(raw),
            "chunk_chars": max_chars,
            "chunks": len(raw_chunks),
            "mode": "chunked_merge" if len(raw_chunks) > 1 else "single_pass",
        }

    stage_enabled = {
        stage: _stage_enabled(stage, action_value, preset_value, pipeline_cfg)
        for stage in ("cleaner", "segmenter", "speaker_resolver", "structurer", "summary")
    }
    if action_value in SUMMARY_ACTIONS and not stage_enabled["summary"]:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "asr_summary_stage_disabled",
                "message": "Summary stage is disabled in ASR pipeline settings.",
            },
        )
    if action_value == "smart_summary" and not stage_enabled["structurer"]:
        _append_warning_once(warnings, "smart_summary_structurer_disabled_fallback_summary")
    if len(raw_chunks) > 1 and stage_enabled["summary"] and action_value == "full":
        forced = False
        for stage in ("segmenter", "structurer"):
            stage_cfg = pipeline_cfg.get(stage) or {}
            if bool(stage_cfg.get("enabled", True)) and not stage_enabled[stage]:
                stage_enabled[stage] = True
                forced = True
        if forced:
            _append_warning_once(warnings, "long_transcript_forced_merge_stages")

    cleaned_chunks: list[str] = []
    cleaned = raw
    segments: list[dict[str, Any]] = []
    speaker_mapping: list[dict[str, Any]] = []
    structured_chunks: list[dict[str, Any]] = []
    structured: dict[str, Any] | list[Any] | None = None
    summary: str | None = None
    analysis_context = _asr_analysis_context(settings)
    analysis_context_block = (
        profile_configuration_envelope(
            "asr_analysis_prompt",
            analysis_context,
            allowed_influence="analysis_focus_and_output_format",
        )
        + "\n\n"
        if analysis_context
        else ""
    )

    if stage_enabled["cleaner"]:
        stage_cfg = _stage_settings(settings, "cleaner")
        for chunk_id, raw_chunk in enumerate(raw_chunks, start=1):
            prompt = [
                {"role": "system", "content": "Clean ASR text without changing meaning. Do not add facts."},
                {"role": "system", "content": GLOBAL_GUARD_POLICY},
                {
                    "role": "user",
                    "content": (
                        "Убери явный ASR-мусор, повторы и слова-паразиты. Не меняй смысл и не добавляй факты.\n\n"
                        + data_envelope(
                            "asr_transcript_chunk",
                            raw_chunk,
                            provenance={"chunk_id": chunk_id, "derived": False},
                        )
                    ),
                },
            ]
            _debug_stage_input(debug, "cleaner", prompt, chunk_id if len(raw_chunks) > 1 else None)
            cleaned_chunk = _call_stage(
                service=service,
                stage="cleaner",
                model=stage_cfg["model"],
                temperature=float(stage_cfg["temperature"]),
                max_tokens=int(stage_cfg["max_tokens"]),
                messages=prompt,
                timings=timings,
                warnings=warnings,
                runtime_settings=settings,
            ).strip() or _clean_text_fallback(raw_chunk)
            cleaned_chunks.append(cleaned_chunk)
    else:
        cleaned_chunks = [str(item or "").strip() for item in raw_chunks]
    cleaned = "\n\n".join(item for item in cleaned_chunks if item).strip()

    if stage_enabled["segmenter"]:
        stage_cfg = _stage_settings(settings, "segmenter")
        for chunk_id, cleaned_chunk in enumerate(cleaned_chunks, start=1):
            prompt = [
                {"role": "system", "content": "Return only JSON array. Do not assign speakers."},
                {"role": "system", "content": GLOBAL_GUARD_POLICY},
                {
                    "role": "user",
                    "content": (
                        "Разбей transcript на логические реплики или смысловые блоки. "
                        "Верни JSON array: [{\"segment_id\":1,\"text\":\"...\"}].\n\n"
                        + data_envelope(
                            "asr_cleaned_chunk",
                            cleaned_chunk,
                            provenance={"chunk_id": chunk_id, "derived": True},
                        )
                    ),
                },
            ]
            _debug_stage_input(debug, "segmenter", prompt, chunk_id if len(raw_chunks) > 1 else None)
            response = _call_stage(
                service=service,
                stage="segmenter",
                model=stage_cfg["model"],
                temperature=float(stage_cfg["temperature"]),
                max_tokens=int(stage_cfg["max_tokens"]),
                messages=prompt,
                timings=timings,
                warnings=warnings,
                runtime_settings=settings,
            )
            parsed = _extract_json(response, [])
            local_segments = [
                {"segment_id": idx + 1, "text": str(item.get("text") or "").strip()}
                for idx, item in enumerate(parsed if isinstance(parsed, list) else [])
                if isinstance(item, dict) and str(item.get("text") or "").strip()
            ]
            if not local_segments:
                local_segments = _segment_fallback(cleaned_chunk)
            segments.extend(_reindex_segments(local_segments, chunk_id=chunk_id, next_segment_id=len(segments) + 1))
    if not segments:
        for chunk_id, cleaned_chunk in enumerate(cleaned_chunks, start=1):
            segments.extend(
                _reindex_segments(
                    _segment_fallback(cleaned_chunk),
                    chunk_id=chunk_id,
                    next_segment_id=len(segments) + 1,
                )
            )

    if stage_enabled["speaker_resolver"]:
        stage_cfg = _stage_settings(settings, "speaker_resolver")
        for chunk_id in range(1, len(cleaned_chunks) + 1):
            chunk_segments = [item for item in segments if int(item.get("chunk_id") or 0) == chunk_id]
            if not chunk_segments:
                continue
            prompt = [
                {
                    "role": "system",
                    "content": (
                        "Return only JSON array. Never use real names. Use Speaker_1, Speaker_2 or Unknown speaker. "
                        "Include confidence from 0 to 1."
                    ),
                },
                {"role": "system", "content": GLOBAL_GUARD_POLICY},
                {
                    "role": "user",
                    "content": (
                        "Попробуй сгруппировать сегменты по говорящим, но не придумывай личности. "
                        "Если уверенности нет, ставь Unknown speaker.\n\n"
                        + data_envelope(
                            "asr_segments",
                            json.dumps(chunk_segments, ensure_ascii=False),
                            provenance={"chunk_id": chunk_id, "derived": True},
                        )
                    ),
                },
            ]
            _debug_stage_input(debug, "speaker_resolver", prompt, chunk_id if len(raw_chunks) > 1 else None)
            response = _call_stage(
                service=service,
                stage="speaker_resolver",
                model=stage_cfg["model"],
                temperature=float(stage_cfg["temperature"]),
                max_tokens=int(stage_cfg["max_tokens"]),
                messages=prompt,
                timings=timings,
                warnings=warnings,
                runtime_settings=settings,
            )
            speaker_mapping.extend(
                _attach_chunk_to_mapping(
                    _sanitize_speaker_mapping(_extract_json(response, []), chunk_segments),
                    chunk_segments,
                )
            )
    else:
        speaker_mapping = _attach_chunk_to_mapping(_sanitize_speaker_mapping([], segments), segments)

    if stage_enabled["structurer"]:
        stage_cfg = _stage_settings(settings, "structurer")
        for chunk_id in range(1, len(cleaned_chunks) + 1):
            chunk_mapping = [item for item in speaker_mapping if int(item.get("chunk_id") or 0) == chunk_id]
            if not chunk_mapping:
                chunk_segments = [item for item in segments if int(item.get("chunk_id") or 0) == chunk_id]
                chunk_mapping = _attach_chunk_to_mapping(_sanitize_speaker_mapping([], chunk_segments), chunk_segments)
            prompt = [
                {
                    "role": "system",
                    "content": (
                        "Return only one valid JSON object. Do not add facts. "
                        f"{_json_language_instruction(output_language)} "
                        "Separate confirmed decisions, proposals, agreements, tasks, risks, open questions, and next steps. "
                        "If the discussion compares current and target architecture/process/state, extract both explicitly. "
                        "If the same topic, constraint or action is repeated in different words, treat the repetition as an importance signal. "
                        f"{_summary_guardrails(output_language)}"
                    ),
                },
                {"role": "system", "content": GLOBAL_GUARD_POLICY},
                {
                    "role": "user",
                    "content": (
                        f"{_structurer_task_instruction(output_language, chunk_id, len(cleaned_chunks))}\n"
                        f"Do not switch away from {_language_name(output_language)} for human-readable values.\n\n"
                        f"{analysis_context_block}"
                        + data_envelope(
                            "asr_speaker_mapping",
                            json.dumps(chunk_mapping, ensure_ascii=False),
                            provenance={"chunk_id": chunk_id, "derived": True},
                            allowed_influence="transcript_evidence_only",
                        )
                    ),
                },
            ]
            _debug_stage_input(debug, "structurer", prompt, chunk_id if len(raw_chunks) > 1 else None)
            response = _call_stage(
                service=service,
                stage="structurer",
                model=stage_cfg["model"],
                temperature=float(stage_cfg["temperature"]),
                max_tokens=int(stage_cfg["max_tokens"]),
                messages=prompt,
                timings=timings,
                warnings=warnings,
                runtime_settings=settings,
            )
            parsed = _extract_json(response, _empty_structure())
            chunk_structured = _normalize_structured_output(parsed, warnings)
            chunk_structured["chunk_id"] = chunk_id
            structured_chunks.append(chunk_structured)
        structured = _merge_structured_outputs(structured_chunks)
    elif action_value in {"tasks", "smart_summary", "full"} or (len(raw_chunks) > 1 and stage_enabled["summary"]):
        structured = _empty_structure()

    if stage_enabled["summary"]:
        try:
            summary = generate_summary(
                cleaned_transcript=cleaned,
                speaker_mapping=speaker_mapping,
                structured_json=structured,
                settings=settings,
                timings=timings,
                warnings=warnings,
                debug=debug,
                service=service,
                chunk_count=len(raw_chunks),
            )
        except HTTPException as exc:
            _log_asr_diagnostic_event(
                settings,
                profile_id,
                {
                    "event": "summary_failed",
                    "transcript_id": transcript.get("id"),
                    "action": action_value,
                    "preset": preset_value,
                    "detail": exc.detail,
                    "warnings": warnings,
                    "stage_timings": timings,
                    "chunks": len(raw_chunks),
                    "structured_available": bool(structured),
                },
            )
            raise

    run = db.create_pipeline_run(
        transcript_id=int(transcript["id"]),
        profile_id=profile_id,
        session_id=transcript.get("session_id"),
        preset=preset_value,
        action=action_value,
        raw_transcript=raw,
        cleaned_transcript=cleaned,
        segments=segments,
        speaker_mapping=speaker_mapping,
        speaker_overrides={},
        structured_json=structured,
        summary=summary,
        stage_timings=timings,
        warnings=warnings,
        used_settings=settings,
        debug=debug,
    )
    _sync_transcript_pipeline_fields(int(transcript["id"]), run)

    if summary and (PIPELINE_PRESETS[preset_value].get("memory_save") or action_value in {"summary", "smart_summary"}):
        db.create_session_summary(
            profile_id=profile_id,
            session_id=transcript.get("session_id"),
            source_type="asr",
            source_id=str(transcript["id"]),
            summary=summary,
            structured_json=structured,
        )

    _log_pipeline_event(
        {
            "run_id": run.get("id"),
            "session_id": transcript.get("session_id"),
            "profile_id": profile_id,
            "model": model_name or config.SETTINGS.model,
            "stage": "pipeline",
            "elapsed_ms": sum(int(item.get("elapsed_ms") or 0) for item in timings.values()),
            "input_size": len(raw),
            "output_size": len(summary or cleaned or ""),
            "truncated": "raw_transcript_truncated" in warnings,
            "chunks": len(raw_chunks),
            "used_settings": settings,
        }
    )
    _log_asr_diagnostic_event(
        settings,
        profile_id,
        {
            "event": "pipeline_completed",
            "run_id": run.get("id"),
            "transcript_id": transcript.get("id"),
            "action": action_value,
            "preset": preset_value,
            "warnings": warnings,
            "stage_timings": timings,
            "chunks": len(raw_chunks),
            "used_settings_model": settings.get("_settings_model"),
        },
    )
    return run


def _segment_digest_for_summary(speaker_mapping: list[dict[str, Any]], max_chars: int = SUMMARY_SEGMENT_DIGEST_CHARS) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    sizes: list[int] = []
    for item in speaker_mapping:
        text = _short_text(item.get("text") or "", 260)
        if not text:
            continue
        entry = {
            "segment_id": item.get("segment_id"),
            "chunk_id": item.get("chunk_id"),
            "speaker": item.get("speaker") or "Unknown speaker",
            "text": text,
        }
        entries.append(entry)
        sizes.append(len(json.dumps(entry, ensure_ascii=False)))

    if not entries:
        return []
    if sum(sizes) <= max_chars:
        return entries

    gap_template = {"omitted_segments": 0, "note": "middle_segments_omitted_from_digest"}
    gap_size = len(json.dumps(gap_template, ensure_ascii=False))
    head_budget = max(0, (max_chars - gap_size) // 2)
    tail_budget = max(0, max_chars - gap_size - head_budget)

    head_indices: list[int] = []
    used_head = 0
    left = 0
    while left < len(entries) and used_head + sizes[left] <= head_budget:
        head_indices.append(left)
        used_head += sizes[left]
        left += 1
    if not head_indices:
        head_indices.append(0)
        used_head = sizes[0]
        left = 1

    tail_indices: list[int] = []
    used_tail = 0
    right = len(entries) - 1
    remaining_budget = max(0, max_chars - used_head - gap_size)
    tail_budget = min(tail_budget, remaining_budget)
    while right >= left and used_tail + sizes[right] <= tail_budget:
        tail_indices.append(right)
        used_tail += sizes[right]
        right -= 1
    if not tail_indices and len(entries) > 1 and sizes[-1] <= remaining_budget:
        tail_indices.append(len(entries) - 1)
        right = len(entries) - 2

    tail_indices.reverse()
    omitted = max(0, (tail_indices[0] if tail_indices else len(entries)) - left)
    digest = [entries[index] for index in head_indices]
    if omitted:
        digest.append({"omitted_segments": omitted, "note": "middle_segments_omitted_from_digest"})
    digest.extend(entries[index] for index in tail_indices)
    return digest


def _summary_input_payload(
    *,
    cleaned_transcript: str,
    speaker_mapping: list[dict[str, Any]],
    structured_json: dict[str, Any] | list[Any] | None,
    settings: dict[str, Any],
    chunk_count: int,
) -> dict[str, Any]:
    try:
        inline_limit = int(settings.get("max_transcript_chars") or SUMMARY_INLINE_TRANSCRIPT_CHARS)
    except (TypeError, ValueError):
        inline_limit = SUMMARY_INLINE_TRANSCRIPT_CHARS
    inline_limit = max(MIN_TRANSCRIPT_CHUNK_CHARS, inline_limit)

    if chunk_count <= 1 and len(cleaned_transcript) <= inline_limit:
        return {
            "source_mode": "single_pass",
            "cleaned_transcript": cleaned_transcript,
            "speaker_mapping": speaker_mapping,
            "structured": structured_json,
        }

    coverage_topics = _coverage_topics_from_structure(structured_json)
    return {
        "source_mode": "chunked_merge",
        "transcript_fully_processed": True,
        "chunk_count": chunk_count,
        "cleaned_transcript_chars": len(cleaned_transcript),
        "segment_count": len(speaker_mapping),
        "coverage_topics": coverage_topics,
        "structured": structured_json,
        "segment_digest": _segment_digest_for_summary(speaker_mapping),
    }


def _significant_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for token in TOKEN_RE.findall(str(text or "").lower()):
        if token in TOPIC_STOPWORDS or len(token) < 3:
            continue
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _token_grounding_keys(token: str) -> set[str]:
    raw = str(token or "").lower()
    keys = {raw}
    if len(raw) >= 5:
        keys.add(raw[:5])
    return {item for item in keys if item}


def _topic_is_covered(topic: str, summary: str) -> bool:
    tokens = _significant_tokens(topic)
    if not tokens:
        return True
    haystack = str(summary or "").lower()
    normalized_topic = re.sub(r"\s+", " ", str(topic or "").strip().lower())
    if normalized_topic and normalized_topic in re.sub(r"\s+", " ", haystack):
        return True
    hits = sum(1 for token in tokens if token in haystack)
    if len(tokens) == 1:
        return hits == 1
    if len(tokens) == 2:
        return hits == 2
    required = max(3, int(len(tokens) * 0.65 + 0.999))
    return hits >= min(len(tokens), required)


def _summary_has_required_heading(summary: str, output_language: str) -> bool:
    heading = "Brief Summary" if output_language == "en" else "Краткое резюме"
    return bool(re.search(rf"(?im)^\s*##\s*{re.escape(heading)}\s*$", str(summary or "")))


def _ensure_required_summary_heading(summary: str, output_language: str, warnings: list[str]) -> str:
    text = str(summary or "").strip()
    if not text or _summary_has_required_heading(text, output_language):
        return text
    heading = "Brief Summary" if output_language == "en" else "Краткое резюме"
    _append_warning_once(warnings, "summary_required_heading_added")
    return f"## {heading}\n{text}"


def _summary_grounding_reasons(
    summary: str,
    *,
    evidence_text: str,
    output_language: str,
) -> list[str]:
    text = str(summary or "").strip()
    if not text:
        return ["empty_summary"]

    lowered = text.lower()
    reasons: list[str] = []
    for pattern in SUMMARY_INVALID_PATTERNS:
        if pattern.search(text):
            reasons.append("instruction_or_example_output")
            break

    if not _summary_has_required_heading(text, output_language):
        reasons.append("summary_missing_required_heading")

    for pattern in SUMMARY_OVERVIEW_ARTIFACT_PATTERNS:
        if pattern.search(text):
            reasons.append("generic_dialogue_overview_output")
            break

    cyrillic_count, latin_count = _language_counts(text)
    if output_language == "ru" and len(text) >= 120:
        if cyrillic_count < 20 or cyrillic_count < max(10, int(latin_count * 0.18)):
            reasons.append("summary_language_mismatch")
    elif output_language == "en" and len(text) >= 120:
        if cyrillic_count > 40 and cyrillic_count > latin_count * 0.6:
            reasons.append("summary_language_mismatch")

    evidence_language = _detect_transcript_language(evidence_text)
    if evidence_language == output_language:
        evidence_tokens = _significant_tokens(evidence_text)
        summary_tokens: set[str] = set()
        for token in _significant_tokens(text):
            summary_tokens.update(_token_grounding_keys(token))
        if len(evidence_tokens) >= 8 and len(summary_tokens) >= 4:
            evidence_sample = evidence_tokens[:80]
            hits = sum(1 for token in evidence_sample if _token_grounding_keys(token) & summary_tokens)
            required_hits = 2 if len(evidence_sample) < 20 else 3
            if hits < required_hits and "insufficient" not in lowered and "недостаточно" not in lowered:
                reasons.append("summary_not_grounded_in_evidence")

    return _dedupe_strings(reasons)


def _structured_decision_items(structured: Any) -> list[str]:
    if not isinstance(structured, dict):
        return []
    items = [*_as_list(structured.get("decisions")), *_as_list(structured.get("agreements"))]
    return _dedupe_strings(items, limit=12)


def _repair_empty_decisions_section(summary: str, structured: Any, warnings: list[str]) -> str:
    decision_items = _structured_decision_items(structured)
    if not decision_items:
        return summary
    match = re.search(r"(##\s*Ключевые решения\s*\n)(.*?)(?=\n##\s|\Z)", summary, flags=re.IGNORECASE | re.DOTALL)
    replacement = "\n".join(f"- {item}" for item in decision_items).strip() + "\n"
    if not match:
        _append_warning_once(warnings, "summary_decisions_section_repaired")
        return summary.rstrip() + "\n\n## Ключевые решения\n" + replacement
    body = match.group(2).strip()
    if not NO_DECISIONS_RE.search(body):
        return summary
    _append_warning_once(warnings, "summary_decisions_section_repaired")
    return summary[: match.start(2)] + replacement + summary[match.end(2) :]


def _append_to_markdown_section(summary: str, heading: str, items: list[str]) -> str:
    if not items:
        return summary
    section_re = re.compile(rf"(##\s*{re.escape(heading)}\s*\n)(.*?)(?=\n##\s|\Z)", re.IGNORECASE | re.DOTALL)
    bullets = "\n".join(f"- {item}" for item in items)
    match = section_re.search(summary)
    if not match:
        return summary.rstrip() + f"\n\n## {heading}\n{bullets}"
    body = match.group(2).strip()
    if NO_DECISIONS_RE.fullmatch(body.lower()) or body.lower() in {"- не зафиксировано", "не зафиксировано"}:
        replacement = bullets + "\n"
    else:
        replacement = body.rstrip() + "\n" + bullets + "\n"
    return summary[: match.start(2)] + replacement + summary[match.end(2) :]


def _demote_unconfirmed_decisions_section(summary: str, warnings: list[str]) -> str:
    match = re.search(r"(##\s*Ключевые решения\s*\n)(.*?)(?=\n##\s|\Z)", summary, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return summary
    body = match.group(2)
    keep_lines: list[str] = []
    demoted: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        item = re.sub(r"^[-*]\s*", "", line).strip()
        if not item or _is_empty_marker(item):
            keep_lines.append(raw_line)
            continue
        if _looks_unconfirmed_or_proposed(item):
            demoted.append(item)
        else:
            keep_lines.append(raw_line)
    if not demoted:
        return summary
    _append_warning_once(warnings, f"summary_decisions_demoted:{len(demoted)}")
    clean_keep = [line for line in keep_lines if line.strip() and not NO_DECISIONS_RE.search(line)]
    replacement = ("\n".join(clean_keep).strip() or "- не зафиксировано") + "\n"
    next_summary = summary[: match.start(2)] + replacement + summary[match.end(2) :]
    return _append_to_markdown_section(next_summary, "Предложения / варианты дальнейших действий", demoted)


def _missing_coverage_topics(summary: str, structured: Any, *, chunk_count: int) -> list[str]:
    if chunk_count <= 1:
        return []
    topics = _coverage_topics_from_structure(structured)
    missing: list[str] = []
    for topic in topics:
        if not _topic_is_covered(topic, summary):
            missing.append(topic)
        if len(missing) >= 12:
            break
    return missing


def _normalize_summary_markdown(summary: str, structured: Any, warnings: list[str]) -> str:
    context = _context_text(structured, summary)
    return "\n".join(_normalize_pipeline_text(line, context, warnings) for line in str(summary or "").splitlines()).strip()


def _append_incomplete_summary_section(summary: str, missing_topics: list[str]) -> str:
    if not missing_topics or INCOMPLETE_SUMMARY_HEADING in summary:
        return summary
    bullets = "\n".join(f"- {topic}" for topic in missing_topics[:8])
    return summary.rstrip() + f"\n\n{INCOMPLETE_SUMMARY_HEADING}\n" + bullets


def _summary_labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "brief": "Brief Summary",
            "decisions": "Key Decisions",
            "tasks": "Tasks",
            "proposals": "Proposals / Options",
            "risks": "Risks",
            "questions": "Questions to Clarify",
            "next_steps": "Next Steps",
            "current": "Current state",
            "target": "Target state",
            "topic": "Topic",
            "context": "Context",
            "responsible": "Responsible",
            "status": "Status",
            "empty": "not recorded",
            "fallback_note": "The LLM summary failed validation, so this safe version was assembled from structured evidence.",
        }
    return {
        "brief": "Краткое резюме",
        "decisions": "Ключевые решения",
        "tasks": "Задачи",
        "proposals": "Предложения / варианты дальнейших действий",
        "risks": "Риски",
        "questions": "Вопросы для уточнения",
        "next_steps": "Следующие действия",
        "current": "Текущее состояние",
        "target": "Целевое состояние",
        "topic": "Тема",
        "context": "Контекст",
        "responsible": "Ответственный",
        "status": "Статус",
        "empty": "не зафиксировано",
        "fallback_note": "LLM-summary не прошло проверку, поэтому эта безопасная версия собрана из структурированных данных анализа.",
    }


def _structured_summary_text(value: Any) -> list[str]:
    lines: list[str] = []
    for item in _as_list(value):
        text = _normalize_pipeline_text(item)
        text = re.sub(r"(?im)^chunk\s+\d+\s*:\s*", "", text).strip()
        if not _is_empty_marker(text):
            lines.append(text)
    return _dedupe_strings(lines, limit=8)


def _structured_bullets(value: Any, *, limit: int = 10) -> list[str]:
    items: list[str] = []
    for item in _as_list(value):
        if isinstance(item, dict):
            text = _normalize_pipeline_text(item.get("task") or item.get("title") or item.get("name") or item.get("text") or item.get("value"))
        else:
            text = _normalize_pipeline_text(item)
        if not _is_empty_marker(text):
            items.append(text)
    return _dedupe_strings(items, limit=limit)


def _structured_task_bullets(value: Any, labels: dict[str, str], *, limit: int = 10) -> list[str]:
    items: list[str] = []
    for item in _as_list(value):
        if isinstance(item, dict):
            task = _normalize_pipeline_text(item.get("task") or item.get("title") or item.get("name") or item.get("text") or "")
            if _is_empty_marker(task):
                continue
            details: list[str] = []
            context = _normalize_pipeline_text(item.get("context") or item.get("details") or item.get("description") or item.get("evidence") or "")
            if not _is_empty_marker(context):
                details.append(f"{labels['context']}: {context}")
            responsible = _normalize_responsible(item.get("responsible") or item.get("owner") or "")
            if not _is_empty_marker(responsible):
                details.append(f"{labels['responsible']}: {responsible}")
            status = _normalize_pipeline_text(item.get("status") or "")
            if not _is_empty_marker(status):
                details.append(f"{labels['status']}: {status}")
            items.append(task if not details else f"{task} ({'; '.join(details)})")
        else:
            text = _normalize_pipeline_text(item)
            if not _is_empty_marker(text):
                items.append(text)
    return _dedupe_strings(items, limit=limit)


def _markdown_section(title: str, items: list[str], *, empty: str) -> str:
    bullets = items or [empty]
    return f"## {title}\n" + "\n".join(f"- {item}" for item in bullets)


def _safe_summary_from_structured(structured: Any, output_language: str) -> str | None:
    if not isinstance(structured, dict):
        return None
    labels = _summary_labels(output_language)
    topic = _normalize_pipeline_text(structured.get("topic") or "")
    brief_lines = _structured_summary_text(structured.get("summary"))
    if not _is_empty_marker(topic):
        brief_lines.insert(0, f"{labels['topic']}: {topic}")
    current_state = _normalize_pipeline_text(structured.get("current_state") or "")
    target_state = _normalize_pipeline_text(structured.get("target_state") or "")
    if not _is_empty_marker(current_state):
        brief_lines.append(f"{labels['current']}: {current_state}")
    if not _is_empty_marker(target_state):
        brief_lines.append(f"{labels['target']}: {target_state}")

    sections = {
        "decisions": _structured_bullets([*_as_list(structured.get("decisions")), *_as_list(structured.get("agreements"))]),
        "tasks": _structured_task_bullets(structured.get("tasks"), labels),
        "proposals": _structured_bullets(structured.get("proposals")),
        "risks": _structured_bullets(structured.get("risks")),
        "questions": _structured_bullets(structured.get("open_questions")),
        "next_steps": _structured_bullets(structured.get("next_steps")),
    }
    has_content = bool(brief_lines) or any(sections.values())
    if not has_content:
        return None

    parts = [
        f"## {labels['brief']}",
        *[f"- {line}" for line in _dedupe_strings(brief_lines, limit=10)],
        "",
        _markdown_section(labels["decisions"], sections["decisions"], empty=labels["empty"]),
        "",
        _markdown_section(labels["tasks"], sections["tasks"], empty=labels["empty"]),
        "",
        _markdown_section(labels["proposals"], sections["proposals"], empty=labels["empty"]),
        "",
        _markdown_section(labels["risks"], sections["risks"], empty=labels["empty"]),
        "",
        _markdown_section(labels["questions"], sections["questions"], empty=labels["empty"]),
        "",
        _markdown_section(labels["next_steps"], sections["next_steps"], empty=labels["empty"]),
        "",
        f"Note: {labels['fallback_note']}" if output_language == "en" else f"Примечание: {labels['fallback_note']}",
    ]
    return "\n".join(parts).strip()


def _qa_summary_output(
    summary: str,
    *,
    structured_json: dict[str, Any] | list[Any] | None,
    chunk_count: int,
    output_language: str,
    warnings: list[str],
    debug: dict[str, Any] | None,
) -> tuple[str, list[str]]:
    checked = _repair_empty_decisions_section(summary, structured_json, warnings)
    checked = _normalize_summary_markdown(checked, structured_json, warnings)
    checked = _demote_unconfirmed_decisions_section(checked, warnings)
    checked = _ensure_required_summary_heading(checked, output_language, warnings)
    missing_topics = _missing_coverage_topics(checked, structured_json, chunk_count=chunk_count)
    if debug:
        debug["summary_coverage"] = {
            "chunk_count": chunk_count,
            "missing_topics": missing_topics,
            "decision_repaired": "summary_decisions_section_repaired" in warnings,
        }
    return checked, missing_topics


def generate_summary(
    *,
    cleaned_transcript: str,
    speaker_mapping: list[dict[str, Any]],
    structured_json: dict[str, Any] | list[Any] | None,
    settings: dict[str, Any],
    timings: dict[str, Any],
    warnings: list[str],
    debug: dict[str, Any] | None,
    service: ChatService | None = None,
    chunk_count: int = 1,
) -> str:
    stage_cfg = _stage_settings(settings, "summary")
    if isinstance(structured_json, dict):
        try:
            chunk_count = max(chunk_count, int(structured_json.get("chunk_count") or 1))
        except (TypeError, ValueError):
            pass
    summary_input = _summary_input_payload(
        cleaned_transcript=cleaned_transcript,
        speaker_mapping=speaker_mapping,
        structured_json=structured_json,
        settings=settings,
        chunk_count=chunk_count,
    )
    analysis_context = _asr_analysis_context(settings)
    analysis_context_block = (
        profile_configuration_envelope(
            "asr_analysis_prompt",
            analysis_context,
            allowed_influence="analysis_focus_and_output_format",
        )
        + "\n\n"
        if analysis_context
        else ""
    )
    output_language = _asr_output_language(settings)
    summary_input["output_language"] = output_language
    prompt = [
        {
            "role": "system",
            "content": (
                f"Generate concise transcript summary in {_language_name(output_language)}. Do not add facts. "
                f"{_json_language_instruction(output_language)} "
                "If speaker attribution is uncertain, do not base conclusions on it. "
                "Do not label proposals as decisions. If source_mode is chunked_merge, treat structured and "
                "coverage_topics as merged evidence from the full transcript, including the end of the meeting. "
                "When evidence has current_state and target_state, describe both and do not collapse one into the other. "
                "If the same topic, constraint or action is repeated in different words, treat the repetition as an importance signal. "
                "Return only the requested markdown summary, with no preamble. "
                f"{_summary_grounding_rules(output_language)} "
                f"{_summary_guardrails(output_language)}"
            ),
        },
        {"role": "system", "content": GLOBAL_GUARD_POLICY},
        {
            "role": "user",
            "content": (
                f"{_summary_format_instruction(output_language)}\n\n"
                f"{analysis_context_block}"
                + data_envelope(
                    "asr_summary_evidence",
                    json.dumps(summary_input, ensure_ascii=False),
                    provenance={"derived": True, "chunk_count": chunk_count},
                    allowed_influence="transcript_evidence_only",
                )
            ),
        },
    ]
    if debug:
        debug.setdefault("stage_inputs", {})["summary"] = prompt
    runner = service or ChatService()
    summary = _call_stage(
        service=runner,
        stage="summary",
        model=stage_cfg["model"],
        temperature=float(stage_cfg["temperature"]),
        max_tokens=int(stage_cfg["max_tokens"]),
        messages=prompt,
        timings=timings,
        warnings=warnings,
        runtime_settings=settings,
    ).strip()
    checked_summary, missing_topics = _qa_summary_output(
        summary,
        structured_json=structured_json,
        chunk_count=chunk_count,
        output_language=output_language,
        warnings=warnings,
        debug=debug,
    )
    evidence_text = json.dumps(summary_input, ensure_ascii=False)
    grounding_reasons = _summary_grounding_reasons(
        checked_summary,
        evidence_text=evidence_text,
        output_language=output_language,
    )
    if grounding_reasons:
        _append_warning_once(warnings, f"summary_grounding_validation_failed:{','.join(grounding_reasons)}")
        structured_fallback = _safe_summary_from_structured(structured_json, output_language)
        if structured_fallback:
            _append_warning_once(warnings, f"summary_safe_structured_fallback_used:{','.join(grounding_reasons)}")
            checked_summary, missing_topics = _qa_summary_output(
                structured_fallback,
                structured_json=structured_json,
                chunk_count=chunk_count,
                output_language=output_language,
                warnings=warnings,
                debug=debug,
            )
            if missing_topics:
                _append_warning_once(warnings, f"summary_safe_structured_fallback_missing_topics:{len(missing_topics)}")
                return _append_incomplete_summary_section(checked_summary, missing_topics)
            return checked_summary
        grounding_prompt = [
            {
                "role": "system",
                "content": (
                    f"Repair the transcript summary in {_language_name(output_language)}. Do not add facts. "
                    f"{_json_language_instruction(output_language)} "
                    f"{_summary_grounding_rules(output_language)} "
                    "The previous output failed validation because it looked ungrounded, was in the wrong language, "
                    "missed the required markdown structure, included placeholder speaker artifacts, generic dialogue overview, "
                    "or resembled an instruction/example conversation. Return only the corrected markdown summary. "
                    f"{_summary_guardrails(output_language)}"
                ),
            },
            {"role": "system", "content": GLOBAL_GUARD_POLICY},
            {
                "role": "user",
                "content": (
                    f"{_summary_format_instruction(output_language)}\n\n"
                    f"{analysis_context_block}"
                    + data_envelope(
                        "asr_summary_repair_evidence",
                        json.dumps(
                            {
                                "validation_failures": grounding_reasons,
                                "invalid_previous_summary": checked_summary,
                                "evidence": evidence_text,
                            },
                            ensure_ascii=False,
                        ),
                        provenance={"derived": True, "retry": "grounding"},
                        allowed_influence="transcript_evidence_and_validation_only",
                    )
                ),
            },
        ]
        if debug:
            debug.setdefault("stage_inputs", {})["summary_grounding_retry"] = grounding_prompt
        grounding_retry = _call_stage(
            service=runner,
            stage="summary",
            model=stage_cfg["model"],
            temperature=float(stage_cfg["temperature"]),
            max_tokens=int(stage_cfg["max_tokens"]),
            messages=grounding_prompt,
            timings=timings,
            warnings=warnings,
            runtime_settings=settings,
        ).strip()
        checked_summary, missing_topics = _qa_summary_output(
            grounding_retry,
            structured_json=structured_json,
            chunk_count=chunk_count,
            output_language=output_language,
            warnings=warnings,
            debug=debug,
        )
        remaining_grounding_reasons = _summary_grounding_reasons(
            checked_summary,
            evidence_text=evidence_text,
            output_language=output_language,
        )
        if remaining_grounding_reasons:
            _append_warning_once(warnings, f"summary_grounding_retry_failed:{','.join(remaining_grounding_reasons)}")
            structured_fallback = _safe_summary_from_structured(structured_json, output_language)
            if structured_fallback:
                _append_warning_once(warnings, f"summary_safe_structured_fallback_used:{','.join(remaining_grounding_reasons)}")
                checked_summary, missing_topics = _qa_summary_output(
                    structured_fallback,
                    structured_json=structured_json,
                    chunk_count=chunk_count,
                    output_language=output_language,
                    warnings=warnings,
                    debug=debug,
                )
                if missing_topics:
                    _append_warning_once(warnings, f"summary_safe_structured_fallback_missing_topics:{len(missing_topics)}")
                    return _append_incomplete_summary_section(checked_summary, missing_topics)
                return checked_summary
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "asr_summary_grounding_failed",
                    "message": "Summary output failed validation against transcript evidence and required ASR summary format.",
                    "reasons": remaining_grounding_reasons,
                },
            )
        _append_warning_once(warnings, "summary_grounding_retry_succeeded")
    if not missing_topics:
        return checked_summary

    _append_warning_once(warnings, f"summary_topic_coverage_missing:{len(missing_topics)}")
    if output_language == "en":
        retry_intro = (
            "The previous summary missed major topics from the transcript.\n"
            "Generate a complete final summary, explaining missing_topics meaningfully rather than with a single keyword.\n\n"
        )
    else:
        retry_intro = (
            "Предыдущее summary не покрыло все крупные темы встречи.\n"
            "Сгенерируй полную финальную версию summary, обязательно раскрыв missing_topics смыслом, а не одним словом.\n\n"
        )
    retry_prompt = [
        {
            "role": "system",
            "content": (
                f"Regenerate the transcript summary in {_language_name(output_language)}. Keep the same markdown sections. Do not add facts. "
                f"{_json_language_instruction(output_language)} "
                "You must explain every missing topic from the user message in the appropriate section, not merely mention one keyword. "
                "Keep proposals separate from confirmed decisions. "
                "Repeated source points are importance signals and must not be dropped as cleanup noise. "
                "If a technical term looks ambiguous in ASR evidence, mark it as requiring clarification instead of inventing a normalized term. "
                "Return only the requested markdown summary, with no preamble. "
                f"{_summary_grounding_rules(output_language)} "
                f"{_summary_guardrails(output_language)}"
            ),
        },
        {"role": "system", "content": GLOBAL_GUARD_POLICY},
        {
            "role": "user",
            "content": (
                retry_intro +
                f"{analysis_context_block}"
                + data_envelope(
                    "asr_summary_coverage_retry",
                    json.dumps(
                        {
                            "missing_topics": missing_topics,
                            "previous_summary": checked_summary,
                            "evidence": summary_input,
                        },
                        ensure_ascii=False,
                    ),
                    provenance={"derived": True, "retry": "coverage"},
                    allowed_influence="transcript_evidence_and_coverage_only",
                )
            ),
        },
    ]
    if debug:
        debug.setdefault("stage_inputs", {})["summary_retry"] = retry_prompt
    retry_summary = _call_stage(
        service=runner,
        stage="summary",
        model=stage_cfg["model"],
        temperature=float(stage_cfg["temperature"]),
        max_tokens=int(stage_cfg["max_tokens"]),
        messages=retry_prompt,
        timings=timings,
        warnings=warnings,
        runtime_settings=settings,
    ).strip()
    checked_retry, remaining_topics = _qa_summary_output(
        retry_summary,
        structured_json=structured_json,
        chunk_count=chunk_count,
        output_language=output_language,
        warnings=warnings,
        debug=debug,
    )
    retry_grounding_reasons = _summary_grounding_reasons(
        checked_retry,
        evidence_text=evidence_text,
        output_language=output_language,
    )
    if retry_grounding_reasons:
        _append_warning_once(warnings, f"summary_topic_coverage_retry_invalid_grounding:{','.join(retry_grounding_reasons)}")
        return _append_incomplete_summary_section(checked_summary, missing_topics)
    if not remaining_topics:
        _append_warning_once(warnings, "summary_topic_coverage_retry_succeeded")
        return checked_retry

    _append_warning_once(warnings, f"summary_topic_coverage_retry_failed:{len(remaining_topics)}")
    return _append_incomplete_summary_section(checked_retry, remaining_topics)


def update_speakers(run_id: int, overrides: dict[str, Any] | None) -> dict[str, Any]:
    run = db.get_pipeline_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="pipeline_run_not_found")
    merged = dict(run.get("speaker_overrides") or {})
    if overrides:
        for key, value in overrides.items():
            merged[str(key)] = _manual_speaker_name(value)
    mapping = apply_speaker_overrides(list(run.get("speaker_mapping") or []), merged)
    updated = db.update_pipeline_run(run_id, speaker_mapping=mapping, speaker_overrides=merged)
    return updated or run


def regenerate_summary(run_id: int, *, save_memory: bool = True) -> dict[str, Any]:
    reset_pipeline_stop_request()
    run = db.get_pipeline_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="pipeline_run_not_found")
    settings = run.get("used_settings") or _resolve_settings(int(run["profile_id"]))
    timings = dict(run.get("stage_timings") or {})
    warnings = list(run.get("warnings") or [])
    debug = deepcopy(run.get("debug") or {})
    summary = generate_summary(
        cleaned_transcript=str(run.get("cleaned_transcript") or ""),
        speaker_mapping=list(run.get("speaker_mapping") or []),
        structured_json=run.get("structured_json"),
        settings=settings,
        timings=timings,
        warnings=warnings,
        debug=debug,
    )
    updated = db.update_pipeline_run(run_id, summary=summary, stage_timings=timings, warnings=warnings, debug=debug)
    if updated:
        _sync_transcript_pipeline_fields(int(run["transcript_id"]), updated)
    if save_memory and summary:
        db.create_session_summary(
            profile_id=int(run["profile_id"]),
            session_id=run.get("session_id"),
            source_type="asr",
            source_id=str(run.get("transcript_id")),
            summary=summary,
            structured_json=run.get("structured_json"),
        )
    return updated or run
