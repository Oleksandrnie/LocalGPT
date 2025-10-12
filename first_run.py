# Copyright (c) 2025 Oleksandr Niemchenko. All Rights Reserved.

#!/usr/bin/env python3
"""
first_run.py — быстрый автосетап LocalGPT на чистой машине.

⚡ Делает:
  1) Проверяет/создаёт venv и ставит зависимости из app/requirements.txt + нужные допы
  2) Создаёт .env (если нет) со всеми относительными путями внутри проекта
  3) Готовит кастомную Ollama-модель qwen2.5-7b-long (Modelfile → ollama create)
  4) Скачивает локально модели Whisper (Systran/faster-whisper-medium) в ./ollama_models/whisper/medium
  5) Даёт команды запуска API/UI

Все файлы и модели кладутся строго ВНУТРЬ папки проекта.

Примечание:
- Для шага с Ollama нужен установленный `ollama` в системе. Если его нет — скрипт подскажет, что сделать.
- Для скачивания моделей Whisper требуется интернет-доступ.
"""
from __future__ import annotations
import os
import sys
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
VENV_DIR = ROOT / "venv"
VENV_PY = VENV_DIR / "bin" / "python"
VENV_PIP = VENV_DIR / "bin" / "pip"
ENV_FILE = ROOT / ".env"

WHISPER_ROOT = ROOT / "ollama_models" / "whisper"
WHISPER_MEDIUM_DIR = WHISPER_ROOT / "medium"

QWEN_LONG_DIR = ROOT / "ollama_models" / "qwen2.5-7b-long"
QWEN_MODEFILE = QWEN_LONG_DIR / "Modelfile"

APP_REQ = ROOT / "app" / "requirements.txt"

EXTRA_PY_REQ = [
    # Часто полезные доп. пакеты для dev/запуска FastAPI
    "uvicorn[standard]",
    "python-multipart",
    "huggingface_hub>=0.23.0",
    # faster-whisper обычно уже в requirements.txt, но если нет — разкомментируй
    # "faster-whisper>=1.0.0",
]

MODEFILE_CONTENT = """FROM qwen2.5:7b-instruct

# Длина контекста (вход)
PARAMETER num_ctx 32768

# Длина ответа по умолчанию (токенов)
PARAMETER num_predict 4096

# Дефолтные параметры генерации
PARAMETER temperature 0.25
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.05

# Шаблон совместим с server.py
TEMPLATE \"\"\"{{ .System }}
{{ .Prompt }}\"\"\"
"""

DEFAULT_ENV = """ENV=local

# OpenAI-совместимый эндпоинт Ollama
LOCAL_BASE_URL=http://localhost:11434/v1
LOCAL_API_KEY=LOCAL-KEY

# Модель по умолчанию (после сборки будет qwen2.5-7b-long)
LOCAL_MODEL=qwen2.5-7b-long

# Параметры генерации
TEMP=0.25
MAX_TOKENS=4096

# Whisper (ASR) — строго внутри проекта
WHISPER_MODELS_DIR=./ollama_models/whisper
WHISPER_MODEL_SIZE=medium
WHISPER_COMPUTE_TYPE=int8
WHISPER_DEVICE=cpu

# Админ-токен для UI (если используется)
ADMIN_TOKEN=local-admin-123
"""


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd or ROOT, check=check)


def ensure_venv():
    if VENV_PY.exists():
        print("✓ venv уже существует")
        return
    print("→ Создаю venv…")
    run([PYTHON, "-m", "venv", str(VENV_DIR)])
    print("✓ venv создан")


def pip_install():
    print("→ Обновляю pip/setuptools/wheel…")
    run([str(VENV_PIP), "install", "--upgrade", "pip", "setuptools", "wheel"])

    if APP_REQ.exists():
        print("→ Устанавливаю зависимости из app/requirements.txt …")
        run([str(VENV_PIP), "install", "-r", str(APP_REQ)])
    else:
        print("! app/requirements.txt не найден — пропускаю")

    if EXTRA_PY_REQ:
        print("→ Устанавливаю дополнительные пакеты …")
        run([str(VENV_PIP), "install", *EXTRA_PY_REQ])


