from __future__ import annotations

import json
import logging
import re
import time
from copy import deepcopy
from typing import Any

from fastapi import HTTPException

from app import config, db
from app.services import models as model_service
from backend.apps.chat.service import ChatService

LOGGER = logging.getLogger(__name__)

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

VALID_ACTIONS = {"clean", "summary", "tasks", "full"}
SPEAKER_RE = re.compile(r"^Speaker_\d+$")


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
            detail={"code": "invalid_pipeline_action", "message": "Pipeline action must be clean, summary, tasks or full."},
        )
    return action


def _stage_enabled(stage: str, action: str, preset: str, pipeline: dict[str, Any]) -> bool:
    preset_cfg = PIPELINE_PRESETS[preset]
    if action == "clean":
        desired = stage == "cleaner"
    elif action == "summary":
        desired = stage in {"cleaner", "summary"}
    elif action == "tasks":
        desired = stage in {"cleaner", "segmenter", "structurer"}
    else:
        desired = bool(preset_cfg.get(stage))
    stage_cfg = pipeline.get(stage) or {}
    return desired and bool(stage_cfg.get("enabled", True))


def _stage_settings(settings: dict[str, Any], stage: str) -> dict[str, Any]:
    stage_cfg = ((settings.get("pipeline") or {}).get(stage) or {}).copy()
    model = stage_cfg.get("model") or config.SETTINGS.model
    fallback_model = settings.get("_fallback_model")
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


def _empty_structure() -> dict[str, Any]:
    return {
        "topic": "не указано",
        "tasks": [],
        "decisions": [],
        "agreements": [],
        "risks": [],
        "open_questions": [],
        "owners": "не указано",
        "deadlines": "не указано",
    }


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
) -> str:
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
        return service.chat_completion(model, messages, settings={"temperature": temperature, "max_tokens": max_tokens})
    except HTTPException:
        raise
    except Exception as exc:
        warnings.append(f"{stage}_failed: {exc}")
        raise HTTPException(status_code=502, detail={"code": f"{stage}_failed", "message": str(exc)}) from exc
    finally:
        timings[stage] = {"elapsed_ms": int((time.perf_counter() - started) * 1000), "model": model}


def _log_pipeline_event(payload: dict[str, Any]) -> None:
    try:
        config.PIPELINE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with config.PIPELINE_LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("Failed to write pipeline log: %s", exc)


def _resolve_settings(profile_id: int, model_name: str | None = None) -> dict[str, Any]:
    model = model_name or config.SETTINGS.model
    settings = db.effective_settings(profile_id, model, config.DEFAULT_SETTINGS).get("effective") or {}
    settings["_fallback_model"] = model
    return settings


