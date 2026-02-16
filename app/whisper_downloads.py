from __future__ import annotations

import os
import socket
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from . import config
from .asr_whisper import is_local_model_ready, local_model_dir, repository_for_model

_TASKS: dict[str, dict[str, Any]] = {}
_ACTIVE_BY_MODEL: dict[str, str] = {}
_LOCK = threading.Lock()
_CHUNK_SIZE = 1024 * 512
_PROGRESS_INTERVAL_SECONDS = 0.2
_DEFAULT_HF_ENDPOINT = "https://huggingface.co"
_DEFAULT_HF_FALLBACK_ENDPOINT = "https://hf-mirror.com"


class PrepareModelError(Exception):
    pass


def _now() -> float:
    return time.time()


def _sanitize_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id"),
        "model": task.get("model"),
        "repo_id": task.get("repo_id"),
        "state": task.get("state"),
        "message": task.get("message"),
        "percent": task.get("percent", 0.0),
        "speed_bps": task.get("speed_bps", 0.0),
        "downloaded_bytes": task.get("downloaded_bytes", 0),
        "total_bytes": task.get("total_bytes", 0),
        "started_at": task.get("started_at"),
        "finished_at": task.get("finished_at"),
    }


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _hf_token_raw() -> str:
    return (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACE_TOKEN")
        or os.getenv("HUGGINGFACE_HUB_TOKEN")
        or ""
    ).strip()


def _is_ascii_text(value: str) -> bool:
    try:
        value.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _has_invalid_hf_token() -> bool:
    raw = _hf_token_raw()
    return bool(raw) and not _is_ascii_text(raw)


def _hf_token() -> str:
    token = _hf_token_raw()
    if not token:
        return ""
    if not _is_ascii_text(token):
        return ""
    return token


def _http_headers() -> dict[str, str]:
    headers = {"User-Agent": "LocalGPT-Whisper-Transcriber/1.0"}
    token = _hf_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _huggingface_endpoints() -> list[str]:
    primary = (os.getenv("HF_ENDPOINT") or _DEFAULT_HF_ENDPOINT).strip().rstrip("/")
    fallback = (os.getenv("HF_FALLBACK_ENDPOINT") or _DEFAULT_HF_FALLBACK_ENDPOINT).strip().rstrip("/")

    endpoints: list[str] = []
    for item in (primary, fallback, _DEFAULT_HF_ENDPOINT):
        if item and item not in endpoints:
            endpoints.append(item)

    return endpoints


def _endpoint_host(endpoint: str) -> str:
    return endpoint.split("://", 1)[-1]


def _join_url(endpoint: str, path: str) -> str:
    return f"{endpoint.rstrip('/')}/{path.lstrip('/')}"


def _update_task(task_id: str, **fields: Any) -> None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        task.update(fields)


def _get_model_files(client: httpx.Client, endpoint: str, repo_id: str) -> list[dict[str, Any]]:
    response = client.get(_join_url(endpoint, f"/api/models/{repo_id}"))
    response.raise_for_status()

    payload = response.json()
    siblings = payload.get("siblings") or []

    files: list[dict[str, Any]] = []
    for sibling in siblings:
        filename = sibling.get("rfilename")
        if not filename:
            continue
        if filename.startswith("."):
            continue
        if filename.endswith(".gitattributes"):
            continue
        files.append(
            {
                "name": filename,
                "size": int(sibling.get("size") or 0),
            }
        )

    if not files:
        raise PrepareModelError("Список файлов модели пуст")

    for item in files:
        if item["size"] > 0:
            continue
        encoded_name = quote(item["name"], safe="/")
        head = client.head(_join_url(endpoint, f"/{repo_id}/resolve/main/{encoded_name}"))
        if head.status_code < 400:
            item["size"] = int(head.headers.get("Content-Length") or 0)

    return files


def _calculate_existing_bytes(model_dir: Path, files: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    existing = 0
    pending: list[dict[str, Any]] = []

    for item in files:
        target = model_dir / item["name"]
        expected = int(item.get("size") or 0)
        if target.exists() and expected > 0:
            try:
                current_size = target.stat().st_size
            except OSError:
                current_size = 0
            if current_size >= expected:
                existing += expected
                continue
        pending.append(item)

    return existing, pending


def _is_dns_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, socket.gaierror):
            return True
        if isinstance(current, OSError) and getattr(current, "errno", None) == 8:
            return True
        current = current.__cause__ or current.__context__

    message = str(exc).lower()
    markers = (
        "nodename nor servname provided",
        "name or service not known",
        "temporary failure in name resolution",
        "failed to resolve",
    )
    return any(marker in message for marker in markers)


