from __future__ import annotations

import json
import os
import shutil
import socket
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app import config
from backend.apps.asr.whisper import clear_model_cache, is_local_model_ready, local_model_dir, repository_for_model
from backend.apps.asr.whisper_cpp import is_whisper_cpp_model_ready, whisper_cpp_model_path

_TASKS: dict[str, dict[str, Any]] = {}
_ACTIVE_BY_MODEL: dict[str, str] = {}
_LOCK = threading.Lock()
_CHUNK_SIZE = 1024 * 512
_PROGRESS_INTERVAL_SECONDS = 0.2
_DEFAULT_HF_ENDPOINT = "https://huggingface.co"
_DEFAULT_HF_FALLBACK_ENDPOINT = "https://hf-mirror.com"
_MODEL_META_FILENAME = ".localgpt_model_meta.json"
_DEFAULT_WHISPER_CPP_REPO = "ggerganov/whisper.cpp"


class PrepareModelError(Exception):
    def __init__(self, message: str, *, code: str = "model_prepare_failed") -> None:
        super().__init__(message)
        self.code = code


def _now() -> float:
    return time.time()


def _sanitize_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id"),
        "model": task.get("model"),
        "repo_id": task.get("repo_id"),
        "force": bool(task.get("force", False)),
        "revision": task.get("revision"),
        "state": task.get("state"),
        "message": task.get("message"),
        "error_code": task.get("error_code"),
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _model_meta_path(model_name: str) -> Path:
    return local_model_dir(model_name) / _MODEL_META_FILENAME


def _use_whisper_cpp_models() -> bool:
    return config.SETTINGS.whisper_backend in {"auto", "whisper_cpp"}


def _whisper_cpp_repo_id() -> str:
    return (os.getenv("WHISPER_CPP_HF_REPO") or _DEFAULT_WHISPER_CPP_REPO).strip() or _DEFAULT_WHISPER_CPP_REPO


def _whisper_cpp_meta_path(model_name: str) -> Path:
    model_path = whisper_cpp_model_path(model_name)
    return model_path.with_name(f"{model_path.name}.localgpt.json")


