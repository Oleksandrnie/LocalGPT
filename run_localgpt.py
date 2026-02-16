#!/usr/bin/env python3
"""Lightweight launcher for LocalGPT Whisper transcription app.

- Ensures virtual environment exists
- Installs dependencies from app/requirements.txt when changed
- Starts FastAPI backend (uvicorn)
- Opens UI in browser
"""

from __future__ import annotations

import hashlib
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / "venv"
REQUIREMENTS = ROOT / "app" / "requirements.txt"
DEPS_MARKER = VENV_DIR / ".deps_installed"
UI_URL = "http://127.0.0.1:8000/ui/gui_html.html"


def run(cmd: list[str], **kwargs) -> None:
    printable = " ".join(cmd)
    print(f">> {printable}")
    subprocess.run(cmd, check=True, **kwargs)


def check_port(host: str, port: int, timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def ensure_venv() -> str:
    if not VENV_DIR.exists():
        print("[*] Creating virtual environment in ./venv ...")
        run([sys.executable, "-m", "venv", str(VENV_DIR)])

    if os.name == "nt":
        python = VENV_DIR / "Scripts" / "python.exe"
    else:
        python = VENV_DIR / "bin" / "python"

    if not python.exists():
        raise RuntimeError(f"Python not found in venv: {python}")

    print(f"[i] Using venv Python: {python}")
    return str(python)


def install_requirements(python: str) -> None:
    if not REQUIREMENTS.exists():
        print(f"[!] Missing requirements file: {REQUIREMENTS}")
        return

    current_hash = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    previous_hash = DEPS_MARKER.read_text(encoding="utf-8").strip() if DEPS_MARKER.exists() else ""

    if previous_hash == current_hash:
        print("[i] Requirements unchanged, skipping pip install.")
        return

    print("[*] Installing dependencies from app/requirements.txt ...")
    run([python, "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    DEPS_MARKER.write_text(current_hash, encoding="utf-8")


def open_browser_delayed(delay_seconds: float = 1.0) -> None:
    def _open() -> None:
        time.sleep(delay_seconds)
        print(f"[*] Opening UI: {UI_URL}")
        try:
            webbrowser.open(UI_URL)
        except Exception as exc:  # pragma: no cover - зависит от окружения
            print(f"[!] Could not open browser automatically: {exc}")
            print(f"[i] Open manually: {UI_URL}")

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def start_backend(python: str) -> None:
    if check_port("127.0.0.1", 8000):
        print("[!] Port 8000 is already in use. Stop existing process and rerun.")
        return

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    print("[*] Starting FastAPI backend...")
    run(
        [
            python,
            "-m",
            "uvicorn",
            "app.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--log-level",
            "info",
            "--reload",
        ],
        cwd=str(ROOT),
        env=env,
    )


def main() -> None:
    print(f"[*] Project root: {ROOT}")
    os.chdir(ROOT)

    python = ensure_venv()
    install_requirements(python)
    open_browser_delayed()
    start_backend(python)


if __name__ == "__main__":
    main()
