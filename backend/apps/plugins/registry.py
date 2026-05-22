from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app import config, db
from backend.apps.plugins import tailscale

PLUGIN_STATE_KEY = "plugins.enabled"
PLUGINS_DIR = config.PROJECT_ROOT / "plugins"
TRUSTED_PLUGIN_IDS = frozenset({"tailscale"})
TRUSTED_HANDLER_STATUS = {
    "tailscale": tailscale.get_status,
}
TRUSTED_NETWORK_ADDRESS_ITEMS = {
    "tailscale": tailscale.network_address_item,
}

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


def _attach_handler_status(response: dict[str, Any], *, request: Any | None = None) -> dict[str, Any]:
    for plugin in response.get("plugins", []):
        if not isinstance(plugin, dict) or not plugin.get("trusted"):
            continue
        status_provider = TRUSTED_HANDLER_STATUS.get(str(plugin.get("id") or ""))
        if not status_provider:
            continue
        plugin["handler_status"] = status_provider(request=request)
        if plugin["id"] == "tailscale":
            plugin["security_warnings"] = list(tailscale.SECURITY_WARNINGS)
    return response


def list_plugins(
    *,
    request: Any | None = None,
    plugins_dir: Path | None = None,
    enabled_state: dict[str, bool] | None = None,
) -> dict[str, Any]:
    return _attach_handler_status(
        scan_plugins(plugins_dir=plugins_dir, enabled_state=enabled_state).as_response(),
        request=request,
    )


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
    return list_plugins()


def list_network_addresses(
    *,
    request: Any | None = None,
    plugins_dir: Path | None = None,
    enabled_state: dict[str, bool] | None = None,
    handler_status: dict[str, dict[str, Any]] | None = None,
    core_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scan = scan_plugins(plugins_dir=plugins_dir, enabled_state=enabled_state)
    items: list[dict[str, Any]] = [
        item for item in (core_items or []) if item.get("copyable") and str(item.get("url") or "").strip()
    ]
    providers: list[dict[str, Any]] = []

    for plugin in scan.plugins:
        plugin_id = str(plugin.get("id") or "")
        if not plugin.get("effective_enabled"):
            continue
        status_provider = TRUSTED_HANDLER_STATUS.get(plugin_id)
        item_provider = TRUSTED_NETWORK_ADDRESS_ITEMS.get(plugin_id)
        if not status_provider or not item_provider:
            continue
        status = (handler_status or {}).get(plugin_id) or status_provider(request=request)
        providers.append(
            {
                "id": plugin_id,
                "enabled": True,
                "trusted": True,
                "address_available": bool(status.get("address_available")),
                "message": status.get("message") or "",
            }
        )
        item = item_provider(status)
        if item:
            items.append(item)

    items.sort(key=lambda item: (int(item.get("priority") or 100), str(item.get("label") or "")))
    return {
        "items": items,
        "providers": providers,
        "message": "No network addresses are available." if not items else "",
    }