def _read_whisper_cpp_meta(model_name: str) -> dict[str, Any]:
    path = _whisper_cpp_meta_path(model_name)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_whisper_cpp_meta(
    model_name: str,
    *,
    revision: str | None,
    endpoint: str | None,
    etag: str | None = None,
    size: int | None = None,
) -> None:
    model_path = whisper_cpp_model_path(model_name)
    payload = {
        "model": model_name,
        "repo_id": _whisper_cpp_repo_id(),
        "filename": model_path.name,
        "revision": revision or None,
        "endpoint": endpoint or None,
        "etag": etag or None,
        "size": size if size is not None else None,
        "updated_at": _utc_now(),
    }
    try:
        model_path.parent.mkdir(parents=True, exist_ok=True)
        _whisper_cpp_meta_path(model_name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return


def _read_whisper_cpp_revision(model_name: str) -> str | None:
    raw = _read_whisper_cpp_meta(model_name).get("revision")
    if not raw:
        return None
    value = str(raw).strip()
    return value or None


def _read_model_meta(model_name: str) -> dict[str, Any]:
    path = _model_meta_path(model_name)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_local_revision(model_name: str) -> str | None:
    raw = _read_model_meta(model_name).get("revision")
    if not raw:
        return None
    value = str(raw).strip()
    return value or None


def _write_model_meta(model_name: str, *, revision: str | None, endpoint: str | None) -> None:
    path = _model_meta_path(model_name)
    payload = {
        "model": model_name,
        "repo_id": repository_for_model(model_name),
        "revision": revision or None,
        "endpoint": endpoint or None,
        "updated_at": _utc_now(),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return


def _fetch_model_payload(client: httpx.Client, endpoint: str, repo_id: str) -> dict[str, Any]:
    response = client.get(_join_url(endpoint, f"/api/models/{repo_id}"))
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _get_model_files(client: httpx.Client, endpoint: str, repo_id: str) -> tuple[list[dict[str, Any]], str | None]:
    payload = _fetch_model_payload(client, endpoint, repo_id)
    siblings = payload.get("siblings") or []
    revision_raw = payload.get("sha")
    revision = str(revision_raw).strip() if revision_raw else None

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
        raise PrepareModelError("Список файлов модели пуст", code="download_empty_file_list")

    for item in files:
        if item["size"] > 0:
            continue
        encoded_name = quote(item["name"], safe="/")
        head = client.head(_join_url(endpoint, f"/{repo_id}/resolve/main/{encoded_name}"))
        if head.status_code < 400:
            item["size"] = int(head.headers.get("Content-Length") or 0)

    return files, revision


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


def _hf_repo_cache_root(model_name: str) -> Path:
    repo_id = repository_for_model(model_name)
    org, repo_name = repo_id.split("/", 1)
    return config.HF_CACHE_DIR / Path(f"models--{org}--{repo_name}")


def _legacy_model_dirs(model_name: str) -> list[Path]:
    repo_suffix = repository_for_model(model_name).split("/", 1)[1]
    candidates = [
        config.MODELS_DIR / "whisper" / repo_suffix,
        config.MODELS_DIR / "whisper" / model_name,
        config.WHISPER_MODELS_DIR / repo_suffix,
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = str(candidate.resolve())
        except OSError:
            key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _format_download_error(endpoint: str, exc: BaseException) -> tuple[str, str]:
    host = _endpoint_host(endpoint)

    if _has_invalid_hf_token() or isinstance(exc, UnicodeEncodeError):
        return (
            "invalid_hf_token",
            "HF_TOKEN в .env содержит недопустимые символы. "
            "Используйте только ASCII токен вида hf_xxx (без кавычек) "
            "или удалите строку HF_TOKEN и используйте HF_FALLBACK_ENDPOINT."
        )

    if _is_dns_error(exc):
        return (
            "download_dns_error",
            f"Не удалось подключиться к {host} (ошибка DNS). "
            "Проверьте интернет/VPN/DNS. "
            "При необходимости задайте HF_ENDPOINT в .env."
        )

    if isinstance(exc, httpx.TimeoutException):
        return ("download_timeout", f"Тайм-аут загрузки модели с {host}. Попробуйте снова.")

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 404:
            return ("download_model_not_found", f"Репозиторий модели недоступен на {host} (404).")
        if status in {401, 403}:
            if _hf_token():
                return ("download_auth_failed", f"Нет доступа к модели на {host} (HTTP {status}) даже с HF_TOKEN.")
            return (
                "download_auth_required",
                f"Нет доступа к модели на {host} (HTTP {status}). "
                "Добавьте HF_TOKEN в .env (или выполните huggingface-cli login) "
                "или задайте HF_FALLBACK_ENDPOINT (например https://hf-mirror.com), "
                "затем перезапустите сервер."
            )
        return ("download_http_error", f"Ошибка HTTP {status} при загрузке модели с {host}.")

    status = _http_status_from_exception(exc)
    if status in {401, 403}:
        if _hf_token():
            return ("download_auth_failed", f"Нет доступа к модели на {host} (HTTP {status}) даже с HF_TOKEN.")
        return (
            "download_auth_required",
            f"Нет доступа к модели на {host} (HTTP {status}). "
            "Добавьте HF_TOKEN в .env (или выполните huggingface-cli login) "
            "или задайте HF_FALLBACK_ENDPOINT (например https://hf-mirror.com), "
            "затем перезапустите сервер."
        )

    return ("model_prepare_failed", str(exc))


def _download_from_endpoint(task_id: str, model: str, endpoint: str) -> tuple[int, int, float, str | None]:
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
        files, revision = _get_model_files(client, endpoint, repo_id)
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
        return downloaded_bytes, max(total_bytes, downloaded_bytes), final_speed, revision


def _fetch_whisper_cpp_remote_meta(
    client: httpx.Client,
    endpoint: str,
    model: str,
) -> tuple[str | None, str | None, int]:
    repo_id = _whisper_cpp_repo_id()
    filename = whisper_cpp_model_path(model).name
    revision: str | None = None
    try:
        payload = _fetch_model_payload(client, endpoint, repo_id)
        raw_revision = payload.get("sha")
        revision = str(raw_revision).strip() if raw_revision else None
    except Exception:
        revision = None

    encoded_name = quote(filename, safe="/")
    response = client.head(_join_url(endpoint, f"/{repo_id}/resolve/main/{encoded_name}"))
    response.raise_for_status()
    etag = (response.headers.get("ETag") or "").strip().strip('"') or None
    size = int(response.headers.get("Content-Length") or 0)
    return revision, etag, size


def _download_whisper_cpp_from_endpoint(
    task_id: str,
    model: str,
    endpoint: str,
) -> tuple[int, int, float, str | None, str | None]:
    repo_id = _whisper_cpp_repo_id()
    target = whisper_cpp_model_path(model)
    target.parent.mkdir(parents=True, exist_ok=True)
    filename = target.name
    temp_path = target.with_suffix(target.suffix + ".part")

    trust_env = _env_flag("HF_TRUST_ENV", default=False)
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(90.0, connect=30.0),
        trust_env=trust_env,
        headers=_http_headers(),
    ) as client:
        revision, etag, total_bytes = _fetch_whisper_cpp_remote_meta(client, endpoint, model)
        encoded_name = quote(filename, safe="/")
        url = _join_url(endpoint, f"/{repo_id}/resolve/main/{encoded_name}")

        _update_task(
            task_id,
            repo_id=repo_id,
            total_bytes=total_bytes,
            downloaded_bytes=0,
            percent=0.0,
            speed_bps=0.0,
            message=f"Загрузка GGML: {filename}",
        )

        downloaded_bytes = 0
        start_ts = _now()
        last_progress_ts = 0.0
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
                        percent = 0.0
                        if total_bytes > 0:
                            percent = min(100.0, round(downloaded_bytes / total_bytes * 100.0, 2))
                        _update_task(
                            task_id,
                            percent=percent,
                            speed_bps=downloaded_bytes / elapsed,
                            downloaded_bytes=downloaded_bytes,
                            total_bytes=total_bytes,
                        )
                        last_progress_ts = now_ts

        temp_path.replace(target)
        final_elapsed = max(_now() - start_ts, 0.001)
        total_downloaded = downloaded_bytes
        total_expected = max(total_bytes, downloaded_bytes)

        if config.SETTINGS.whisper_cpp_download_coreml:
            coreml_filename = f"ggml-{model}-encoder.mlmodelc.zip"
            coreml_target = target.parent / coreml_filename
            coreml_dir = target.parent / f"ggml-{model}-encoder.mlmodelc"
            if not coreml_dir.exists():
                try:
                    coreml_downloaded, coreml_total = _download_whisper_cpp_extra_file(
                        task_id,
                        client,
                        endpoint,
                        repo_id,
                        coreml_filename,
                        coreml_target,
                        "Загрузка CoreML encoder",
                    )
                    total_downloaded += coreml_downloaded
                    total_expected += coreml_total
                    _update_task(task_id, message="Распаковка CoreML encoder")
                    with zipfile.ZipFile(coreml_target, "r") as archive:
                        archive.extractall(target.parent)
                except Exception as exc:
                    status = _http_status_from_exception(exc)
                    if status != 404:
                        raise
                    _update_task(
                        task_id,
                        message="CoreML encoder не найден для этой модели; GGML-модель готова",
                        error_code=None,
                    )

        final_elapsed = max(_now() - start_ts, 0.001)
        return total_downloaded, total_expected, total_downloaded / final_elapsed, revision, etag


def _download_whisper_cpp_extra_file(
    task_id: str,
    client: httpx.Client,
    endpoint: str,
    repo_id: str,
    filename: str,
    target: Path,
    label: str,
) -> tuple[int, int]:
    encoded_name = quote(filename, safe="/")
    url = _join_url(endpoint, f"/{repo_id}/resolve/main/{encoded_name}")
    temp_path = target.with_suffix(target.suffix + ".part")

    head = client.head(url)
    head.raise_for_status()
    total_bytes = int(head.headers.get("Content-Length") or 0)

    _update_task(
        task_id,
        message=f"{label}: {filename}",
        total_bytes=total_bytes,
        downloaded_bytes=0,
        percent=0.0,
        speed_bps=0.0,
    )

    downloaded_bytes = 0
    start_ts = _now()
    last_progress_ts = 0.0
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
                    percent = 0.0
                    if total_bytes > 0:
                        percent = min(100.0, round(downloaded_bytes / total_bytes * 100.0, 2))
                    _update_task(
                        task_id,
                        percent=percent,
                        speed_bps=downloaded_bytes / elapsed,
                        downloaded_bytes=downloaded_bytes,
                        total_bytes=total_bytes,
                    )
                    last_progress_ts = now_ts

    temp_path.replace(target)
    return downloaded_bytes, max(total_bytes, downloaded_bytes)


def _download_via_hf_hub(task_id: str, model: str, endpoint: str) -> tuple[int, int, float, str | None]:
    from huggingface_hub import snapshot_download

    repo_id = repository_for_model(model)
    model_dir = local_model_dir(model)
    model_dir.mkdir(parents=True, exist_ok=True)
    remote_revision: str | None = None

    trust_env = _env_flag("HF_TRUST_ENV", default=False)
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, connect=20.0),
            trust_env=trust_env,
            headers=_http_headers(),
        ) as client:
            payload = _fetch_model_payload(client, endpoint, repo_id)
            raw_revision = payload.get("sha")
            remote_revision = str(raw_revision).strip() if raw_revision else None
    except Exception:
        remote_revision = None

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
    return downloaded, downloaded, downloaded / elapsed, remote_revision


