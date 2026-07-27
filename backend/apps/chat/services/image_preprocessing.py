from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError


SUPPORTED_IMAGE_FORMATS = {
    "PNG": ("image/png", ".png"),
    "JPEG": ("image/jpeg", ".jpg"),
    "WEBP": ("image/webp", ".webp"),
}


class ImagePreprocessingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ProcessedImage:
    mime_type: str
    extension: str
    size_bytes: int
    width: int
    height: int
    sha256: str


def _safe_dimensions(width: int, height: int, *, max_pixels: int) -> None:
    if width <= 0 or height <= 0:
        raise ImagePreprocessingError("INVALID_IMAGE", "Изображение имеет недопустимые размеры.")
    if width * height > max_pixels * 4:
        raise ImagePreprocessingError(
            "IMAGE_TOO_LARGE",
            f"Разрешение изображения превышает безопасный decode-лимит {max_pixels * 4} пикселей.",
        )


def _target_size(width: int, height: int, *, max_side: int, max_pixels: int) -> tuple[int, int]:
    scale = min(1.0, max_side / max(width, height))
    if width * height * scale * scale > max_pixels:
        scale = min(scale, (max_pixels / float(width * height)) ** 0.5)
    return max(1, int(round(width * scale))), max(1, int(round(height * scale)))


def _normalize_mode(image: Image.Image, image_format: str) -> Image.Image:
    if image_format == "JPEG":
        if image.mode == "RGB":
            return image
        if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
            background = Image.new("RGB", image.size, "white")
            alpha = image.convert("RGBA")
            background.paste(alpha, mask=alpha.getchannel("A"))
            return background
        return image.convert("RGB")
    if image.mode in {"RGB", "RGBA"}:
        return image
    return image.convert("RGBA" if "transparency" in image.info else "RGB")


def _save_image(image: Image.Image, output_path: Path, image_format: str) -> None:
    save_kwargs: dict[str, Any] = {}
    if image_format == "JPEG":
        save_kwargs.update(quality=92, optimize=True, progressive=True)
    elif image_format == "PNG":
        save_kwargs.update(optimize=True)
    elif image_format == "WEBP":
        save_kwargs.update(quality=92, method=4)
    image.save(output_path, format=image_format, **save_kwargs)


def _save_thumbnail(image: Image.Image, thumbnail_path: Path) -> None:
    thumbnail = image.copy()
    thumbnail.thumbnail((512, 512), Image.Resampling.LANCZOS)
    thumbnail = _normalize_mode(thumbnail, "WEBP")
    thumbnail.save(thumbnail_path, format="WEBP", quality=82, method=4)


def preprocess_image(
    source_path: Path,
    output_path: Path,
    thumbnail_path: Path,
    *,
    declared_mime_type: str | None,
    max_side: int,
    max_pixels: int,
) -> ProcessedImage:
    try:
        with Image.open(source_path) as source:
            image_format = str(source.format or "").upper()
            if image_format not in SUPPORTED_IMAGE_FORMATS:
                raise ImagePreprocessingError(
                    "UNSUPPORTED_IMAGE_TYPE",
                    "Поддерживаются только PNG, JPEG/JPG и WebP.",
                )
            mime_type, extension = SUPPORTED_IMAGE_FORMATS[image_format]
            normalized_declared = str(declared_mime_type or "").strip().lower()
            if normalized_declared == "image/jpg":
                normalized_declared = "image/jpeg"
            if normalized_declared and normalized_declared not in {"application/octet-stream", mime_type}:
                raise ImagePreprocessingError(
                    "INVALID_IMAGE",
                    "Фактический формат изображения не совпадает с заявленным MIME.",
                )

            _safe_dimensions(int(source.width), int(source.height), max_pixels=max_pixels)
            source.load()
            normalized = ImageOps.exif_transpose(source)
            normalized = _normalize_mode(normalized, image_format)
            target_size = _target_size(
                int(normalized.width),
                int(normalized.height),
                max_side=max_side,
                max_pixels=max_pixels,
            )
            if target_size != normalized.size:
                normalized = normalized.resize(target_size, Image.Resampling.LANCZOS)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
            _save_image(normalized, output_path, image_format)
            _save_thumbnail(normalized, thumbnail_path)
    except ImagePreprocessingError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImagePreprocessingError("IMAGE_TOO_LARGE", "Изображение превышает безопасный decode-лимит.") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImagePreprocessingError("INVALID_IMAGE", "Файл повреждён или не является поддерживаемым изображением.") from exc

    digest = hashlib.sha256()
    with output_path.open("rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return ProcessedImage(
        mime_type=mime_type,
        extension=extension,
        size_bytes=output_path.stat().st_size,
        width=target_size[0],
        height=target_size[1],
        sha256=digest.hexdigest(),
    )
