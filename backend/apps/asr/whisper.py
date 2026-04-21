from __future__ import annotations

import json
import os
import shutil
import threading
from pathlib import Path
from typing import Any, Iterable

from app import config

MODEL_REPOSITORIES = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}

DEFAULT_FALLBACK_LANGUAGE = (
    os.getenv("WHISPER_FALLBACK_LANGUAGE", "ru").strip().lower() or "ru"
)
FALLBACK_USE_PROMPT = os.getenv("WHISPER_FALLBACK_USE_PROMPT", "true").strip().lower()
FALLBACK_USE_PROMPT = FALLBACK_USE_PROMPT not in {"0", "false", "no"}

DEFAULT_ROLE_KEYWORDS = {
    "hr": [
        "компания",
        "коллег",
        "зарплат",
        "ваканси",
        "обязанн",
        "тестовое",
        "условия",
        "расскажите",
        "задач",
        "офер",
    ],
    "candidate": [
        "меня зовут",
        "мой опыт",
        "работал",
        "учился",
        "занимался",
        "команда",
        "портфолио",
        "проживаю",
        "ищу",
        "готов",
    ],
}

RU_PRESET_PROMPT = (
    "корректная пунктуация, нормальная орфография, числа, даты, проценты, имена, "
    "названия компаний; не искажать слова; сохранять смысл речи"
)

EN_PRESET_PROMPT = (
    "use correct punctuation and spelling, numbers, dates, percentages, proper names; "
    "do not hallucinate; preserve meaning"
)

_PROMPT_PRESETS = {
    "ru": RU_PRESET_PROMPT,
    "en": EN_PRESET_PROMPT,
}

_MODEL_CACHE: dict[tuple[str, str, str], Any] = {}
_MODEL_LOCK = threading.Lock()


def _whisper_root() -> Path:
    return config.WHISPER_MODELS_DIR


def _normalize_model(model_name: str) -> str:
    model = (model_name or "").strip()
    if model not in config.ALLOWED_WHISPER_MODELS:
        raise ValueError("invalid_model")
    return model


def clear_model_cache(model_name: str | None = None) -> None:
    with _MODEL_LOCK:
        if model_name is None:
            _MODEL_CACHE.clear()
            return

        try:
            normalized = _normalize_model(model_name)
        except ValueError:
            return

        model_dir = str(local_model_dir(normalized))
        keys_to_drop = [key for key in _MODEL_CACHE if key[0] in {normalized, model_dir}]
        for key in keys_to_drop:
            _MODEL_CACHE.pop(key, None)


def repository_for_model(model_name: str) -> str:
    model = _normalize_model(model_name)
    return MODEL_REPOSITORIES[model]


def local_model_dir(model_name: str) -> Path:
    model = _normalize_model(model_name)
    return config.WHISPER_MODELS_DIR / model


def _copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def _model_is_ready(path: Path) -> bool:
    return path.exists() and (path / "model.bin").exists()


def _snapshot_dirs(repo_id: str) -> list[Path]:
    org, repo_name = repo_id.split("/", 1)
    relative = Path(f"models--{org}--{repo_name}") / "snapshots"

    result: list[Path] = []
    snapshots_root = config.HF_CACHE_DIR / relative
    if not snapshots_root.exists():
        return result

    for snapshot in snapshots_root.iterdir():
        if snapshot.is_dir():
            result.append(snapshot)

    result.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0.0, reverse=True)
    return result