def _run_prepare_whisper_cpp_task(task_id: str) -> None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        model = task["model"]
        force = bool(task.get("force", False))

    try:
        repo_id = _whisper_cpp_repo_id()
        target = whisper_cpp_model_path(model)

        if force:
            _update_task(task_id, message="Очистка локальной GGML-модели перед обновлением")
            for path in (target, target.with_suffix(target.suffix + ".part"), _whisper_cpp_meta_path(model)):
                try:
                    path.unlink()
                except OSError:
                    pass

        _update_task(task_id, state="running", repo_id=repo_id, message="Подготовка загрузки GGML-модели")
        endpoints = _huggingface_endpoints()
        for idx, endpoint in enumerate(endpoints):
            _update_task(task_id, message=f"Подключение к {_endpoint_host(endpoint)}")
            try:
                downloaded_bytes, total_bytes, final_speed, remote_revision, etag = _download_whisper_cpp_from_endpoint(
                    task_id, model, endpoint
                )
            except Exception as exc:
                error_code, error_message = _format_download_error(endpoint, exc)
                has_next_endpoint = idx < len(endpoints) - 1
                if has_next_endpoint:
                    _update_task(
                        task_id,
                        message=f"{error_message} Пробуем резервный endpoint...",
                        error_code=error_code,
                    )
                    continue
                raise PrepareModelError(error_message, code=error_code) from exc

            if not is_whisper_cpp_model_ready(model):
                raise PrepareModelError("GGML-модель загружена не полностью", code="download_incomplete_model")

            _write_whisper_cpp_meta(
                model,
                revision=remote_revision,
                endpoint=endpoint,
                etag=etag,
                size=total_bytes,
            )

            _update_task(
                task_id,
                state="completed",
                message="GGML-модель готова",
                error_code=None,
                revision=remote_revision,
                percent=100.0,
                speed_bps=final_speed,
                downloaded_bytes=downloaded_bytes,
                total_bytes=total_bytes,
                finished_at=_now(),
            )
            return

    except Exception as exc:
        error_code = getattr(exc, "code", "model_prepare_failed")
        _update_task(
            task_id,
            state="error",
            message=str(exc),
            error_code=error_code,
            finished_at=_now(),
        )
    finally:
        with _LOCK:
            task = _TASKS.get(task_id)
            if task and _ACTIVE_BY_MODEL.get(task["model"]) == task_id:
                _ACTIVE_BY_MODEL.pop(task["model"], None)


