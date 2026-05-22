from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app import config, db

PLUGIN_STATE_KEY = "plugins.enabled"
PLUGINS_DIR = config.PROJECT_ROOT / "plugins"
TRUSTED_PLUGIN_IDS = frozenset({"tailscale"})

PLUGIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
REQUIRED_FIELDS = (
    "id",
    "name",
    "type",
    "version",
    "enabled_by_default",
    "description",
    "permissions",
    "dangerous_permissions",
    "docs",
)


@dataclass(frozen=True)
class RegistryScan:
    plugins: list[dict[str, Any]]
    invalid_plugins: list[dict[str, Any]]
    message: str | None = None

    def as_response(self) -> dict[str, Any]:
        return {
            "plugins": self.plugins,
            "invalid_plugins": self.invalid_plugins,
            "trusted_plugin_ids": sorted(TRUSTED_PLUGIN_IDS),
            "message": self.message,
        }


class PluginToggleError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _load_enabled_state() -> dict[str, bool]:
    raw = db.get_app_setting(PLUGIN_STATE_KEY)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): bool(value) for key, value in parsed.items()}


def _save_enabled_state(state: dict[str, bool]) -> None:
    safe_state = {str(key): bool(value) for key, value in state.items() if str(key).strip()}
    db.set_app_setting(PLUGIN_STATE_KEY, json.dumps(safe_state, ensure_ascii=False, sort_keys=True))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _public_plugin_dir(path: Path) -> str:
    try:
        return str(path.relative_to(config.PROJECT_ROOT))
    except ValueError:
        return path.name


def _manifest_docs(plugin_dir: Path, docs: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for doc in docs:
        doc_path = plugin_dir / doc
        items.append(
            {
                "path": doc,
                "available": doc_path.is_file(),
            }
        )
    return items


def _validate_manifest(raw: Any, *, plugin_dir: Path) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not isinstance(raw, dict):
        return None, ["plugin.json must contain a JSON object"]

    missing = [field for field in REQUIRED_FIELDS if field not in raw]
    if missing:
        errors.append(f"Missing required fields: {', '.join(missing)}")

    plugin_id = str(raw.get("id", "")).strip()
    if not plugin_id or not PLUGIN_ID_RE.match(plugin_id):
        errors.append("Plugin id must use lowercase letters, digits, underscore, or hyphen")
    if plugin_id and plugin_dir.name != plugin_id:
        errors.append("Plugin id must match its folder name")

    for field in ("name", "type", "version", "description"):
        if not str(raw.get(field, "")).strip():
            errors.append(f"{field} must be a non-empty string")

    if not isinstance(raw.get("enabled_by_default"), bool):
        errors.append("enabled_by_default must be a boolean")

    for field in ("permissions", "dangerous_permissions", "docs"):
        if not isinstance(raw.get(field), list) or any(not isinstance(item, str) for item in raw.get(field, [])):
            errors.append(f"{field} must be a list of strings")

    if errors:
        return None, errors

    docs = _string_list(raw.get("docs"))
    manifest = {
        "id": plugin_id,
        "name": str(raw.get("name", "")).strip(),
        "type": str(raw.get("type", "")).strip(),
        "version": str(raw.get("version", "")).strip(),
        "enabled_by_default": bool(raw.get("enabled_by_default")),
        "description": str(raw.get("description", "")).strip(),
        "permissions": _string_list(raw.get("permissions")),
        "dangerous_permissions": _string_list(raw.get("dangerous_permissions")),
        "docs": docs,
        "docs_status": _manifest_docs(plugin_dir, docs),
        "plugin_dir": _public_plugin_dir(plugin_dir),
    }
    return manifest, []


def _load_manifest(plugin_dir: Path) -> tuple[dict[str, Any] | None, list[str]]:
    manifest_path = plugin_dir / "plugin.json"
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"Invalid JSON: {exc.msg}"]
    except OSError as exc:
        return None, [f"Cannot read plugin.json: {exc}"]
    return _validate_manifest(raw, plugin_dir=plugin_dir)


def scan_plugins(
    *,
    plugins_dir: Path | None = None,
    enabled_state: dict[str, bool] | None = None,
) -> RegistryScan:
    root = plugins_dir or PLUGINS_DIR
    state = _load_enabled_state() if enabled_state is None else {str(k): bool(v) for k, v in enabled_state.items()}
    plugins: list[dict[str, Any]] = []
    invalid_plugins: list[dict[str, Any]] = []

    if not root.exists():
        return RegistryScan(
            plugins=[],
            invalid_plugins=[],
            message="No plugins installed. Add a plugin folder to plugins/ to make it appear here.",
        )

    for plugin_dir in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name):
        manifest_path = plugin_dir / "plugin.json"
        if not manifest_path.is_file():
            continue

        manifest, errors = _load_manifest(plugin_dir)
        if errors or manifest is None:
            invalid_plugins.append(
                {
                    "plugin_dir": _public_plugin_dir(plugin_dir),
                    "manifest_path": _public_plugin_dir(manifest_path),
                    "errors": errors or ["Invalid plugin manifest"],
                    "status": "invalid",
                    "trusted": False,
                    "enabled": False,
                    "effective_enabled": False,
                }
            )
            continue

        trusted = manifest["id"] in TRUSTED_PLUGIN_IDS
        enabled = bool(state.get(manifest["id"], False))
        manifest.update(
            {
                "trusted": trusted,
                "enabled": enabled,
                "effective_enabled": bool(enabled and trusted),
                "status": "enabled" if enabled and trusted else ("untrusted" if not trusted else "disabled"),
                "execution": "trusted_handler" if trusted else "unavailable",
                "security_note": (
                    "Trusted backend handler is available for this plugin id."
                    if trusted
                    else "Detected, but not trusted. Execution unavailable."
                ),
            }
        )
        plugins.append(manifest)

    message = None
    if not plugins and not invalid_plugins:
        message = "No plugins installed. Add a plugin folder to plugins/ to make it appear here."
    return RegistryScan(plugins=plugins, invalid_plugins=invalid_plugins, message=message)


def list_plugins() -> dict[str, Any]:
    return scan_plugins().as_response()


def set_plugin_enabled(plugin_id: str, enabled: bool) -> dict[str, Any]:
    requested_id = (plugin_id or "").strip()
    scan = scan_plugins()
    plugin = next((item for item in scan.plugins if item.get("id") == requested_id), None)
    if plugin is None:
        raise PluginToggleError("plugin_not_found", "Plugin was not found.", status_code=404)
    if not plugin.get("trusted"):
        raise PluginToggleError(
            "plugin_not_trusted",
            "Detected plugin has no trusted backend handler and cannot be enabled.",
            status_code=403,
        )

    state = _load_enabled_state()
    state[requested_id] = bool(enabled)
    _save_enabled_state(state)
    return scan_plugins().as_response()


def list_network_addresses() -> dict[str, Any]:
    return {
        "items": [],
        "message": "No plugin network address providers are enabled.",
    }
