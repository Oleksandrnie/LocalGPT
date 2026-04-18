from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Any

from . import config

MODEL_REPOSITORIES = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
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

    result.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0.0, reverse=True)
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


def _normalize_language(language: str | None) -> str | None:
    if not language:
        return None
    normalized = language.strip().lower()
    if not normalized or normalized in {"auto", "auto-detect", "detect"}:
        return None
    return normalized


def build_initial_prompt(audio_path: Path, prompt_preset: str | None = None) -> str | None:
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


def _load_model(model_name: str):
    from faster_whisper import WhisperModel

    local_ready = is_local_model_ready(model_name)
    model_source = str(local_model_dir(model_name)) if local_ready else model_name

    model_key = (
        model_source,
        config.SETTINGS.whisper_device,
        config.SETTINGS.whisper_compute_type,
    )

    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(model_key)
        if cached is not None:
            return cached

        model = WhisperModel(
            model_source,
            device=config.SETTINGS.whisper_device,
            compute_type=config.SETTINGS.whisper_compute_type,
            download_root=str(config.WHISPER_MODELS_DIR),
        )
        _MODEL_CACHE[model_key] = model
        return model


def ensure_model_available(model_name: str) -> None:
    model = _normalize_model(model_name)
    _load_model(model)


def transcribe_with_fallback(
    audio_path: str,
    model_name: str,
    *,
    prompt_preset: str | None = None,
    preferred_language: str | None = None,
) -> dict[str, Any]:
    model = _normalize_model(model_name)
    file_path = Path(audio_path)

    if not file_path.exists():
        raise RuntimeError("audio_file_missing")

    try:
        whisper_model = _load_model(model)
    except ValueError:
        raise
    except Exception as exc:  # pragma: no cover - зависит от окружения и сети
        raise RuntimeError("model_prepare_failed") from exc

    initial_prompt = build_initial_prompt(file_path, prompt_preset)
    fallback_language = _normalize_language(preferred_language) or _normalize_language(
        config.SETTINGS.whisper_fallback_language
    )

    def _run_once(language: str | None, use_vad: bool) -> tuple[str, list[dict[str, Any]], str | None, float]:
        segments, info = whisper_model.transcribe(
            str(file_path),
            language=language,
            vad_filter=use_vad,
            beam_size=config.SETTINGS.whisper_beam_size,
            initial_prompt=initial_prompt,
        )

        text_parts: list[str] = []
        collected_segments: list[dict[str, Any]] = []
        max_end = 0.0

        for segment in segments:
            segment_text = (segment.text or "").strip()
            if not segment_text:
                continue

            start = float(segment.start)
            end = float(segment.end)
            max_end = max(max_end, end)

            text_parts.append(segment_text)
            collected_segments.append(
                {
                    "start": start,
                    "end": end,
                    "text": segment_text,
                }
            )

        detected_language = getattr(info, "language", None)
        return " ".join(text_parts).strip(), collected_segments, detected_language, max_end

    text, segments, detected_language, duration_sec = _run_once(language=None, use_vad=True)

    if not text:
        text, segments, detected_language, duration_sec = _run_once(
            language=fallback_language,
            use_vad=False,
        )

    return {
        "text": text,
        "segments": segments,
        "language": detected_language,
        "duration_sec": round(duration_sec, 3) if duration_sec else 0.0,
    }
