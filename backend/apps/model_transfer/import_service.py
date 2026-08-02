from __future__ import annotations

import os
import shutil
import threading
import uuid
import zipfile
from pathlib import Path

from app import config
from .manifest import BundleManifest, BundleValidationError, sha256_file

_UPLOADS: dict[str, Path] = {}
_LOCK = threading.Lock()


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


def inspect_archive(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as bundle:
            names = bundle.namelist()
            if "manifest.json" not in names:
                raise BundleValidationError("bundle_incomplete", "manifest.json is missing.")
            manifest = BundleManifest.parse(bundle.read("manifest.json"))
            expected = {item.path.casefold(): item for item in manifest.files}
            actual = {name.casefold() for name in names if name != "manifest.json" and not name.endswith("/")}
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
                with bundle.open(info) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest() != item.sha256:
                    raise BundleValidationError("bundle_checksum_mismatch", f"Checksum mismatch: {item.path}")
            return {
                "valid": True,
                "bundle_id": manifest.bundle_id,
                "models": list(manifest.models),
                "file_count": len(manifest.files),
                "total_size": sum(item.size for item in manifest.files),
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
        with zipfile.ZipFile(archive) as bundle:
            manifest = BundleManifest.parse(bundle.read("manifest.json"))
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
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
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
