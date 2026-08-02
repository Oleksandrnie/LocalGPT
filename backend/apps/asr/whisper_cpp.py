from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from app import config


_QUANT_SUFFIXES = ("", "-q8_0", "-q5_0", "-q5_1", "-q4_0", "-q4_1")
DEFAULT_TRANSCRIBE_LOG_MAX_BYTES = 2 * 1024 * 1024
DEFAULT_DECODER_GUARD_ARGS = (
    "--suppress-nst",
    "--no-fallback",
    "--no-speech-thold",
    "0.8",
)


def _resolve_path_template(raw: str, model_name: str) -> Path:
    value = raw.format(model=model_name)
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = config.PROJECT_ROOT / path
    return path.resolve()


def whisper_cpp_model_path(model_name: str) -> Path:
    configured = config.SETTINGS.whisper_cpp_model_path
    if configured:
        return _resolve_path_template(configured, model_name)

    models_dir = config.SETTINGS.whisper_cpp_models_dir
    candidates = [
        models_dir / f"ggml-{model_name}{suffix}.bin"
        for suffix in _QUANT_SUFFIXES
    ]
    candidates.extend(
        models_dir / f"{model_name}{suffix}.bin"
        for suffix in _QUANT_SUFFIXES
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return candidates[0].resolve()


def is_whisper_cpp_model_ready(model_name: str) -> bool:
    return whisper_cpp_model_path(model_name).exists()


def _binary_path() -> str:
    binary = config.SETTINGS.whisper_cpp_binary
    if not binary:
        binary = "whisper-cli"

    expanded = Path(binary).expanduser()
    if expanded.is_absolute():
        return str(expanded)
    if len(expanded.parts) > 1:
        return str((config.PROJECT_ROOT / expanded).resolve())

    resolved = shutil.which(binary)
    return resolved or binary


def whisper_cpp_binary_path() -> str:
    return _binary_path()


def is_whisper_cpp_binary_ready() -> bool:
    binary = _binary_path()
    path = Path(binary).expanduser()
    if path.is_absolute() or len(path.parts) > 1:
        return path.exists() and os.access(path, os.X_OK)

    resolved = shutil.which(binary)
    return bool(resolved and os.access(resolved, os.X_OK))


def whisper_cpp_coreml_path(model_name: str) -> Path:
    return whisper_cpp_model_path(model_name).parent / f"ggml-{model_name}-encoder.mlmodelc"


def whisper_cpp_vad_model_path() -> Path:
    return config.SETTINGS.whisper_cpp_models_dir / "ggml-silero-v6.2.0.bin"


def is_whisper_cpp_vad_ready() -> bool:
    return whisper_cpp_vad_model_path().is_file()


def is_whisper_cpp_coreml_ready(model_name: str) -> bool:
    if not config.SETTINGS.whisper_cpp_download_coreml:
        return True
    return whisper_cpp_coreml_path(model_name).is_dir()


def whisper_cpp_runtime_status(model_name: str) -> dict[str, Any]:
    model_path = whisper_cpp_model_path(model_name)
    binary_path = whisper_cpp_binary_path()
    coreml_path = whisper_cpp_coreml_path(model_name)
    model_ready = model_path.exists()
    binary_ready = is_whisper_cpp_binary_ready()
    vad_path = whisper_cpp_vad_model_path()
    vad_ready = is_whisper_cpp_vad_ready()
    coreml_required = bool(config.SETTINGS.whisper_cpp_download_coreml)
    coreml_ready = is_whisper_cpp_coreml_ready(model_name)
    warnings: list[str] = []

    if not model_ready:
        warnings.append(f"GGML-модель не найдена: {model_path}")
    if not binary_ready:
        warnings.append(f"whisper-cli не найден или не исполняемый: {binary_path}")
    if not vad_ready:
        warnings.append(f"Silero VAD model не найден: {vad_path}")
    if coreml_required and not coreml_ready:
        warnings.append(f"CoreML encoder не найден: {coreml_path}")

    return {
        "ready": model_ready and binary_ready and vad_ready,
        "model_installed": model_ready,
        "model_path": str(model_path),
        "runtime_installed": binary_ready and vad_ready,
        "runtime_binary": str(binary_path),
        "vad_installed": vad_ready,
        "vad_model_path": str(vad_path),
        "coreml_required": coreml_required,
        "coreml_installed": coreml_ready,
        "coreml_path": str(coreml_path),
        "warnings": warnings,
    }


def is_whisper_cpp_runtime_ready(model_name: str) -> bool:
    if not is_whisper_cpp_model_ready(model_name):
        return False
    return is_whisper_cpp_binary_ready() and is_whisper_cpp_vad_ready()


def _redacted_command(command: list[str]) -> list[str]:
    result: list[str] = []
    skip_next = False
    for idx, item in enumerate(command):
        if skip_next:
            skip_next = False
            continue
        result.append(item)
        if item == "--prompt" and idx + 1 < len(command):
            result.append(f"<prompt chars={len(command[idx + 1])}>")
            skip_next = True
    return result


def _log_transcription_event(payload: dict[str, Any]) -> None:
    try:
        max_bytes = int(os.getenv("TRANSCRIBE_LOG_MAX_BYTES", str(DEFAULT_TRANSCRIBE_LOG_MAX_BYTES)) or "0")
        if max_bytes <= 0:
            return
        config.TRANSCRIBE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if config.TRANSCRIBE_LOG_FILE.exists() and config.TRANSCRIBE_LOG_FILE.stat().st_size > max_bytes:
            backup_path = config.TRANSCRIBE_LOG_FILE.with_name(f"{config.TRANSCRIBE_LOG_FILE.name}.1")
            try:
                backup_path.unlink()
            except FileNotFoundError:
                pass
            config.TRANSCRIBE_LOG_FILE.replace(backup_path)
        with config.TRANSCRIBE_LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _prepare_audio(input_path: Path, temp_dir: Path) -> tuple[Path, dict[str, Any]]:
    info: dict[str, Any] = {
        "convert_audio": bool(config.SETTINGS.whisper_cpp_convert_audio),
        "source_path": str(input_path),
        "input_path": str(input_path),
        "converted": False,
        "ffmpeg_binary": config.SETTINGS.whisper_cpp_ffmpeg_binary,
    }
    if not config.SETTINGS.whisper_cpp_convert_audio:
        return input_path, info

    ffmpeg_binary = config.SETTINGS.whisper_cpp_ffmpeg_binary
    ffmpeg = shutil.which(ffmpeg_binary) or ffmpeg_binary
    if not ffmpeg:
        info["ffmpeg_found"] = False
        return input_path, info

    info["ffmpeg_binary"] = ffmpeg
    info["ffmpeg_found"] = True
    output_path = temp_dir / "input.wav"
    command = [
        ffmpeg,
        "-y",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    info["ffmpeg_command"] = command
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        info["ffmpeg_found"] = False
        return input_path, info
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        info["error"] = f"WHISPER_CPP_AUDIO_CONVERT_FAILED::{detail}"
        _log_transcription_event({"event": "whisper_cpp_audio_convert_error", "audio": info})
        raise RuntimeError(f"WHISPER_CPP_AUDIO_CONVERT_FAILED::{detail}") from exc

    if output_path.exists():
        info["input_path"] = str(output_path)
        info["converted"] = True
        info["format"] = "wav_pcm_s16le_16000hz_mono"
        return output_path, info
    return input_path, info


def _offset_to_seconds(value: Any) -> float:
    try:
        return max(0.0, float(value) / 1000.0)
    except (TypeError, ValueError):
        return 0.0


def _segments_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_segments = payload.get("transcription")
    if not isinstance(raw_segments, list):
        return []

    segments: list[dict[str, Any]] = []
    for item in raw_segments:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        offsets = item.get("offsets") if isinstance(item.get("offsets"), dict) else {}
        segments.append(
            {
                "start": _offset_to_seconds(offsets.get("from")),
                "end": _offset_to_seconds(offsets.get("to")),
                "text": text,
            }
        )
    return segments


def _dedupe_repeated_segments(
    segments: list[dict[str, Any]],
    *,
    max_repeats: int = 2,
    min_chars: int = 12,
) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    previous_key = ""
    repeat_count = 0

    for segment in segments:
        text = str(segment.get("text") or "").strip()
        key = " ".join(text.lower().split())
        if key and key == previous_key:
            repeat_count += 1
        else:
            previous_key = key
            repeat_count = 1

        if key and len(key) >= min_chars and repeat_count > max_repeats:
            continue
        deduped.append(segment)

    return deduped


def _language_from_payload(payload: dict[str, Any]) -> str | None:
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    language = str(result.get("language") or "").strip().lower()
    return language or None


def transcribe_with_whisper_cpp(
    *,
    audio_path: Path,
    model_name: str,
    prompt: str | None,
    language: str | None,
    beam_size: int,
    threads: int | None = None,
) -> dict[str, Any]:
    model_path = whisper_cpp_model_path(model_name)
    if not model_path.exists():
        raise RuntimeError(f"WHISPER_CPP_MODEL_NOT_FOUND::{model_path}")
    vad_model_path = whisper_cpp_vad_model_path()
    if not vad_model_path.is_file():
        raise RuntimeError(f"WHISPER_CPP_VAD_MODEL_NOT_FOUND::{vad_model_path}")

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="localgpt-whisper-cpp-") as temp_name:
        temp_dir = Path(temp_name)
        output_prefix = temp_dir / "transcript"
        input_path, audio_info = _prepare_audio(audio_path, temp_dir)
        resolved_threads = int(threads if threads is not None else config.SETTINGS.whisper_cpp_threads)
        command = [
            _binary_path(),
            "--model",
            str(model_path),
            "--file",
            str(input_path),
            "--language",
            language or "auto",
            "--beam-size",
            str(max(1, int(beam_size))),
            "--output-json",
            "--output-file",
            str(output_prefix),
            "--no-prints",
        ]
        if resolved_threads > 0:
            command.extend(["--threads", str(resolved_threads)])
        if prompt:
            command.extend(["--prompt", prompt])
        command.extend(DEFAULT_DECODER_GUARD_ARGS)
        command.extend(["--vad", "--vad-model", str(vad_model_path)])
        command.extend(config.SETTINGS.whisper_cpp_extra_args)
        runtime: dict[str, Any] = {
            "backend": "whisper_cpp",
            "binary": command[0],
            "model": model_name,
            "model_path": str(model_path),
            "source_audio_path": str(audio_path),
            "input_audio_path": str(input_path),
            "audio": audio_info,
            "language": language or "auto",
            "beam_size": max(1, int(beam_size)),
            "threads": resolved_threads,
            "threads_arg_used": resolved_threads > 0,
            "prompt_present": bool(prompt),
            "prompt_chars": len(prompt or ""),
            "decoder_guard_args": list(DEFAULT_DECODER_GUARD_ARGS),
            "vad_model_path": str(vad_model_path),
            "extra_args": list(config.SETTINGS.whisper_cpp_extra_args),
            "output_json": str(output_prefix.with_suffix(".json")),
            "command": _redacted_command(command),
        }
        _log_transcription_event({"event": "whisper_cpp_start", "runtime": runtime})

        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            runtime["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
            runtime["error"] = f"WHISPER_CPP_BINARY_NOT_FOUND::{command[0]}"
            _log_transcription_event({"event": "whisper_cpp_error", "runtime": runtime})
            raise RuntimeError(f"WHISPER_CPP_BINARY_NOT_FOUND::{command[0]}") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            runtime["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
            runtime["returncode"] = exc.returncode
            runtime["error"] = f"WHISPER_CPP_FAILED::{detail}"
            _log_transcription_event({"event": "whisper_cpp_error", "runtime": runtime})
            raise RuntimeError(f"WHISPER_CPP_FAILED::{detail}") from exc

        json_path = output_prefix.with_suffix(".json")
        if not json_path.exists():
            detail = (completed.stderr or completed.stdout or "").strip()
            runtime["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
            runtime["returncode"] = completed.returncode
            runtime["error"] = f"WHISPER_CPP_EMPTY_OUTPUT::{detail}"
            _log_transcription_event({"event": "whisper_cpp_error", "runtime": runtime})
            raise RuntimeError(f"WHISPER_CPP_EMPTY_OUTPUT::{detail}")

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            runtime["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
            runtime["returncode"] = completed.returncode
            runtime["error"] = "WHISPER_CPP_INVALID_OUTPUT"
            _log_transcription_event({"event": "whisper_cpp_error", "runtime": runtime})
            raise RuntimeError("WHISPER_CPP_INVALID_OUTPUT")

    segments = _dedupe_repeated_segments(_segments_from_payload(payload))
    text = "\n".join(segment["text"] for segment in segments).strip()
    runtime["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    runtime["returncode"] = completed.returncode
    runtime["detected_language"] = _language_from_payload(payload)
    runtime["segments_count"] = len(segments)
    runtime["text_chars"] = len(text)
    _log_transcription_event({"event": "whisper_cpp_done", "runtime": runtime})
    return {
        "text": text,
        "segments": segments,
        "language": runtime["detected_language"],
        "runtime": runtime,
    }