def ensure_env_file():
    if ENV_FILE.exists():
        print("✓ .env уже существует — не трогаю")
        return
    print("→ Создаю .env с дефолтными настройками…")
    ENV_FILE.write_text(DEFAULT_ENV, encoding="utf-8")
    print("✓ .env создан")


def ensure_modelfile():
    QWEN_LONG_DIR.mkdir(parents=True, exist_ok=True)
    if QWEN_MODEFILE.exists():
        print("✓ Modelfile уже существует")
        return
    print("→ Пишу Modelfile для qwen2.5-7b-long…")
    QWEN_MODEFILE.write_text(MODEFILE_CONTENT, encoding="utf-8")
    print("✓ Modelfile создан")


def which(prog: str) -> str | None:
    return shutil.which(prog)


def ensure_ollama_model():
    if which("ollama") is None:
        print("! Ollama не найден. Установи Ollama и запусти сервис, затем перезапусти этот скрипт.")
        print("  macOS: brew install ollama && brew services start ollama")
        print("  Linux: curl -fsSL https://ollama.com/install.sh | sh && sudo systemctl enable --now ollama")
        return

    # Проверим, существует ли уже кастомная модель
    try:
        out = subprocess.check_output(["ollama", "list"], text=True)
        if "qwen2.5-7b-long" in out:
            print("✓ Модель qwen2.5-7b-long уже есть")
            return
    except Exception:
        pass

    print("→ Тяну базовую модель qwen2.5:7b-instruct (если ещё не скачана)…")
    try:
        run(["ollama", "pull", "qwen2.5:7b-instruct"], check=False)
    except Exception:
        print("! Не удалось выполнить `ollama pull`. Продолжаю создание модели — если база уже есть, всё ок.")

    print("→ Создаю кастомную модель qwen2.5-7b-long …")
    run(["ollama", "create", "qwen2.5-7b-long", "-f", str(QWEN_MODEFILE)])
    print("✓ Готово: qwen2.5-7b-long")


def ensure_whisper_models():
    """Скачиваем Systran/faster-whisper-medium в проект (HF snapshots)."""
    WHISPER_MEDIUM_DIR.mkdir(parents=True, exist_ok=True)
    # Если уже есть snapshots — пропускаем
    snap = WHISPER_MEDIUM_DIR / "snapshots"
    if snap.exists() and any(snap.iterdir()):
        print("✓ Whisper medium уже скачан (snapshots найден)")
        return

    print("→ Скачиваю Systran/faster-whisper-medium в ./ollama_models/whisper/medium …")
    # Используем huggingface_hub для точной структуры
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id="Systran/faster-whisper-medium",
            local_dir=str(WHISPER_MEDIUM_DIR),
            local_dir_use_symlinks=False,
            allow_patterns=["*.bin", "*.json", "*.txt", "*.model", "*tokenizer*", "*vocabulary*"],
            tqdm_class=None,
        )
        print("✓ Whisper medium — скачан")
    except Exception as e:
        print(f"! Не удалось скачать Whisper medium: {e}")
        print("  Можно пропустить — модель докачается при первом вызове /transcribe, если есть интернет.")


def main():
    print("== LocalGPT: первый запуск ==")
    ensure_venv()
    pip_install()
    ensure_env_file()
    ensure_modelfile()
    ensure_ollama_model()
    ensure_whisper_models()

    print("\n== Готово ==")
    print("1) Активируй venv:")
    print(f"   source {VENV_DIR}/bin/activate")
    print("2) Запусти API:")
    print("   export PYTHONPATH=\"$(pwd)\" && uvicorn app.server:app --host 127.0.0.1 --port 8000 --log-level info")
    print("3) Открой UI: http://127.0.0.1:8000/")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as cpe:
        print("\n✖ Ошибка команды:", cpe)
        sys.exit(cpe.returncode)
    except KeyboardInterrupt:
        print("\nПрервано пользователем")
        sys.exit(130)