def _legacy_model_dirs(model_name: str) -> list[Path]:
    model = _normalize_model(model_name)
    repo_suffix = repository_for_model(model).split("/", 1)[1]

    candidates = [
        config.MODELS_DIR / "whisper" / repo_suffix,
        config.MODELS_DIR / "whisper" / model,
        config.WHISPER_MODELS_DIR / repo_suffix,
    ]

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = str(candidate.resolve())
        except OSError:
            key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _hydrate_model_from_cache(model_name: str) -> bool:
    target = local_model_dir(model_name)
    if _model_is_ready(target):
        return True

    for legacy in _legacy_model_dirs(model_name):
        if not _model_is_ready(legacy):
            continue
        _copy_tree(legacy, target)
        if _model_is_ready(target):
            return True

    repo_id = repository_for_model(model_name)
    for snapshot in _snapshot_dirs(repo_id):
        if not _model_is_ready(snapshot):
            continue
        _copy_tree(snapshot, target)
        if _model_is_ready(target):
            return True

    return _model_is_ready(target)


def is_local_model_ready(model_name: str) -> bool:
    model_dir = local_model_dir(model_name)
    if _model_is_ready(model_dir):
        return True
    return _hydrate_model_from_cache(model_name)


def build_whisper_prompt(audio_path: Path, prompt_preset: str | None) -> str | None:
    preset = (prompt_preset or "").strip().lower()
    prompt_from_preset = _PROMPT_PRESETS.get(preset, "")

    local_prompt_file = audio_path.parent / "whisper_prompt.txt"
    local_prompt = ""
    if local_prompt_file.exists():
        try:
            local_prompt = local_prompt_file.read_text(encoding="utf-8").strip()
        except OSError:
            local_prompt = ""

    parts: list[str] = []
    if prompt_from_preset:
        parts.append(prompt_from_preset)
    if local_prompt:
        parts.append(local_prompt)

    if not parts:
        return None
    return "; ".join(parts)


