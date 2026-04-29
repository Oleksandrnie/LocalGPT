#!/usr/bin/env python3
"""Cross-platform launcher for LocalGPT (macOS / Linux / Windows)."""

import argparse
import hashlib
import os
import sys
import time
import socket
import subprocess
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / "venv"
REQUIREMENTS = ROOT / "app" / "requirements.txt"
DEPS_MARKER = VENV_DIR / ".deps_installed"
OLLAMA_HEALTH_URL = "http://127.0.0.1:11434/v1/models"
OLLAMA_LOG_FILE = ROOT / "ollama.log"
ENV_FILE = ROOT / ".env"
MODELS_BASE = ROOT / "models"


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


ENV_VARS = read_env(ENV_FILE)


def resolve_env_path(raw: str | Path | None, fallback: Path) -> Path:
    if not raw:
        return fallback.expanduser().resolve()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


MODELS_DIR = resolve_env_path(ENV_VARS.get("MODELS_DIR"), MODELS_BASE)
OLLAMA_MODELS_DIR = resolve_env_path(ENV_VARS.get("OLLAMA_MODELS_DIR"), MODELS_DIR / "ollama")
WHISPER_DIR = resolve_env_path(ENV_VARS.get("WHISPER_MODELS_DIR"), MODELS_DIR / "whisper")
WHISPER_CPP_DIR = resolve_env_path(ENV_VARS.get("WHISPER_CPP_MODELS_DIR"), MODELS_DIR / "whisper_cpp")
HF_CACHE_DIR = resolve_env_path(ENV_VARS.get("HF_CACHE_DIR"), MODELS_DIR / "hf_cache")
CT2_CACHE_DIR = resolve_env_path(ENV_VARS.get("CTRANSLATE2_CACHE_DIR"), MODELS_DIR / "ctranslate2_cache")

for path in (MODELS_DIR, OLLAMA_MODELS_DIR, WHISPER_DIR, WHISPER_CPP_DIR, HF_CACHE_DIR, CT2_CACHE_DIR):
    path.mkdir(parents=True, exist_ok=True)

os.environ.update(
    {
        "MODELS_DIR": str(MODELS_DIR),
        "OLLAMA_MODELS": str(OLLAMA_MODELS_DIR),
        "OLLAMA_MODELS_DIR": str(OLLAMA_MODELS_DIR),
        "WHISPER_MODELS_DIR": str(WHISPER_DIR),
        "WHISPER_CPP_MODELS_DIR": str(WHISPER_CPP_DIR),
        "HF_HOME": str(HF_CACHE_DIR),
        "HUGGINGFACE_HUB_CACHE": str(HF_CACHE_DIR),
        "HF_CACHE_DIR": str(HF_CACHE_DIR),
        "CTRANSLATE2_CACHE_DIR": str(CT2_CACHE_DIR),
        "CT2_TRANSLATORS_CACHE": str(CT2_CACHE_DIR),
    }
)
OLLAMA_ENV = {**os.environ, "OLLAMA_MODELS": str(OLLAMA_MODELS_DIR)}


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


def report_chat_models() -> None:
    """Report local Ollama models without pulling, creating, or selecting one."""

    env_values = read_env(ENV_FILE)
    configured_model = env_values.get("LOCAL_MODEL", "").strip()

    print("[*] Checking local Ollama models ...")
    append_ollama_log(
        "Checking local Ollama models only; startup will not pull or select a fallback model.",
        leading_newline=True,
    )
    available_models = list(ollama_list())

    if available_models:
        print("[i] Available models:", ", ".join(available_models))
    else:
        print("[i] No available Ollama models found. The app will start without an LLM model.")

    if configured_model:
        if configured_model in available_models:
            print(f"[i] Configured LOCAL_MODEL is available: {configured_model}")
        else:
            print(
                f"[i] Configured LOCAL_MODEL '{configured_model}' is not available. "
                "Open the UI settings to download it or choose another local model."
            )
        return

    print("[i] LOCAL_MODEL is not set. Choose or download a model in the UI when you need chat generation.")


def build_ui_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/ui/gui_html.html"


def open_browser_delayed(ui_url: str, delay_seconds: float = 1.0) -> None:
    """Try to open the UI URL in a browser after a short delay."""

    def _open() -> None:
        time.sleep(delay_seconds)
        print(f"[*] Opening UI in browser: {ui_url}")
        try:
            webbrowser.open(ui_url)
        except Exception as exc:
            print(f"[!] Could not open browser automatically: {exc}")
            print(f"[i] Please open {ui_url} manually.")

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def build_backend_cmd(python: str, host: str, port: int, reload_enabled: bool) -> list[str]:
    cmd = [
        python,
        "-m",
        "uvicorn",
        "backend.server:app",
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


def start_backend(python: str, *, host: str, port: int, reload_enabled: bool, exec_mode: bool = False) -> None:
    """Start uvicorn backend."""
    if check_port(host, port):
        print(f"[!] Port {port} on {host} is already in use. Not starting backend.")
        print("[i] If this is an old uvicorn, stop it and rerun this script.")
        return

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    cmd = build_backend_cmd(python, host, port, reload_enabled)

    print("[*] Starting FastAPI backend (uvicorn backend.server:app) ...")
    if exec_mode:
        printable = " ".join(cmd)
        print(f">> {printable}")
        os.chdir(ROOT)
        os.execvpe(cmd[0], cmd, env)

    run(cmd, cwd=str(ROOT), env=env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch LocalGPT")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="Do not open the UI in a browser")
    parser.add_argument("--no-reload", action="store_true", help="Run uvicorn without --reload")
    parser.add_argument(
        "--exec-backend",
        action="store_true",
        help="Replace the current process with uvicorn after bootstrap",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"[*] Project root: {ROOT}")
    print(f"[i] Models dir: {MODELS_DIR}")
    print(f"[i] Ollama models dir: {OLLAMA_MODELS_DIR}")
    print(f"[i] Whisper models dir: {WHISPER_DIR}")
    print(f"[i] whisper.cpp models dir: {WHISPER_CPP_DIR}")
    os.chdir(ROOT)

    py = ensure_venv()
    install_requirements(py)
    verify_python_multipart(py)
    ensure_ollama_running()
    report_chat_models()
    if not args.no_browser:
        open_browser_delayed(build_ui_url(args.host, args.port))
    start_backend(
        py,
        host=args.host,
        port=args.port,
        reload_enabled=not args.no_reload,
        exec_mode=args.exec_backend,
    )


if __name__ == "__main__":
    main()