def _http_status_from_exception(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    status = getattr(response, "status_code", None)
    return int(status) if isinstance(status, int) else None


def _is_auth_error(exc: BaseException) -> bool:
    status = _http_status_from_exception(exc)
    if status in {401, 403}:
        return True

    message = str(exc).lower()
    return "401" in message or "403" in message


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0

    total = 0
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            total += file_path.stat().st_size
        except OSError:
            continue

    return total


def _format_download_error(endpoint: str, exc: BaseException) -> str:
    host = _endpoint_host(endpoint)

    if _has_invalid_hf_token() or isinstance(exc, UnicodeEncodeError):
        return (
            "HF_TOKEN в .env содержит недопустимые символы. "
            "Используйте только ASCII токен вида hf_xxx (без кавычек) "
            "или удалите строку HF_TOKEN и используйте HF_FALLBACK_ENDPOINT."
        )

    if _is_dns_error(exc):
        return (
            f"Не удалось подключиться к {host} (ошибка DNS). "
            "Проверьте интернет/VPN/DNS. "
            "При необходимости задайте HF_ENDPOINT в .env."
        )

    if isinstance(exc, httpx.TimeoutException):
        return f"Тайм-аут загрузки модели с {host}. Попробуйте снова."

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 404:
            return f"Репозиторий модели недоступен на {host} (404)."
        if status in {401, 403}:
            if _hf_token():
                return f"Нет доступа к модели на {host} (HTTP {status}) даже с HF_TOKEN."
            return (
                f"Нет доступа к модели на {host} (HTTP {status}). "
                "Добавьте HF_TOKEN в .env (или выполните huggingface-cli login) "
                "или задайте HF_FALLBACK_ENDPOINT (например https://hf-mirror.com), "
                "затем перезапустите сервер."
            )
        return f"Ошибка HTTP {status} при загрузке модели с {host}."

    status = _http_status_from_exception(exc)
    if status in {401, 403}:
        if _hf_token():
            return f"Нет доступа к модели на {host} (HTTP {status}) даже с HF_TOKEN."
        return (
            f"Нет доступа к модели на {host} (HTTP {status}). "
            "Добавьте HF_TOKEN в .env (или выполните huggingface-cli login) "
            "или задайте HF_FALLBACK_ENDPOINT (например https://hf-mirror.com), "
            "затем перезапустите сервер."
        )

    return str(exc)


def _download_from_endpoint(task_id: str, model: str, endpoint: str) -> tuple[int, int, float]:
    repo_id = repository_for_model(model)
    model_dir = local_model_dir(model)
    model_dir.mkdir(parents=True, exist_ok=True)

    trust_env = _env_flag("HF_TRUST_ENV", default=False)
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(90.0, connect=30.0),
        trust_env=trust_env,
        headers=_http_headers(),
    ) as client:
        files = _get_model_files(client, endpoint, repo_id)
        total_bytes = sum(int(item.get("size") or 0) for item in files)

        existing_bytes, pending = _calculate_existing_bytes(model_dir, files)
        downloaded_bytes = existing_bytes
        start_ts = _now()
        last_progress_ts = 0.0

        _update_task(
            task_id,
            total_bytes=total_bytes,
            downloaded_bytes=downloaded_bytes,
            percent=(100.0 if total_bytes > 0 and downloaded_bytes >= total_bytes else 0.0),
            speed_bps=0.0,
            message="Проверка локального кэша",
        )

        for item in pending:
            filename = item["name"]
            expected_size = int(item.get("size") or 0)
            target = model_dir / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            encoded_name = quote(filename, safe="/")
            url = _join_url(endpoint, f"/{repo_id}/resolve/main/{encoded_name}")
            temp_path = target.with_suffix(target.suffix + ".part")

            _update_task(task_id, message=f"Загрузка: {filename}")

            with client.stream("GET", url) as response:
                response.raise_for_status()

                with temp_path.open("wb") as out:
                    for chunk in response.iter_bytes(chunk_size=_CHUNK_SIZE):
                        if not chunk:
                            continue
                        out.write(chunk)
                        downloaded_bytes += len(chunk)

                        now_ts = _now()
                        if now_ts - last_progress_ts >= _PROGRESS_INTERVAL_SECONDS:
                            elapsed = max(now_ts - start_ts, 0.001)
                            speed = downloaded_bytes / elapsed
                            percent = 0.0
                            if total_bytes > 0:
                                percent = min(100.0, round(downloaded_bytes / total_bytes * 100.0, 2))

                            _update_task(
                                task_id,
                                percent=percent,
                                speed_bps=speed,
                                downloaded_bytes=downloaded_bytes,
                                total_bytes=total_bytes,
                            )
                            last_progress_ts = now_ts

            temp_path.replace(target)

            if expected_size <= 0:
                try:
                    expected_size = target.stat().st_size
                except OSError:
                    expected_size = 0
                item["size"] = expected_size

        final_elapsed = max(_now() - start_ts, 0.001)
        final_speed = downloaded_bytes / final_elapsed
        return downloaded_bytes, max(total_bytes, downloaded_bytes), final_speed


