from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass
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
QWEN3_HYBRID_MODEL_RE = re.compile(r"(?:^|/)qwen3(?::|-)(?!.*(?:instruct|thinking))", re.IGNORECASE)


@dataclass(frozen=True)
class ChatCompletionResult:
    content: str
    reasoning: str = ""
    done_reason: str | None = None
    eval_count: int | None = None


@dataclass(frozen=True)
class ChatStreamEvent:
    content: str = ""
    reasoning: str = ""
    done: bool = False
    done_reason: str | None = None
    eval_count: int | None = None


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


def _messages_with_thinking_instruction(
    model_name: str,
    messages: list[dict[str, Any]],
    think: bool | None,
) -> list[dict[str, Any]]:
    if think is None or not QWEN3_HYBRID_MODEL_RE.search(str(model_name or "")):
        return messages
    prepared = [dict(message) for message in messages]
    marker = "/think" if think else "/no_think"
    for index in range(len(prepared) - 1, -1, -1):
        if str(prepared[index].get("role") or "") != "user":
            continue
        content = str(prepared[index].get("content") or "").rstrip()
        prepared[index]["content"] = f"{content}\n\n{marker}" if content else marker
        break
    return prepared


def _chat_payload(
    model_name: str,
    messages: list[dict[str, Any]],
    *,
    stream: bool,
    temperature: float | None,
    max_tokens: int | None,
    num_ctx: int | None,
    keep_alive: str | None,
    num_gpu: int | None,
    think: bool | None,
) -> dict[str, Any]:
    options: dict[str, Any] = {}
    if temperature is not None:
        options["temperature"] = temperature
    if max_tokens is not None:
        options["num_predict"] = int(max_tokens)
    if num_ctx is not None:
        options["num_ctx"] = int(num_ctx)
    if num_gpu is not None:
        options["num_gpu"] = int(num_gpu)

    payload: dict[str, Any] = {
        "model": model_name,
        "messages": _messages_with_thinking_instruction(model_name, messages, think),
        "stream": stream,
    }
    if think is not None:
        payload["think"] = bool(think)
    if options:
        payload["options"] = options
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    return payload


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


def _get_json(path: str, *, timeout: float | None = None) -> dict[str, Any]:
    url = f"{native_ollama_base_url()}{path}"
    req = request.Request(url, method="GET")
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
    allow_cpu_fallback: bool = True,
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
        if not allow_cpu_fallback:
            LOGGER.warning("Ollama Metal backend still unavailable for %s; CPU fallback is disabled.", model_name)
            raise RuntimeError(
                f"Ollama Metal backend failed for {model_name}; CPU fallback is disabled for this request."
            ) from exc
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


def chat_completion_result(
    model_name: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    num_ctx: int | None = None,
    keep_alive: str | None = None,
    num_gpu: int | None = None,
    allow_cpu_fallback: bool = True,
    think: bool | None = None,
) -> ChatCompletionResult:
    payload = _chat_payload(
        model_name,
        messages,
        stream=False,
        temperature=temperature,
        max_tokens=max_tokens,
        num_ctx=num_ctx,
        keep_alive=keep_alive,
        num_gpu=num_gpu,
        think=think,
    )

    if num_gpu == 0:
        unload_model(model_name, timeout=1.5)

    response = _post_json_with_metal_recovery(
        "/api/chat",
        payload,
        model_name=model_name,
        allow_cpu_fallback=allow_cpu_fallback,
    )
    message = response.get("message") if isinstance(response.get("message"), dict) else {}
    return ChatCompletionResult(
        content=str(message.get("content") or response.get("response") or ""),
        reasoning=str(message.get("thinking") or response.get("thinking") or ""),
        done_reason=str(response.get("done_reason") or "").strip() or None,
        eval_count=int(response["eval_count"]) if isinstance(response.get("eval_count"), int) else None,
    )