def _run_prepare_task(task_id: str) -> None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if not task:
            return
        model = task["model"]
        force = bool(task.get("force", False))

    if _use_whisper_cpp_models():
        _run_prepare_whisper_cpp_task(task_id)
        return

    try:
        repo_id = repository_for_model(model)
        model_dir = local_model_dir(model)
        model_dir.mkdir(parents=True, exist_ok=True)

        if force:
            _update_task(task_id, message="Очистка локальной модели перед обновлением")
            clear_model_cache(model)
            shutil.rmtree(model_dir, ignore_errors=True)
            model_dir.mkdir(parents=True, exist_ok=True)

        _update_task(task_id, state="running", repo_id=repo_id, message="Получение списка файлов модели")
        if _has_invalid_hf_token():
            _update_task(
                task_id,
                message=(
                    "HF_TOKEN содержит не-ASCII символы, токен будет проигнорирован. "
                    "Укажите ASCII токен вида hf_xxx или удалите HF_TOKEN."
                ),
                error_code="invalid_hf_token",
            )

        endpoints = _huggingface_endpoints()
        for idx, endpoint in enumerate(endpoints):
            _update_task(task_id, message=f"Подключение к {_endpoint_host(endpoint)}")

            try:
                downloaded_bytes, total_bytes, final_speed, remote_revision = _download_from_endpoint(
                    task_id, model, endpoint
                )
            except Exception as exc:
                if _is_auth_error(exc):
                    try:
                        _update_task(
                            task_id,
                            message="Получен HTTP 401/403. Пробуем загрузку через huggingface_hub...",
                        )
                        downloaded_bytes, total_bytes, final_speed, remote_revision = _download_via_hf_hub(
                            task_id, model, endpoint
                        )
                    except Exception as fallback_exc:
                        error_code, error_message = _format_download_error(endpoint, fallback_exc)
                        has_next_endpoint = idx < len(endpoints) - 1

                        if has_next_endpoint:
                            _update_task(
                                task_id,
                                message=f"{error_message} Пробуем резервный endpoint...",
                                error_code=error_code,
                            )
                            continue

                        raise PrepareModelError(error_message, code=error_code) from fallback_exc
                else:
                    error_code, error_message = _format_download_error(endpoint, exc)
                    has_next_endpoint = idx < len(endpoints) - 1

                    if has_next_endpoint:
                        _update_task(
                            task_id,
                            message=f"{error_message} Пробуем резервный endpoint...",
                            error_code=error_code,
                        )
                        continue

                    raise PrepareModelError(error_message, code=error_code) from exc

            if not is_local_model_ready(model):
                raise PrepareModelError("Модель загружена не полностью", code="download_incomplete_model")

            _write_model_meta(model, revision=remote_revision, endpoint=endpoint)
            clear_model_cache(model)

            _update_task(
                task_id,
                state="completed",
                message="Модель готова",
                error_code=None,
                revision=remote_revision,
                percent=100.0,
                speed_bps=final_speed,
                downloaded_bytes=downloaded_bytes,
                total_bytes=total_bytes,
                finished_at=_now(),
            )
            return

    except Exception as exc:
        error_code = getattr(exc, "code", "model_prepare_failed")
        _update_task(
            task_id,
            state="error",
            message=str(exc),
            error_code=error_code,
            finished_at=_now(),
        )
    finally:
        with _LOCK:
            task = _TASKS.get(task_id)
            if task and _ACTIVE_BY_MODEL.get(task["model"]) == task_id:
                _ACTIVE_BY_MODEL.pop(task["model"], None)