def _normalize_language(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized or normalized in {"auto", "auto-detect", "detect"}:
        return None
    return normalized


def _normalize_role_keywords(data: dict[str, Iterable[str]] | None) -> dict[str, list[str]]:
    if not data:
        return {key: list(values) for key, values in DEFAULT_ROLE_KEYWORDS.items()}

    normalized: dict[str, list[str]] = {}
    for role, raw_keywords in data.items():
        if not isinstance(role, str):
            continue
        if isinstance(raw_keywords, str):
            candidates = [raw_keywords]
        elif isinstance(raw_keywords, Iterable):
            candidates = list(raw_keywords)
        else:
            continue
        cleaned: list[str] = []
        for item in candidates:
            if not isinstance(item, str):
                continue
            keyword = item.strip().lower()
            if keyword and keyword not in cleaned:
                cleaned.append(keyword)
        if cleaned:
            normalized[role.strip().lower() or role] = cleaned

    if not normalized:
        return {key: list(values) for key, values in DEFAULT_ROLE_KEYWORDS.items()}
    return normalized


def _load_role_keywords(audio_path: Path) -> dict[str, list[str]]:
    env_inline = os.getenv("WHISPER_ROLE_KEYWORDS")
    if env_inline:
        try:
            parsed = json.loads(env_inline)
            if isinstance(parsed, dict):
                return _normalize_role_keywords(parsed)
        except json.JSONDecodeError:
            pass

    env_path = os.getenv("WHISPER_ROLE_KEYWORDS_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    return _normalize_role_keywords(parsed)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass

    local_file = audio_path.parent / "role_keywords.json"
    if local_file.exists():
        try:
            parsed = json.loads(local_file.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                return _normalize_role_keywords(parsed)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass

    module_default = Path(__file__).with_name("role_keywords.json")
    if module_default.exists():
        try:
            parsed = json.loads(module_default.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                return _normalize_role_keywords(parsed)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass

    return {key: list(values) for key, values in DEFAULT_ROLE_KEYWORDS.items()}


def _annotate_speakers(
    segments: list[dict[str, Any]],
    role_keywords: dict[str, list[str]],
) -> list[dict[str, Any]]:
    if not segments:
        return []

    speakers = list(role_keywords.keys()) or list(DEFAULT_ROLE_KEYWORDS.keys())
    default_speaker = speakers[0] if speakers else "hr"
    annotated: list[dict[str, Any]] = []
    last_speaker = None

    for segment in segments:
        text = (segment.get("text") or "").lower()
        best_speaker = None
        best_score = 0

        for speaker, keywords in role_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword and keyword in text:
                    score += 1
            if score > best_score:
                best_score = score
                best_speaker = speaker
            elif score == best_score and score > 0:
                best_speaker = last_speaker

        if not best_speaker:
            best_speaker = last_speaker or default_speaker

        annotated_segment = {
            **segment,
            "speaker": best_speaker or default_speaker,
        }
        annotated.append(annotated_segment)
        last_speaker = annotated_segment["speaker"]

    return annotated


def _load_model(model_name: str, *, compute_type: str | None = None, device: str | None = None):
    from faster_whisper import WhisperModel

    model = _normalize_model(model_name)
    local_ready = is_local_model_ready(model)
    model_source = str(local_model_dir(model)) if local_ready else model
    resolved_device = (device or config.SETTINGS.whisper_device).strip()
    resolved_compute_type = (compute_type or config.SETTINGS.whisper_compute_type).strip()

    model_key = (
        model_source,
        resolved_device,
        resolved_compute_type,
    )

    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(model_key)
        if cached is not None:
            return cached

        whisper_model = WhisperModel(
            model_source,
            device=resolved_device,
            compute_type=resolved_compute_type,
            download_root=str(config.WHISPER_MODELS_DIR),
        )
        _MODEL_CACHE[model_key] = whisper_model
        return whisper_model


def ensure_model_available(model_name: str) -> None:
    _load_model(model_name)


def transcribe_with_fallback(
    audio_path: str,
    model_name: str,
    prompt_preset: str | None = None,
    preferred_language: str | None = None,
    compute_type: str | None = None,
    device: str | None = None,
    beam_size: int | None = None,
) -> dict[str, Any]:
    path = Path(audio_path)
    if not path.exists():
        raise RuntimeError("audio_file_missing")

    model = _normalize_model(model_name)
    resolved_beam_size = max(1, int(beam_size or config.SETTINGS.whisper_beam_size))
    full_prompt = build_whisper_prompt(path, prompt_preset)
    fallback_language = _normalize_language(preferred_language) or _normalize_language(
        config.SETTINGS.whisper_fallback_language or DEFAULT_FALLBACK_LANGUAGE
    )
    fallback_prompt = full_prompt if FALLBACK_USE_PROMPT else None

    try:
        whisper_model = _load_model(model, compute_type=compute_type, device=device)
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError(f"WHISPER_MODEL_NOT_FOUND::{model}") from exc

    role_keywords = _load_role_keywords(path)

    def run_once(language: str | None, use_vad: bool, prompt: str | None) -> tuple[str, list[dict[str, Any]], Any]:
        segments, info = whisper_model.transcribe(
            str(path),
            language=language,
            vad_filter=use_vad,
            beam_size=resolved_beam_size,
            initial_prompt=prompt,
        )
        collected_segments: list[dict[str, Any]] = []
        text_parts: list[str] = []

        for segment in segments:
            segment_text = (segment.text or "").strip()
            if not segment_text:
                continue
            text_parts.append(segment.text)
            collected_segments.append(
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": segment_text,
                }
            )

        return "".join(text_parts).strip(), collected_segments, info

    text, segments_data, info = run_once(language=None, use_vad=True, prompt=full_prompt)

    if not text:
        text, segments_data, info = run_once(
            language=fallback_language,
            use_vad=False,
            prompt=fallback_prompt,
        )

    annotated_segments = _annotate_speakers(segments_data, role_keywords)
    result: dict[str, Any] = {
        "text": text,
        "segments": annotated_segments,
        "role_keywords": role_keywords,
    }

    detected_language = getattr(info, "language", None)
    if detected_language:
        result["language"] = detected_language

    return result