def chat_completion(
    model_name: str,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> str:
    return chat_completion_result(model_name, messages, **kwargs).content


def chat_completion_stream_events(
    model_name: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    num_ctx: int | None = None,
    keep_alive: str | None = None,
    num_gpu: int | None = None,
    allow_cpu_fallback: bool = True,
    think: bool | None = None,
) -> Iterator[ChatStreamEvent]:
    payload = _chat_payload(
        model_name,
        messages,
        stream=True,
        temperature=temperature,
        max_tokens=max_tokens,
        num_ctx=num_ctx,
        keep_alive=keep_alive,
        num_gpu=num_gpu,
        think=think,
    )

    if num_gpu == 0:
        unload_model(model_name, timeout=1.5)

    attempts = [payload, payload]
    if allow_cpu_fallback:
        attempts.append(_cpu_fallback_payload(payload))
    for attempt_index, current_payload in enumerate(attempts):
        yielded = False
        try:
            for parsed in _post_json_stream("/api/chat", current_payload):
                message = parsed.get("message") if isinstance(parsed.get("message"), dict) else {}
                event = ChatStreamEvent(
                    content=str(message.get("content") or parsed.get("response") or ""),
                    reasoning=str(message.get("thinking") or parsed.get("thinking") or ""),
                    done=bool(parsed.get("done")),
                    done_reason=str(parsed.get("done_reason") or "").strip() or None,
                    eval_count=int(parsed["eval_count"]) if isinstance(parsed.get("eval_count"), int) else None,
                )
                if event.content or event.reasoning:
                    yielded = True
                if event.content or event.reasoning or event.done:
                    yield event
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


def chat_completion_stream(
    model_name: str,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> Iterator[str]:
    for event in chat_completion_stream_events(model_name, messages, **kwargs):
        if event.content:
            yield event.content


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


def loaded_model_names(*, timeout: float = 1.0) -> set[str]:
    try:
        payload = _get_json("/api/ps", timeout=timeout)
    except RuntimeError as exc:
        LOGGER.debug("Failed to list Ollama loaded models: %s", exc)
        return set()
    models = payload.get("models")
    if not isinstance(models, list):
        return set()
    names: set[str] = set()
    for item in models:
        if not isinstance(item, dict):
            continue
        for key in ("name", "model"):
            name = str(item.get(key) or "").strip()
            if name:
                names.add(name)
    return names


def _ollama_runner_pids() -> list[int]:
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ollama.*runner"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        LOGGER.debug("Failed to list Ollama runner processes: %s", exc)
        return []
    pids: list[int] = []
    for line in result.stdout.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid > 0 and pid != os.getpid():
            pids.append(pid)
    return sorted(set(pids))


def force_unload_models(
    model_names: set[str] | list[str] | tuple[str, ...],
    *,
    unload_timeout: float = 1.0,
    wait_timeout: float = 1.5,
    terminate_stuck_runners: bool = True,
) -> dict[str, Any]:
    models = sorted({str(model or "").strip() for model in model_names if str(model or "").strip()})
    unloaded: list[str] = []
    unload_failed: list[str] = []
    for model in models:
        if unload_model(model, timeout=unload_timeout):
            unloaded.append(model)
        else:
            unload_failed.append(model)

    stuck_models: list[str] = []
    if models:
        deadline = time.monotonic() + max(0.0, wait_timeout)
        while True:
            loaded = loaded_model_names(timeout=0.75)
            stuck_models = [model for model in models if model in loaded]
            if not stuck_models or time.monotonic() >= deadline:
                break
            time.sleep(0.2)

    terminated_runner_pids: list[int] = []
    terminate_failed_pids: list[int] = []
    if stuck_models and terminate_stuck_runners:
        for pid in _ollama_runner_pids():
            try:
                os.kill(pid, signal.SIGTERM)
                terminated_runner_pids.append(pid)
            except OSError:
                terminate_failed_pids.append(pid)

    return {
        "unloaded_models": unloaded,
        "unload_failed": unload_failed,
        "stuck_models": stuck_models,
        "terminated_runner_pids": terminated_runner_pids,
        "terminate_failed_pids": terminate_failed_pids,
    }