def start_prepare_task(model_name: str, *, force: bool = False) -> dict[str, Any]:
    model = (model_name or "").strip()
    if model not in config.ALLOWED_WHISPER_MODELS:
        raise ValueError("invalid_model")

    repo_id = _whisper_cpp_repo_id() if _use_whisper_cpp_models() else repository_for_model(model)
    local_ready = is_whisper_cpp_model_ready(model) if _use_whisper_cpp_models() else is_local_model_ready(model)
    local_revision = _read_whisper_cpp_revision(model) if _use_whisper_cpp_models() else _read_local_revision(model)

    if local_ready and not force:
        task_id = uuid.uuid4().hex
        task = {
            "task_id": task_id,
            "model": model,
            "repo_id": repo_id,
            "force": False,
            "revision": local_revision,
            "state": "completed",
            "message": "Модель уже доступна локально",
            "error_code": None,
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
            "repo_id": repo_id,
            "force": force,
            "revision": None,
            "state": "pending",
            "message": "Подготовка обновления" if force else "Подготовка загрузки",
            "error_code": None,
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


def list_prepare_tasks() -> list[dict[str, Any]]:
    with _LOCK:
        items = [_sanitize_task(task) for task in _TASKS.values()]
    items.sort(key=lambda item: float(item.get("started_at") or 0.0), reverse=True)
    return items


def delete_local_model(model_name: str) -> dict[str, Any]:
    model = (model_name or "").strip()
    if model not in config.ALLOWED_WHISPER_MODELS:
        raise ValueError("invalid_model")

    with _LOCK:
        active_task_id = _ACTIVE_BY_MODEL.get(model)
        active_task = _TASKS.get(active_task_id) if active_task_id else None
        if active_task and active_task.get("state") in {"pending", "running"}:
            raise PrepareModelError("Сначала дождитесь завершения загрузки модели.", code="model_prepare_running")

    clear_model_cache(model)

    if _use_whisper_cpp_models():
        targets = [
            whisper_cpp_model_path(model),
            whisper_cpp_model_path(model).with_suffix(whisper_cpp_model_path(model).suffix + ".part"),
            _whisper_cpp_meta_path(model),
        ]
        removed_any = False
        for target in targets:
            try:
                if target.exists():
                    target.unlink()
                    removed_any = True
            except OSError:
                pass
        return {
            "ok": True,
            "model": model,
            "deleted": removed_any,
            "message": "Локальная GGML-модель удалена." if removed_any else "Локальная GGML-модель уже отсутствует.",
        }

    targets = [local_model_dir(model), _hf_repo_cache_root(model), *_legacy_model_dirs(model)]
    removed_any = False
    seen: set[str] = set()
    for target in targets:
        try:
            key = str(target.resolve())
        except OSError:
            key = str(target)
        if key in seen:
            continue
        seen.add(key)
        if not target.exists():
            continue
        shutil.rmtree(target, ignore_errors=True)
        removed_any = True

    meta_path = _model_meta_path(model)
    try:
        if meta_path.exists():
            meta_path.unlink()
            removed_any = True
    except OSError:
        pass

    return {
        "ok": True,
        "model": model,
        "deleted": removed_any,
        "message": "Локальная Whisper-модель удалена." if removed_any else "Локальная Whisper-модель уже отсутствует.",
    }


def list_local_models() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with _LOCK:
        active_by_model = dict(_ACTIVE_BY_MODEL)
        tasks = {task_id: dict(task) for task_id, task in _TASKS.items()}

    for model in config.ALLOWED_WHISPER_MODELS:
        active_task_id = active_by_model.get(model)
        active_task = tasks.get(active_task_id) if active_task_id else None
        if _use_whisper_cpp_models():
            items.append(
                {
                    "name": model,
                    "repo_id": _whisper_cpp_repo_id(),
                    "installed": is_whisper_cpp_model_ready(model),
                    "local_revision": _read_whisper_cpp_revision(model),
                    "path": str(whisper_cpp_model_path(model)),
                    "backend": config.SETTINGS.whisper_backend,
                    "active_task": _sanitize_task(active_task) if active_task else None,
                }
            )
            continue
        items.append(
            {
                "name": model,
                "repo_id": repository_for_model(model),
                "installed": is_local_model_ready(model),
                "local_revision": _read_local_revision(model),
                "path": str(local_model_dir(model)),
                "backend": config.SETTINGS.whisper_backend,
                "active_task": _sanitize_task(active_task) if active_task else None,
            }
        )

    return items


def check_model_update(model_name: str) -> dict[str, Any]:
    model = (model_name or "").strip()
    if model not in config.ALLOWED_WHISPER_MODELS:
        raise ValueError("invalid_model")

    if _use_whisper_cpp_models():
        local_ready = is_whisper_cpp_model_ready(model)
        local_meta = _read_whisper_cpp_meta(model)
        local_revision = str(local_meta.get("revision") or "").strip() or None
        local_etag = str(local_meta.get("etag") or "").strip() or None
        local_size = 0
        try:
            local_size = whisper_cpp_model_path(model).stat().st_size if local_ready else 0
        except OSError:
            local_size = 0

        repo_id = _whisper_cpp_repo_id()
        checked_endpoint: str | None = None
        remote_revision: str | None = None
        remote_etag: str | None = None
        remote_size = 0
        error_code: str | None = None
        error_message: str | None = None

        trust_env = _env_flag("HF_TRUST_ENV", default=False)
        endpoints = _huggingface_endpoints()
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(10.0, connect=5.0),
            trust_env=trust_env,
            headers=_http_headers(),
        ) as client:
            for endpoint in endpoints:
                checked_endpoint = endpoint
                try:
                    remote_revision, remote_etag, remote_size = _fetch_whisper_cpp_remote_meta(client, endpoint, model)
                    error_code = None
                    error_message = None
                    break
                except Exception as exc:
                    error_code, error_message = _format_download_error(endpoint, exc)
                    continue

        update_available = False
        status = "up_to_date"
        message = "Локальная GGML-модель уже актуальна."

        if not local_ready:
            status = "local_missing"
            message = "GGML-модель ещё не загружена локально."
        elif error_code:
            status = "check_failed"
            message = error_message or "Не удалось проверить обновление GGML-модели."
        elif remote_etag and local_etag and remote_etag != local_etag:
            status = "update_available"
            update_available = True
            message = "Для GGML-модели доступно обновление."
        elif remote_size and local_size and remote_size != local_size:
            status = "update_available"
            update_available = True
            message = "Размер локальной GGML-модели отличается. Рекомендуется обновление."
        elif remote_revision and local_revision and remote_revision != local_revision:
            status = "update_available"
            update_available = True
            message = "Для GGML-модели доступно обновление."
        elif not local_etag and not local_revision:
            status = "unknown_local_revision"
            update_available = True
            message = "Локальная ревизия GGML-модели неизвестна. Рекомендуется обновление."

        return {
            "model": model,
            "repo_id": repo_id,
            "local_ready": local_ready,
            "local_revision": local_revision,
            "remote_revision": remote_revision,
            "update_available": update_available,
            "status": status,
            "checked_endpoint": checked_endpoint,
            "error_code": error_code,
            "message": message,
            "checked_at": _now(),
        }

    local_ready = is_local_model_ready(model)
    local_revision = _read_local_revision(model)
    repo_id = repository_for_model(model)
    checked_endpoint: str | None = None
    remote_revision: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    trust_env = _env_flag("HF_TRUST_ENV", default=False)
    endpoints = _huggingface_endpoints()
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(10.0, connect=5.0),
        trust_env=trust_env,
        headers=_http_headers(),
    ) as client:
        for endpoint in endpoints:
            checked_endpoint = endpoint
            try:
                payload = _fetch_model_payload(client, endpoint, repo_id)
                raw_revision = payload.get("sha")
                remote_revision = str(raw_revision).strip() if raw_revision else None
                error_code = None
                error_message = None
                break
            except Exception as exc:
                error_code, error_message = _format_download_error(endpoint, exc)
                continue

    update_available = False
    status = "up_to_date"
    message = "Локальная Whisper-модель уже актуальна."

    if not local_ready:
        status = "local_missing"
        message = "Модель ещё не загружена локально."
    elif error_code:
        status = "check_failed"
        message = error_message or "Не удалось проверить обновление модели."
    elif remote_revision and local_revision:
        if remote_revision != local_revision:
            status = "update_available"
            update_available = True
            message = "Для модели доступно обновление."
        else:
            status = "up_to_date"
            message = "Локальная Whisper-модель уже актуальна."
    elif remote_revision and not local_revision:
        status = "unknown_local_revision"
        update_available = True
        message = "Локальная ревизия модели неизвестна. Рекомендуется обновление."
    elif not remote_revision:
        status = "check_failed"
        message = "Не удалось получить удалённую ревизию модели."
        error_code = "model_prepare_failed"

    return {
        "model": model,
        "repo_id": repo_id,
        "local_ready": local_ready,
        "local_revision": local_revision,
        "remote_revision": remote_revision,
        "update_available": update_available,
        "status": status,
        "checked_endpoint": checked_endpoint,
        "error_code": error_code,
        "message": message,
        "checked_at": _now(),
    }
