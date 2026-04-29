from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import threading
import time
import uuid
from typing import Any

from fastapi import HTTPException

from .. import config

LOGGER = logging.getLogger(__name__)
MODEL_PULLS: dict[str, dict[str, Any]] = {}
MODEL_PULL_PROCS: dict[str, subprocess.Popen] = {}
MODEL_PULL_LOCK = threading.Lock()
AUTO_PULL_TRIGGERED = False
DEFAULT_LLAMA_MODEL = os.getenv("DEFAULT_LOCAL_MODEL", config.MODEL_RECOMMENDATIONS[0]["name"])


def _public_pull_status(data: dict[str, Any]) -> dict[str, Any]:
    copy = dict(data)
    copy.pop("_last_completed", None)
    copy.pop("_last_ts", None)
    return copy


def _pull_statuses() -> list[dict[str, Any]]:
    with MODEL_PULL_LOCK:
        return [_public_pull_status(item) for item in MODEL_PULLS.values()]


def _update_pull(task_id: str, **fields: Any) -> None:
    with MODEL_PULL_LOCK:
        if task_id not in MODEL_PULLS:
            return
        MODEL_PULLS[task_id].update(fields)
        if fields.get("state") == "canceled":
            MODEL_PULL_PROCS.pop(task_id, None)


def _list_local_models() -> list[dict[str, Any]]:
    cmd_json = ["ollama", "list", "--json"]
    try:
        result = subprocess.run(
            cmd_json,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            env=config.OLLAMA_ENV,
        )
    except FileNotFoundError as exc:  # pragma: no cover - зависит от окружения
        raise HTTPException(status_code=500, detail="Ollama не установлена или недоступна.") from exc
    except subprocess.SubprocessError as exc:  # pragma: no cover - зависит от окружения
        raise HTTPException(status_code=500, detail="Ошибка обращения к Ollama.") from exc

    stdout = result.stdout or ""
    stderr = (result.stderr or "").strip()
    fallback_plain = result.returncode != 0 and "unknown flag: --json" in stderr.lower()

    lines: list[str] = []
    if not fallback_plain:
        if result.returncode != 0:
            msg = stderr or "не удалось получить список моделей"
            raise HTTPException(status_code=500, detail={"code": "ollama_list_failed", "message": msg})
        lines = stdout.splitlines()
    else:
        try:
            plain = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
                env=config.OLLAMA_ENV,
            )
        except Exception as exc:  # pragma: no cover - зависит от окружения
            raise HTTPException(status_code=500, detail={"code": "ollama_list_failed", "message": str(exc)}) from exc
        if plain.returncode != 0:
            msg = (plain.stderr or plain.stdout or "не удалось получить список моделей").strip()
            raise HTTPException(status_code=500, detail={"code": "ollama_list_failed", "message": msg})
        lines = (plain.stdout or "").splitlines()
        lines = [line for line in lines if line.strip() and not line.lower().startswith("name ")]

    models: list[dict[str, Any]] = []
    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
            name = (payload.get("model") or payload.get("name") or "").strip()
            size = payload.get("size")
            modified_at = payload.get("modified_at")
        except json.JSONDecodeError:
            parts = raw.split()
            if not parts:
                continue
            name = parts[0]
            size = None
            modified_at = None
        models.append(
            {
                "name": name,
                "size": size,
                "size_gb": round(size / (1024**3), 2) if isinstance(size, (int, float)) else None,
                "modified_at": modified_at,
            }
        )
    return models


