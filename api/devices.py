"""REST API endpoints for device management."""

from fastapi import APIRouter, HTTPException
from typing import Any

from core.device_manager import device_manager
from models.device import (
    DeviceCreate, DeviceUpdate, DeviceResponse, DeviceStateUpdate,
    DeviceCommand, DEVICE_TEMPLATES,
)

router = APIRouter(prefix="/api/v1", tags=["devices"])


@router.get("/devices")
async def list_devices() -> list[dict[str, Any]]:
    devices = await device_manager.get_all_devices()
    return devices


@router.post("/devices")
async def create_device(data: DeviceCreate) -> dict[str, Any]:
    device = await device_manager.create_device(data)
    return device


@router.get("/devices/{device_id}")
async def get_device(device_id: str) -> dict[str, Any]:
    device = await device_manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.put("/devices/{device_id}")
async def update_device(device_id: str, data: DeviceUpdate) -> dict[str, Any]:
    device = await device_manager.update_device(device_id, data)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.delete("/devices/{device_id}")
async def delete_device(device_id: str):
    ok = await device_manager.delete_device(device_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"status": "deleted"}


@router.get("/devices/{device_id}/state")
async def get_device_state(device_id: str) -> dict[str, Any]:
    state = await device_manager.get_state(device_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return state


@router.post("/devices/{device_id}/state")
async def set_device_state(device_id: str, data: DeviceStateUpdate) -> dict[str, Any]:
    state = await device_manager.set_state(device_id, data.state, source="api")
    if state is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return state


@router.post("/devices/{device_id}/command")
async def execute_device_command(device_id: str, data: DeviceCommand) -> dict[str, Any]:
    state = await device_manager.execute_command(device_id, data.command, data.params, source="api")
    if state is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return state


@router.get("/devices/{device_id}/history")
async def get_device_history(device_id: str, limit: int = 100) -> list[dict]:
    return await device_manager.get_history(device_id, limit)


@router.post("/devices/{device_id}/restart")
async def restart_device_protocol(device_id: str):
    device = await device_manager.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await device_manager.restart_protocol(device_id)
    return {"status": "restarted"}


# Templates
@router.get("/templates")
async def list_templates() -> dict[str, Any]:
    return DEVICE_TEMPLATES


@router.get("/templates/{device_type}")
async def get_template(device_type: str) -> dict[str, Any]:
    template = DEVICE_TEMPLATES.get(device_type)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template
