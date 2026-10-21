#!/usr/bin/env python3
"""Interactive cross-platform first-time setup for LocalGPT."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "app" / "requirements.txt"
VENV_DIR = ROOT / "venv"
DOT_VENV_DIR = ROOT / ".venv"
WHISPER_CPP_SETUP_SCRIPT = ROOT / "tools" / "setup_whisper_cpp_macos.sh"
WHISPER_CPP_CLI = ROOT / "models" / "whisper_cpp" / "bin" / "whisper-cli"
WHISPER_CPP_VAD_MODEL = ROOT / "models" / "whisper_cpp" / "ggml-silero-v6.2.0.bin"
MIN_PYTHON = (3, 11)


class SetupError(RuntimeError):
    pass


def info(message: str) -> None:
    print(f"[i] {message}")


def step(message: str) -> None:
    print(f"\n[*] {message}")


def warn(message: str) -> None:
    print(f"[!] {message}")


def ask(message: str, *, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            answer = input(f"{message} {suffix} ").strip().lower()
        except EOFError as exc:
            raise SetupError("Interactive input is required.") from exc
        if not answer:
            return default
        if answer in {"y", "yes", "д", "да"}:
            return True
        if answer in {"n", "no", "н", "нет"}:
            return False
        warn("Enter yes/y or no/n.")


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(">>", subprocess.list2cmdline(command))
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if completed.returncode != 0:
        raise SetupError(
            f"Command failed with exit code {completed.returncode}: "
            f"{subprocess.list2cmdline(command)}"
        )


def host_os() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    raise SetupError(f"Unsupported operating system: {platform.system() or 'unknown'}")


def linux_package_manager() -> str:
    for name in ("apt-get", "dnf", "pacman", "zypper"):
        if shutil.which(name):
            return name
    raise SetupError(
        "No supported Linux package manager found (apt-get, dnf, pacman, zypper)."
    )


def sudo_prefix() -> list[str]:
    if os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() != 0:
        if not shutil.which("sudo"):
            raise SetupError("Administrative privileges are required, but sudo is missing.")
        return ["sudo"]
    return []


def refresh_windows_path() -> None:
    if os.name != "nt":
        return
    try:
        import winreg

        values: list[str] = []
        locations = (
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, r"Environment"),
        )
        for hive, key_name in locations:
            with winreg.OpenKey(hive, key_name) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
                values.append(str(value))
        os.environ["PATH"] = os.pathsep.join(values)
    except OSError:
        warn("Could not refresh Windows PATH; reopen PowerShell if a new CLI is not detected.")


def install_macos(packages: list[str]) -> None:
    if not packages:
        return
    brew = shutil.which("brew")
    if not brew:
        raise SetupError("Homebrew is missing. Rerun the .command launcher to install it first.")
    run([brew, "install", *packages])


LINUX_PACKAGES = {
    "apt-get": {
        "core": ["git", "curl", "unzip", "cmake", "build-essential", "ffmpeg", "tesseract-ocr"],
        "node": ["nodejs", "npm"],
    },
    "dnf": {
        "core": ["git", "curl", "unzip", "cmake", "gcc-c++", "make", "ffmpeg", "tesseract"],
        "node": ["nodejs", "npm"],
    },
    "pacman": {
        "core": ["git", "curl", "unzip", "cmake", "base-devel", "ffmpeg", "tesseract"],
        "node": ["nodejs", "npm"],
    },
    "zypper": {
        "core": ["git", "curl", "unzip", "cmake", "gcc-c++", "make", "ffmpeg", "tesseract-ocr"],
        "node": ["nodejs", "npm"],
    },
}


def install_linux(manager: str, packages: list[str]) -> None:
    if not packages:
        return
    prefix = sudo_prefix()
    if manager == "apt-get":
        run([*prefix, manager, "update"])
        run([*prefix, manager, "install", "-y", *packages])
    elif manager == "dnf":
        run([*prefix, manager, "install", "-y", *packages])
    elif manager == "pacman":
        run([*prefix, manager, "-S", "--needed", "--noconfirm", *packages])
    elif manager == "zypper":
        run([*prefix, manager, "--non-interactive", "install", *packages])


WINGET_PACKAGES = {
    "git": "Git.Git",
    "cmake": "Kitware.CMake",
    "ffmpeg": "Gyan.FFmpeg",
    "tesseract": "UB-Mannheim.TesseractOCR",
    "ollama": "Ollama.Ollama",
    "node": "OpenJS.NodeJS.LTS",
}


def install_windows(package_ids: list[str]) -> None:
    winget = shutil.which("winget")
    if not winget:
        raise SetupError("winget is required on Windows. Install Microsoft App Installer and rerun.")
    for package_id in package_ids:
        run(
            [
                winget,
                "install",
                "--id",
                package_id,
                "--exact",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
        )
    refresh_windows_path()


def install_official_linux_script(url: str, label: str) -> None:
    curl = shutil.which("curl")
    if not curl:
        raise SetupError(f"curl is required to install {label}.")
    command = f'"{curl}" -fsSL "{url}" | sh'
    prefix = sudo_prefix()
    run([*prefix, "sh", "-c", command])


def missing_commands(names: list[str]) -> list[str]:
    return [name for name in names if not shutil.which(name)]


def build_whisper_cpp_cli(system: str) -> None:
    if system != "macos":
        info("whisper.cpp CLI build is currently automated by setup on macOS only.")
        return
    if WHISPER_CPP_CLI.is_file() and os.access(WHISPER_CPP_CLI, os.X_OK) and WHISPER_CPP_VAD_MODEL.is_file():
        info(f"whisper.cpp CLI and Silero VAD already built: {WHISPER_CPP_CLI}")
        return
    if not WHISPER_CPP_SETUP_SCRIPT.is_file():
        raise SetupError(f"whisper.cpp setup script is missing: {WHISPER_CPP_SETUP_SCRIPT}")

    step("Building standard whisper.cpp CLI")
    run(
        [str(WHISPER_CPP_SETUP_SCRIPT)],
        env={
            **os.environ,
            "WHISPER_CPP_ENABLE_COREML": "0",
            "WHISPER_CPP_DOWNLOAD_MODEL": "0",
            "WHISPER_CPP_DOWNLOAD_VAD": "1",
        },
    )
    if not WHISPER_CPP_CLI.is_file() or not os.access(WHISPER_CPP_CLI, os.X_OK):
        raise SetupError(f"whisper.cpp build completed without an executable CLI: {WHISPER_CPP_CLI}")
    if not WHISPER_CPP_VAD_MODEL.is_file():
        raise SetupError(f"whisper.cpp build completed without a Silero VAD model: {WHISPER_CPP_VAD_MODEL}")


def install_system_dependencies(system: str) -> None:
    step("Phase 1/3 — system dependencies")
    if system == "macos" and subprocess.run(
        ["xcode-select", "-p"], capture_output=True, check=False
    ).returncode != 0:
        info("Apple Command Line Tools are missing and are required to build whisper.cpp.")
        if ask("Open the macOS Command Line Tools installer?"):
            run(["xcode-select", "--install"])
            raise SetupError(
                "Finish the macOS Command Line Tools installer, then rerun setup."
            )
        warn("Skipped optional whisper.cpp build prerequisite: Apple Command Line Tools.")

    required_names = (
        ["git", "cmake", "ffmpeg", "tesseract"]
        if system == "windows"
        else ["git", "curl", "unzip", "cmake", "ffmpeg", "tesseract"]
    )
    required = missing_commands(required_names)
    if required:
        info("Missing required tools: " + ", ".join(required))
        if not ask("Install missing system tools?"):
            raise SetupError("Required system dependency installation was declined.")
        if system == "macos":
            package_map = {"tesseract": "tesseract"}
            install_macos([package_map.get(name, name) for name in required])
        elif system == "linux":
            manager = linux_package_manager()
            install_linux(manager, LINUX_PACKAGES[manager]["core"])
        else:
            ids = [WINGET_PACKAGES[name] for name in required if name in WINGET_PACKAGES]
            install_windows(ids)
    else:
        info("Core system tools are already installed; skipping.")

    build_whisper_cpp_cli(system)

    if not shutil.which("ollama"):
        if not ask("Ollama is missing. Install the runtime (without models)?"):
            raise SetupError("Ollama is required by the standard LocalGPT launcher.")
        if system == "macos":
            install_macos(["ollama"])
        elif system == "linux":
            install_official_linux_script("https://ollama.com/install.sh", "Ollama")
        else:
            install_windows([WINGET_PACKAGES["ollama"]])
    else:
        info("Ollama is already installed; skipping.")

    install_optional_dependencies(system)


def install_optional_dependencies(system: str) -> None:
    optional = (
        ("node", "Node.js is only needed for frontend static checks and .mjs tests."),
    )
    for command, description in optional:
        lookup = "node" if command == "node" else command
        if shutil.which(lookup):
            info(f"Optional {command} is already installed; skipping.")
            continue
        info(description)
        if not ask(f"Install optional {command}?", default=False):
            info(f"Skipped optional {command}.")
            continue
        if system == "macos":
            install_macos([command])
        elif system == "linux":
            manager = linux_package_manager()
            install_linux(manager, LINUX_PACKAGES[manager][command])
        else:
            install_windows([WINGET_PACKAGES[command]])


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def install_project_dependencies() -> None:
    step("Phase 2/3 — project dependencies")
    if sys.version_info < MIN_PYTHON:
        raise SetupError(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required; found {platform.python_version()}."
        )
    if not REQUIREMENTS.is_file():
        raise SetupError(f"Requirements file not found: {REQUIREMENTS}")
    python = venv_python()
    if not python.exists():
        if DOT_VENV_DIR.exists():
            warn(
                f"Found {DOT_VENV_DIR}, but LocalGPT uses {VENV_DIR}. "
                "The existing .venv is left untouched."
            )
        info(f"Creating virtual environment: {VENV_DIR}")
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
    else:
        info("Virtual environment already exists; reusing it.")
    if ask("Install/verify pinned Python packages in venv?"):
        run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
        run([str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    else:
        info("Skipped Python package installation by request.")


def verify_environment(system: str) -> bool:
    step("Phase 3/3 — final verification")
    failures: list[str] = []
    required = ["git", "curl", "cmake", "ffmpeg", "tesseract", "ollama"]
    for command in required:
        path = shutil.which(command)
        if path:
            info(f"{command}: {path}")
        else:
            failures.append(command)
            warn(f"{command}: missing")

    python = venv_python()
    if not python.exists():
        failures.append("venv")
        warn("venv Python is missing")
    else:
        probe = subprocess.run(
            [
                str(python),
                "-c",
                "import fastapi, uvicorn, multipart, PIL, httpx, openpyxl, piper, faster_whisper",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode == 0:
            info(f"Python runtime imports: OK ({python})")
        else:
            failures.append("python packages")
            warn((probe.stderr or probe.stdout or "Python import verification failed").strip())

    if system == "macos":
        if WHISPER_CPP_CLI.is_file() and os.access(WHISPER_CPP_CLI, os.X_OK):
            info(f"whisper.cpp CLI: {WHISPER_CPP_CLI}")
        else:
            failures.append("whisper.cpp CLI")
            warn(f"whisper.cpp CLI: missing ({WHISPER_CPP_CLI})")
        if WHISPER_CPP_VAD_MODEL.is_file():
            info(f"whisper.cpp Silero VAD: {WHISPER_CPP_VAD_MODEL}")
        else:
            failures.append("whisper.cpp Silero VAD")
            warn(f"whisper.cpp Silero VAD: missing ({WHISPER_CPP_VAD_MODEL})")

    if failures:
        warn("Setup is incomplete: " + ", ".join(failures))
        if system == "windows":
            warn("If tools were just installed, close this window, reopen PowerShell, and rerun setup.")
        return False
    print("\n[OK] LocalGPT runtime dependencies are ready.")
    info("No models, RAG data, user configuration, or network exposure were created.")
    info("Start LocalGPT with the platform launcher documented in README.md.")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive LocalGPT first-time setup")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only inspect the current environment; do not offer installations.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        system = host_os()
        print("LocalGPT first-time setup")
        info(f"Detected OS: {system} ({platform.platform()})")
        info(f"Project root: {ROOT}")
        info("Every installation requires confirmation. Models and user data are out of scope.")
        if not args.verify_only:
            install_system_dependencies(system)
            install_project_dependencies()
        return 0 if verify_environment(system) else 1
    except (SetupError, OSError) as exc:
        warn(str(exc))
        return 1
    except KeyboardInterrupt:
        warn("Setup cancelled by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
