from __future__ import annotations

import json
import logging
from typing import Any
from urllib import error, request
from urllib.parse import urlsplit, urlunsplit

from app import config

LOGGER = logging.getLogger(__name__)

ROUTER_MODEL_ID = "qwen3:0.6b"
HEAVY_KEEP_ALIVE_MODELS = {"mistral-nemo:12b"}
CODE_KEEP_ALIVE_MODELS = {"qwen2.5-coder:7b", "deepseek-coder:6.7b"}


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


def chat_completion(
    model_name: str,
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    keep_alive: str | None = None,
) -> str:
    options: dict[str, Any] = {}
    if temperature is not None:
        options["temperature"] = temperature
    if max_tokens is not None:
        options["num_predict"] = int(max_tokens)

    payload: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "stream": False,
    }
    if options:
        payload["options"] = options
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    response = _post_json("/api/chat", payload)
    message = response.get("message") if isinstance(response.get("message"), dict) else {}
    return str(message.get("content") or response.get("response") or "")


def load_model(model_name: str, *, keep_alive: str | None = None, timeout: float = 30.0) -> bool:
    model = str(model_name or "").strip()
    if not model:
        return False
    payload: dict[str, Any] = {"model": model, "prompt": "", "stream": False}
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    _post_json("/api/generate", payload, timeout=timeout)
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
