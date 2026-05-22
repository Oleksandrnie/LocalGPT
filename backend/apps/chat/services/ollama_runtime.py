from __future__ import annotations

import json
import logging
import time
from typing import Any, Iterator
from urllib import error, request
from urllib.parse import urlsplit, urlunsplit

from app import config

LOGGER = logging.getLogger(__name__)

ROUTER_MODEL_ID = "qwen3:0.6b"
HEAVY_KEEP_ALIVE_MODELS = {"mistral-nemo:12b"}
CODE_KEEP_ALIVE_MODELS = {"qwen2.5-coder:7b", "deepseek-coder:6.7b"}
METAL_BACKEND_ERROR_MARKERS = (
    "mtllibraryerrordomain",
    "mtlcompilerservice",
    "ggml_metal_init",
    "failed to initialize metal backend",
    "failed to initialize the metal library",
    "failed to allocate context",
)


def _normalize_keep_alive(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def is_immediate_keep_alive(value: Any) -> bool:
    return str(value or "").strip().lower() in {"0", "0s", "0m", "0h"}


def resolve_keep_alive(model_name: str, settings: dict[str, Any] | None = None, *, router: bool = False) -> str | None:
    effective = _normalize_keep_alive((settings or {}).get("ollama_keep_alive_effective"))
    if effective is not None:
        return effective
    explicit = _normalize_keep_alive((settings or {}).get("ollama_keep_alive"))
    if explicit is not None:
        return explicit
    model = str(model_name or "").strip()
    if router or model == ROUTER_MODEL_ID:
        return (
            _normalize_keep_alive((settings or {}).get("router_keep_alive"))
            or _normalize_keep_alive(config.SETTINGS.ollama_router_keep_alive)
        )
    if model in HEAVY_KEEP_ALIVE_MODELS:
        return (
            _normalize_keep_alive((settings or {}).get("heavy_model_keep_alive"))
            or _normalize_keep_alive(config.SETTINGS.ollama_heavy_keep_alive)
        )
    if model in CODE_KEEP_ALIVE_MODELS:
        return (
            _normalize_keep_alive((settings or {}).get("code_model_keep_alive"))
            or _normalize_keep_alive(config.SETTINGS.ollama_code_keep_alive)
        )
    return (
        _normalize_keep_alive((settings or {}).get("manual_keep_alive"))
        or _normalize_keep_alive(config.SETTINGS.ollama_manual_keep_alive)
        or _normalize_keep_alive(config.SETTINGS.ollama_chat_keep_alive)
    )


def apply_keep_alive_setting(
    model_name: str,
    settings: dict[str, Any] | None,
    *,
    router: bool = False,
) -> dict[str, Any]:
    payload = dict(settings or {})
    keep_alive = resolve_keep_alive(model_name, payload, router=router)
    if keep_alive is not None:
        payload["ollama_keep_alive"] = keep_alive
        payload["ollama_keep_alive_effective"] = keep_alive
    return payload


def native_ollama_base_url() -> str:
    base = str(config.SETTINGS.base_url or "http://localhost:11434/v1").strip().rstrip("/")
    parts = urlsplit(base)
    path = parts.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3] or ""
    return urlunsplit((parts.scheme, parts.netloc, path, "", "")).rstrip("/")


def is_metal_backend_error(value: Any) -> bool:
    text = str(value or "").lower()
    return any(marker in text for marker in METAL_BACKEND_ERROR_MARKERS)


def _cpu_fallback_payload(payload: dict[str, Any]) -> dict[str, Any]:
    fallback = dict(payload)
    options = dict(fallback.get("options") or {})
    options["num_gpu"] = 0
    fallback["options"] = options
    fallback["keep_alive"] = 0
    return fallback


