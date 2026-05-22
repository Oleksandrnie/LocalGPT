from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.routes import meta as meta_routes
from backend.apps.plugins import registry

router = APIRouter()


class PluginEnabledRequest(BaseModel):
    enabled: bool


@router.get("/plugins")
def list_plugins(request: Request) -> dict[str, object]:
    return registry.list_plugins(request=request)


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
def network_addresses(request: Request) -> dict[str, object]:
    return registry.list_network_addresses(
        request=request,
        core_items=meta_routes.get_network_address_items(request),
    )
