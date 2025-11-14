#!/usr/bin/env python3
"""
Cross-platform launcher for LocalGPT (macOS / Linux / Windows).

- Ensures venv exists and installs dependencies
- Ensures Ollama is running
- Ensures qwen2.5:7b-instruct model is available
- Starts FastAPI backend via uvicorn
- Opens web UI in browser
"""

import hashlib
import os
import sys
import time
import socket
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / "venv"
REQUIREMENTS = ROOT / "app" / "requirements.txt"
DEPS_MARKER = VENV_DIR / ".deps_installed"
UI_URL = "http://127.0.0.1:8000/"
OLLAMA_HEALTH_URL = "http://127.0.0.1:11434/v1/models"
OLLAMA_LOG_FILE = ROOT / "ollama.log"


def run(cmd, **kwargs):
    """Run a command with logging."""
    printable = " ".join(str(c) for c in cmd)
    print(">>", printable)
    return subprocess.run(cmd, check=True, **kwargs)


def append_ollama_log(message: str, *, leading_newline: bool = False) -> None:
    """Append a timestamped message to the Ollama diagnostics log."""
    prefix = "\n" if leading_newline else ""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    OLLAMA_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OLLAMA_LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(f"{prefix}[{timestamp}] {message}\n")


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


def install_requirements(python: str) -> bool:
    """Install backend dependencies from requirements.txt.

    Returns True if installation was performed, False if skipped.
    """
    if not REQUIREMENTS.exists():
        print(f"[!] {REQUIREMENTS} not found, skipping pip install.")
        return False

    current_hash = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    if DEPS_MARKER.exists():
        previous_hash = DEPS_MARKER.read_text().strip()
        if previous_hash == current_hash:
            print("[i] Requirements unchanged, skipping pip install.")
            return False

    print("[*] Installing dependencies from app/requirements.txt ...")
    run([python, "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    DEPS_MARKER.write_text(current_hash)
    return True


def verify_python_multipart(python: str) -> None:
    """Check that python-multipart is importable and warn if missing."""

    result = subprocess.run(
        [python, "-c", "import multipart"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("[i] Verified python-multipart is available.")
        return

    print("[!] python-multipart is not available in the virtual environment.")
    if result.stderr:
        print(result.stderr.strip())
    print(
        "[i] Try rerunning this script or install it manually with "
        f"'{python} -m pip install python-multipart'."
    )


def ensure_ollama_running() -> None:
    """Ensure Ollama server is up (127.0.0.1:11434)."""
    import urllib.request

    def ping() -> bool:
        try:
            with urllib.request.urlopen(
                OLLAMA_HEALTH_URL, timeout=1
            ):
                return True
        except Exception:
            return False

    print("[*] Checking if Ollama is running ...")
    print(f"[i] Ollama health-check URL: {OLLAMA_HEALTH_URL}")
    append_ollama_log(
        f"Health-check URL: {OLLAMA_HEALTH_URL}", leading_newline=True
    )
    if ping():
        print("[i] Ollama already running.")
        append_ollama_log("Ollama already running.")
        return

    print("[*] Starting Ollama (ollama serve) ...")
    append_ollama_log("Starting 'ollama serve' ...")
    # Detached process; works on macOS / Linux / Windows (if ollama in PATH)
    serve_log = open(OLLAMA_LOG_FILE, "ab")
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=serve_log,
        stderr=subprocess.STDOUT,
        cwd=str(ROOT),
    )
    serve_log.close()

    for _ in range(30):
        if ping():
            print("[i] Ollama is up.")
            append_ollama_log("Ollama responded to health-check.")
            return
        time.sleep(0.5)

    print("[!] Could not verify Ollama is running after waiting 15 seconds.")
    print("[i] Check ollama.log for details or run 'ollama serve' manually.")
    append_ollama_log(
        "Health-check timed out after starting 'ollama serve'. Aborting."
    )
    sys.exit(1)


def ensure_model() -> None:
    """Ensure qwen2.5:7b-instruct model is available in Ollama."""
    model_name = "qwen2.5:7b-instruct"
    print(f"[*] Ensuring model {model_name} is available ...")
    append_ollama_log("Running 'ollama list' ...", leading_newline=True)
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=True,
        )
        with open(OLLAMA_LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(result.stdout)
            if result.stdout and not result.stdout.endswith("\n"):
                log_file.write("\n")
            if result.stderr:
                log_file.write(result.stderr)
                if not result.stderr.endswith("\n"):
                    log_file.write("\n")
    except Exception as e:
        print(f"[!] Failed to list Ollama models: {e}")
        append_ollama_log(f"'ollama list' failed: {e}")
        return

    if model_name in result.stdout:
        print("[i] Model already present.")
        append_ollama_log(f"Model {model_name} already present.")
        return

    print(f"[*] Pulling model {model_name} ...")
    append_ollama_log(f"Pulling model {model_name} ...")
    try:
        run(["ollama", "pull", model_name])
    except subprocess.CalledProcessError as e:
        print(f"[!] Failed to pull model {model_name}: {e}")
        append_ollama_log(f"Failed to pull model {model_name}: {e}")


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
    verify_python_multipart(py)
    ensure_ollama_running()
    ensure_model()
    open_browser()
    start_backend(py)


if __name__ == "__main__":
    main()