def _post_json(path: str, payload: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
    url = f"{native_ollama_base_url()}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        kwargs = {} if timeout is None else {"timeout": timeout}
        with request.urlopen(req, **kwargs) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except OSError:
            body = str(exc)
        raise RuntimeError(f"Ollama API error {exc.code}: {body}") from exc
    except (OSError, error.URLError) as exc:
        raise RuntimeError(f"Ollama API request failed: {exc}") from exc

    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ollama API returned invalid JSON: {raw[:500]}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Ollama API returned a non-object response")
    return parsed


def _post_json_with_metal_recovery(
    path: str,
    payload: dict[str, Any],
    *,
    model_name: str,
    timeout: float | None = None,
) -> dict[str, Any]:
    try:
        return _post_json(path, payload, timeout=timeout)
    except RuntimeError as exc:
        if not is_metal_backend_error(exc):
            raise
        LOGGER.warning("Ollama Metal backend failed for %s; unloading model and retrying once.", model_name)

    unload_model(model_name, timeout=1.5)
    time.sleep(0.75)

    try:
        return _post_json(path, payload, timeout=timeout)
    except RuntimeError as exc:
        if not is_metal_backend_error(exc):
            raise
        LOGGER.warning("Ollama Metal backend still unavailable for %s; retrying with CPU fallback.", model_name)
        unload_model(model_name, timeout=1.5)
        time.sleep(0.75)
        return _post_json(path, _cpu_fallback_payload(payload), timeout=timeout)


def _post_json_stream(path: str, payload: dict[str, Any], *, timeout: float | None = None) -> Iterator[dict[str, Any]]:
    url = f"{native_ollama_base_url()}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        kwargs = {} if timeout is None else {"timeout": timeout}
        with request.urlopen(req, **kwargs) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"Ollama API returned invalid stream JSON: {line[:500]}") from exc
                if not isinstance(parsed, dict):
                    raise RuntimeError("Ollama API returned a non-object stream response")
                if parsed.get("error"):
                    raise RuntimeError(f"Ollama API stream error: {parsed.get('error')}")
                yield parsed
    except error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
        except OSError:
            body = str(exc)
        raise RuntimeError(f"Ollama API error {exc.code}: {body}") from exc
    except (OSError, error.URLError) as exc:
        raise RuntimeError(f"Ollama API request failed: {exc}") from exc


def chat_completion(
    model_name: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    keep_alive: str | None = None,
    num_gpu: int | None = None,
) -> str:
    options: dict[str, Any] = {}
    if temperature is not None:
        options["temperature"] = temperature
    if max_tokens is not None:
        options["num_predict"] = int(max_tokens)
    if num_gpu is not None:
        options["num_gpu"] = int(num_gpu)

    payload: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "stream": False,
    }
    if options:
        payload["options"] = options
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    if num_gpu == 0:
        unload_model(model_name, timeout=1.5)

    response = _post_json_with_metal_recovery("/api/chat", payload, model_name=model_name)
    message = response.get("message") if isinstance(response.get("message"), dict) else {}
    return str(message.get("content") or response.get("response") or "")


def chat_completion_stream(
    model_name: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    keep_alive: str | None = None,
    num_gpu: int | None = None,
) -> Iterator[str]:
    options: dict[str, Any] = {}
    if temperature is not None:
        options["temperature"] = temperature
    if max_tokens is not None:
        options["num_predict"] = int(max_tokens)
    if num_gpu is not None:
        options["num_gpu"] = int(num_gpu)

    payload: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "stream": True,
    }
    if options:
        payload["options"] = options
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    if num_gpu == 0:
        unload_model(model_name, timeout=1.5)

    attempts = [payload, payload, _cpu_fallback_payload(payload)]
    for attempt_index, current_payload in enumerate(attempts):
        yielded = False
        try:
            for parsed in _post_json_stream("/api/chat", current_payload):
                message = parsed.get("message") if isinstance(parsed.get("message"), dict) else {}
                text = str(message.get("content") or parsed.get("response") or "")
                if text:
                    yielded = True
                    yield text
            return
        except RuntimeError as exc:
            if yielded or not is_metal_backend_error(exc) or attempt_index >= len(attempts) - 1:
                raise
            if attempt_index == 0:
                LOGGER.warning("Ollama Metal backend failed for %s; unloading model and retrying once.", model_name)
                unload_model(model_name, timeout=1.5)
                time.sleep(0.75)
            else:
                LOGGER.warning("Ollama Metal backend still unavailable for %s; retrying with CPU fallback.", model_name)
                unload_model(model_name, timeout=1.5)
                time.sleep(0.75)


def load_model(model_name: str, *, keep_alive: str | None = None, timeout: float = 30.0) -> bool:
    model = str(model_name or "").strip()
    if not model:
        return False
    payload: dict[str, Any] = {"model": model, "prompt": "", "stream": False}
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    _post_json_with_metal_recovery("/api/generate", payload, model_name=model, timeout=timeout)
    return True


def unload_model(model_name: str, *, timeout: float = 3.0) -> bool:
    model = str(model_name or "").strip()
    if not model:
        return False
    try:
        _post_json("/api/generate", {"model": model, "keep_alive": 0}, timeout=timeout)
        return True
    except RuntimeError as exc:
        LOGGER.debug("Failed to unload Ollama model %s: %s", model, exc)
        return False
