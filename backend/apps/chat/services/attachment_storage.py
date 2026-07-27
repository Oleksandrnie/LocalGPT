from __future__ import annotations

import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterable

from app import config, db
from backend.apps.chat.services.image_preprocessing import ImagePreprocessingError, preprocess_image


SUPPORTED_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "application/octet-stream", ""}
ACTIVE_ATTACHMENT_STATUSES = {
    "attached",
    "preparing",
    "analyzing",
    "loading_model",
    "generating",
    "processing",
}


class AttachmentStorageError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 422, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def attachments_root() -> Path:
    root = Path(config.CHAT_ATTACHMENTS_DIR).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_display_name(value: str | None) -> str:
    name = Path(str(value or "image")).name
    name = re.sub(r"[\x00-\x1f\x7f]+", "", name).strip()
    return name[:120] or "image"


def _relative_path(path: Path) -> str:
    return path.resolve().relative_to(attachments_root()).as_posix()


def resolve_storage_path(relative_path: str) -> Path:
    root = attachments_root()
    candidate = (root / str(relative_path or "")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise AttachmentStorageError(
            "ATTACHMENT_PATH_INVALID",
            "Attachment storage path выходит за разрешённый каталог.",
            status_code=500,
        ) from exc
    return candidate


def _profile_or_error(profile_id: int) -> dict[str, Any]:
    profile = db.get_profile(int(profile_id))
    if not profile or not profile.get("is_active", 1):
        raise AttachmentStorageError("PROFILE_NOT_FOUND", "Профиль не найден.", status_code=404)
    return profile


def _session_or_error(profile_id: int, session_id: str | None) -> dict[str, Any] | None:
    if not session_id:
        return None
    session = db.get_session(str(session_id))
    if not session:
        raise AttachmentStorageError("SESSION_NOT_FOUND", "Сессия чата не найдена.", status_code=404)
    if int(session.get("profile_id") or 0) != int(profile_id):
        raise AttachmentStorageError(
            "ATTACHMENT_OWNERSHIP_MISMATCH",
            "Сессия не принадлежит активному профилю.",
            status_code=403,
        )
    return session


def _write_limited(source: BinaryIO, destination: Path, *, max_bytes: int) -> int:
    total = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise AttachmentStorageError(
                    "IMAGE_TOO_LARGE",
                    f"Размер изображения превышает лимит {max_bytes} байт.",
                    details={"max_file_bytes": max_bytes},
                )
            output.write(chunk)
    if total <= 0:
        raise AttachmentStorageError("INVALID_IMAGE", "Получен пустой файл изображения.")
    return total


def store_upload(
    *,
    file_stream: BinaryIO,
    filename: str | None,
    content_type: str | None,
    profile_id: int,
    session_id: str | None,
    settings: dict[str, Any],
) -> dict[str, Any]:
    _profile_or_error(profile_id)
    _session_or_error(profile_id, session_id)
    if not bool(settings.get("chat_images_enabled", True)):
        raise AttachmentStorageError("CHAT_IMAGES_DISABLED", "Изображения в чате отключены.", status_code=403)
    declared_mime = str(content_type or "").strip().lower()
    if declared_mime not in SUPPORTED_MIME_TYPES:
        raise AttachmentStorageError(
            "UNSUPPORTED_IMAGE_TYPE",
            "Поддерживаются только PNG, JPEG/JPG и WebP.",
        )

    attachment_id = str(uuid.uuid4())
    profile_root = attachments_root() / f"profile-{int(profile_id)}"
    source_path = profile_root / "temporary" / f"{attachment_id}.upload"
    output_stub = profile_root / "images" / attachment_id
    thumbnail_path = profile_root / "thumbnails" / f"{attachment_id}.webp"
    max_file_bytes = int(settings.get("chat_image_max_file_bytes") or config.DEFAULT_RUNTIME_SETTINGS["chat_image_max_file_bytes"])
    max_side = int(settings.get("chat_image_max_side") or config.DEFAULT_RUNTIME_SETTINGS["chat_image_max_side"])
    max_pixels = int(settings.get("chat_image_max_pixels") or config.DEFAULT_RUNTIME_SETTINGS["chat_image_max_pixels"])

    output_path: Path | None = None
    try:
        _write_limited(file_stream, source_path, max_bytes=max_file_bytes)
        # Pillow determines the real format; the temporary suffix is intentionally untrusted.
        probe_path = output_stub.with_suffix(".normalized")
        processed = preprocess_image(
            source_path,
            probe_path,
            thumbnail_path,
            declared_mime_type=declared_mime,
            max_side=max_side,
            max_pixels=max_pixels,
        )
        output_path = output_stub.with_suffix(processed.extension)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        probe_path.replace(output_path)
        record = db.create_chat_attachment(
            attachment_id=attachment_id,
            profile_id=int(profile_id),
            session_id=session_id,
            mime_type=processed.mime_type,
            original_name=_safe_display_name(filename),
            storage_path=_relative_path(output_path),
            thumbnail_path=_relative_path(thumbnail_path),
            size_bytes=processed.size_bytes,
            width=processed.width,
            height=processed.height,
            sha256=processed.sha256,
            status="ready",
        )
        return record
    except ImagePreprocessingError as exc:
        raise AttachmentStorageError(exc.code, exc.message) from exc
    finally:
        for candidate in (source_path, output_stub.with_suffix(".normalized")):
            try:
                candidate.unlink()
            except OSError:
                pass
        if not db.get_chat_attachment(attachment_id):
            for candidate in (output_path, thumbnail_path):
                if not candidate:
                    continue
                try:
                    candidate.unlink()
                except OSError:
                    pass


def get_owned_attachment(attachment_id: str, profile_id: int) -> dict[str, Any]:
    attachment = db.get_chat_attachment(attachment_id)
    if not attachment:
        raise AttachmentStorageError("ATTACHMENT_NOT_FOUND", "Вложение не найдено.", status_code=404)
    if int(attachment.get("profile_id") or 0) != int(profile_id):
        raise AttachmentStorageError(
            "ATTACHMENT_OWNERSHIP_MISMATCH",
            "Вложение не принадлежит активному профилю.",
            status_code=403,
        )
    return attachment


def prepare_chat_attachments(
    attachment_ids: Iterable[str],
    *,
    profile_id: int,
    session_id: str,
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate ready attachments and return task-safe descriptors.

    Storage paths are resolved here, before the worker is spawned. They remain
    internal task arguments and are never exposed by the public task contract.
    """
    normalized: list[str] = []
    for raw_id in attachment_ids:
        attachment_id = str(raw_id or "").strip()
        if attachment_id and attachment_id not in normalized:
            normalized.append(attachment_id)
    if not normalized:
        return []
    if not bool(settings.get("chat_images_enabled", True)):
        raise AttachmentStorageError(
            "CHAT_IMAGES_DISABLED",
            "Изображения в чате отключены.",
            status_code=403,
        )

    _profile_or_error(profile_id)
    _session_or_error(profile_id, session_id)
    max_images = max(
        1,
        min(
            10,
            int(
                settings.get("max_images_per_message")
                or config.DEFAULT_RUNTIME_SETTINGS["max_images_per_message"]
            ),
        ),
    )
    if len(normalized) > max_images:
        raise AttachmentStorageError(
            "TOO_MANY_IMAGES",
            f"Можно прикрепить не больше {max_images} изображений.",
            details={"max_images_per_message": max_images},
        )

    descriptors: list[dict[str, Any]] = []
    total_bytes = 0
    max_total_bytes = int(
        settings.get("chat_image_max_total_bytes")
        or config.DEFAULT_RUNTIME_SETTINGS["chat_image_max_total_bytes"]
    )
    for attachment_id in normalized:
        record = get_owned_attachment(attachment_id, profile_id)
        bound_session = str(record.get("session_id") or "").strip()
        if bound_session and bound_session != str(session_id):
            raise AttachmentStorageError(
                "ATTACHMENT_OWNERSHIP_MISMATCH",
                "Вложение принадлежит другой сессии.",
                status_code=403,
            )
        if record.get("message_id") is not None or record.get("task_id"):
            raise AttachmentStorageError(
                "ATTACHMENT_ALREADY_USED",
                "Вложение уже привязано к сообщению.",
                status_code=409,
            )
        if str(record.get("status") or "") != "ready":
            raise AttachmentStorageError(
                "ATTACHMENT_NOT_READY",
                "Вложение ещё не готово к анализу.",
                status_code=409,
                details={"attachment_id": attachment_id, "status": record.get("status")},
            )
        path = resolve_storage_path(str(record.get("storage_path") or ""))
        if not path.is_file():
            raise AttachmentStorageError(
                "ATTACHMENT_FILE_MISSING",
                "Файл вложения отсутствует в локальном хранилище.",
                status_code=409,
            )
        size_bytes = int(record.get("size_bytes") or path.stat().st_size)
        total_bytes += size_bytes
        if total_bytes > max_total_bytes:
            raise AttachmentStorageError(
                "IMAGES_TOTAL_TOO_LARGE",
                f"Общий размер изображений превышает лимит {max_total_bytes} байт.",
                details={"max_total_bytes": max_total_bytes},
            )
        descriptors.append(
            {
                "id": attachment_id,
                "path": str(path),
                "mime_type": str(record.get("mime_type") or ""),
                "size_bytes": size_bytes,
                "width": int(record.get("width") or 0),
                "height": int(record.get("height") or 0),
            }
        )
    return descriptors


def delete_attachment(attachment_id: str, profile_id: int, *, allow_active: bool = False) -> dict[str, Any]:
    attachment = get_owned_attachment(attachment_id, profile_id)
    if not allow_active and attachment.get("status") in ACTIVE_ATTACHMENT_STATUSES:
        raise AttachmentStorageError(
            "ATTACHMENT_IN_USE",
            "Вложение используется активной задачей.",
            status_code=409,
        )
    deleted_bytes = int(attachment.get("size_bytes") or 0)
    errors: list[str] = []
    for field in ("storage_path", "thumbnail_path"):
        relative = str(attachment.get(field) or "")
        if not relative:
            continue
        try:
            resolve_storage_path(relative).unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"{field}:{exc}")
    if errors:
        raise AttachmentStorageError(
            "ATTACHMENT_DELETE_FAILED",
            "Не удалось полностью удалить файлы вложения.",
            status_code=500,
            details={"errors": errors},
        )
    db.delete_chat_attachment_record(attachment_id)
    return {"id": attachment_id, "deleted_bytes": deleted_bytes}


def _delete_records(records: Iterable[dict[str, Any]], *, allow_active: bool = False) -> dict[str, Any]:
    deleted_count = 0
    deleted_bytes = 0
    skipped_active_count = 0
    errors: list[str] = []
    for record in records:
        if not allow_active and record.get("status") in ACTIVE_ATTACHMENT_STATUSES:
            skipped_active_count += 1
            continue
        try:
            result = delete_attachment(str(record["id"]), int(record["profile_id"]), allow_active=allow_active)
            deleted_count += 1
            deleted_bytes += int(result.get("deleted_bytes") or 0)
        except AttachmentStorageError as exc:
            errors.append(f"{record.get('id')}:{exc.code}")
    return {
        "deleted_count": deleted_count,
        "deleted_bytes": deleted_bytes,
        "skipped_active_count": skipped_active_count,
        "errors": errors,
    }


def delete_profile_attachments(profile_id: int, *, allow_active: bool = True) -> dict[str, Any]:
    result = _delete_records(db.list_chat_attachments(profile_id=int(profile_id)), allow_active=allow_active)
    profile_root = attachments_root() / f"profile-{int(profile_id)}"
    if allow_active:
        shutil.rmtree(profile_root, ignore_errors=True)
    return result


def delete_session_attachments(session_id: str, *, allow_active: bool = True) -> dict[str, Any]:
    return _delete_records(db.list_chat_attachments(session_id=str(session_id)), allow_active=allow_active)


def delete_all_attachments(*, allow_active: bool = True) -> dict[str, Any]:
    result = _delete_records(db.list_chat_attachments(), allow_active=allow_active)
    if allow_active:
        root = attachments_root()
        for child in root.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
    return result


def cleanup_attachments(*, profile_id: int, scope: str, temporary_ttl_seconds: int) -> dict[str, Any]:
    _profile_or_error(profile_id)
    records = db.list_chat_attachments(profile_id=int(profile_id))
    if scope == "orphans":
        cutoff = time.time() - max(60, int(temporary_ttl_seconds))
        filtered: list[dict[str, Any]] = []
        for record in records:
            if record.get("message_id") is not None or record.get("task_id"):
                continue
            created_at = str(record.get("updated_at") or record.get("created_at") or "")
            try:
                parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                record_timestamp = parsed.timestamp()
            except ValueError:
                record_timestamp = 0
            if record_timestamp <= cutoff:
                filtered.append(record)
        records = filtered
    result = _delete_records(records, allow_active=False)
    return {"scope": scope, "profile_id": int(profile_id), **result}


def attachment_cache_stats(*, profile_id: int) -> dict[str, Any]:
    _profile_or_error(profile_id)
    records = db.list_chat_attachments(profile_id=int(profile_id))
    status_counts: dict[str, int] = {}
    total_bytes = 0
    thumbnail_bytes = 0
    for record in records:
        status = str(record.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        total_bytes += int(record.get("size_bytes") or 0)
        thumbnail_path = str(record.get("thumbnail_path") or "")
        if thumbnail_path:
            try:
                thumbnail_bytes += resolve_storage_path(thumbnail_path).stat().st_size
            except OSError:
                pass
    return {
        "profile_id": int(profile_id),
        "attachment_count": len(records),
        "image_bytes": total_bytes,
        "thumbnail_bytes": thumbnail_bytes,
        "total_bytes": total_bytes + thumbnail_bytes,
        "active_count": sum(status_counts.get(status, 0) for status in ACTIVE_ATTACHMENT_STATUSES),
        "status_counts": status_counts,
    }
