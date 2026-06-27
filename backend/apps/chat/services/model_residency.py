from __future__ import annotations

import logging
import threading
from typing import Any

from app import config
from backend.apps.chat.services import ollama_runtime

LOGGER = logging.getLogger(__name__)

ROUTER_MODEL_ID = "qwen3:0.6b"
LOCAL_CALCULATOR_TARGET = "__local_calculator__"

MODEL_WEIGHT_CLASS = {
    "qwen2.5:3b-instruct": "light",
    "qwen3:4b": "light",
    "qwen2.5:7b-instruct": "medium",
    "qwen3:8b": "medium",
    "qwen2.5-coder:7b": "code",
    "deepseek-coder:6.7b": "code",
    "mistral-nemo:12b": "heavy",
    "qwen3:0.6b": "router",
}
TARGET_MODEL_CLASSES = {"light", "medium", "code", "heavy"}
LARGE_TARGET_CLASSES = {"medium", "code", "heavy"}

_LOCK = threading.Lock()
_ACTIVE_TARGET_MODELS: list[str] = []
_ROUTER_MODEL_ACTIVE = False
_LAST_MODE: str | None = None


def _normalize_keep_alive(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _keep_alive_seconds(value: str | None) -> int | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    unit = text[-1]
    raw_number = text[:-1] if unit in {"s", "m", "h"} else text
    try:
        amount = int(raw_number)
    except ValueError:
        return None
    if amount < 0:
        return None
    if unit == "h":
        return amount * 3600
    if unit == "m":
        return amount * 60
    return amount


def _at_least_keep_alive(value: str | None, minimum: str) -> str:
    current = _normalize_keep_alive(value)
    minimum_value = _normalize_keep_alive(minimum) or "5m"
    current_seconds = _keep_alive_seconds(current)
    minimum_seconds = _keep_alive_seconds(minimum_value)
    if current is None or current_seconds is None or minimum_seconds is None or current_seconds < minimum_seconds:
        return minimum_value
    return current


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def _max_resident_target_models(settings: dict[str, Any] | None = None) -> int:
    raw = (settings or {}).get("max_resident_target_models", config.SETTINGS.max_resident_target_models)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 2
    return max(1, min(5, value))


def _allow_light_with_heavy(settings: dict[str, Any] | None = None) -> bool:
    return _coerce_bool((settings or {}).get("allow_light_with_heavy"), config.SETTINGS.allow_light_with_heavy)


def _single_large_target_model(settings: dict[str, Any] | None = None) -> bool:
    return _coerce_bool((settings or {}).get("single_large_target_model"), config.SETTINGS.single_large_target_model)


def model_weight_class(model_name: str | None) -> str:
    return MODEL_WEIGHT_CLASS.get(str(model_name or "").strip(), "medium")


def is_router_model(model_name: str | None) -> bool:
    return model_weight_class(model_name) == "router"


def is_target_model(model_name: str | None) -> bool:
    model = str(model_name or "").strip()
    return bool(model) and model != LOCAL_CALCULATOR_TARGET and model_weight_class(model) in TARGET_MODEL_CLASSES


def _remove_model(active: list[str], model_name: str) -> None:
    while model_name in active:
        active.remove(model_name)


def _evict_model(active: list[str], model_name: str, evicted: list[str], policies: list[str], policy: str) -> None:
    if model_name not in active:
        return
    _remove_model(active, model_name)
    if model_name not in evicted:
        evicted.append(model_name)
        policies.append(policy)


def _apply_heavy_policy(active: list[str], target_model: str, settings: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    evicted: list[str] = []
    policies: list[str] = []
    allow_light = _allow_light_with_heavy(settings)

    if model_weight_class(target_model) != "heavy":
        return evicted, policies

    light_models = [item for item in active if model_weight_class(item) == "light" and item != target_model]
    keep_light = light_models[-1:] if allow_light else []

    for item in list(active):
        if item == target_model:
            continue
        item_class = model_weight_class(item)
        if item_class in {"medium", "code", "heavy"}:
            _evict_model(active, item, evicted, policies, "heavy_policy")
        elif item_class == "light" and item not in keep_light:
            _evict_model(active, item, evicted, policies, "heavy_policy")

    return evicted, policies


def _apply_lru_limit(active: list[str], limit: int, evicted: list[str], policies: list[str]) -> None:
    while len(active) > limit:
        oldest = active.pop(0)
        if oldest not in evicted:
            evicted.append(oldest)
            policies.append("lru")


def _apply_single_large_policy(
    active: list[str],
    target_model: str,
    settings: dict[str, Any] | None,
    evicted: list[str],
    policies: list[str],
) -> bool:
    if not _single_large_target_model(settings):
        return False
    if model_weight_class(target_model) not in LARGE_TARGET_CLASSES:
        return True
    for item in list(active):
        if item == target_model:
            continue
        if model_weight_class(item) in LARGE_TARGET_CLASSES:
            _evict_model(active, item, evicted, policies, "single_large_target_model")
    return True


def _unload_evicted(evicted: list[str]) -> None:
    for model in evicted:
        if not model or model == LOCAL_CALCULATOR_TARGET or model_weight_class(model) == "router":
            continue
        ok = ollama_runtime.unload_model(model)
        LOGGER.info("Model residency evicted %s via Ollama unload: %s", model, ok)


def resolve_model_keep_alive(
    model_name: str,
    settings: dict[str, Any] | None = None,
    *,
    mode: str | None = None,
    router: bool = False,
) -> str | None:
    payload = settings or {}
    explicit = _normalize_keep_alive(payload.get("ollama_keep_alive"))

    model_class = "router" if router else model_weight_class(model_name)
    if model_class == "router":
        if explicit is not None:
            return explicit
        return _normalize_keep_alive(payload.get("router_keep_alive")) or _normalize_keep_alive(
            config.SETTINGS.ollama_router_keep_alive
        )
    if mode == "manual":
        manual = explicit or _normalize_keep_alive(payload.get("manual_keep_alive")) or _normalize_keep_alive(
            config.SETTINGS.ollama_manual_keep_alive
        )
        return _at_least_keep_alive(manual, "5m")
    if explicit is not None:
        return explicit
    if model_class == "heavy":
        return _normalize_keep_alive(payload.get("heavy_model_keep_alive")) or _normalize_keep_alive(
            config.SETTINGS.ollama_heavy_keep_alive
        )
    if model_class == "code":
        return _normalize_keep_alive(payload.get("code_model_keep_alive")) or _normalize_keep_alive(
            config.SETTINGS.ollama_code_keep_alive
        )
    if mode == "auto":
        return _normalize_keep_alive(payload.get("auto_target_keep_alive")) or _normalize_keep_alive(
            config.SETTINGS.ollama_auto_target_keep_alive
        )
    return _normalize_keep_alive(config.SETTINGS.ollama_chat_keep_alive)


def prepare_router_for_request(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    global _ROUTER_MODEL_ACTIVE, _LAST_MODE
    keep_alive = resolve_model_keep_alive(ROUTER_MODEL_ID, settings, mode="auto", router=True)
    with _LOCK:
        _ROUTER_MODEL_ACTIVE = True
        _LAST_MODE = "auto"
    return {
        "router_model": ROUTER_MODEL_ID,
        "router_keep_alive": keep_alive,
        "router_resident_tracked": True,
    }


def prepare_target_for_request(
    model_name: str,
    settings: dict[str, Any] | None = None,
    *,
    mode: str = "manual",
) -> dict[str, Any]:
    global _LAST_MODE
    target = str(model_name or "").strip()
    if not is_target_model(target):
        return {
            "model_selection_mode": mode,
            "target_model": target,
            "target_model_class": model_weight_class(target),
        }

    keep_alive = resolve_model_keep_alive(target, settings, mode=mode)
    max_resident = 1
    allow_light = _allow_light_with_heavy(settings)
    single_large = _single_large_target_model(settings)
    target_class = model_weight_class(target)

    with _LOCK:
        before = list(_ACTIVE_TARGET_MODELS)
        active = list(_ACTIVE_TARGET_MODELS)
        evicted, policies = _apply_heavy_policy(active, target, settings)
        _apply_single_large_policy(active, target, settings, evicted, policies)

        _remove_model(active, target)
        active.append(target)
        _apply_lru_limit(active, max_resident, evicted, policies)

        _ACTIVE_TARGET_MODELS[:] = active
        _LAST_MODE = mode
        after = list(_ACTIVE_TARGET_MODELS)

    _unload_evicted(evicted)
    eviction_policy = "none"
    if evicted:
        unique_policies = list(dict.fromkeys(policies))
        eviction_policy = unique_policies[0] if len(unique_policies) == 1 else "mixed"

    debug: dict[str, Any] = {
        "model_selection_mode": mode,
        "target_model": target,
        "target_model_class": target_class,
        "target_keep_alive": keep_alive,
        "ollama_keep_alive_effective": keep_alive,
        "max_resident_target_models": max_resident,
        "allow_light_with_heavy": allow_light,
        "single_large_target_model": single_large,
        "active_target_models_before": before,
        "active_target_models_after": after,
        "eviction_policy": eviction_policy,
    }
    if evicted:
        debug["evicted_models"] = evicted
        debug["evicted_model"] = evicted[0]
    return debug


def apply_target_settings(
    model_name: str,
    settings: dict[str, Any] | None,
    *,
    mode: str = "manual",
) -> dict[str, Any]:
    payload = dict(settings or {})
    residency_debug = prepare_target_for_request(model_name, payload, mode=mode)
    keep_alive = residency_debug.get("target_keep_alive")
    if keep_alive is not None:
        payload["ollama_keep_alive_effective"] = keep_alive
    payload.update(residency_debug)
    return payload


def preload_target_model(
    model_name: str,
    settings: dict[str, Any] | None = None,
    *,
    mode: str = "manual",
) -> dict[str, Any]:
    debug = prepare_target_for_request(model_name, settings, mode=mode)
    keep_alive = debug.get("target_keep_alive")
    ollama_runtime.load_model(model_name, keep_alive=keep_alive)
    return debug


def snapshot_state() -> dict[str, Any]:
    with _LOCK:
        return {
            "active_target_models": list(_ACTIVE_TARGET_MODELS),
            "router_model_active": _ROUTER_MODEL_ACTIVE,
            "last_mode": _LAST_MODE,
        }


def reset_state() -> None:
    global _ROUTER_MODEL_ACTIVE, _LAST_MODE
    with _LOCK:
        _ACTIVE_TARGET_MODELS.clear()
        _ROUTER_MODEL_ACTIVE = False
        _LAST_MODE = None
