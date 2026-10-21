from __future__ import annotations

import json
import logging
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from fastapi import HTTPException

from .. import config

LOGGER = logging.getLogger(__name__)
MODEL_PULLS: dict[str, dict[str, Any]] = {}
MODEL_PULL_PROCS: dict[str, subprocess.Popen] = {}
MODEL_PULL_STREAMS: dict[str, Any] = {}
MODEL_PULL_CANCEL_EVENTS: dict[str, threading.Event] = {}
MODEL_PULL_LOCK = threading.Lock()
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
PULL_LOG_TAIL_LIMIT = 80
OLLAMA_API_PULL_TIMEOUT_SECONDS = 15
OLLAMA_API_SHOW_TIMEOUT_SECONDS = 5
THINKING_VALUE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
OLLAMA_MODEL_REF_RE = re.compile(
    r"(?:[A-Za-z0-9][A-Za-z0-9._-]*(?::[0-9]+)?/)*"
    r"[A-Za-z0-9][A-Za-z0-9._-]*(?::[A-Za-z0-9_][A-Za-z0-9._-]*)?"
)


def validate_pull_model_ref(model: str) -> str:
    """Accept registry references only, never commands or CLI options."""
    if not isinstance(model, str) or len(model) > 200 or not OLLAMA_MODEL_REF_RE.fullmatch(model):
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_ollama_model_ref", "message": "Укажите корректное имя модели Ollama (до 200 символов), без команд, пробелов и shell-синтаксиса."},
        )
    return model


def _size_gb(size: Any) -> float | None:
    if not isinstance(size, (int, float)):
        return None
    return round(float(size) / (1024**3), 2)


def _native_ollama_base_url() -> str:
    """Return the native Ollama API base for an OpenAI-compatible base URL."""
    base = str(config.SETTINGS.base_url or "http://localhost:11434/v1").strip().rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3].rstrip("/")
    return base or "http://localhost:11434"


