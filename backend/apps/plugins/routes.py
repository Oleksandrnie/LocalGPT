from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.apps.plugins import registry

router = APIRouter()


class PluginEnabledRequest(BaseModel):
    enabled: bool


@router.get("/plugins")
def list_plugins() -> dict[str, object]:
    return registry.list_plugins()


@router.post("/plugins/{plugin_id}/enabled")
def set_plugin_enabled(plugin_id: str, req: PluginEnabledRequest) -> dict[str, object]:
    try:
        return registry.set_plugin_enabled(plugin_id, req.enabled)
    except registry.PluginToggleError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@router.get("/plugins/network-addresses")
def network_addresses() -> dict[str, object]:
    return registry.list_network_addresses()
