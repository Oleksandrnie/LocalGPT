from __future__ import annotations

import os
import shutil
import struct
import threading
import uuid
import zipfile
from pathlib import Path

from app import config
from app.services.upload_limits import UploadLimitExceeded, copy_limited
from .manifest import MAX_BUNDLE_BYTES, MAX_BUNDLE_FILES, MAX_MANIFEST_BYTES, BundleManifest, BundleValidationError, sha256_file

_UPLOADS: dict[str, Path] = {}
_LOCK = threading.Lock()
MAX_CENTRAL_DIRECTORY_BYTES = 32 * 1024 * 1024

_RUNTIME_REQUIREMENTS = {
    "ollama": ("ollama_runtime",),
    "faster-whisper": ("faster_whisper_runtime",),
    "whisper-cpp": ("whisper_cpp_cli", "whisper_cpp_vad"),
    "piper": ("piper_runtime",),
}


def _runtime_requirements(models: tuple[dict, ...]) -> list[str]:
    families = {str(model.get("family") or "") for model in models}
    return sorted({requirement for family in families for requirement in _RUNTIME_REQUIREMENTS.get(family, ())})


def upload_storage_dir() -> Path:
    return config.DATA_DIR / "model_transfer" / "uploads"


def _upload_files() -> list[Path]:
    directory = upload_storage_dir()
    if not directory.is_dir():
        return []
    return [
        path for path in directory.iterdir()
        if path.is_file() and not path.is_symlink() and path.suffix == ".localgpt-models"
    ]


def upload_storage_summary() -> dict:
    files = _upload_files()
    return {
        "file_count": len(files),
        "total_size": sum(path.stat().st_size for path in files),
    }


def clear_upload_storage() -> dict:
    directory = upload_storage_dir()
    files = _upload_files()
    total_size = sum(path.stat().st_size for path in files)
    for path in files:
        path.unlink()
    with _LOCK:
        for upload_id, path in list(_UPLOADS.items()):
            if path.parent == directory:
                _UPLOADS.pop(upload_id, None)
    return {"deleted_files": len(files), "freed_size": total_size}


def _preflight_archive_directory(path: Path) -> None:
    file_size = path.stat().st_size
    tail_size = min(file_size, 22 + 65_535)
    with path.open("rb") as stream:
        stream.seek(file_size - tail_size)
        tail = stream.read(tail_size)
    eocd_offset = tail.rfind(b"PK\x05\x06")
    eocd_values = None
    while eocd_offset >= 0:
        if eocd_offset + 22 <= len(tail):
            candidate = struct.unpack_from("<4s4H2LH", tail, eocd_offset)
            if eocd_offset + 22 + candidate[-1] == len(tail):
                eocd_values = candidate
                break
        eocd_offset = tail.rfind(b"PK\x05\x06", 0, eocd_offset)
    if eocd_values is None:
        raise BundleValidationError("bundle_invalid", "Archive directory is missing or invalid.")

    _, disk_number, directory_disk, disk_entries, total_entries, directory_size, directory_offset, _ = eocd_values
    if disk_number or directory_disk:
        raise BundleValidationError("bundle_invalid", "Multi-disk or malformed ZIP archives are not supported.")

    if (
        disk_entries == 0xFFFF
        or total_entries == 0xFFFF
        or directory_size == 0xFFFFFFFF
        or directory_offset == 0xFFFFFFFF
    ):
        eocd_absolute = file_size - tail_size + eocd_offset
        locator_absolute = eocd_absolute - 20
        if locator_absolute < 0:
            raise BundleValidationError("bundle_invalid", "ZIP64 directory locator is missing.")
        with path.open("rb") as stream:
            stream.seek(locator_absolute)
            locator = stream.read(20)
            if len(locator) != 20:
                raise BundleValidationError("bundle_invalid", "ZIP64 directory locator is invalid.")
            locator_signature, locator_disk, zip64_offset, disk_count = struct.unpack("<4sLQL", locator)
            if locator_signature != b"PK\x06\x07" or locator_disk or disk_count != 1:
                raise BundleValidationError("bundle_invalid", "ZIP64 directory locator is invalid.")
            stream.seek(zip64_offset)
            record = stream.read(56)
        if len(record) != 56:
            raise BundleValidationError("bundle_invalid", "ZIP64 directory record is invalid.")
        values = struct.unpack("<4sQ2H2L4Q", record)
        if values[0] != b"PK\x06\x06" or values[1] < 44 or values[4] or values[5] or values[6] != values[7]:
            raise BundleValidationError("bundle_invalid", "Multi-disk or malformed ZIP64 archives are not supported.")
        total_entries, directory_size = values[7], values[8]
    elif disk_entries != total_entries:
        raise BundleValidationError("bundle_invalid", "Multi-disk or malformed ZIP archives are not supported.")

    if total_entries > MAX_BUNDLE_FILES + 1:
        raise BundleValidationError("bundle_invalid", "Archive contains too many entries.")
    if directory_size > MAX_CENTRAL_DIRECTORY_BYTES:
        raise BundleValidationError("bundle_invalid", "Archive directory is too large.")


