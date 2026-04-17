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
from typing import Dict, Iterable, Optional


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / "venv"
REQUIREMENTS = ROOT / "app" / "requirements.txt"
DEPS_MARKER = VENV_DIR / ".deps_installed"
OLLAMA_HEALTH_URL = "http://127.0.0.1:11434/v1/models"
OLLAMA_LOG_FILE = ROOT / "ollama.log"
ENV_FILE = ROOT / ".env"
DEFAULT_MODEL = "qwen2.5:3b"
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
HF_CACHE_DIR = resolve_env_path(ENV_VARS.get("HF_CACHE_DIR"), MODELS_DIR / "hf_cache")
CT2_CACHE_DIR = resolve_env_path(ENV_VARS.get("CTRANSLATE2_CACHE_DIR"), MODELS_DIR / "ctranslate2_cache")

for path in (MODELS_DIR, OLLAMA_MODELS_DIR, WHISPER_DIR, HF_CACHE_DIR, CT2_CACHE_DIR):
    path.mkdir(parents=True, exist_ok=True)

os.environ.update(
    {
        "MODELS_DIR": str(MODELS_DIR),
        "OLLAMA_MODELS": str(OLLAMA_MODELS_DIR),
        "OLLAMA_MODELS_DIR": str(OLLAMA_MODELS_DIR),
        "WHISPER_MODELS_DIR": str(WHISPER_DIR),
        "HF_HOME": str(HF_CACHE_DIR),
        "HUGGINGFACE_HUB_CACHE": str(HF_CACHE_DIR),
        "HF_CACHE_DIR": str(HF_CACHE_DIR),
        "CTRANSLATE2_CACHE_DIR": str(CT2_CACHE_DIR),
        "CT2_TRANSLATORS_CACHE": str(CT2_CACHE_DIR),
    }
)
OLLAMA_ENV = {**os.environ, "OLLAMA_MODELS": str(OLLAMA_MODELS_DIR)}


def modelfile_for(model_name: str) -> Optional[Path]:
    """Return Modelfile path for the given model if it exists."""

    sanitized = model_name.replace(":", "-")
    candidates = [
        MODELS_DIR / "ollama" / sanitized / "Modelfile",
        MODELS_DIR / sanitized / "Modelfile",
        ROOT / "ollama_models" / sanitized / "Modelfile",  # legacy path for older installs
    ]
    for candidate in candidates:
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


def start_backend(python: str, *, host: str, port: int, reload_enabled: bool, exec_mode: bool = False) -> None:
    """Start uvicorn backend."""
    if check_port(host, port):
        print(f"[!] Port {port} on {host} is already in use. Not starting backend.")
        print("[i] If this is an old uvicorn, stop it and rerun this script.")
        return

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    cmd = build_backend_cmd(python, host, port, reload_enabled)

    print("[*] Starting FastAPI backend (uvicorn app.server:app) ...")
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
    os.chdir(ROOT)

    py = ensure_venv()
    install_requirements(py)
    verify_python_multipart(py)
    ensure_ollama_running()
    active_model = ensure_model()
    print(f"[i] Active LOCAL_MODEL: {active_model}")
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