def _run_model_pull(task_id: str, model: str) -> None:
    start_ts = time.time()
    _update_pull(task_id, state="running", started_at=start_ts)

    def _run(cmd: list[str], parse_json: bool) -> tuple[int, str | None]:
        nonlocal start_ts
        last_completed = 0
        last_ts = start_ts
        raw_error = None
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=config.OLLAMA_ENV
            )
            with MODEL_PULL_LOCK:
                MODEL_PULL_PROCS[task_id] = process
        except FileNotFoundError:
            _update_pull(task_id, state="error", message="Ollama не установлена", finished_at=time.time())
            return 1, "Ollama не установлена"
        except Exception as exc:  # pragma: no cover - зависит от окружения
            _update_pull(task_id, state="error", message=str(exc), finished_at=time.time())
            return 1, str(exc)

        try:
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                with MODEL_PULL_LOCK:
                    if MODEL_PULLS.get(task_id, {}).get("state") == "canceled":
                        process.terminate()
                        break
                if parse_json:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        if "unknown flag: --json" in line.lower():
                            raw_error = "unknown flag: --json"
                            break
                        continue

                    status_text = payload.get("status") or payload.get("digest") or ""
                    total = payload.get("total")
                    completed = payload.get("completed")

                    percent = None
                    speed_mbps = None
                    eta_seconds = None

                    if isinstance(total, (int, float)) and isinstance(completed, (int, float)) and total > 0:
                        percent = round(100 * completed / total, 2)
                        now = time.time()
                        delta_bytes = completed - last_completed
                        delta_time = max(now - last_ts, 1e-3)
                        if delta_bytes > 0:
                            speed_mbps = round(delta_bytes / delta_time / (1024 * 1024), 2)
                            remaining = total - completed
                            eta_seconds = round(remaining / (delta_bytes / delta_time)) if delta_bytes else None
                        last_completed = completed
                        last_ts = now

                    _update_pull(
                        task_id,
                        state="running",
                        message=status_text,
                        completed=completed,
                        total=total,
                        percent=percent,
                        speed_mbps=speed_mbps,
                        eta_seconds=eta_seconds,
                        _last_completed=last_completed,
                        _last_ts=last_ts,
                    )
                else:
                    _update_pull(task_id, state="running", message=line)

            process.wait()
            finished = time.time()
            with MODEL_PULL_LOCK:
                current_state = MODEL_PULLS.get(task_id, {}).get("state")
            if current_state == "canceled":
                _update_pull(task_id, state="canceled", message="Остановлено пользователем", finished_at=finished)
                return process.returncode, raw_error
            if process.returncode == 0:
                _update_pull(task_id, state="completed", message="Готово", finished_at=finished)
            else:
                _update_pull(
                    task_id,
                    state="error",
                    message=f"ollama pull вернул код {process.returncode}",
                    finished_at=finished,
                )
            return process.returncode, raw_error
        finally:
            with MODEL_PULL_LOCK:
                if task_id in MODEL_PULLS:
                    MODEL_PULLS[task_id]["finished_at"] = MODEL_PULLS[task_id].get("finished_at") or time.time()
                MODEL_PULL_PROCS.pop(task_id, None)

    rc, err = _run(["ollama", "pull", model, "--json"], parse_json=True)
    if err and "unknown flag: --json" in err.lower():
        _update_pull(task_id, state="running", message="Старая версия Ollama, включён текстовый прогресс")
        _run(["ollama", "pull", model], parse_json=False)


def start_model_pull(model: str) -> dict[str, Any]:
    task_id = uuid.uuid4().hex
    entry = {
        "task_id": task_id,
        "model": model,
        "state": "pending",
        "message": "Запуск загрузки…",
        "started_at": None,
        "finished_at": None,
        "completed": None,
        "total": None,
    }
    with MODEL_PULL_LOCK:
        active = next(
            (
                item
                for item in MODEL_PULLS.values()
                if item.get("model") == model and item.get("state") in {"pending", "running"}
            ),
            None,
        )
        if active:
            return _public_pull_status(active)
        MODEL_PULLS[task_id] = entry

    thread = threading.Thread(target=_run_model_pull, args=(task_id, model), daemon=True)
    thread.start()
    return _public_pull_status(entry)


def _maybe_trigger_default_pull(installed: list[dict[str, Any]], downloads: list[dict[str, Any]]) -> None:
    global AUTO_PULL_TRIGGERED
    if AUTO_PULL_TRIGGERED:
        return
    if installed:
        return
    active = [item for item in downloads if item.get("state") in {"pending", "running"}]
    if active:
        return
    AUTO_PULL_TRIGGERED = True
    downloads.append(start_model_pull(DEFAULT_LLAMA_MODEL))