def _read_bundle_manifest(bundle: zipfile.ZipFile, infos: list[zipfile.ZipInfo]) -> BundleManifest:
    if len(infos) > MAX_BUNDLE_FILES + 1:
        raise BundleValidationError("bundle_invalid", "Archive contains too many entries.")
    manifest_infos = [info for info in infos if info.filename == "manifest.json"]
    if not manifest_infos:
        raise BundleValidationError("bundle_incomplete", "manifest.json is missing.")
    if len(manifest_infos) != 1:
        raise BundleValidationError("bundle_invalid", "Archive contains duplicate manifests.")
    manifest_info = manifest_infos[0]
    if manifest_info.flag_bits & 0x1:
        raise BundleValidationError("bundle_invalid", "Encrypted archive entries are not supported.")
    if manifest_info.file_size > MAX_MANIFEST_BYTES:
        raise BundleValidationError("bundle_invalid", "Manifest is too large.")
    with bundle.open(manifest_info) as manifest_stream:
        manifest_raw = manifest_stream.read(MAX_MANIFEST_BYTES + 1)
    return BundleManifest.parse(manifest_raw)


def inspect_archive(path: Path) -> dict:
    if path.stat().st_size > MAX_BUNDLE_BYTES:
        raise BundleValidationError("bundle_too_large", "Model bundle exceeds the 50 GiB upload limit.")
    _preflight_archive_directory(path)
    try:
        with zipfile.ZipFile(path) as bundle:
            infos = bundle.infolist()
            manifest = _read_bundle_manifest(bundle, infos)
            expected = {item.path.casefold(): item for item in manifest.files}
            actual: set[str] = set()
            total_size = 0
            for info in infos:
                if info.filename == "manifest.json" or info.is_dir():
                    continue
                folded = info.filename.casefold()
                if folded in actual:
                    raise BundleValidationError("bundle_invalid", "Archive contains duplicate payload paths.")
                actual.add(folded)
                total_size += info.file_size
                if total_size > MAX_BUNDLE_BYTES:
                    raise BundleValidationError("bundle_invalid", "Bundle payload is too large.")
                if info.flag_bits & 0x1:
                    raise BundleValidationError("bundle_invalid", "Encrypted archive entries are not supported.")
            if actual != set(expected):
                raise BundleValidationError("bundle_invalid", "Archive payload does not match manifest.")
            for info in bundle.infolist():
                if info.filename == "manifest.json" or info.is_dir():
                    continue
                item = expected[info.filename.casefold()]
                if info.file_size != item.size:
                    raise BundleValidationError("bundle_checksum_mismatch", f"Size mismatch: {item.path}")
                import hashlib
                digest = hashlib.sha256()
                member_size = 0
                with bundle.open(info) as stream:
                    while chunk := stream.read(1024 * 1024):
                        member_size += len(chunk)
                        if member_size > item.size:
                            raise BundleValidationError("bundle_checksum_mismatch", f"Size mismatch: {item.path}")
                        digest.update(chunk)
                if member_size != item.size:
                    raise BundleValidationError("bundle_checksum_mismatch", f"Size mismatch: {item.path}")
                if digest.hexdigest() != item.sha256:
                    raise BundleValidationError("bundle_checksum_mismatch", f"Checksum mismatch: {item.path}")
            return {
                "valid": True,
                "bundle_id": manifest.bundle_id,
                "models": list(manifest.models),
                "file_count": len(manifest.files),
                "total_size": sum(item.size for item in manifest.files),
                "runtime_requirements": _runtime_requirements(manifest.models),
            }
    except zipfile.BadZipFile as exc:
        raise BundleValidationError("bundle_invalid", "File is not a valid model bundle.") from exc


