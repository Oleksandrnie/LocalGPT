from __future__ import annotations

import json
import multiprocessing as mp
import os
import re
import signal
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from secrets import token_hex
from tempfile import NamedTemporaryFile
from typing import Any

from .. import config
from ..providers.tts.base import VoiceDefinition
from ..providers.tts.piper_provider import PiperProvider
from .audio_postprocess_service import apply_speed_to_wav

_PROCESS_CTX = mp.get_context("spawn")
_LOCK = threading.Lock()
_TASKS: dict[str, dict[str, Any]] = {}
_ACTIVE_STATES = {"queued", "generating", "processing_speed"}
_FINAL_STATES = {"completed", "error"}
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


def _provider_by_name(provider_name: str | None = None):
    selected = (provider_name or config.SETTINGS.tts_default_provider).strip().lower()
    provider = _PROVIDERS.get(selected)
    if provider is None:
        raise TTSServiceError(422, "unsupported_provider", f"Провайдер TTS не поддерживается: {selected}")
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


def _validate_text(text: str) -> str:
    clean = (text or "").strip()
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
            "message": provider_message,
            "voices_count": len(voices),
        }
    except TTSServiceError as exc:
        provider_available = False
        voices = []
        provider_payload = {
            "name": provider_name,
            "available": False,
            "message": exc.message,
            "voices_count": 0,
        }

    status = "ok" if config.SETTINGS.tts_enabled and provider_available else "degraded"
    if not config.SETTINGS.tts_enabled:
        status = "disabled"

    return {
        "status": status,
        "env": config.SETTINGS.env,
        "tts_enabled": config.SETTINGS.tts_enabled,
        "default_provider": config.SETTINGS.tts_default_provider,
        "audio_format": config.SETTINGS.tts_audio_format,
        "max_text_chars": config.SETTINGS.tts_max_text_chars,
        "speed_options": list(config.SETTINGS.tts_speed_options),
        "models_dir": str(config.TTS_MODELS_DIR),
        "piper_models_dir": str(config.PIPER_MODELS_DIR),
        "output_dir": str(config.TTS_OUTPUT_DIR),
        "history_dir": str(config.TTS_HISTORY_DIR),
        "temp_dir": str(config.TTS_TEMP_DIR),
        "provider": provider_payload,
    }


def list_voices() -> list[dict[str, object]]:
    provider = _provider_by_name(config.SETTINGS.tts_default_provider)
    return [voice.to_public_dict() for voice in provider.list_voices()]


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