def cancel_model_pull(task_id: str) -> dict[str, Any]:
    with MODEL_PULL_LOCK:
        entry = MODEL_PULLS.get(task_id)
        process = MODEL_PULL_PROCS.get(task_id)
    if not entry:
        raise HTTPException(status_code=404, detail="task_not_found")
    if entry.get("state") in {"completed", "error", "canceled"}:
        return _public_pull_status(entry)

    _update_pull(task_id, state="canceled", message="Остановлено пользователем", finished_at=time.time())
    if process and process.poll() is None:
        try:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        finally:
            with MODEL_PULL_LOCK:
                MODEL_PULL_PROCS.pop(task_id, None)

    return _public_pull_status(MODEL_PULLS[task_id])


def pause_model_pull(task_id: str) -> dict[str, Any]:
    with MODEL_PULL_LOCK:
        entry = MODEL_PULLS.get(task_id)
        process = MODEL_PULL_PROCS.get(task_id)
    if not entry:
        raise HTTPException(status_code=404, detail="task_not_found")
    if entry.get("state") not in {"running"} or process is None:
        return _public_pull_status(entry)
    try:
        process.send_signal(signal.SIGSTOP)
        _update_pull(task_id, state="paused", message="Пауза", finished_at=None)
    except Exception as exc:  # pragma: no cover - сигналы зависят от ОС
        raise HTTPException(status_code=500, detail=f"Не удалось поставить на паузу: {exc}") from exc
    return _public_pull_status(MODEL_PULLS[task_id])


def resume_model_pull(task_id: str) -> dict[str, Any]:
    with MODEL_PULL_LOCK:
        entry = MODEL_PULLS.get(task_id)
        process = MODEL_PULL_PROCS.get(task_id)
    if not entry:
        raise HTTPException(status_code=404, detail="task_not_found")
    if entry.get("state") not in {"paused"} or process is None:
        return _public_pull_status(entry)
    try:
        process.send_signal(signal.SIGCONT)
        _update_pull(task_id, state="running", message="Возобновлено", finished_at=None)
    except Exception as exc:  # pragma: no cover - сигналы зависят от ОС
        raise HTTPException(status_code=500, detail=f"Не удалось возобновить: {exc}") from exc
    return _public_pull_status(MODEL_PULLS[task_id])


def list_models() -> dict[str, Any]:
    error = None
    try:
        installed = _list_local_models()
    except HTTPException as exc:
        installed = []
        error = exc.detail
        LOGGER.warning("Оllama list failed: %s", exc.detail)
    downloads = _pull_statuses()
    if not error:
        _maybe_trigger_default_pull(installed, downloads)
    return {
        "installed": installed,
        "models": [item.get("name") for item in installed if item.get("name")],
        "recommended": config.MODEL_RECOMMENDATIONS,
        "downloads": downloads,
        "error": error,
    }


def delete_model(model_name: str) -> dict[str, Any]:
    target = (model_name or "").strip()
    if not target:
        raise HTTPException(status_code=422, detail={"code": "model_required", "message": "Укажите модель"})

    try:
        result = subprocess.run(
            ["ollama", "rm", target], capture_output=True, text=True, check=False, timeout=30, env=config.OLLAMA_ENV
        )
    except FileNotFoundError as exc:  # pragma: no cover - зависит от окружения
        raise HTTPException(status_code=500, detail="Ollama не установлена или недоступна.") from exc
    except subprocess.SubprocessError as exc:  # pragma: no cover - зависит от окружения
        raise HTTPException(status_code=500, detail="Ошибка удаления модели через Ollama") from exc

    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "Не удалось удалить модель").strip()
        raise HTTPException(status_code=500, detail={"code": "ollama_rm_failed", "message": msg})

    return {"deleted": target}


def pull_status(task_id: str) -> dict[str, Any]:
    with MODEL_PULL_LOCK:
        entry = MODEL_PULLS.get(task_id)
    if not entry:
        raise HTTPException(status_code=404, detail="task_not_found")
    return _public_pull_status(entry)


def pull_statuses() -> dict[str, Any]:
    return {"downloads": _pull_statuses()}
