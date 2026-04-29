from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app import config


_QUANT_SUFFIXES = ("", "-q8_0", "-q5_0", "-q5_1", "-q4_0", "-q4_1")


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


def is_whisper_cpp_runtime_ready(model_name: str) -> bool:
    if not is_whisper_cpp_model_ready(model_name):
        return False

    binary = config.SETTINGS.whisper_cpp_binary or "whisper-cli"
    expanded = Path(binary).expanduser()
    if expanded.is_absolute():
        return expanded.exists()
    if len(expanded.parts) > 1:
        return (config.PROJECT_ROOT / expanded).exists()
    return shutil.which(binary) is not None


def _prepare_audio(input_path: Path, temp_dir: Path) -> Path:
    if not config.SETTINGS.whisper_cpp_convert_audio:
        return input_path

    ffmpeg_binary = config.SETTINGS.whisper_cpp_ffmpeg_binary
    ffmpeg = shutil.which(ffmpeg_binary) or ffmpeg_binary
    if not ffmpeg:
        return input_path

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
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        return input_path
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"WHISPER_CPP_AUDIO_CONVERT_FAILED::{detail}") from exc

    return output_path if output_path.exists() else input_path


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
) -> dict[str, Any]:
    model_path = whisper_cpp_model_path(model_name)
    if not model_path.exists():
        raise RuntimeError(f"WHISPER_CPP_MODEL_NOT_FOUND::{model_path}")

    with tempfile.TemporaryDirectory(prefix="localgpt-whisper-cpp-") as temp_name:
        temp_dir = Path(temp_name)
        output_prefix = temp_dir / "transcript"
        input_path = _prepare_audio(audio_path, temp_dir)
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
        if config.SETTINGS.whisper_cpp_threads > 0:
            command.extend(["--threads", str(config.SETTINGS.whisper_cpp_threads)])
        if prompt:
            command.extend(["--prompt", prompt])
        command.extend(config.SETTINGS.whisper_cpp_extra_args)

        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise RuntimeError(f"WHISPER_CPP_BINARY_NOT_FOUND::{command[0]}") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise RuntimeError(f"WHISPER_CPP_FAILED::{detail}") from exc

        json_path = output_prefix.with_suffix(".json")
        if not json_path.exists():
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(f"WHISPER_CPP_EMPTY_OUTPUT::{detail}")

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("WHISPER_CPP_INVALID_OUTPUT")

    segments = _segments_from_payload(payload)
    text = " ".join(segment["text"] for segment in segments).strip()
    return {
        "text": text,
        "segments": segments,
        "language": _language_from_payload(payload),
    }