def _redact_ollama_endpoint(endpoint: str) -> str:
    """Avoid writing credentials from a custom endpoint into application logs."""
    try:
        parsed = urlsplit(endpoint)
    except ValueError:
        return "<invalid Ollama endpoint>"
    if not parsed.scheme or not parsed.hostname:
        return "<invalid Ollama endpoint>"
    host = parsed.hostname
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def _ollama_cli_info() -> dict[str, str | None]:
    """Resolve the CLI actually visible to this backend without making it required."""
    cli_path = shutil.which("ollama")
    if not cli_path:
        return {"path": None, "version": None, "error": "not found in PATH"}
    try:
        result = subprocess.run(
            [cli_path, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
            env=config.OLLAMA_ENV,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"path": cli_path, "version": None, "error": str(exc)}
    if result.returncode != 0:
        return {
            "path": cli_path,
            "version": None,
            "error": (result.stderr or result.stdout or f"exit {result.returncode}").strip(),
        }
    return {"path": cli_path, "version": (result.stdout or result.stderr or "").strip(), "error": None}


def _file_modified_at(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return None


def _digest_blob_name(digest: str) -> str:
    return str(digest or "").replace(":", "-")


def _partial_blob_digest(filename: str) -> str | None:
    base = str(filename or "").split("-partial", 1)[0]
    if not base.startswith("sha256-"):
        return None
    return base.replace("sha256-", "sha256:", 1)


def _ollama_store_dirs() -> list[Path]:
    candidates = [
        getattr(getattr(config, "MODEL_PATHS", None), "ollama", None),
        config.OLLAMA_ENV.get("OLLAMA_MODELS") if isinstance(config.OLLAMA_ENV, dict) else None,
        Path.home() / ".ollama" / "models",
    ]
    result: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser().resolve()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _manifest_model_name(manifest_path: Path, store_dir: Path) -> str | None:
    try:
        rel = manifest_path.relative_to(store_dir / "manifests")
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 4:
        return None

    namespace = parts[1]
    model_parts = parts[2:-1]
    tag = parts[-1]
    if not model_parts or not tag:
        return None
    if namespace == "library":
        return f"{'/'.join(model_parts)}:{tag}"
    return f"{namespace}/{'/'.join(model_parts)}:{tag}"


def _inspect_storage_manifests() -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    storage_by_model: dict[str, dict[str, Any]] = {}
    digest_models: dict[str, set[str]] = {}

    for store_dir in _ollama_store_dirs():
        manifests_dir = store_dir / "manifests"
        blobs_dir = store_dir / "blobs"
        if not manifests_dir.exists():
            continue
        for manifest_path in manifests_dir.rglob("*"):
            if not manifest_path.is_file() or manifest_path.name.startswith("."):
                continue
            model_name = _manifest_model_name(manifest_path, store_dir)
            if not model_name:
                continue
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue

            blobs: list[dict[str, Any]] = []
            missing_blobs: list[str] = []
            total_size = 0
            descriptors = []
            config_descriptor = payload.get("config")
            if isinstance(config_descriptor, dict):
                descriptors.append(config_descriptor)
            layers = payload.get("layers")
            if isinstance(layers, list):
                descriptors.extend(item for item in layers if isinstance(item, dict))

            for descriptor in descriptors:
                digest = str(descriptor.get("digest") or "").strip()
                if not digest:
                    continue
                size = descriptor.get("size")
                if isinstance(size, (int, float)):
                    total_size += int(size)
                blob_path = blobs_dir / _digest_blob_name(digest)
                present = blob_path.exists()
                if not present:
                    missing_blobs.append(digest)
                blobs.append(
                    {
                        "digest": digest,
                        "size": size if isinstance(size, (int, float)) else None,
                        "size_gb": _size_gb(size),
                        "present": present,
                    }
                )
                digest_models.setdefault(digest, set()).add(model_name)

            complete = bool(blobs) and not missing_blobs
            store_entry = {
                "store_path": str(store_dir),
                "manifest_path": str(manifest_path),
                "complete": complete,
                "missing_blobs": missing_blobs,
                "size": total_size or None,
                "size_gb": _size_gb(total_size) if total_size else None,
                "modified_at": _file_modified_at(manifest_path),
            }
            current = storage_by_model.setdefault(
                model_name,
                {
                    "model": model_name,
                    "storage_present": False,
                    "storage_size": None,
                    "storage_size_gb": None,
                    "stores": [],
                },
            )
            current["stores"].append(store_entry)
            if complete:
                current["storage_present"] = True
            if total_size and (not current.get("storage_size") or total_size > int(current.get("storage_size") or 0)):
                current["storage_size"] = total_size
                current["storage_size_gb"] = _size_gb(total_size)

    return storage_by_model, digest_models


def _list_partial_blobs(digest_models: dict[str, set[str]]) -> list[dict[str, Any]]:
    partials: list[dict[str, Any]] = []
    for store_dir in _ollama_store_dirs():
        blobs_dir = store_dir / "blobs"
        if not blobs_dir.exists():
            continue
        for path in blobs_dir.glob("*-partial*"):
            if not path.is_file():
                continue
            digest = _partial_blob_digest(path.name)
            try:
                size = path.stat().st_size
            except OSError:
                size = None
            partials.append(
                {
                    "path": str(path),
                    "filename": path.name,
                    "store_path": str(store_dir),
                    "digest": digest,
                    "size": size,
                    "size_gb": _size_gb(size),
                    "modified_at": _file_modified_at(path),
                    "model_candidates": sorted(digest_models.get(digest or "", set())),
                }
            )
    partials.sort(key=lambda item: int(item.get("size") or 0), reverse=True)
    return partials


def _partial_models_by_name(partials: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for partial in partials:
        candidates = partial.get("model_candidates")
        if not isinstance(candidates, list):
            continue
        for model_name in candidates:
            target = str(model_name or "").strip()
            if not target:
                continue
            entry = result.setdefault(
                target,
                {
                    "model": target,
                    "count": 0,
                    "size": 0,
                    "size_gb": 0,
                    "largest_blob": None,
                    "store_paths": [],
                },
            )
            size = int(partial.get("size") or 0)
            entry["count"] = int(entry.get("count") or 0) + 1
            entry["size"] = int(entry.get("size") or 0) + size
            entry["size_gb"] = _size_gb(entry["size"])
            if size > int((entry.get("largest_blob") or {}).get("size") or 0):
                entry["largest_blob"] = partial
            store_path = partial.get("store_path")
            if store_path and store_path not in entry["store_paths"]:
                entry["store_paths"].append(store_path)
    return result


def _public_storage_summary(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    return {
        "model": value.get("model"),
        "storage_present": bool(value.get("storage_present")),
        "storage_size": value.get("storage_size"),
        "storage_size_gb": value.get("storage_size_gb"),
        "stores_count": len(value.get("stores") or []),
    }


def _public_partial_summary(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    return {
        "model": value.get("model"),
        "count": int(value.get("count") or 0),
        "size": int(value.get("size") or 0),
        "size_gb": value.get("size_gb"),
    }


def _public_partial_blob(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "size": value.get("size"),
        "size_gb": value.get("size_gb"),
        "modified_at": value.get("modified_at"),
        "model_candidates": list(value.get("model_candidates") or []),
    }


def _normalize_capabilities(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = re.split(r"[\s,]+", value)
    elif isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        raw_items = []
    aliases = {"image": "vision", "images": "vision"}
    result: list[str] = []
    for item in raw_items:
        normalized = str(item or "").strip().lower().replace("-", "_")
        normalized = aliases.get(normalized, normalized)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _normalize_thinking(value: Any) -> dict[str, Any] | None:
    """Keep only a bounded provider-declared control; absent is not unsupported."""
    if not isinstance(value, dict):
        return None
    raw_values = value.get("values")
    if not isinstance(raw_values, list) or not 1 <= len(raw_values) <= 32:
        return None

    def valid(item: Any) -> bool:
        return isinstance(item, bool) or (isinstance(item, str) and bool(THINKING_VALUE_RE.fullmatch(item)))

    if not all(valid(item) for item in raw_values):
        return None
    values: list[bool | str] = []
    for item in raw_values:
        if item not in values:
            values.append(item)
    default = value.get("default")
    if not valid(default) or default not in values:
        default = None
    return {"values": values, "default": default}


def _show_json_details(payload: dict[str, Any]) -> dict[str, Any]:
    raw_details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    model_info = payload.get("model_info") if isinstance(payload.get("model_info"), dict) else {}
    details: dict[str, Any] = {}

    architecture = str(raw_details.get("family") or model_info.get("general.architecture") or "").strip()
    parameters = str(raw_details.get("parameter_size") or "").strip()
    quantization = str(raw_details.get("quantization_level") or "").strip()
    if architecture:
        details["architecture"] = architecture
    if parameters:
        details["parameters"] = parameters
    if quantization:
        details["quantization"] = quantization

    context_length = next(
        (
            value
            for key, value in model_info.items()
            if str(key).endswith(".context_length") and isinstance(value, (int, float, str))
        ),
        None,
    )
    if context_length is not None:
        details["context_length"] = str(context_length)

    families = raw_details.get("families")
    if isinstance(families, list):
        normalized_families = [str(item).strip() for item in families if str(item or "").strip()]
        if normalized_families:
            details["families"] = normalized_families

    capabilities = _normalize_capabilities(payload.get("capabilities") or raw_details.get("capabilities"))
    if capabilities:
        details["capabilities"] = capabilities
        details["capabilities_confirmed"] = True
    thinking = _normalize_thinking(payload.get("thinking"))
    if thinking is not None:
        details["thinking"] = thinking
    return details


def _show_plain_details(stdout: str) -> dict[str, Any]:
    details: dict[str, Any] = {}
    in_capabilities = False
    capabilities: list[str] = []
    for line in (stdout or "").splitlines():
        stripped = line.strip()
        if not stripped:
            in_capabilities = False
            continue
        if stripped.lower() == "capabilities":
            in_capabilities = True
            continue
        if in_capabilities:
            normalized = _normalize_capabilities(stripped)
            if len(normalized) == 1:
                capability = normalized[0]
                if capability not in capabilities:
                    capabilities.append(capability)
                continue
            in_capabilities = False
        key, _, value = stripped.partition(" ")
        normalized_key = key.strip().lower().replace(" ", "_")
        clean_value = value.strip()
        if normalized_key in {"architecture", "parameters", "quantization"} and clean_value:
            details[normalized_key] = clean_value
        elif stripped.startswith("context length"):
            details["context_length"] = stripped.removeprefix("context length").strip()
        elif stripped.startswith("embedding length"):
            details["embedding_length"] = stripped.removeprefix("embedding length").strip()
    if capabilities:
        details["capabilities"] = capabilities
        details["capabilities_confirmed"] = True
    return details


def _show_model_details(model_name: str) -> dict[str, Any]:
    target = str(model_name or "").strip()
    if not target:
        return {}
    try:
        request = Request(
            f"{_native_ollama_base_url()}/api/show",
            data=json.dumps({"model": target}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=OLLAMA_API_SHOW_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
        if isinstance(payload, dict) and not payload.get("error"):
            return _show_json_details(payload)
    except (OSError, ValueError):
        # Older/unreachable native endpoints retain the existing CLI discovery.
        pass
    command = ["ollama", "show", target, "--json"]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            env=config.OLLAMA_ENV,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return {}
    if result.returncode == 0:
        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            return _show_json_details(payload)

    error_text = str(result.stderr or result.stdout or "").lower()
    if result.returncode != 0 and "unknown flag" not in error_text and "unknown shorthand" not in error_text:
        return {}
    try:
        plain = subprocess.run(
            ["ollama", "show", target],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            env=config.OLLAMA_ENV,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return {}
    if plain.returncode != 0:
        return {}
    return _show_plain_details(plain.stdout or "")


def _list_active_models() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["ollama", "ps"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            env=config.OLLAMA_ENV,
        )
    except FileNotFoundError as exc:  # pragma: no cover - зависит от окружения
        raise HTTPException(status_code=500, detail="Ollama не установлена или недоступна.") from exc
    except subprocess.SubprocessError as exc:  # pragma: no cover - зависит от окружения
        raise HTTPException(status_code=500, detail="Ошибка обращения к Ollama.") from exc

    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "не удалось получить список активных моделей").strip()
        raise HTTPException(status_code=500, detail={"code": "ollama_ps_failed", "message": msg})

    active: list[dict[str, Any]] = []
    for line in (result.stdout or "").splitlines():
        raw = line.strip()
        if not raw or raw.lower().startswith("name "):
            continue
        parts = raw.split()
        if not parts:
            continue
        active.append(
            {
                "name": parts[0],
                "id": parts[1] if len(parts) > 1 else None,
                "size_label": " ".join(parts[2:4]) if len(parts) > 3 else None,
                "processor": parts[4] if len(parts) > 4 else None,
                "context": parts[5] if len(parts) > 5 else None,
                "until": " ".join(parts[6:]) if len(parts) > 6 else None,
            }
        )
    return active


def _status_label(state: str) -> str:
    return {
        "active": "Активна",
        "installed": "Установлена",
        "downloading": "Загружается",
        "partial": "Недокачана",
        "configured": "Настроена, но не установлена",
        "missing": "Отсутствует",
    }.get(state, state)


def _normalize_pull_error_message(candidate: Any) -> str:
    text = ANSI_ESCAPE_RE.sub("", str(candidate or ""))
    text = text.replace("\r", "\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    progress_prefixes = (
        "pulling ",
        "verifying ",
        "writing manifest",
        "removing any unused layers",
        "success",
    )
    noise_markers = (" MB/", " GB/", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇")

    for line in reversed(lines):
        lowered = line.lower()
        if lowered in {"error", "failed"}:
            continue
        if lowered.startswith(progress_prefixes):
            continue
        if any(marker in line for marker in noise_markers):
            continue
        while lowered.startswith("error:"):
            line = line.split(":", 1)[1].strip()
            lowered = line.lower()
        if not line:
            continue

        network_markers = (
            "dial tcp",
            "connection refused",
            "connection reset",
            "context deadline exceeded",
            "tls handshake timeout",
            "i/o timeout",
            "no such host",
            "network is unreachable",
            "temporary failure",
            "unexpected eof",
            "service unavailable",
            "lookup ",
        )
        if any(marker in lowered for marker in network_markers):
            return f"Сетевая ошибка Ollama: {line}"
        return line
    return ""


def _extract_pull_error_message(*candidates: Any) -> str:
    for candidate in candidates:
        text = _normalize_pull_error_message(candidate)
        if not text:
            continue
        return text
    return ""


def _public_pull_status(data: dict[str, Any]) -> dict[str, Any]:
    copy = dict(data)
    copy.pop("_last_completed", None)
    copy.pop("_last_ts", None)
    copy.pop("output_tail", None)
    return copy


def _append_pull_output(task_id: str, line: str) -> None:
    clean = ANSI_ESCAPE_RE.sub("", str(line or "")).replace("\r", "\n").strip()
    if not clean:
        return
    with MODEL_PULL_LOCK:
        entry = MODEL_PULLS.get(task_id)
        if not entry:
            return
        tail = list(entry.get("output_tail") or [])
        tail.append(clean)
        entry["output_tail"] = tail[-PULL_LOG_TAIL_LIMIT:]


def _pull_statuses() -> list[dict[str, Any]]:
    with MODEL_PULL_LOCK:
        return [_public_pull_status(item) for item in MODEL_PULLS.values()]


def _update_pull(task_id: str, **fields: Any) -> None:
    with MODEL_PULL_LOCK:
        if task_id not in MODEL_PULLS:
            return
        MODEL_PULLS[task_id].update(fields)
        if fields.get("state") == "canceled":
            MODEL_PULL_PROCS.pop(task_id, None)


def _list_local_models() -> list[dict[str, Any]]:
    cmd_json = ["ollama", "list", "--json"]
    try:
        result = subprocess.run(
            cmd_json,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            env=config.OLLAMA_ENV,
        )
    except FileNotFoundError as exc:  # pragma: no cover - зависит от окружения
        raise HTTPException(status_code=500, detail="Ollama не установлена или недоступна.") from exc
    except subprocess.SubprocessError as exc:  # pragma: no cover - зависит от окружения
        raise HTTPException(status_code=500, detail="Ошибка обращения к Ollama.") from exc

    stdout = result.stdout or ""
    stderr = (result.stderr or "").strip()
    fallback_plain = result.returncode != 0 and "unknown flag: --json" in stderr.lower()

    lines: list[str] = []
    if not fallback_plain:
        if result.returncode != 0:
            msg = stderr or "не удалось получить список моделей"
            raise HTTPException(status_code=500, detail={"code": "ollama_list_failed", "message": msg})
        lines = stdout.splitlines()
    else:
        try:
            plain = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
                env=config.OLLAMA_ENV,
            )
        except Exception as exc:  # pragma: no cover - зависит от окружения
            raise HTTPException(status_code=500, detail={"code": "ollama_list_failed", "message": str(exc)}) from exc
        if plain.returncode != 0:
            msg = (plain.stderr or plain.stdout or "не удалось получить список моделей").strip()
            raise HTTPException(status_code=500, detail={"code": "ollama_list_failed", "message": msg})
        lines = (plain.stdout or "").splitlines()
        lines = [line for line in lines if line.strip() and not line.lower().startswith("name ")]

    models: list[dict[str, Any]] = []
    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
            name = (payload.get("model") or payload.get("name") or "").strip()
            size = payload.get("size")
            modified_at = payload.get("modified_at")
            digest = payload.get("digest") or payload.get("id")
            size_label = None
            details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
        except json.JSONDecodeError:
            parts = raw.split()
            if not parts:
                continue
            name = parts[0]
            size = None
            modified_at = None
            digest = parts[1] if len(parts) > 1 else None
            size_label = " ".join(parts[2:4]) if len(parts) > 3 else None
            modified_at = " ".join(parts[4:]) if len(parts) > 4 else None
            details = {}
        if not name:
            continue
        runtime_details = _show_model_details(name)
        if runtime_details:
            details = {**details, **runtime_details}
        # Only /show declares this control; never publish unvalidated list data.
        details.pop("thinking", None)
        thinking = _normalize_thinking(runtime_details.get("thinking"))
        if thinking is not None:
            details["thinking"] = thinking
        capabilities = _normalize_capabilities(details.get("capabilities"))
        models.append(
            {
                "name": name,
                "id": digest,
                "digest": digest,
                "size": size,
                "size_gb": _size_gb(size),
                "size_label": size_label,
                "modified_at": modified_at,
                "installed": True,
                "runtime_installed": True,
                "details": details,
                "capabilities": capabilities,
                "capabilities_confirmed": bool(details.get("capabilities_confirmed") and capabilities),
                "thinking": thinking,
            }
        )
    return models


def _update_pull_progress(task_id: str, payload: dict[str, Any], progress: dict[str, float]) -> None:
    """Apply one streamed `/api/pull` progress event to a download task."""
    status_text = str(payload.get("status") or payload.get("digest") or "").strip()
    error_text = str(payload.get("error") or payload.get("message") or "").strip()
    total = payload.get("total")
    completed = payload.get("completed")
    fields: dict[str, Any] = {"state": "running", "message": status_text or error_text or "Загрузка модели…"}
    if isinstance(total, (int, float)) and isinstance(completed, (int, float)) and total > 0:
        now = time.time()
        previous_completed = progress["completed"]
        delta_bytes = completed - previous_completed
        delta_time = max(now - progress["timestamp"], 1e-3)
        speed_mbps = None
        eta_seconds = None
        if delta_bytes > 0:
            bytes_per_second = delta_bytes / delta_time
            speed_mbps = round(bytes_per_second / (1024 * 1024), 2)
            eta_seconds = round((total - completed) / bytes_per_second) if bytes_per_second else None
        progress["completed"] = float(completed)
        progress["timestamp"] = now
        fields.update(
            completed=completed,
            total=total,
            percent=round(100 * completed / total, 2),
            speed_mbps=speed_mbps,
            eta_seconds=eta_seconds,
            _last_completed=completed,
            _last_ts=now,
        )
    _update_pull(task_id, **fields)


def _pull_was_canceled(task_id: str) -> bool:
    with MODEL_PULL_LOCK:
        entry = MODEL_PULLS.get(task_id, {})
        cancel_event = MODEL_PULL_CANCEL_EVENTS.get(task_id)
    return entry.get("state") == "canceled" or bool(cancel_event and cancel_event.is_set())


def _run_api_model_pull(task_id: str, model: str) -> bool:
    """Run a native Ollama `/api/pull` stream. Return False only when CLI fallback is safe."""
    endpoint = f"{_native_ollama_base_url()}/api/pull"
    body = json.dumps({"name": model, "stream": True}).encode("utf-8")
    request = Request(endpoint, data=body, headers={"Content-Type": "application/json"}, method="POST")
    _update_pull(task_id, transport="api", command="POST /api/pull", endpoint=_redact_ollama_endpoint(endpoint))
    LOGGER.info("Ollama pull task %s using HTTP API POST %s", task_id, _redact_ollama_endpoint(endpoint))

    try:
        response = urlopen(request, timeout=OLLAMA_API_PULL_TIMEOUT_SECONDS)
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        message = _extract_pull_error_message(body_text, str(exc)) or f"Ollama API error {exc.code}"
        LOGGER.error("Ollama pull API request failed (%s): %s", exc.code, message)
        if exc.code in {404, 405, 501}:
            return False
        _update_pull(task_id, state="error", message=message, reason=message, finished_at=time.time(), stderr=body_text)
        return True
    except (URLError, OSError) as exc:
        LOGGER.warning("Ollama pull API is unavailable at %s: %s", _redact_ollama_endpoint(endpoint), exc)
        return False

    progress = {"completed": 0.0, "timestamp": time.time()}
    last_error = ""
    try:
        with MODEL_PULL_LOCK:
            MODEL_PULL_STREAMS[task_id] = response
        for raw_line in response:
            if _pull_was_canceled(task_id):
                break
            line = raw_line.decode("utf-8", errors="replace").strip() if isinstance(raw_line, bytes) else str(raw_line).strip()
            if not line:
                continue
            _append_pull_output(task_id, line)
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                last_error = line
                continue
            if not isinstance(payload, dict):
                last_error = line
                continue
            if payload.get("error"):
                last_error = str(payload["error"])
                break
            _update_pull_progress(task_id, payload, progress)
    except (HTTPError, URLError, OSError) as exc:
        if not _pull_was_canceled(task_id):
            last_error = str(exc)
            LOGGER.error("Ollama pull API stream failed: %s", exc)
    finally:
        try:
            response.close()
        except OSError:
            pass
        with MODEL_PULL_LOCK:
            MODEL_PULL_STREAMS.pop(task_id, None)

    finished = time.time()
    if _pull_was_canceled(task_id):
        _update_pull(task_id, state="canceled", message="Остановлено пользователем", finished_at=finished)
        return True
    if last_error:
        message = _extract_pull_error_message(last_error) or "Не удалось скачать модель через Ollama API."
        LOGGER.error("Ollama pull API error: %s", message)
        _update_pull(task_id, state="error", message=message, reason=message, finished_at=finished, stderr=last_error)
        return True
    _update_pull(task_id, state="completed", message="Готово", finished_at=finished)
    return True


def _run_cli_model_pull(task_id: str, model: str, cli_path: str) -> None:
    """Compatible fallback for servers without `/api/pull`; never pass unsupported `--json`."""
    command = [cli_path, "pull", model]
    _update_pull(task_id, transport="cli", command=" ".join(command))
    LOGGER.info("Ollama pull task %s using CLI command: %s", task_id, " ".join(command))
    last_output_line = ""
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=config.OLLAMA_ENV
        )
        with MODEL_PULL_LOCK:
            MODEL_PULL_PROCS[task_id] = process
        stdout, stderr = process.communicate()
        combined_lines = [line.strip() for line in f"{stdout}\n{stderr}".splitlines() if line.strip()]
        for line in combined_lines[-PULL_LOG_TAIL_LIMIT:]:
            _append_pull_output(task_id, line)
        last_output_line = combined_lines[-1] if combined_lines else ""
    except FileNotFoundError:
        _update_pull(task_id, state="error", message="Ollama не установлена", finished_at=time.time())
        return
    except (OSError, subprocess.SubprocessError) as exc:
        message = str(exc)
        LOGGER.error("Ollama CLI pull failed before completion: %s", message)
        _update_pull(task_id, state="error", message=message, reason=message, finished_at=time.time(), stderr=message)
        return
    finally:
        with MODEL_PULL_LOCK:
            MODEL_PULL_PROCS.pop(task_id, None)

    finished = time.time()
    if _pull_was_canceled(task_id):
        _update_pull(task_id, state="canceled", message="Остановлено пользователем", finished_at=finished)
    elif process.returncode == 0:
        _update_pull(task_id, state="completed", message="Готово", finished_at=finished)
    else:
        message = _extract_pull_error_message(last_output_line) or "Не удалось скачать модель через Ollama CLI."
        stderr_text = (stderr or "").strip()
        LOGGER.error("Ollama CLI pull failed (exit %s): %s; stderr: %s", process.returncode, message, stderr_text)
        _update_pull(task_id, state="error", message=message, reason=message, finished_at=finished, stderr=stderr_text)


def _run_model_pull(task_id: str, model: str) -> None:
    start_ts = time.time()
    cli_info = _ollama_cli_info()
    _update_pull(
        task_id,
        state="running",
        started_at=start_ts,
        cli_path=cli_info["path"],
        cli_version=cli_info["version"],
    )
    LOGGER.info(
        "Ollama pull task %s: cli_path=%s cli_version=%s endpoint=%s",
        task_id,
        cli_info["path"] or "<not found>",
        cli_info["version"] or cli_info["error"] or "<unknown>",
        _redact_ollama_endpoint(_native_ollama_base_url()),
    )
    if _pull_was_canceled(task_id):
        _update_pull(task_id, state="canceled", message="Остановлено пользователем", finished_at=time.time())
        return
    api_handled = _run_api_model_pull(task_id, model)
    if not api_handled:
        cli_path = cli_info["path"]
        if cli_path:
            _run_cli_model_pull(task_id, model, cli_path)
        else:
            message = "Ollama API недоступен, а бинарник Ollama не найден в PATH."
            _update_pull(task_id, state="error", message=message, reason=message, finished_at=time.time())
    with MODEL_PULL_LOCK:
        if task_id in MODEL_PULLS:
            MODEL_PULLS[task_id]["finished_at"] = MODEL_PULLS[task_id].get("finished_at") or time.time()
        MODEL_PULL_CANCEL_EVENTS.pop(task_id, None)


def start_model_pull(model: str) -> dict[str, Any]:
    validate_pull_model_ref(model)
    task_id = uuid.uuid4().hex
    entry = {
        "task_id": task_id,
        "model": model,
        "state": "pending",
        "message": "Запуск загрузки…",
        "started_at": None,
        "finished_at": None,
        "completed": None,
        "total": None,
        "output_tail": [],
        "transport": None,
    }
    with MODEL_PULL_LOCK:
        active = next(
            (
                item
                for item in MODEL_PULLS.values()
                if item.get("model") == model and item.get("state") in {"pending", "running"}
            ),
            None,
        )
        if active:
            return _public_pull_status(active)
        MODEL_PULLS[task_id] = entry
        MODEL_PULL_CANCEL_EVENTS[task_id] = threading.Event()

    thread = threading.Thread(target=_run_model_pull, args=(task_id, model), daemon=True)
    thread.start()
    return _public_pull_status(entry)


def cancel_model_pull(task_id: str) -> dict[str, Any]:
    with MODEL_PULL_LOCK:
        entry = MODEL_PULLS.get(task_id)
        process = MODEL_PULL_PROCS.get(task_id)
        stream = MODEL_PULL_STREAMS.get(task_id)
        cancel_event = MODEL_PULL_CANCEL_EVENTS.get(task_id)
    if not entry:
        raise HTTPException(status_code=404, detail="task_not_found")
    if entry.get("state") in {"completed", "error", "canceled"}:
        return _public_pull_status(entry)

    _update_pull(task_id, state="canceled", message="Остановлено пользователем", finished_at=time.time())
    if cancel_event:
        cancel_event.set()
    if stream:
        try:
            stream.close()
        except OSError:
            pass
    if process and process.poll() is None:
        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        finally:
            with MODEL_PULL_LOCK:
                MODEL_PULL_PROCS.pop(task_id, None)

    return _public_pull_status(MODEL_PULLS[task_id])


def pause_model_pull(task_id: str) -> dict[str, Any]:
    with MODEL_PULL_LOCK:
        entry = MODEL_PULLS.get(task_id)
        process = MODEL_PULL_PROCS.get(task_id)
    if not entry:
        raise HTTPException(status_code=404, detail="task_not_found")
    if entry.get("transport") == "api":
        raise HTTPException(
            status_code=409,
            detail="Пауза недоступна для потоковой загрузки через Ollama API; остановите и возобновите загрузку позже.",
        )
    if entry.get("state") not in {"running"} or process is None:
        return _public_pull_status(entry)
    try:
        process.send_signal(signal.SIGSTOP)
        _update_pull(task_id, state="paused", message="Пауза", finished_at=None)
    except Exception as exc:  # pragma: no cover - сигналы зависят от ОС
        raise HTTPException(status_code=500, detail="Не удалось поставить загрузку модели на паузу.") from exc
    return _public_pull_status(MODEL_PULLS[task_id])


def resume_model_pull(task_id: str) -> dict[str, Any]:
    with MODEL_PULL_LOCK:
        entry = MODEL_PULLS.get(task_id)
        process = MODEL_PULL_PROCS.get(task_id)
    if not entry:
        raise HTTPException(status_code=404, detail="task_not_found")
    if entry.get("state") not in {"paused"} or process is None:
        return _public_pull_status(entry)
    try:
        process.send_signal(signal.SIGCONT)
        _update_pull(task_id, state="running", message="Возобновлено", finished_at=None)
    except Exception as exc:  # pragma: no cover - сигналы зависят от ОС
        raise HTTPException(status_code=500, detail="Не удалось возобновить загрузку модели.") from exc
    return _public_pull_status(MODEL_PULLS[task_id])


def list_models() -> dict[str, Any]:
    error = None
    try:
        installed = _list_local_models()
    except HTTPException as exc:
        installed = []
        error = exc.detail
        LOGGER.warning("Оllama list failed: %s", exc.detail)
    active_error = None
    try:
        active = _list_active_models()
    except HTTPException as exc:
        active = []
        active_error = exc.detail
        LOGGER.warning("Оllama ps failed: %s", exc.detail)

    downloads = _pull_statuses()
    storage_by_model, digest_models = _inspect_storage_manifests()
    partial_blobs = _list_partial_blobs(digest_models)
    partial_by_model = _partial_models_by_name(partial_blobs)

    active_names = {item.get("name") for item in active if item.get("name")}
    installed_by_name = {item.get("name"): item for item in installed if item.get("name")}
    installed_names = set(installed_by_name)
    configured_ids = {
        item.get("id")
        for item in [
            *config.MODEL_CATALOG,
            *getattr(config, "VISION_MODEL_CATALOG", []),
            *getattr(config, "UTILITY_MODEL_CATALOG", []),
        ]
        if item.get("id")
    }
    download_by_model = {
        item.get("model"): item
        for item in downloads
        if item.get("model") and item.get("state") in {"pending", "running", "paused"}
    }

    for item in installed:
        name = item.get("name")
        if not name:
            continue
        item["configured"] = name in configured_ids
        item["active"] = name in active_names
        item["downloading"] = name in download_by_model
        item["partial"] = name in partial_by_model and name not in installed_names
        item["partial_blob_found"] = name in partial_by_model
        item["missing"] = False
        item["not_installed"] = False
        item["state"] = "active" if item["active"] else "installed"
        item["status"] = item["state"]
        item["status_label"] = _status_label(item["state"])
        if storage_by_model.get(name):
            item["storage"] = _public_storage_summary(storage_by_model[name])

    def _catalog_item(item: dict[str, Any]) -> dict[str, Any]:
        model_id = str(item.get("id") or "").strip()
        installed_info = installed_by_name.get(model_id)
        download_info = download_by_model.get(model_id)
        partial_info = partial_by_model.get(model_id)
        storage_info = storage_by_model.get(model_id)
        runtime_installed = bool(installed_info)
        declared_capabilities = _normalize_capabilities(item.get("capabilities"))
        runtime_capabilities = _normalize_capabilities((installed_info or {}).get("capabilities"))
        active_now = model_id in active_names
        downloading_now = bool(download_info and download_info.get("state") in {"pending", "running", "paused"})
        partial_now = bool(partial_info and not runtime_installed)

        if downloading_now:
            state = "downloading"
        elif active_now:
            state = "active"
        elif runtime_installed:
            state = "installed"
        elif partial_now:
            state = "partial"
        else:
            state = "configured"

        return {
            **item,
            "name": model_id,
            "label": item.get("title"),
            "configured": True,
            "installed": runtime_installed,
            "runtime_installed": runtime_installed,
            "active": active_now,
            "downloading": downloading_now,
            "partial": partial_now,
            "partial_blob_found": bool(partial_info),
            "missing": not runtime_installed,
            "not_installed": not runtime_installed,
            "selected": False,
            "state": state,
            "status": state,
            "status_label": _status_label(state),
            "runtime": installed_info,
            "declared_capabilities": declared_capabilities,
            "capabilities": runtime_capabilities or declared_capabilities,
            "capabilities_confirmed": bool(
                installed_info
                and installed_info.get("capabilities_confirmed")
                and runtime_capabilities
            ),
            "thinking": _normalize_thinking((installed_info or {}).get("thinking")),
            "download": download_info,
            "partial_info": _public_partial_summary(partial_info),
            "storage": _public_storage_summary(storage_info),
        }

    catalog = [_catalog_item(item) for item in config.MODEL_CATALOG]
    vision_catalog = [_catalog_item(item) for item in getattr(config, "VISION_MODEL_CATALOG", [])]
    utility = [_catalog_item(item) for item in getattr(config, "UTILITY_MODEL_CATALOG", [])]
    return {
        "installed": installed,
        "models": [item.get("name") for item in installed if item.get("name")],
        "active": active,
        "catalog": catalog,
        "vision_catalog": vision_catalog,
        "utility": utility,
        "recommended": catalog,
        "downloads": downloads,
        "partial_blobs": [_public_partial_blob(item) for item in partial_blobs],
        "storage_models": [
            summary
            for item in storage_by_model.values()
            if (summary := _public_storage_summary(item)) is not None
        ],
        "diagnostics": {
            "runtime_installed_count": len(installed_names),
            "active_count": len(active_names),
            "configured_count": len(configured_ids),
            "partial_blob_count": len(partial_blobs),
            "storage_model_count": len(storage_by_model),
            "runtime_available": not bool(active_error),
        },
        "error": "model_runtime_unavailable" if error else None,
    }


def is_model_installed(model_name: str) -> bool:
    target = (model_name or "").strip()
    if not target:
        return False
    return any(item.get("name") == target for item in _list_local_models())


def delete_model(model_name: str) -> dict[str, Any]:
    target = (model_name or "").strip()
    if not target:
        raise HTTPException(status_code=422, detail={"code": "model_required", "message": "Укажите модель"})

    try:
        result = subprocess.run(
            ["ollama", "rm", target], capture_output=True, text=True, check=False, timeout=30, env=config.OLLAMA_ENV
        )
    except FileNotFoundError as exc:  # pragma: no cover - зависит от окружения
        raise HTTPException(status_code=500, detail="Ollama не установлена или недоступна.") from exc
    except subprocess.SubprocessError as exc:  # pragma: no cover - зависит от окружения
        raise HTTPException(status_code=500, detail="Ошибка удаления модели через Ollama") from exc

    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "Не удалось удалить модель").strip()
        raise HTTPException(status_code=500, detail={"code": "ollama_rm_failed", "message": msg})

    return {"deleted": target}


def pull_status(task_id: str) -> dict[str, Any]:
    with MODEL_PULL_LOCK:
        entry = MODEL_PULLS.get(task_id)
    if not entry:
        raise HTTPException(status_code=404, detail="task_not_found")
    return _public_pull_status(entry)


def pull_statuses() -> dict[str, Any]:
    return {"downloads": _pull_statuses()}
