#!/usr/bin/env python3
"""
Cross-platform launcher for LocalGPT (macOS / Linux / Windows).

- Ensures venv exists and installs dependencies
- Ensures Ollama is running
- Reads `.env`, verifies LOCAL_MODEL via `ollama show` and prepares it if missing
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
from typing import Dict, Iterable, Optional


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / "venv"
REQUIREMENTS = ROOT / "app" / "requirements.txt"
DEPS_MARKER = VENV_DIR / ".deps_installed"
UI_URL = "http://127.0.0.1:8000/"
OLLAMA_HEALTH_URL = "http://127.0.0.1:11434/v1/models"
OLLAMA_LOG_FILE = ROOT / "ollama.log"
ENV_FILE = ROOT / ".env"
DEFAULT_MODEL = "qwen2.5:3b"
OLLAMA_MODELS_DIR = os.environ.get("OLLAMA_MODELS") or str(ROOT / "ollama" / "models")
os.environ["OLLAMA_MODELS"] = OLLAMA_MODELS_DIR
Path(OLLAMA_MODELS_DIR).mkdir(parents=True, exist_ok=True)
OLLAMA_ENV = {**os.environ, "OLLAMA_MODELS": OLLAMA_MODELS_DIR}


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


def read_env(path: Path) -> Dict[str, str]:
    """Parse a minimal .env file and return key-value pairs."""

    if not path.exists():
        return {}

    env: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def update_env_variable(path: Path, key: str, value: str) -> None:
    """Update or append the given key in the .env file."""

    lines: Iterable[str]
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    updated = False
    new_lines = []
    for raw_line in lines:
        if raw_line.lstrip().startswith("#") or "=" not in raw_line:
            new_lines.append(raw_line)
            continue
        current_key, _ = raw_line.split("=", 1)
        if current_key.strip() == key:
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(raw_line)

    if not updated:
        new_lines.append(f"{key}={value}")

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def modelfile_for(model_name: str) -> Optional[Path]:
    """Return Modelfile path for the given model if it exists."""

    sanitized = model_name.replace(":", "-")
    candidate = ROOT / "ollama_models" / sanitized / "Modelfile"
    if candidate.exists():
        return candidate
    return None


def ollama_show(model_name: str) -> bool:
    """Return True if `ollama show <model_name>` succeeds."""

    try:
        subprocess.run(
            ["ollama", "show", model_name],
            capture_output=True,
            text=True,
            check=True,
            env=OLLAMA_ENV,
        )
        append_ollama_log(f"'ollama show {model_name}' succeeded.")
        return True
    except subprocess.CalledProcessError as exc:
        append_ollama_log(
            f"'ollama show {model_name}' failed with code {exc.returncode}: {exc.stderr.strip() if exc.stderr else 'no stderr'}"
        )
        return False


def ollama_list() -> Iterable[str]:
    """Return available model names from `ollama list`."""

    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=True,
            env=OLLAMA_ENV,
        )
    except Exception as exc:
        append_ollama_log(f"'ollama list' failed: {exc}")
        return []

    models = []
    for idx, line in enumerate(result.stdout.splitlines()):
        parts = line.strip().split()
        if not parts:
            continue
        if idx == 0 and parts[0].lower() in {"name", "model"}:
            continue  # skip header line
        models.append(parts[0])

    with open(OLLAMA_LOG_FILE, "a", encoding="utf-8") as log_file:
        if result.stdout:
            log_file.write(result.stdout)
            if not result.stdout.endswith("\n"):
                log_file.write("\n")
        if result.stderr:
            log_file.write(result.stderr)
            if not result.stderr.endswith("\n"):
                log_file.write("\n")

    return models


def create_from_modelfile(model_name: str, modelfile: Path) -> bool:
    """Run `ollama create` for the provided Modelfile."""

    print(f"[*] Creating model {model_name} from {modelfile} ...")
    append_ollama_log(
        f"Creating model {model_name} from {modelfile}", leading_newline=True
    )
    try:
        run(["ollama", "create", model_name, "-f", str(modelfile)], env=OLLAMA_ENV)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[!] Failed to create model {model_name}: {exc}")
        append_ollama_log(
            f"'ollama create {model_name}' failed with code {exc.returncode}"
        )
        return False


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
        env=OLLAMA_ENV,
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


def ensure_model() -> str:
    """Ensure the model specified in .env is available in Ollama."""

    env_values = read_env(ENV_FILE)
    configured_model = env_values.get("LOCAL_MODEL", "").strip()

    if not configured_model:
        print(
            f"[i] LOCAL_MODEL is not set in {ENV_FILE.name}. Using default {DEFAULT_MODEL}."
        )
        configured_model = DEFAULT_MODEL

    print(f"[*] Ensuring model '{configured_model}' is available ...")
    append_ollama_log(
        f"Ensuring model '{configured_model}' is available.", leading_newline=True
    )

    if ollama_show(configured_model):
        print(f"[i] Model '{configured_model}' is ready.")
        return configured_model

    def try_pull(model: str) -> bool:
        print(f"[*] Pulling model '{model}' ...")
        append_ollama_log(f"Pulling model '{model}' ...")
        try:
            run(["ollama", "pull", model], env=OLLAMA_ENV)
            return True
        except subprocess.CalledProcessError as exc:
            print(f"[!] Failed to pull model '{model}': {exc}")
            append_ollama_log(
                f"'ollama pull {model}' failed with code {exc.returncode}: {exc.stderr if exc.stderr else ''}"
            )
            return False

    modelfile = modelfile_for(configured_model)
    if modelfile and create_from_modelfile(configured_model, modelfile):
        if ollama_show(configured_model):
            print(
                f"[i] Model '{configured_model}' was created from Modelfile and is ready."
            )
            return configured_model
        print(
            f"[!] Model '{configured_model}' was created from Modelfile but still not accessible."
        )

    available_models = list(ollama_list())
    if available_models:
        print("[i] Available models:", ", ".join(available_models))

    # попытка скачать явно, если модели нет среди доступных
    if configured_model not in available_models:
        if try_pull(configured_model) and ollama_show(configured_model):
            print(f"[i] Model '{configured_model}' pulled and ready.")
            return configured_model

    print(
        f"[!] Model '{configured_model}' is not available and cannot be prepared automatically."
    )

    fallback_model: Optional[str] = None

    if configured_model != DEFAULT_MODEL:
        print(f"[*] Trying to prepare default model '{DEFAULT_MODEL}' ...")
        if DEFAULT_MODEL not in available_models:
            if try_pull(DEFAULT_MODEL):
                available_models.append(DEFAULT_MODEL)

        if ollama_show(DEFAULT_MODEL):
            fallback_model = DEFAULT_MODEL

    if fallback_model is None:
        for candidate in available_models:
            if candidate == configured_model:
                continue
            if ollama_show(candidate):
                fallback_model = candidate
                break

    if fallback_model:
        update_env_variable(ENV_FILE, "LOCAL_MODEL", fallback_model)
        print(
            f"[i] Updated {ENV_FILE.name}: LOCAL_MODEL={fallback_model}. "
            "Restart LocalGPT if it is already running."
        )
        append_ollama_log(
            f"LOCAL_MODEL switched to '{fallback_model}' due to missing '{configured_model}'."
        )
        return fallback_model

    print(
        "[!] No usable Ollama models found. Install or pull a model manually and rerun this script."
    )
    append_ollama_log(
        "Failed to locate a usable model after checking .env and available models."
    )
    sys.exit(1)


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
    active_model = ensure_model()
    print(f"[i] Active LOCAL_MODEL: {active_model}")
    open_browser()
    start_backend(py)


if __name__ == "__main__":
    main()
