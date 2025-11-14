#!/usr/bin/env python3
"""
Cross-platform launcher for LocalGPT (macOS / Linux / Windows).

- Ensures venv exists and installs dependencies
- Ensures Ollama is running
- Ensures qwen2.5:7b-instruct model is available
- Starts FastAPI backend via uvicorn
- Opens web UI in browser
"""

import os
import sys
import time
import socket
import subprocess
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / "venv"
REQUIREMENTS = ROOT / "app" / "requirements.txt"
UI_URL = "http://127.0.0.1:8000/"


def run(cmd, **kwargs):
    """Run a command with logging."""
    printable = " ".join(str(c) for c in cmd)
    print(">>", printable)
    return subprocess.run(cmd, check=True, **kwargs)


def check_port(host: str, port: int, timeout: float = 0.5) -> bool:
    """Return True if (host, port) is accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def ensure_venv() -> str:
    """Create venv if needed and return path to its python executable."""
    if not VENV_DIR.exists():
        print("[*] Creating virtual environment in ./venv ...")
        run([sys.executable, "-m", "venv", str(VENV_DIR)])

    if os.name == "nt":
        python = VENV_DIR / "Scripts" / "python.exe"
    else:
        python = VENV_DIR / "bin" / "python"

    if not python.exists():
        raise RuntimeError(f"Python in venv not found at {python}")

    print(f"[i] Using venv Python: {python}")
    return str(python)


def install_requirements(python: str) -> None:
    """Install backend dependencies from requirements.txt."""
    if not REQUIREMENTS.exists():
        print(f"[!] {REQUIREMENTS} not found, skipping pip install.")
        return
    print("[*] Installing dependencies from app/requirements.txt ...")
    run([python, "-m", "pip", "install", "-r", str(REQUIREMENTS)])


def ensure_ollama_running() -> None:
    """Ensure Ollama server is up (127.0.0.1:11434)."""
    import urllib.request

    def ping() -> bool:
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:11434/v1/models", timeout=1
            ):
                return True
        except Exception:
            return False

    print("[*] Checking if Ollama is running ...")
    if ping():
        print("[i] Ollama already running.")
        return

    print("[*] Starting Ollama (ollama serve) ...")
    # Detached process; works on macOS / Linux / Windows (if ollama in PATH)
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(ROOT),
    )

    for _ in range(30):
        if ping():
            print("[i] Ollama is up.")
            return
        time.sleep(0.5)

    print("[!] Could not verify Ollama is running. Continuing anyway.")


def ensure_model() -> None:
    """Ensure qwen2.5:7b-instruct model is available in Ollama."""
    model_name = "qwen2.5:7b-instruct"
    print(f"[*] Ensuring model {model_name} is available ...")
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception as e:
        print(f"[!] Failed to list Ollama models: {e}")
        return

    if model_name in result.stdout:
        print("[i] Model already present.")
        return

    print(f"[*] Pulling model {model_name} ...")
    try:
        run(["ollama", "pull", model_name])
    except subprocess.CalledProcessError as e:
        print(f"[!] Failed to pull model {model_name}: {e}")


def open_browser() -> None:
    """Try to open the UI URL in a browser."""
    print(f"[*] Opening UI in browser: {UI_URL}")
    try:
        webbrowser.open(UI_URL)
    except Exception as e:
        print(f"[!] Could not open browser automatically: {e}")
        print(f"[i] Please open {UI_URL} manually.")


def start_backend(python: str) -> None:
    """Start uvicorn backend if port 8000 is free."""
    if check_port("127.0.0.1", 8000):
        print("[!] Port 8000 is already in use. Not starting backend.")
        print("[i] If this is an old uvicorn, stop it and rerun this script.")
        return

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    print("[*] Starting FastAPI backend (uvicorn app.server:app) ...")

    # Foreground process: when user stops script (Ctrl+C), backend also stops
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

    py = ensure_venv()
    install_requirements(py)
    ensure_ollama_running()
    ensure_model()
    open_browser()
    start_backend(py)


if __name__ == "__main__":
    main()