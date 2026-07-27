from __future__ import annotations

import json
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app import config
from .inventory import export_units
from .manifest import SCHEMA, VERSION, sha256_file

_LOCK = threading.Lock()
_TASKS: dict[str, dict[str, Any]] = {}
_CANCEL: dict[str, threading.Event] = {}


def _public(task: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task.items() if key != "archive_path"}


def _entry_path(unit: dict[str, Any], path: Path) -> str:
    return f"payload/{unit['family']}/{path.relative_to(unit['_root']).as_posix()}"


def _run(task_id: str, selected: list[str]) -> None:
    task = _TASKS[task_id]
    try:
        units = [unit for unit in export_units() if unit["id"] in selected]
        if len(units) != len(set(selected)) or any(not unit["complete"] for unit in units):
            raise ValueError("source_model_partial")
        staging = config.DATA_DIR / "model_transfer"
        staging.mkdir(parents=True, exist_ok=True)
        archive = staging / f"{task_id}.localgpt-models"
        files: dict[str, tuple[dict[str, Any], Path]] = {}
        for unit in units:
            for path in unit["_files"]:
                files.setdefault(_entry_path(unit, path).casefold(), (unit, path))
        task.update(total_bytes=sum(path.stat().st_size for _, path in files.values()), total_files=len(files))
        manifest_files = []
        model_files: dict[str, list[str]] = {unit["id"]: [] for unit in units}
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as bundle:
            for unit, path in files.values():
                if _CANCEL[task_id].is_set():
                    raise InterruptedError("cancelled")
                entry = _entry_path(unit, path)
                digest = sha256_file(path)
                bundle.write(path, entry)
                size = path.stat().st_size
                manifest_files.append({"path": entry, "size": size, "sha256": digest})
                model_files[unit["id"]].append(entry)
                task["processed_bytes"] += size
                task["processed_files"] += 1
                task["current_file"] = path.name
            manifest = {
                "schema": SCHEMA,
                "version": VERSION,
                "bundle_id": task_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "models": [
                    {"id": unit["id"], "family": unit["family"], "model_id": unit["model_id"], "files": model_files[unit["id"]]}
                    for unit in units
                ],
                "files": manifest_files,
            }
            bundle.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, separators=(",", ":")))
        task.update(status="completed", archive_path=str(archive), filename=f"LocalGPT-models-{task_id[:8]}.localgpt-models")
    except InterruptedError:
        task["status"] = "cancelled"
    except Exception as exc:
        task.update(status="failed", error_code=str(exc))
    finally:
        if task["status"] != "completed":
            path = Path(task.get("archive_path") or config.DATA_DIR / "model_transfer" / f"{task_id}.localgpt-models")
            path.unlink(missing_ok=True)


def start_export(selected: list[str]) -> dict[str, Any]:
    clean = list(dict.fromkeys(str(item).strip() for item in selected if str(item).strip()))
    if not clean:
        raise ValueError("selection_required")
    task_id = str(uuid.uuid4())
    task = {"task_id": task_id, "status": "running", "processed_bytes": 0, "processed_files": 0}
    with _LOCK:
        _TASKS[task_id] = task
        _CANCEL[task_id] = threading.Event()
    threading.Thread(target=_run, args=(task_id, clean), daemon=True).start()
    return _public(task)


def get_task(task_id: str) -> dict[str, Any] | None:
    with _LOCK:
        task = _TASKS.get(task_id)
        return _public(task) if task else None


def cancel(task_id: str) -> dict[str, Any] | None:
    with _LOCK:
        event, task = _CANCEL.get(task_id), _TASKS.get(task_id)
        if not event or not task:
            return None
        event.set()
        return _public(task)


def archive_path(task_id: str) -> tuple[Path, str] | None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task or task.get("status") != "completed":
            return None
        return Path(task["archive_path"]), task["filename"]
