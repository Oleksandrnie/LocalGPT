from __future__ import annotations

import base64
import copy
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

from app import config
from backend.apps.chat.services import ollama_runtime


AUTO_ROUTER_MODEL_ID = "__auto_router__"
LOCAL_CALCULATOR_MODEL_ID = "__local_calculator__"
VISION_INFERENCE_LIMIT = 1
_VISION_INFERENCE_SEMAPHORE = threading.BoundedSemaphore(VISION_INFERENCE_LIMIT)


class VisionRuntimeError(Exception):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class VisionRoutePlan:
    mode: str
    vision_model: str
    response_model: str
    reason: str
    capabilities: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        return payload


def _normalize_capabilities(value: Any) -> tuple[str, ...]:
    raw_items = value if isinstance(value, (list, tuple, set)) else []
    result: list[str] = []
    for item in raw_items:
        normalized = str(item or "").strip().lower().replace("-", "_")
        if normalized in {"image", "images"}:
            normalized = "vision"
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result)


def model_capabilities(record: dict[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(record, dict):
        return ()
    direct = _normalize_capabilities(record.get("capabilities"))
    if direct:
        return direct
    details = record.get("details") if isinstance(record.get("details"), dict) else {}
    return _normalize_capabilities(details.get("capabilities"))


def has_confirmed_vision_capability(record: dict[str, Any] | None) -> bool:
    if not isinstance(record, dict):
        return False
    installed = bool(record.get("runtime_installed", record.get("installed")))
    confirmed = bool(record.get("capabilities_confirmed"))
    return installed and confirmed and "vision" in model_capabilities(record)


def _model_name(record: dict[str, Any]) -> str:
    return str(record.get("name") or record.get("model") or record.get("id") or "").strip()


def _preferred_vision_records(installed_models: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    catalog_order = {
        str(item.get("id") or ""): index
        for index, item in enumerate(getattr(config, "VISION_MODEL_CATALOG", []))
        if str(item.get("id") or "").strip()
    }
    candidates = [
        record
        for record in installed_models
        if _model_name(record) and has_confirmed_vision_capability(record)
    ]
    return sorted(
        candidates,
        key=lambda record: (catalog_order.get(_model_name(record), len(catalog_order)), _model_name(record)),
    )


def resolve_vision_route(
    *,
    selected_model: str,
    configured_vision_model: str | None,
    installed_models: Iterable[dict[str, Any]],
) -> VisionRoutePlan:
    records = [record for record in installed_models if isinstance(record, dict) and _model_name(record)]
    by_name = {_model_name(record): record for record in records}
    selected = str(selected_model or "").strip()
    configured = str(configured_vision_model or "auto").strip() or "auto"

    selected_record = by_name.get(selected)
    if selected_record and has_confirmed_vision_capability(selected_record):
        return VisionRoutePlan(
            mode="direct",
            vision_model=selected,
            response_model=selected,
            reason="selected_model_has_confirmed_vision",
            capabilities=model_capabilities(selected_record),
        )

    if selected == LOCAL_CALCULATOR_MODEL_ID:
        raise VisionRuntimeError(
            "VISION_ROUTE_UNSUPPORTED_SELECTION",
            "Local Calculator не может обрабатывать изображения. Выберите vision или chat-модель.",
        )

    vision_record: dict[str, Any] | None = None
    if configured.lower() != "auto":
        configured_record = by_name.get(configured)
        if not configured_record:
            raise VisionRuntimeError(
                "VISION_MODEL_NOT_INSTALLED",
                f"Настроенная vision-модель {configured} не установлена в текущем Ollama runtime.",
                details={"vision_model": configured},
            )
        if not has_confirmed_vision_capability(configured_record):
            raise VisionRuntimeError(
                "VISION_CAPABILITY_NOT_CONFIRMED",
                f"Ollama не подтвердил vision capability для модели {configured}.",
                details={"vision_model": configured, "capabilities": list(model_capabilities(configured_record))},
            )
        vision_record = configured_record
    else:
        candidates = _preferred_vision_records(records)
        if candidates:
            vision_record = candidates[0]

    if not vision_record:
        raise VisionRuntimeError(
            "VISION_MODEL_MISSING",
            "Не установлена ни одна модель с подтверждённой vision capability.",
            details={
                "recommended_models": [
                    str(item.get("id"))
                    for item in getattr(config, "VISION_MODEL_CATALOG", [])
                    if item.get("id")
                ]
            },
        )

    vision_model = _model_name(vision_record)
    capabilities = model_capabilities(vision_record)
    if selected == AUTO_ROUTER_MODEL_ID or not selected:
        return VisionRoutePlan(
            mode="direct",
            vision_model=vision_model,
            response_model=vision_model,
            reason="image_bypasses_text_intent_router",
            capabilities=capabilities,
        )
    if not selected_record or not bool(selected_record.get("runtime_installed", selected_record.get("installed"))):
        raise VisionRuntimeError(
            "RESPONSE_MODEL_NOT_INSTALLED",
            f"Выбранная chat-модель {selected} не установлена в текущем Ollama runtime.",
            details={"response_model": selected},
        )
    return VisionRoutePlan(
        mode="vision_context",
        vision_model=vision_model,
        response_model=selected,
        reason="selected_model_is_text_only",
        capabilities=capabilities,
    )


def build_multimodal_messages(
    messages: list[dict[str, Any]],
    image_paths: Iterable[str | Path],
    *,
    max_total_bytes: int | None = None,
) -> list[dict[str, Any]]:
    paths = [Path(path).expanduser().resolve() for path in image_paths]
    if not paths:
        raise VisionRuntimeError("VISION_IMAGES_REQUIRED", "Для vision-запроса нужно хотя бы одно изображение.")
    if len(paths) > 10:
        raise VisionRuntimeError("TOO_MANY_IMAGES", "За один запрос можно передать не больше 10 изображений.")

    byte_limit = int(
        max_total_bytes
        or config.DEFAULT_RUNTIME_SETTINGS.get("chat_image_max_total_bytes")
        or 40 * 1024 * 1024
    )
    total_bytes = 0
    encoded_images: list[str] = []
    for path in paths:
        if not path.is_file():
            raise VisionRuntimeError(
                "ATTACHMENT_FILE_MISSING",
                "Файл изображения отсутствует в локальном attachment storage.",
            )
        size = path.stat().st_size
        total_bytes += size
        if total_bytes > byte_limit:
            raise VisionRuntimeError(
                "IMAGES_TOTAL_TOO_LARGE",
                f"Общий размер изображений превышает лимит {byte_limit} байт.",
                details={"max_total_bytes": byte_limit},
            )
        encoded_images.append(base64.b64encode(path.read_bytes()).decode("ascii"))

    copied_messages = copy.deepcopy(messages)
    target_index = next(
        (
            index
            for index in range(len(copied_messages) - 1, -1, -1)
            if str(copied_messages[index].get("role") or "") == "user"
        ),
        None,
    )
    if target_index is None:
        copied_messages.append({"role": "user", "content": ""})
        target_index = len(copied_messages) - 1
    copied_messages[target_index]["images"] = encoded_images
    return copied_messages


def chat_completion(
    model_name: str,
    messages: list[dict[str, Any]],
    image_paths: Iterable[str | Path],
    *,
    max_total_bytes: int | None = None,
    **runtime_kwargs: Any,
) -> str:
    multimodal_messages = build_multimodal_messages(
        messages,
        image_paths,
        max_total_bytes=max_total_bytes,
    )
    with _VISION_INFERENCE_SEMAPHORE:
        return ollama_runtime.chat_completion(
            model_name,
            messages=multimodal_messages,
            **runtime_kwargs,
        )


def chat_completion_stream(
    model_name: str,
    messages: list[dict[str, Any]],
    image_paths: Iterable[str | Path],
    *,
    max_total_bytes: int | None = None,
    **runtime_kwargs: Any,
) -> Iterator[str]:
    multimodal_messages = build_multimodal_messages(
        messages,
        image_paths,
        max_total_bytes=max_total_bytes,
    )
    with _VISION_INFERENCE_SEMAPHORE:
        yield from ollama_runtime.chat_completion_stream(
            model_name,
            messages=multimodal_messages,
            **runtime_kwargs,
        )