def register_upload(path: Path) -> str:
    upload_id = str(uuid.uuid4())
    with _LOCK:
        _UPLOADS[upload_id] = path
    return upload_id


def _upload_path(upload_id: str) -> Path:
    with _LOCK:
        path = _UPLOADS.get(str(upload_id or ""))
    if not path or not path.is_file():
        raise BundleValidationError("bundle_incomplete", "Uploaded bundle is no longer available.")
    return path


def discard_upload(upload_id: str) -> bool:
    with _LOCK:
        path = _UPLOADS.pop(str(upload_id or ""), None)
    if not path:
        return False
    path.unlink(missing_ok=True)
    return True


def _target_for(entry: str) -> Path:
    parts = Path(entry).parts
    if len(parts) < 3 or parts[0] != "payload":
        raise BundleValidationError("unsafe_bundle_path", "Invalid payload path.")
    roots = {
        "ollama": config.MODEL_PATHS.ollama,
        "faster-whisper": config.MODEL_PATHS.whisper,
        "whisper-cpp": config.MODEL_PATHS.whisper_cpp,
        "piper": config.MODEL_PATHS.piper,
    }
    root = roots.get(parts[1])
    if root is None:
        raise BundleValidationError("unsafe_bundle_path", "Unknown provider path.")
    target = root.joinpath(*parts[2:])
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise BundleValidationError("unsafe_bundle_path", "Target escapes provider storage.") from exc
    return target


def apply_import(upload_id: str) -> dict:
    archive = _upload_path(upload_id)
    inspected = inspect_archive(archive)
    staging_root = config.DATA_DIR / "model_transfer" / "import_staging" / upload_id
    published = skipped = 0
    try:
        _preflight_archive_directory(archive)
        with zipfile.ZipFile(archive) as bundle:
            manifest = _read_bundle_manifest(bundle, bundle.infolist())
            targets = [(item, _target_for(item.path)) for item in manifest.files]
            conflicts = [
                item.path for item, target in targets
                if target.exists() and (not target.is_file() or target.stat().st_size != item.size or sha256_file(target) != item.sha256)
            ]
            if conflicts:
                raise BundleValidationError("target_conflict", f"Existing target differs: {conflicts[0]}")
            ordered = sorted(
                targets,
                key=lambda pair: (
                    pair[0].path.startswith("payload/ollama/manifests/"),
                    pair[0].path,
                ),
            )
            for item, target in ordered:
                if target.exists():
                    skipped += 1
                    continue
                staged = staging_root / item.path
                staged.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item.path) as source, staged.open("wb") as destination:
                    try:
                        copied = copy_limited(source, destination, max_bytes=item.size)
                    except UploadLimitExceeded as exc:
                        raise BundleValidationError("bundle_checksum_mismatch", f"Size mismatch: {item.path}") from exc
                if copied != item.size:
                    raise BundleValidationError("bundle_checksum_mismatch", f"Size mismatch: {item.path}")
                if staged.stat().st_size != item.size or sha256_file(staged) != item.sha256:
                    raise BundleValidationError("bundle_checksum_mismatch", f"Checksum mismatch: {item.path}")
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, target)
                published += 1
        return {**inspected, "status": "imported", "published_files": published, "skipped_files": skipped}
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
        with _LOCK:
            _UPLOADS.pop(upload_id, None)
        archive.unlink(missing_ok=True)
