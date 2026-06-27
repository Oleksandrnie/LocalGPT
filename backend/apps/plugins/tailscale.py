from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

TAILSCALE_PLUGIN_ID = "tailscale"
MANUAL_COMMAND_TEMPLATE = "tailscale serve --bg http://127.0.0.1:<LOCALGPT_PORT>"
SECURITY_WARNINGS = (
    "Do not expose LocalGPT directly to the public internet.",
    "Do not enable Tailscale Funnel unless you fully understand the risk.",
    "Preferred mode: Tailscale private tailnet only.",
)

_USER_ID = os.getuid() if hasattr(os, "getuid") else 0
_DEFAULT_RUNTIME_DIR = Path(tempfile.gettempdir()) / f"LocalGPT-{_USER_ID}"
_RUNTIME_DIR = Path(os.getenv("LOCALGPT_RUNTIME_DIR", str(_DEFAULT_RUNTIME_DIR)))
_BACKEND_PORT_FILE = _RUNTIME_DIR / "backend.port"


def _request_port(request: Any | None) -> int | None:
    if request is None:
        return None
    scope = getattr(request, "scope", None)
    if isinstance(scope, dict):
        server = scope.get("server")
        if isinstance(server, (list, tuple)) and len(server) >= 2:
            port = server[1]
            if isinstance(port, int) and port > 0:
                return port
    host = str(getattr(getattr(request, "url", None), "hostname", "") or "").strip().lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return None
    port = getattr(getattr(request, "url", None), "port", None)
    return port if isinstance(port, int) and port > 0 else None


def _parse_port(raw: str | None) -> int | None:
    value = (raw or "").strip()
    if not value:
        return None
    try:
        port = int(value)
    except ValueError:
        return None
    return port if 0 < port <= 65535 else None


def _read_runtime_port_file() -> int | None:
    try:
        return _parse_port(_BACKEND_PORT_FILE.read_text(encoding="utf-8"))
    except OSError:
        return None


def detect_localgpt_port(request: Any | None = None) -> int:
    return (
        _request_port(request)
        or _read_runtime_port_file()
        or _parse_port(os.getenv("LOCALGPT_PORT"))
        or _parse_port(os.getenv("LOCALGPT_BACKEND_PORT"))
        or 8000
    )


def manual_command(port: int | None = None, *, request: Any | None = None) -> str:
    target_port = port or detect_localgpt_port(request)
    return f"tailscale serve --bg http://127.0.0.1:{target_port}"


def _run_tailscale(cli_path: str, args: list[str], *, timeout: float = 2.0) -> dict[str, Any]:
    command = [cli_path, *args]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": None, "error": "timeout", "stdout": "", "stderr": ""}
    except OSError as exc:
        return {"ok": False, "returncode": None, "error": str(exc), "stdout": "", "stderr": ""}

    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "error": "",
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
    }


def _json_loads(raw: str) -> Any | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _json_has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, list):
        return bool(value)
    return bool(value)


def _trim_dns_name(value: Any) -> str:
    return str(value or "").strip().rstrip(".")


def _tailscale_ips(self_status: dict[str, Any]) -> list[str]:
    raw = self_status.get("TailscaleIPs")
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _serve_mentions_localgpt(serve_payload: Any, serve_stdout: str, port: int) -> bool:
    serialized = ""
    if serve_payload is not None:
        try:
            serialized = json.dumps(serve_payload, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            serialized = ""
    searchable = f"{serve_stdout}\n{serialized}"
    needles = (
        f"127.0.0.1:{port}",
        f"localhost:{port}",
        f"http://:{port}",
        f":{port}",
    )
    return any(needle in searchable for needle in needles)


def _serve_status(cli_path: str, port: int) -> dict[str, Any]:
    result = _run_tailscale(cli_path, ["serve", "status", "--json"])
    payload = _json_loads(str(result.get("stdout") or ""))

    if not result["ok"] and not result.get("stdout"):
        fallback = _run_tailscale(cli_path, ["serve", "status"])
        result = fallback
        payload = None

    stdout = str(result.get("stdout") or "")
    lower = stdout.lower()
    inactive_text = any(
        marker in lower
        for marker in (
            "no serve config",
            "not serving",
            "not currently serving",
            "no services",
        )
    )
    active = bool(result["ok"] and not inactive_text and (_json_has_content(payload) or stdout))
    localgpt_detected = bool(active and _serve_mentions_localgpt(payload, stdout, port))
    return {
        "available": bool(result["ok"]),
        "active": active,
        "localgpt_detected": localgpt_detected,
        "returncode": result.get("returncode"),
        "message": "" if result["ok"] else (result.get("stderr") or result.get("stdout") or result.get("error") or ""),
    }


def get_status(*, request: Any | None = None) -> dict[str, Any]:
    port = detect_localgpt_port(request)
    status: dict[str, Any] = {
        "plugin_id": TAILSCALE_PLUGIN_ID,
        "backend_port": port,
        "manual_command_template": MANUAL_COMMAND_TEMPLATE,
        "manual_command": manual_command(port),
        "security_warnings": list(SECURITY_WARNINGS),
        "cli_available": False,
        "cli_path": "",
        "tailscale_status_available": False,
        "serve_status_available": False,
        "serve_active": False,
        "serve_localgpt_detected": False,
        "address_available": False,
        "url": "",
        "dns_name": "",
        "tailscale_ips": [],
        "backend_state": "",
        "online": None,
        "message": "tailscale CLI was not found in PATH.",
    }

    cli_path = shutil.which("tailscale")
    if not cli_path:
        return status

    status["cli_available"] = True
    status["cli_path"] = cli_path

    raw_status = _run_tailscale(cli_path, ["status", "--json"])
    status["tailscale_status_available"] = bool(raw_status["ok"])
    if not raw_status["ok"]:
        status["message"] = raw_status.get("stderr") or raw_status.get("stdout") or raw_status.get("error") or "tailscale status failed."
        return status

    parsed_status = _json_loads(str(raw_status.get("stdout") or ""))
    if not isinstance(parsed_status, dict):
        status["message"] = "tailscale status did not return JSON."
        return status

    self_status = parsed_status.get("Self")
    if not isinstance(self_status, dict):
        self_status = {}

    dns_name = _trim_dns_name(self_status.get("DNSName"))
    status.update(
        {
            "dns_name": dns_name,
            "tailscale_ips": _tailscale_ips(self_status),
            "backend_state": str(parsed_status.get("BackendState") or ""),
            "online": self_status.get("Online") if isinstance(self_status.get("Online"), bool) else None,
            "message": "",
        }
    )

    serve = _serve_status(cli_path, port)
    status["serve_status_available"] = bool(serve["available"])
    status["serve_active"] = bool(serve["active"])
    status["serve_localgpt_detected"] = bool(serve["localgpt_detected"])
    if not serve["available"] and serve.get("message"):
        status["message"] = str(serve["message"])

    if dns_name and status["serve_localgpt_detected"]:
        status["address_available"] = True
        status["url"] = f"https://{dns_name}/ui/gui_html.html"
    return status


def network_address_item(status: dict[str, Any] | None = None) -> dict[str, Any] | None:
    current = status or get_status()
    url = str(current.get("url") or "").strip()
    if not current.get("address_available") or not url:
        return None
    return {
        "id": TAILSCALE_PLUGIN_ID,
        "provider_id": TAILSCALE_PLUGIN_ID,
        "label": "Tailscale",
        "url": url,
        "detail": "Private tailnet via Tailscale Serve.",
        "trusted": True,
        "copyable": True,
        "priority": 20,
        "security_note": "Private tailnet only. Do not enable Funnel by default.",
    }
