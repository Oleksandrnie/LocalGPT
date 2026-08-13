from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from fastapi import HTTPException, UploadFile

from backend.apps.chat.prompt_policy import data_envelope
from backend.apps.chat.services.vision_runtime import VisionRuntimeError
from backend.apps.ocr.service import extract_text_from_image


OCR_ASSIST_MODES = {"auto", "on", "off", "ocr_only"}


@dataclass(frozen=True)
class OcrEvidence:
    text: str
    engines: tuple[str, ...]
    languages: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["engines"] = list(self.engines)
        payload["languages"] = list(self.languages)
        payload["warnings"] = list(self.warnings)
        return payload


def normalize_ocr_assist_mode(value: Any) -> str:
    mode = str(value or "auto").strip().lower()
    if mode not in OCR_ASSIST_MODES:
        raise VisionRuntimeError(
            "INVALID_OCR_ASSIST_MODE",
            "OCR assist должен быть auto, on, off или ocr_only.",
            details={"ocr_assist": mode},
        )
    return mode


def _http_error_message(exc: HTTPException) -> tuple[str, str]:
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("code") or "ocr_failed"), str(detail.get("message") or "OCR failed")
    return "ocr_failed", str(detail or "OCR failed")


def extract_ocr_evidence(
    image_paths: Iterable[str | Path],
    *,
    mode: str,
    language: str | None = None,
) -> OcrEvidence:
    normalized_mode = normalize_ocr_assist_mode(mode)
    if normalized_mode == "off":
        return OcrEvidence("", (), (), ())

    text_blocks: list[str] = []
    engines: list[str] = []
    languages: list[str] = []
    warnings: list[str] = []
    for index, raw_path in enumerate(image_paths, start=1):
        path = Path(raw_path).expanduser().resolve()
        try:
            with path.open("rb") as stream:
                upload = UploadFile(file=stream, filename=path.name)
                result = extract_text_from_image(upload, lang=language)
        except (OSError, HTTPException) as exc:
            if isinstance(exc, HTTPException):
                code, message = _http_error_message(exc)
            else:
                code, message = "ocr_file_unavailable", "Локальный файл изображения недоступен для OCR."
            warnings.append(f"image_{index}:{code}")
            if normalized_mode in {"on", "ocr_only"}:
                raise VisionRuntimeError(
                    "OCR_ASSIST_FAILED",
                    f"OCR assist не смог обработать изображение {index}: {message}",
                    details={"image_index": index, "ocr_code": code},
                ) from exc
            continue

        text = str(result.get("text") or "").strip()
        if text:
            text_blocks.append(f"[Изображение {index}]\n{text}")
        engine = str(result.get("engine") or "").strip()
        selected_language = str(result.get("language") or "").strip()
        if engine and engine not in engines:
            engines.append(engine)
        if selected_language and selected_language not in languages:
            languages.append(selected_language)

    if normalized_mode == "ocr_only" and not text_blocks:
        raise VisionRuntimeError(
            "OCR_EMPTY_RESULT",
            "OCR-only режим не нашёл читаемый текст в изображениях.",
        )
    return OcrEvidence(
        text="\n\n".join(text_blocks),
        engines=tuple(engines),
        languages=tuple(languages),
        warnings=tuple(warnings),
    )


def append_ocr_evidence(
    messages: list[dict[str, Any]],
    evidence: OcrEvidence,
) -> list[dict[str, Any]]:
    if not evidence.text:
        return list(messages)
    return [
        *messages,
        {
            "role": "user",
            "content": data_envelope(
                "ocr_text",
                evidence.text,
                provenance={
                    "derived": True,
                    "engines": list(evidence.engines),
                    "languages": list(evidence.languages),
                },
                allowed_influence="auxiliary_visual_evidence_only",
            ),
        },
    ]