def run_transcript_pipeline(
    *,
    transcript_id: int,
    preset: str | None = None,
    action: str | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    transcript = db.get_transcript(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="transcript_not_found")
    profile_id = int(transcript["profile_id"])
    settings = _resolve_settings(profile_id, model_name)
    if not settings.get("pipeline_enabled", True):
        raise HTTPException(status_code=409, detail={"code": "pipeline_disabled", "message": "Pipeline is disabled."})
    preset_value = _normalize_preset(preset, settings.get("default_pipeline_preset") or "balanced")
    action_value = _normalize_action(action)
    pipeline_cfg = _json_clone(settings.get("pipeline") or config.DEFAULT_PIPELINE)
    raw = str(transcript.get("content") or "")
    max_chars = int(settings.get("max_transcript_chars") or 24000)
    warnings: list[str] = []
    if len(raw) > max_chars:
        raw_for_pipeline = raw[:max_chars].rstrip()
        warnings.append("raw_transcript_truncated")
    else:
        raw_for_pipeline = raw

    service = ChatService()
    timings: dict[str, Any] = {}
    debug: dict[str, Any] = {"stage_inputs": {}} if PIPELINE_PRESETS[preset_value].get("debug_artifacts") else {}

    cleaned = raw_for_pipeline
    segments: list[dict[str, Any]] = []
    speaker_mapping: list[dict[str, Any]] = []
    structured: dict[str, Any] | list[Any] | None = None
    summary: str | None = None

    if _stage_enabled("cleaner", action_value, preset_value, pipeline_cfg):
        stage_cfg = _stage_settings(settings, "cleaner")
        prompt = [
            {"role": "system", "content": "Clean ASR text without changing meaning. Do not add facts."},
            {
                "role": "user",
                "content": (
                    "Убери явный ASR-мусор, повторы и слова-паразиты. Не меняй смысл и не добавляй факты.\n\n"
                    f"{raw_for_pipeline}"
                ),
            },
        ]
        if debug:
            debug["stage_inputs"]["cleaner"] = prompt
        cleaned = _call_stage(
            service=service,
            stage="cleaner",
            model=stage_cfg["model"],
            temperature=float(stage_cfg["temperature"]),
            max_tokens=int(stage_cfg["max_tokens"]),
            messages=prompt,
            timings=timings,
            warnings=warnings,
        ).strip() or _clean_text_fallback(raw_for_pipeline)
    else:
        cleaned = _clean_text_fallback(raw_for_pipeline)

    if _stage_enabled("segmenter", action_value, preset_value, pipeline_cfg):
        stage_cfg = _stage_settings(settings, "segmenter")
        prompt = [
            {"role": "system", "content": "Return only JSON array. Do not assign speakers."},
            {
                "role": "user",
                "content": (
                    "Разбей transcript на логические реплики или смысловые блоки. "
                    "Верни JSON array: [{\"segment_id\":1,\"text\":\"...\"}].\n\n"
                    f"{cleaned}"
                ),
            },
        ]
        if debug:
            debug["stage_inputs"]["segmenter"] = prompt
        response = _call_stage(
            service=service,
            stage="segmenter",
            model=stage_cfg["model"],
            temperature=float(stage_cfg["temperature"]),
            max_tokens=int(stage_cfg["max_tokens"]),
            messages=prompt,
            timings=timings,
            warnings=warnings,
        )
        parsed = _extract_json(response, [])
        segments = [
            {"segment_id": idx + 1, "text": str(item.get("text") or "").strip()}
            for idx, item in enumerate(parsed if isinstance(parsed, list) else [])
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        ]
    if not segments:
        segments = _segment_fallback(cleaned)

    if _stage_enabled("speaker_resolver", action_value, preset_value, pipeline_cfg):
        stage_cfg = _stage_settings(settings, "speaker_resolver")
        prompt = [
            {
                "role": "system",
                "content": (
                    "Return only JSON array. Never use real names. Use Speaker_1, Speaker_2 or Unknown speaker. "
                    "Include confidence from 0 to 1."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Попробуй сгруппировать сегменты по говорящим, но не придумывай личности. "
                    "Если уверенности нет, ставь Unknown speaker.\n\n"
                    f"{json.dumps(segments, ensure_ascii=False)}"
                ),
            },
        ]
        if debug:
            debug["stage_inputs"]["speaker_resolver"] = prompt
        response = _call_stage(
            service=service,
            stage="speaker_resolver",
            model=stage_cfg["model"],
            temperature=float(stage_cfg["temperature"]),
            max_tokens=int(stage_cfg["max_tokens"]),
            messages=prompt,
            timings=timings,
            warnings=warnings,
        )
        speaker_mapping = _sanitize_speaker_mapping(_extract_json(response, []), segments)
    else:
        speaker_mapping = _sanitize_speaker_mapping([], segments)

    if _stage_enabled("structurer", action_value, preset_value, pipeline_cfg):
        stage_cfg = _stage_settings(settings, "structurer")
        prompt = [
            {"role": "system", "content": "Return only JSON object. Do not add facts."},
            {
                "role": "user",
                "content": (
                    "Извлеки тему, задачи, решения, договорённости, риски, открытые вопросы, ответственных и сроки. "
                    "Если данных нет, пиши 'не указано', 'не зафиксировано' или 'требует уточнения'.\n\n"
                    f"{json.dumps(speaker_mapping, ensure_ascii=False)}"
                ),
            },
        ]
        if debug:
            debug["stage_inputs"]["structurer"] = prompt
        response = _call_stage(
            service=service,
            stage="structurer",
            model=stage_cfg["model"],
            temperature=float(stage_cfg["temperature"]),
            max_tokens=int(stage_cfg["max_tokens"]),
            messages=prompt,
            timings=timings,
            warnings=warnings,
        )
        parsed = _extract_json(response, _empty_structure())
        structured = parsed if isinstance(parsed, dict) else _empty_structure()
    elif action_value in {"tasks", "full"}:
        structured = _empty_structure()

    if _stage_enabled("summary", action_value, preset_value, pipeline_cfg):
        summary = generate_summary(
            cleaned_transcript=cleaned,
            speaker_mapping=speaker_mapping,
            structured_json=structured,
            settings=settings,
            timings=timings,
            warnings=warnings,
            debug=debug,
            service=service,
        )

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

    if summary and (PIPELINE_PRESETS[preset_value].get("memory_save") or action_value == "summary"):
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
            "input_size": len(raw_for_pipeline),
            "output_size": len(summary or cleaned or ""),
            "truncated": "raw_transcript_truncated" in warnings,
            "used_settings": settings,
        }
    )
    return run


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
) -> str:
    stage_cfg = _stage_settings(settings, "summary")
    summary_input = {
        "cleaned_transcript": cleaned_transcript,
        "speaker_mapping": speaker_mapping,
        "structured": structured_json,
    }
    prompt = [
        {
            "role": "system",
            "content": (
                "Generate concise transcript summary. Do not add facts. "
                "If speaker attribution is uncertain, do not base conclusions on it."
            ),
        },
        {
            "role": "user",
            "content": (
                "Сформируй summary строго в формате:\n"
                "## Краткое резюме\n...\n## Ключевые решения\n- ...\n## Задачи\n- ...\n"
                "## Риски\n- ...\n## Вопросы для уточнения\n- ...\n## Следующие действия\n- ...\n\n"
                f"{json.dumps(summary_input, ensure_ascii=False)}"
            ),
        },
    ]
    if debug is not None:
        debug.setdefault("stage_inputs", {})["summary"] = prompt
    runner = service or ChatService()
    return _call_stage(
        service=runner,
        stage="summary",
        model=stage_cfg["model"],
        temperature=float(stage_cfg["temperature"]),
        max_tokens=int(stage_cfg["max_tokens"]),
        messages=prompt,
        timings=timings,
        warnings=warnings,
    ).strip()


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
