from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app import config
from backend.apps.asr import downloads
from backend.apps.asr.whisper_cpp import whisper_cpp_coreml_path, whisper_cpp_model_path
from backend.apps.tts.providers.piper_provider import PiperProvider


def _regular_files(root: Path, target: Path) -> list[Path]:
    root = root.resolve()
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return []
    candidates = [target] if target.is_file() else sorted(target.rglob("*")) if target.is_dir() else []
    result: list[Path] = []
    for path in candidates:
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if path.is_symlink() or not path.is_file() or any(part.startswith(".") for part in rel.parts):
            continue
        if "partial" in path.name.lower():
            continue
        result.append(path)
    return result


def _unit(family: str, model_id: str, root: Path, files: list[Path], *, complete: bool, reason: str | None = None):
    unique = sorted(set(files))
    return {
        "id": f"{family}:{model_id}",
        "family": family,
        "model_id": model_id,
        "complete": complete,
        "selectable": complete,
        "size": sum(path.stat().st_size for path in unique if path.exists()),
        "file_count": len(unique),
        "reason": reason,
        "_root": root,
        "_files": unique,
    }


def _ollama_units() -> list[dict[str, Any]]:
    root = config.MODEL_PATHS.ollama.resolve()
    manifests = root / "manifests"
    blobs = root / "blobs"
    result = []
    if not manifests.is_dir():
        return result
    for manifest in sorted(manifests.rglob("*")):
        if manifest.is_symlink() or not manifest.is_file():
            continue
        rel = manifest.relative_to(manifests)
        if len(rel.parts) < 4:
            continue
        namespace, tag = rel.parts[1], rel.parts[-1]
        name = "/".join(rel.parts[2:-1])
        model_id = f"{name}:{tag}" if namespace == "library" else f"{namespace}/{name}:{tag}"
        try:
            payload = json.loads(manifest.read_text("utf-8"))
            descriptors = [payload.get("config"), *(payload.get("layers") or [])]
            digests = [str(item["digest"]) for item in descriptors if isinstance(item, dict) and item.get("digest")]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError):
            result.append(_unit("ollama", model_id, root, [], complete=False, reason="invalid_manifest"))
            continue
        files = [manifest]
        missing = False
        for digest in digests:
            blob = blobs / digest.replace(":", "-", 1)
            if not blob.is_file() or blob.is_symlink():
                missing = True
            else:
                files.append(blob)
        complete = bool(digests) and not missing
        result.append(_unit("ollama", model_id, root, files, complete=complete, reason=None if complete else "missing_blob"))
    return result


def _asr_units() -> list[dict[str, Any]]:
    result = []
    for item in downloads.list_local_models():
        model_id = str(item.get("name") or "")
        if not item.get("installed"):
            continue
        if item.get("backend") == "whisper_cpp":
            root = config.MODEL_PATHS.whisper_cpp.resolve()
            model = whisper_cpp_model_path(model_id)
            files = _regular_files(root, model)
            coreml = whisper_cpp_coreml_path(model_id)
            if coreml.exists():
                files.extend(_regular_files(root, coreml))
            result.append(_unit("whisper-cpp", model_id, root, files, complete=bool(files)))
        else:
            root = config.MODEL_PATHS.whisper.resolve()
            model_dir = Path(str(item.get("path") or ""))
            files = _regular_files(root, model_dir)
            result.append(_unit("faster-whisper", model_id, root, files, complete=bool(files)))
    return result


def _piper_units() -> list[dict[str, Any]]:
    root = config.MODEL_PATHS.piper.resolve()
    seen: set[str] = set()
    result = []
    for voice in PiperProvider().list_voices():
        model = Path(voice.model_path).resolve()
        key = str(model)
        if key in seen:
            continue
        seen.add(key)
        files = _regular_files(root, model) + _regular_files(root, Path(voice.config_path))
        result.append(_unit("piper", model.relative_to(root).with_suffix("").as_posix(), root, files, complete=len(files) == 2))
    return result


def export_units() -> list[dict[str, Any]]:
    return [*_ollama_units(), *_asr_units(), *_piper_units()]


def export_inventory() -> dict[str, Any]:
    units = export_units()
    public = [{key: value for key, value in unit.items() if not key.startswith("_")} for unit in units]
    unique_files = {str(path): path for unit in units if unit["complete"] for path in unit["_files"]}
    return {
        "models": public,
        "complete_count": sum(1 for unit in units if unit["complete"]),
        "total_unique_size": sum(path.stat().st_size for path in unique_files.values()),
        "container": {"extension": ".localgpt-models", "format": "zip64", "compression": "stored"},
    }
