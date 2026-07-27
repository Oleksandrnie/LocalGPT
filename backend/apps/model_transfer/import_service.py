from __future__ import annotations

import zipfile
from pathlib import Path

from .manifest import BundleManifest, BundleValidationError, sha256_file


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
