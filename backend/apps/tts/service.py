from __future__ import annotations

import json
import multiprocessing as mp
import os
import re
import signal
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from secrets import token_hex
from tempfile import NamedTemporaryFile
from typing import Any

from app import config
from backend.apps.tts.audio_postprocess import apply_speed_to_wav
from backend.apps.tts.providers.base import VoiceDefinition
from backend.apps.tts.providers.piper_provider import PiperProvider

_PROCESS_CTX = mp.get_context("spawn")
_LOCK = threading.Lock()
_TASKS: dict[str, dict[str, Any]] = {}
_ACTIVE_STATES = {"queued", "generating", "processing_speed"}
_FINAL_STATES = {"completed", "error"}
_VOICE_LIBRARY_LOCK = threading.Lock()
_VOICE_DOWNLOAD_TASKS: dict[str, dict[str, Any]] = {}
_VOICE_DOWNLOAD_ACTIVE_STATES = {"queued", "running"}
_VOICE_CATALOG_CACHE: dict[str, Any] = {"items": None, "expires_at": 0.0}
_VOICE_CATALOG_TTL_SEC = 300.0
_PREVIEW_MAX_TEXT_CHARS = 240
_PROVIDERS = {
    "piper": PiperProvider(),
}


class TTSServiceError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp_file:
        json.dump(payload, tmp_file, ensure_ascii=False, indent=2)
        tmp_file.flush()
        temp_name = tmp_file.name
    Path(temp_name).replace(path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _record_path(record_id: str) -> Path:
    return config.TTS_HISTORY_DIR / f"{record_id}.json"


def _record_id() -> str:
    now = datetime.now(timezone.utc)
    return f"tts_{now:%Y%m%d_%H%M%S}_{token_hex(3)}"


def _voice_download_task_id() -> str:
    now = datetime.now(timezone.utc)
    return f"vdl_{now:%Y%m%d_%H%M%S}_{token_hex(3)}"


def _record_preview(text: str, max_chars: int = 120) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def _speed_label(speed: float) -> str:
    return f"{speed:.2f}".rstrip("0").rstrip(".")


def _speed_file_token(speed: float) -> str:
    return _speed_label(speed).replace(".", "_") + "x"


def _relative_project_path(path: Path | None) -> str | None:
    if path is None:
        return None
    resolved = path.resolve()
    try:
        return resolved.relative_to(config.PROJECT_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _absolute_project_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = config.PROJECT_ROOT / path
    return path.resolve()


def _base_output_path(record_id: str) -> Path:
    return config.TTS_OUTPUT_DIR / f"{record_id}_base.wav"


def _processed_output_path(record_id: str, speed: float) -> Path:
    return config.TTS_OUTPUT_DIR / f"{record_id}_speed_{_speed_file_token(speed)}.wav"


def _temp_dir(record_id: str) -> Path:
    return config.TTS_TEMP_DIR / record_id


def _safe_unlink(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink()
    except OSError:
        pass


def _clear_voice_catalog_cache() -> None:
    with _VOICE_LIBRARY_LOCK:
        _VOICE_CATALOG_CACHE["items"] = None
        _VOICE_CATALOG_CACHE["expires_at"] = 0.0


def _public_voice_download_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task.get("id"),
        "voice_key": task.get("voice_key"),
        "force": bool(task.get("force")),
        "state": task.get("state"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "message": task.get("message"),
        "error": task.get("error"),
        "installed_voice_ids": task.get("installed_voice_ids") or [],
    }


def _preview_text_for_language(language: str | None) -> str:
    code = (language or "").strip().lower()
    if code.startswith("ru"):
        return "Привет. Это локальное превью голоса."
    if code.startswith("uk"):
        return "Привіт. Це локальне прев'ю голосу."
    if code.startswith("de"):
        return "Hallo. Das ist eine lokale Stimmvorschau."
    if code.startswith("fr"):
        return "Bonjour. Ceci est un aperçu local de la voix."
    if code.startswith("es"):
        return "Hola. Esta es una vista previa local de la voz."
    return "Hello. This is a local voice preview."


def _normalize_preview_text(text: str | None, language: str | None) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return _preview_text_for_language(language)
    if len(clean) > _PREVIEW_MAX_TEXT_CHARS:
        raise TTSServiceError(
            422,
            "preview_text_too_long",
            f"Текст превью не должен превышать {_PREVIEW_MAX_TEXT_CHARS} символов.",
        )
    return clean


def _sanitize_filename_token(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("._")
    return clean or "voice"


def _provider_by_name(provider_name: str | None = None):
    selected = (provider_name or config.SETTINGS.tts_default_provider).strip().lower()
    provider = _PROVIDERS.get(selected)
    if provider is None:
        raise TTSServiceError(422, "unsupported_provider", f"Провайдер TTS не поддерживается: {selected}")
    return provider


def _voice_library_provider() -> PiperProvider:
    provider = _provider_by_name(config.SETTINGS.tts_default_provider)
    if not isinstance(provider, PiperProvider):
        raise TTSServiceError(422, "unsupported_provider", "Каталог голосов доступен только для Piper.")
    return provider


def _normalized_speed(speed: float | int) -> float:
    try:
        value = round(float(speed), 2)
    except (TypeError, ValueError) as exc:
        raise TTSServiceError(422, "invalid_speed", "Недопустимое значение скорости.") from exc

    if value not in set(config.SETTINGS.tts_speed_options):
        allowed = ", ".join(_speed_label(item) for item in config.SETTINGS.tts_speed_options)
        raise TTSServiceError(422, "invalid_speed", f"Скорость должна быть одной из: {allowed}")
    return value


def _ensure_tts_enabled() -> None:
    if not config.SETTINGS.tts_enabled:
        raise TTSServiceError(503, "tts_disabled", "TTS отключен в текущей конфигурации.")


def _require_record(record_id: str) -> dict[str, Any]:
    record = get_history_item(record_id, raise_if_missing=False)
    if not record:
        raise TTSServiceError(404, "tts_history_not_found", "Запись истории TTS не найдена.")
    return record


def _create_record(*, text: str, voice: VoiceDefinition) -> dict[str, Any]:
    now = _utc_now()
    record = {
        "id": _record_id(),
        "created_at": now,
        "updated_at": now,
        "text": text.strip(),
        "preview": _record_preview(text),
        "voice_id": voice.id,
        "voice_name": voice.name,
        "voice_language": voice.language,
        "provider": voice.provider,
        "base_output_path": None,
        "processed_output_path": None,
        "processed_outputs": {},
        "speed": 1.0,
        "duration_sec": None,
        "processed_duration_sec": None,
        "status": "queued",
        "error": None,
    }
    _atomic_write_json(_record_path(record["id"]), record)
    return record


def _update_record(record_id: str, **changes: Any) -> dict[str, Any]:
    record = _read_json(_record_path(record_id)) or {"id": record_id, "created_at": _utc_now()}
    record.update(changes)
    record["updated_at"] = _utc_now()
    _atomic_write_json(_record_path(record_id), record)
    return record


def _register_task(record_id: str, task_kind: str, process) -> None:
    task = {
        "record_id": record_id,
        "kind": task_kind,
        "process": process,
        "pid": process.pid,
    }
    with _LOCK:
        _TASKS[record_id] = task

    monitor = threading.Thread(target=_monitor_task, args=(record_id,), daemon=True, name=f"tts_monitor_{record_id}")
    monitor.start()


def _monitor_task(record_id: str) -> None:
    process = None
    with _LOCK:
        task = _TASKS.get(record_id)
        if task:
            process = task.get("process")

    if process is not None:
        process.join()

    with _LOCK:
        _TASKS.pop(record_id, None)

    record = _read_json(_record_path(record_id))
    if record and record.get("status") in _ACTIVE_STATES:
        _update_record(
            record_id,
            status="error",
            error="Фоновая задача завершилась без итогового результата.",
        )


def _has_active_task(record_id: str) -> bool:
    with _LOCK:
        task = _TASKS.get(record_id)
        if not task:
            return False
        process = task.get("process")
        return bool(process and process.is_alive())


def _public_processed_outputs(processed_outputs: dict[str, Any], record_id: str) -> dict[str, Any]:
    items: dict[str, Any] = {}
    for speed_key, payload in (processed_outputs or {}).items():
        if not isinstance(payload, dict):
            continue
        speed = payload.get("speed")
        items[speed_key] = {
            **payload,
            "url": _output_url(record_id, variant="processed", speed=speed),
        }
    return items


def _output_url(record_id: str, *, variant: str, speed: float | None = None) -> str:
    url = f"/tts/output/{record_id}?variant={variant}"
    if speed is not None:
        url += f"&speed={_speed_label(speed)}"
    return url


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(record)
    payload["base_output_url"] = _output_url(record["id"], variant="base") if record.get("base_output_path") else None
    payload["processed_output_url"] = (
        _output_url(record["id"], variant="processed", speed=record.get("speed"))
        if record.get("processed_output_path")
        else None
    )
    payload["processed_outputs"] = _public_processed_outputs(record.get("processed_outputs", {}), record["id"])
    return payload


def _history_summary(record: dict[str, Any]) -> dict[str, Any]:
    payload = _public_record(record)
    return {
        "id": payload.get("id"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "preview": payload.get("preview"),
        "voice_id": payload.get("voice_id"),
        "voice_name": payload.get("voice_name"),
        "voice_language": payload.get("voice_language"),
        "provider": payload.get("provider"),
        "speed": payload.get("speed"),
        "duration_sec": payload.get("duration_sec"),
        "processed_duration_sec": payload.get("processed_duration_sec"),
        "status": payload.get("status"),
        "error": payload.get("error"),
        "base_output_url": payload.get("base_output_url"),
        "processed_output_url": payload.get("processed_output_url"),
    }


def _normalize_text_for_speech(text: str) -> str:
    clean = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    clean = re.sub(r"```[a-zA-Z0-9_-]*\n?([\s\S]*?)```", r"\1", clean)
    clean = re.sub(r"`([^`\n]+)`", r"\1", clean)
    clean = re.sub(r"^#{1,6}\s*", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"^\s*>\s?", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"^\s*[-*+]\s+", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"^\s*\d+\.\s+", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", clean)
    clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
    clean = re.sub(r"\*\*([^*\n](?:[\s\S]*?[^*\n])?)\*\*", r"\1", clean)
    clean = re.sub(r"__([^_\n](?:[\s\S]*?[^_\n])?)__", r"\1", clean)
    clean = re.sub(r"(^|[\s(])[*_]([^*_\n]+)[*_](?=[\s).,!?:;]|$)", r"\1\2", clean)
    clean = re.sub(r"<[^>]+>", "", clean)
    clean = re.sub(r"[ \t]+\n", "\n", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    return clean.strip()


def _validate_text(text: str) -> str:
    clean = _normalize_text_for_speech(text)
    if not clean:
        raise TTSServiceError(422, "text_required", "Введите текст для озвучки.")
    if len(clean) > config.SETTINGS.tts_max_text_chars:
        raise TTSServiceError(
            422,
            "text_too_long",
            f"Текст превышает лимит {config.SETTINGS.tts_max_text_chars} символов.",
        )
    return clean


def _assert_provider_ready(provider_name: str | None, voice_id: str) -> VoiceDefinition:
    provider = _provider_by_name(provider_name)
    available, message = provider.is_available()
    if not available:
        raise TTSServiceError(503, "provider_unavailable", message or "TTS provider unavailable.")

    voice = provider.get_voice(voice_id)
    if not voice:
        raise TTSServiceError(422, "voice_not_found", "Выбранный голос не найден.")

    return voice


def _synthesize_worker(record_id: str, text: str, voice_id: str, provider_name: str) -> None:
    temp_dir = _temp_dir(record_id)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        provider = _provider_by_name(provider_name)
        voice = provider.get_voice(voice_id)
        if not voice:
            raise ValueError("voice_not_found")

        _update_record(record_id, status="generating", error=None)
        output_path = _base_output_path(record_id)
        result = provider.synthesize(text, voice_id, output_path)
        _update_record(
            record_id,
            status="completed",
            error=None,
            voice_id=result.voice.id,
            voice_name=result.voice.name,
            voice_language=result.voice.language,
            provider=result.voice.provider,
            speed=1.0,
            duration_sec=result.duration_sec,
            processed_duration_sec=None,
            base_output_path=_relative_project_path(Path(result.output_path)),
            processed_output_path=None,
            processed_outputs={},
        )
    except ValueError as exc:
        code = str(exc)
        if code == "voice_not_found":
            message = "Выбранный голос больше недоступен."
        elif code == "text_required":
            message = "Введите текст для озвучки."
        else:
            message = code or "tts_generation_failed"
        _update_record(record_id, status="error", error=message)
    except Exception as exc:  # pragma: no cover - real runtime path
        _update_record(record_id, status="error", error=str(exc) or "tts_generation_failed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _download_voice_worker(task_id: str, voice_key: str, force: bool) -> None:
    provider = _voice_library_provider()

    with _VOICE_LIBRARY_LOCK:
        task = _VOICE_DOWNLOAD_TASKS.get(task_id)
        if task:
            task["state"] = "running"
            task["message"] = "Загрузка голоса..."
            task["error"] = None
            task["updated_at"] = _utc_now()

    try:
        provider.download_voice(voice_key, force=force)
        _clear_voice_catalog_cache()
        installed_voice_ids = provider.voice_ids_for_catalog_key(voice_key)
        with _VOICE_LIBRARY_LOCK:
            task = _VOICE_DOWNLOAD_TASKS.get(task_id)
            if task:
                task["state"] = "completed"
                task["message"] = "Голос загружен."
                task["error"] = None
                task["installed_voice_ids"] = installed_voice_ids
                task["updated_at"] = _utc_now()
    except Exception as exc:  # pragma: no cover - network/runtime path
        with _VOICE_LIBRARY_LOCK:
            task = _VOICE_DOWNLOAD_TASKS.get(task_id)
            if task:
                task["state"] = "error"
                task["message"] = "Не удалось загрузить голос."
                task["error"] = str(exc) or "voice_download_failed"
                task["updated_at"] = _utc_now()


def _speed_worker(record_id: str, speed: float) -> None:
    temp_dir = _temp_dir(record_id)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        record = _read_json(_record_path(record_id))
        if not record:
            return

        base_output_path = _absolute_project_path(record.get("base_output_path"))
        if base_output_path is None or not base_output_path.exists():
            raise FileNotFoundError("base_output_missing")

        _update_record(record_id, status="processing_speed", error=None)
        output_path = _processed_output_path(record_id, speed)
        duration = apply_speed_to_wav(base_output_path, output_path, speed)

        latest = _read_json(_record_path(record_id)) or record
        processed_outputs = dict(latest.get("processed_outputs", {}))
        processed_outputs[_speed_label(speed)] = {
            "speed": speed,
            "path": _relative_project_path(output_path),
            "duration_sec": duration,
            "created_at": _utc_now(),
        }

        _update_record(
            record_id,
            status="completed",
            error=None,
            speed=speed,
            processed_duration_sec=duration,
            processed_output_path=_relative_project_path(output_path),
            processed_outputs=processed_outputs,
        )
    except FileNotFoundError as exc:
        code = str(exc)
        message = "Исходный WAV-файл не найден." if code == "base_output_missing" else code
        _update_record(record_id, status="error", error=message)
    except Exception as exc:  # pragma: no cover - real runtime path
        _update_record(record_id, status="error", error=str(exc) or "tts_speed_failed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def get_health() -> dict[str, Any]:
    provider_name = config.SETTINGS.tts_default_provider
    try:
        provider = _provider_by_name(provider_name)
        provider_available, provider_message = provider.is_available()
        voices = provider.list_voices() if provider_available else []
        provider_payload = {
            "name": provider.name,
            "available": provider_available,
            "voices_count": len(voices),
        }
    except TTSServiceError as exc:
        provider_available = False
        voices = []
        provider_payload = {
            "name": provider_name,
            "available": False,
            "voices_count": 0,
        }

    status = "ok" if config.SETTINGS.tts_enabled and provider_available else "degraded"
    if not config.SETTINGS.tts_enabled:
        status = "disabled"

    return {
        "status": status,
        "tts_enabled": config.SETTINGS.tts_enabled,
        "default_provider": config.SETTINGS.tts_default_provider,
        "audio_format": config.SETTINGS.tts_audio_format,
        "max_text_chars": config.SETTINGS.tts_max_text_chars,
        "speed_options": list(config.SETTINGS.tts_speed_options),
        "provider": provider_payload,
    }


def list_voices() -> list[dict[str, object]]:
    provider = _provider_by_name(config.SETTINGS.tts_default_provider)
    return [voice.to_public_dict() for voice in provider.list_voices()]


def list_voice_catalog(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    _ensure_tts_enabled()
    provider = _voice_library_provider()

    with _VOICE_LIBRARY_LOCK:
        cached_items = _VOICE_CATALOG_CACHE.get("items")
        expires_at = float(_VOICE_CATALOG_CACHE.get("expires_at") or 0.0)
        if not force_refresh and cached_items is not None and time.monotonic() < expires_at:
            return list(cached_items)

    try:
        items = provider.list_catalog_voices()
    except RuntimeError as exc:
        code = str(exc)
        if code == "voice_catalog_unavailable":
            raise TTSServiceError(502, "voice_catalog_unavailable", "Не удалось получить каталог Piper voices.") from exc
        raise TTSServiceError(502, "voice_catalog_unavailable", str(exc) or "voice_catalog_unavailable") from exc

    with _VOICE_LIBRARY_LOCK:
        _VOICE_CATALOG_CACHE["items"] = list(items)
        _VOICE_CATALOG_CACHE["expires_at"] = time.monotonic() + _VOICE_CATALOG_TTL_SEC

    return items


def start_voice_download(voice_key: str, *, force: bool = False) -> dict[str, Any]:
    _ensure_tts_enabled()
    normalized_key = (voice_key or "").strip()
    if not normalized_key:
        raise TTSServiceError(422, "voice_key_required", "Укажите голос для загрузки.")

    catalog_items = list_voice_catalog()
    catalog_by_key = {item["key"]: item for item in catalog_items}
    catalog_item = catalog_by_key.get(normalized_key)
    if not catalog_item:
        raise TTSServiceError(404, "voice_catalog_item_not_found", "Голос не найден в каталоге Piper.")

    with _VOICE_LIBRARY_LOCK:
        for existing in _VOICE_DOWNLOAD_TASKS.values():
            if (
                existing.get("voice_key") == normalized_key
                and existing.get("state") in _VOICE_DOWNLOAD_ACTIVE_STATES
            ):
                return _public_voice_download_task(existing)

    if catalog_item.get("installed") and not force:
        raise TTSServiceError(409, "voice_already_installed", "Этот голос уже загружен локально.")

    task = {
        "id": _voice_download_task_id(),
        "voice_key": normalized_key,
        "force": bool(force),
        "state": "queued",
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "message": "Задача загрузки создана.",
        "error": None,
        "installed_voice_ids": [],
    }

    with _VOICE_LIBRARY_LOCK:
        _VOICE_DOWNLOAD_TASKS[task["id"]] = task

    worker = threading.Thread(
        target=_download_voice_worker,
        args=(task["id"], normalized_key, bool(force)),
        daemon=True,
        name=f"voice_download_{task['id']}",
    )
    worker.start()
    return _public_voice_download_task(task)


def get_voice_download_task(task_id: str) -> dict[str, Any]:
    if not task_id:
        raise TTSServiceError(404, "voice_download_task_not_found", "Задача загрузки голоса не найдена.")

    with _VOICE_LIBRARY_LOCK:
        task = _VOICE_DOWNLOAD_TASKS.get(task_id)
        if not task:
            raise TTSServiceError(404, "voice_download_task_not_found", "Задача загрузки голоса не найдена.")
        return _public_voice_download_task(task)


def list_voice_download_tasks() -> list[dict[str, Any]]:
    with _VOICE_LIBRARY_LOCK:
        items = [_public_voice_download_task(task) for task in _VOICE_DOWNLOAD_TASKS.values()]
    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return items


def delete_voice(voice_key: str) -> dict[str, Any]:
    _ensure_tts_enabled()
    normalized_key = (voice_key or "").strip()
    if not normalized_key:
        raise TTSServiceError(422, "voice_key_required", "Укажите голос для удаления.")

    provider = _voice_library_provider()
    removed = provider.delete_voice(normalized_key)
    if not removed:
        raise TTSServiceError(404, "voice_not_installed", "Этот голос не найден локально.")

    _clear_voice_catalog_cache()
    return {"ok": True, "voice_key": normalized_key}


def create_voice_preview_file(*, voice_id: str | None = None, voice_key: str | None = None, text: str | None = None) -> tuple[str, str]:
    _ensure_tts_enabled()
    provider = _voice_library_provider()
    available, message = provider.is_available()
    if not available:
        raise TTSServiceError(503, "provider_unavailable", message or "TTS provider unavailable.")

    voice_ref = (voice_id or voice_key or "").strip()
    if not voice_ref:
        raise TTSServiceError(422, "voice_ref_required", "Укажите голос для превью.")

    resolved_voice_id = provider.resolve_preview_voice_id(voice_ref)
    if not resolved_voice_id:
        raise TTSServiceError(
            404,
            "voice_preview_unavailable",
            "Превью доступно только для уже загруженных локальных голосов.",
        )

    voice = provider.get_voice(resolved_voice_id)
    if not voice:
        raise TTSServiceError(404, "voice_not_found", "Голос для превью не найден.")

    preview_text = _normalize_preview_text(text, voice.language)
    previews_dir = config.TTS_TEMP_DIR / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    preview_path = previews_dir / f"preview_{token_hex(4)}.wav"

    try:
        provider.synthesize(preview_text, voice.id, preview_path)
    except Exception as exc:
        _safe_unlink(preview_path)
        raise TTSServiceError(500, "voice_preview_failed", str(exc) or "voice_preview_failed") from exc

    filename = f"preview_{_sanitize_filename_token(voice.id)}.wav"
    return str(preview_path), filename


def start_generation(*, text: str, voice_id: str, provider: str | None = None) -> dict[str, Any]:
    _ensure_tts_enabled()
    normalized_text = _validate_text(text)
    voice = _assert_provider_ready(provider, voice_id)
    record = _create_record(text=normalized_text, voice=voice)

    process = _PROCESS_CTX.Process(
        target=_synthesize_worker,
        args=(record["id"], normalized_text, voice.id, voice.provider),
        daemon=True,
        name=f"localgpt_tts_generate_{record['id']}",
    )

    try:
        process.start()
    except Exception as exc:
        _update_record(record["id"], status="error", error="Не удалось запустить генерацию аудио.")
        raise TTSServiceError(500, "tts_task_start_failed", str(exc) or "tts_task_start_failed") from exc

    _register_task(record["id"], "generate", process)
    return _public_record(record)


def start_speed_processing(record_id: str, speed: float) -> dict[str, Any]:
    _ensure_tts_enabled()
    normalized_speed = _normalized_speed(speed)
    record = _require_record(record_id)

    if _has_active_task(record_id):
        raise TTSServiceError(409, "tts_task_running", "Для этой записи уже выполняется фоновая задача.")

    base_output_path = _absolute_project_path(record.get("base_output_path"))
    if base_output_path is None or not base_output_path.exists():
        raise TTSServiceError(409, "base_output_missing", "Сначала сгенерируйте исходный WAV.")

    _update_record(record_id, status="queued", error=None)
    process = _PROCESS_CTX.Process(
        target=_speed_worker,
        args=(record_id, normalized_speed),
        daemon=True,
        name=f"localgpt_tts_speed_{record_id}",
    )

    try:
        process.start()
    except Exception as exc:
        _update_record(record_id, status="error", error="Не удалось запустить обработку скорости.")
        raise TTSServiceError(500, "tts_task_start_failed", str(exc) or "tts_task_start_failed") from exc

    _register_task(record_id, "speed", process)
    latest = _read_json(_record_path(record_id)) or record
    return _public_record(latest)


def list_history() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in config.TTS_HISTORY_DIR.glob("tts_*.json"):
        payload = _read_json(path)
        if not payload:
            continue
        items.append(_history_summary(payload))

    items.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)
    return items


def get_history_item(record_id: str, *, raise_if_missing: bool = True) -> dict[str, Any] | None:
    if not record_id:
        if raise_if_missing:
            raise TTSServiceError(404, "tts_history_not_found", "Запись истории TTS не найдена.")
        return None

    payload = _read_json(_record_path(record_id))
    if not payload:
        if raise_if_missing:
            raise TTSServiceError(404, "tts_history_not_found", "Запись истории TTS не найдена.")
        return None

    return _public_record(payload)


def delete_history_item(record_id: str) -> None:
    record = _require_record(record_id)
    if _has_active_task(record_id):
        raise TTSServiceError(409, "tts_task_running", "Нельзя удалить запись во время фоновой обработки.")

    seen_paths: set[Path] = set()

    for path_value in (record.get("base_output_path"), record.get("processed_output_path")):
        path = _absolute_project_path(path_value)
        if path is not None:
            seen_paths.add(path)

    for payload in (record.get("processed_outputs") or {}).values():
        if isinstance(payload, dict):
            path = _absolute_project_path(payload.get("path"))
            if path is not None:
                seen_paths.add(path)

    for path in seen_paths:
        _safe_unlink(path)

    shutil.rmtree(_temp_dir(record_id), ignore_errors=True)

    history_path = _record_path(record_id)
    if not history_path.exists():
        raise TTSServiceError(404, "tts_history_not_found", "Запись истории TTS не найдена.")
    try:
        history_path.unlink()
    except OSError as exc:
        raise TTSServiceError(500, "tts_delete_failed", str(exc) or "tts_delete_failed") from exc


def clear_history() -> int:
    records = list_history()
    if not records:
        return 0

    active_ids = [item.get("id") for item in records if item.get("id") and _has_active_task(str(item.get("id")))]
    if active_ids:
        raise TTSServiceError(
            409,
            "tts_task_running",
            "Нельзя очистить историю, пока одна из записей ещё обрабатывается.",
        )

    deleted = 0
    for item in records:
        record_id = str(item.get("id") or "").strip()
        if not record_id:
            continue
        delete_history_item(record_id)
        deleted += 1
    return deleted


def resolve_output_file(record_id: str, *, variant: str, speed: float | None = None) -> tuple[str, str]:
    record = _require_record(record_id)

    path: Path | None = None
    filename = f"{record_id}.wav"

    if variant == "base":
        path = _absolute_project_path(record.get("base_output_path"))
        filename = f"{record_id}_base.wav"
    else:
        if speed is None:
            path = _absolute_project_path(record.get("processed_output_path"))
            if record.get("speed") is not None:
                filename = f"{record_id}_speed_{_speed_file_token(float(record['speed']))}.wav"
        else:
            normalized_speed = _normalized_speed(speed)
            processed_outputs = record.get("processed_outputs") or {}
            processed_payload = processed_outputs.get(_speed_label(normalized_speed))
            if isinstance(processed_payload, dict):
                path = _absolute_project_path(processed_payload.get("path"))
                filename = f"{record_id}_speed_{_speed_file_token(normalized_speed)}.wav"

    if path is None or not path.exists():
        raise TTSServiceError(404, "tts_output_not_found", "Файл озвучки не найден.")

    return str(path), filename


def cancel_all_tasks() -> int:
    with _LOCK:
        active_items = list(_TASKS.items())

    cancelled = 0
    for record_id, task in active_items:
        process = task.get("process")
        pid = task.get("pid")
        if process is not None and process.is_alive():
            try:
                process.terminate()
            except Exception:
                if pid:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                    except OSError:
                        pass
            process.join(timeout=1.0)
            if process.is_alive():
                try:
                    process.kill()
                except Exception:
                    if pid:
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                        except OSError:
                            pass
                process.join(timeout=1.0)
            cancelled += 1

        record = _read_json(_record_path(record_id))
        if record and record.get("status") in _ACTIVE_STATES:
            _update_record(
                record_id,
                status="error",
                error="Фоновая задача остановлена при завершении приложения.",
            )

    with _LOCK:
        _TASKS.clear()

    return cancelled
