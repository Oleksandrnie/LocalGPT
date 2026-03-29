#!/usr/bin/env python3
"""Lightweight launcher for LocalGPT Whisper transcription app.

- Ensures virtual environment exists
- Installs dependencies from app/requirements.txt when changed
- Starts FastAPI backend (uvicorn)
- Opens UI in browser
"""

from __future__ import annotations

import argparse
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


def build_ui_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/ui/gui_html.html"


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


def open_browser_delayed(ui_url: str, delay_seconds: float = 1.0) -> None:
    def _open() -> None:
        time.sleep(delay_seconds)
        print(f"[*] Opening UI: {ui_url}")
        try:
            webbrowser.open(ui_url)
        except Exception as exc:  # pragma: no cover - зависит от окружения
            print(f"[!] Could not open browser automatically: {exc}")
            print(f"[i] Open manually: {ui_url}")

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def build_backend_cmd(python: str, host: str, port: int, reload_enabled: bool) -> list[str]:
    cmd = [
        python,
        "-m",
        "uvicorn",
        "app.server:app",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        "info",
    ]
    if reload_enabled:
        cmd.append("--reload")
    return cmd


def start_backend(python: str, host: str, port: int, reload_enabled: bool, exec_mode: bool = False) -> None:
    if check_port(host, port):
        print(f"[!] Port {port} is already in use. Stop existing process and rerun.")
        return

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    cmd = build_backend_cmd(python, host, port, reload_enabled)

    print("[*] Starting FastAPI backend...")
    if exec_mode:
        printable = " ".join(cmd)
        print(f">> {printable}")
        os.chdir(ROOT)
        os.execvpe(cmd[0], cmd, env)

    run(cmd, cwd=str(ROOT), env=env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch LocalGPT Whisper transcription app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="Do not open the UI in a browser")
    parser.add_argument("--no-reload", action="store_true", help="Run uvicorn without --reload")
    parser.add_argument(
        "--exec-backend",
        action="store_true",
        help="Replace the current process with uvicorn after venv/bootstrap setup",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"[*] Project root: {ROOT}")
    os.chdir(ROOT)

    python = ensure_venv()
    install_requirements(python)
    if not args.no_browser:
        open_browser_delayed(build_ui_url(args.host, args.port))
    start_backend(
        python,
        host=args.host,
        port=args.port,
        reload_enabled=not args.no_reload,
        exec_mode=args.exec_backend,
    )


if __name__ == "__main__":
    main()