def _download_via_hf_hub(task_id: str, model: str, endpoint: str) -> tuple[int, int, float]:
    from huggingface_hub import snapshot_download

    repo_id = repository_for_model(model)
    model_dir = local_model_dir(model)
    model_dir.mkdir(parents=True, exist_ok=True)

    size_before = _directory_size(model_dir)
    start_ts = _now()
    stop_event = threading.Event()

    def _monitor() -> None:
        while not stop_event.wait(_PROGRESS_INTERVAL_SECONDS):
            current_size = _directory_size(model_dir)
            downloaded = max(current_size - size_before, 0)
            elapsed = max(_now() - start_ts, 0.001)
            _update_task(
                task_id,
                message="Загрузка через huggingface_hub...",
                percent=0.0,
                speed_bps=downloaded / elapsed,
                downloaded_bytes=downloaded,
                total_bytes=0,
            )

    monitor_thread = threading.Thread(target=_monitor, daemon=True)
    monitor_thread.start()
    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(model_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
            endpoint=endpoint,
            token=_hf_token() or None,
        )
    finally:
        stop_event.set()
        monitor_thread.join(timeout=2.0)

    size_after = _directory_size(model_dir)
    downloaded = max(size_after - size_before, 0)
    elapsed = max(_now() - start_ts, 0.001)
    return downloaded, downloaded, downloaded / elapsed


def _run_prepare_task(task_id: str) -> None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        model = task["model"]

    try:
        repo_id = repository_for_model(model)
        model_dir = local_model_dir(model)
        model_dir.mkdir(parents=True, exist_ok=True)

        _update_task(task_id, state="running", repo_id=repo_id, message="Получение списка файлов модели")
        if _has_invalid_hf_token():
            _update_task(
                task_id,
                message=(
                    "HF_TOKEN содержит не-ASCII символы, токен будет проигнорирован. "
                    "Укажите ASCII токен вида hf_xxx или удалите HF_TOKEN."
                ),
            )

        endpoints = _huggingface_endpoints()
        for idx, endpoint in enumerate(endpoints):
            _update_task(task_id, message=f"Подключение к {_endpoint_host(endpoint)}")

            try:
                downloaded_bytes, total_bytes, final_speed = _download_from_endpoint(task_id, model, endpoint)
            except Exception as exc:
                if _is_auth_error(exc):
                    try:
                        _update_task(
                            task_id,
                            message="Получен HTTP 401/403. Пробуем загрузку через huggingface_hub...",
                        )
                        downloaded_bytes, total_bytes, final_speed = _download_via_hf_hub(task_id, model, endpoint)
                    except Exception as fallback_exc:
                        error_message = _format_download_error(endpoint, fallback_exc)
                        has_next_endpoint = idx < len(endpoints) - 1

                        if has_next_endpoint:
                            _update_task(
                                task_id,
                                message=f"{error_message} Пробуем резервный endpoint...",
                            )
                            continue

                        raise PrepareModelError(error_message) from fallback_exc
                else:
                    error_message = _format_download_error(endpoint, exc)
                    has_next_endpoint = idx < len(endpoints) - 1

                    if has_next_endpoint:
                        _update_task(
                            task_id,
                            message=f"{error_message} Пробуем резервный endpoint...",
                        )
                        continue

                    raise PrepareModelError(error_message) from exc

            if not is_local_model_ready(model):
                raise PrepareModelError("Модель загружена не полностью")

            _update_task(
                task_id,
                state="completed",
                message="Модель готова",
                percent=100.0,
                speed_bps=final_speed,
                downloaded_bytes=downloaded_bytes,
                total_bytes=total_bytes,
                finished_at=_now(),
            )
            return

    except Exception as exc:
        _update_task(
            task_id,
            state="error",
            message=str(exc),
            finished_at=_now(),
        )
    finally:
        with _LOCK:
            task = _TASKS.get(task_id)
            if task and _ACTIVE_BY_MODEL.get(task["model"]) == task_id:
                _ACTIVE_BY_MODEL.pop(task["model"], None)


def start_prepare_task(model_name: str) -> dict[str, Any]:
    model = (model_name or "").strip()
    if model not in config.ALLOWED_WHISPER_MODELS:
        raise ValueError("invalid_model")

    if is_local_model_ready(model):
        task_id = uuid.uuid4().hex
        task = {
            "task_id": task_id,
            "model": model,
            "repo_id": repository_for_model(model),
            "state": "completed",
            "message": "Модель уже доступна локально",
            "percent": 100.0,
            "speed_bps": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "started_at": _now(),
            "finished_at": _now(),
        }
        with _LOCK:
            _TASKS[task_id] = task
        return _sanitize_task(task)

    with _LOCK:
        active_task_id = _ACTIVE_BY_MODEL.get(model)
        if active_task_id:
            active_task = _TASKS.get(active_task_id)
            if active_task and active_task.get("state") in {"pending", "running"}:
                return _sanitize_task(active_task)

        task_id = uuid.uuid4().hex
        task = {
            "task_id": task_id,
            "model": model,
            "repo_id": repository_for_model(model),
            "state": "pending",
            "message": "Подготовка загрузки",
            "percent": 0.0,
            "speed_bps": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "started_at": _now(),
            "finished_at": None,
        }
        _TASKS[task_id] = task
        _ACTIVE_BY_MODEL[model] = task_id

    thread = threading.Thread(target=_run_prepare_task, args=(task_id,), daemon=True)
    thread.start()
    return _sanitize_task(task)


def get_prepare_task(task_id: str) -> dict[str, Any] | None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return None
        return _sanitize_task(task)
