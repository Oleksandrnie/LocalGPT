from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

SCHEMA = "localgpt-model-bundle"
VERSION = 1
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_BUNDLE_BYTES = 50 * 1024 * 1024 * 1024
MAX_BUNDLE_FILES = 50_000
MAX_BUNDLE_MODELS = 5_000
FAMILIES = {"ollama", "faster-whisper", "whisper-cpp", "piper"}


class BundleValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_bundle_path(value: Any) -> str:
    path = str(value or "")
    if not path or "\x00" in path or "\\" in path:
        raise BundleValidationError("unsafe_bundle_path", "Bundle path must be a POSIX-relative path.")
    pure = PurePosixPath(path)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise BundleValidationError("unsafe_bundle_path", "Bundle path contains an unsafe segment.")
    normalized = pure.as_posix()
    if not normalized.startswith("payload/"):
        raise BundleValidationError("unsafe_bundle_path", "Payload file must be below payload/.")
    return normalized


@dataclass(frozen=True)
class BundleFile:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class BundleManifest:
    bundle_id: str
    created_at: str
    models: tuple[dict[str, Any], ...]
    files: tuple[BundleFile, ...]

    @classmethod
    def parse(cls, raw: bytes) -> "BundleManifest":
        if len(raw) > MAX_MANIFEST_BYTES:
            raise BundleValidationError("bundle_invalid", "Manifest is too large.")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BundleValidationError("bundle_invalid", "Manifest is not valid UTF-8 JSON.") from exc
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
            raise BundleValidationError("bundle_invalid", "Unknown bundle schema.")
        if payload.get("version") != VERSION:
            raise BundleValidationError("unsupported_bundle_version", "Unsupported bundle version.")
        bundle_id = str(payload.get("bundle_id") or "").strip()
        created_at = str(payload.get("created_at") or "").strip()
        models = payload.get("models")
        files = payload.get("files")
        if not bundle_id or not created_at or not isinstance(models, list) or not isinstance(files, list):
            raise BundleValidationError("bundle_invalid", "Manifest fields are incomplete.")
        if len(models) > MAX_BUNDLE_MODELS or len(files) > MAX_BUNDLE_FILES:
            raise BundleValidationError("bundle_invalid", "Manifest contains too many entries.")
        parsed_files: list[BundleFile] = []
        seen: set[str] = set()
        total_size = 0
        for item in files:
            if not isinstance(item, dict):
                raise BundleValidationError("bundle_invalid", "Invalid file entry.")
            path = validate_bundle_path(item.get("path"))
            folded = path.casefold()
            if folded in seen:
                raise BundleValidationError("bundle_invalid", "Duplicate bundle path.")
            seen.add(folded)
            size = item.get("size")
            digest = str(item.get("sha256") or "").lower()
            if isinstance(size, bool) or not isinstance(size, int) or size < 0 or len(digest) != 64:
                raise BundleValidationError("bundle_invalid", "Invalid file size or SHA-256.")
            total_size += size
            if total_size > MAX_BUNDLE_BYTES:
                raise BundleValidationError("bundle_invalid", "Bundle payload is too large.")
            try:
                int(digest, 16)
            except ValueError as exc:
                raise BundleValidationError("bundle_invalid", "Invalid SHA-256.") from exc
            parsed_files.append(BundleFile(path, size, digest))
        referenced: set[str] = set()
        for model in models:
            if not isinstance(model, dict) or model.get("family") not in FAMILIES or not str(model.get("id") or ""):
                raise BundleValidationError("bundle_invalid", "Invalid model entry.")
            family = str(model["family"])
            model_id = str(model.get("model_id") or "").strip()
            model_files = model.get("files")
            if not model_id or not isinstance(model_files, list) or not model_files:
                raise BundleValidationError("bundle_invalid", "Model metadata is incomplete.")
            family_prefix = f"payload/{family}/"
            for raw_path in model_files:
                path = validate_bundle_path(raw_path)
                folded = path.casefold()
                if not path.startswith(family_prefix) or folded not in seen:
                    raise BundleValidationError("bundle_invalid", "Model references an invalid payload file.")
                referenced.add(folded)
        if referenced != seen:
            raise BundleValidationError("bundle_invalid", "Bundle contains unreferenced payload files.")
        return cls(bundle_id, created_at, tuple(models), tuple(parsed_files))


def sha256_file(path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()
