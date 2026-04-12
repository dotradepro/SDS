"""API endpoints for simulated device import from external systems."""

import asyncio
import random
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from core.device_manager import device_manager
from models.device import DeviceCreate
from models.import_source import (
    IMPORT_SOURCES,
    ImportConnectRequest,
    ImportConnectResponse,
    ImportExecuteRequest,
    ImportExecuteResponse,
    DiscoveredDevice,
)
from models.import_presets import IMPORT_PRESETS

router = APIRouter(prefix="/api/v1/import", tags=["import"])

# In-memory session store: session_id -> {source_id, devices}
_sessions: dict[str, dict[str, Any]] = {}


@router.get("/sources")
async def list_sources() -> list[dict[str, Any]]:
    """List all available import sources."""
    return IMPORT_SOURCES


@router.get("/sources/{source_id}")
async def get_source(source_id: str) -> dict[str, Any]:
    """Get details of a specific import source."""
    for src in IMPORT_SOURCES:
        if src["id"] == source_id:
            return src
    raise HTTPException(status_code=404, detail="Source not found")


@router.post("/connect")
async def connect_source(req: ImportConnectRequest) -> ImportConnectResponse:
    """Simulate connecting to an external system and discovering devices."""
    # Validate source exists
    source = None
    for src in IMPORT_SOURCES:
        if src["id"] == req.source_id:
            source = src
            break
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Validate required auth fields
    for field in source.get("auth_fields", []):
        if field.get("required") and not req.auth_data.get(field["name"]):
            raise HTTPException(
                status_code=400,
                detail=f"Required field '{field['label']}' is missing",
            )

    # Simulate connection delay
    await asyncio.sleep(random.uniform(1.5, 3.0))

    # Get preset devices for this source
    preset = IMPORT_PRESETS.get(req.source_id)
    if not preset:
        raise HTTPException(status_code=404, detail="No presets for this source")

    # Build discovered devices
    discovered = []
    for i, dev in enumerate(preset["devices"]):
        discovered.append(DiscoveredDevice(
            temp_id=f"{req.source_id}_{i}",
            name=dev["name"],
            type=dev["type"],
            room=dev.get("room", ""),
            manufacturer=dev.get("manufacturer", ""),
            model=dev.get("model", ""),
            protocol=dev["protocol"],
            source_entity_id=dev.get("source_entity_id", ""),
        ))

    # Store session
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "source_id": req.source_id,
        "devices": preset["devices"],
    }

    return ImportConnectResponse(
        session_id=session_id,
        status="connected",
        system_info=preset.get("system_info", {}),
        discovered_devices=discovered,
    )


@router.post("/execute")
async def execute_import(req: ImportExecuteRequest) -> ImportExecuteResponse:
    """Create selected devices from the import session."""
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    devices = session["devices"]
    source_id = session["source_id"]

    # Map temp_id to device data
    selected_set = set(req.selected_ids)
    created_ids = []

    for i, dev_data in enumerate(devices):
        temp_id = f"{source_id}_{i}"
        if temp_id not in selected_set:
            continue

        # Build DeviceCreate from preset
        protocol_config = dict(dev_data.get("protocol_config", {}))
        if "manufacturer" not in protocol_config:
            protocol_config["manufacturer"] = dev_data.get("manufacturer", "")
        if "model_id" not in protocol_config:
            protocol_config["model_id"] = dev_data.get("model", "")
        if "friendly_name" not in protocol_config:
            protocol_config["friendly_name"] = dev_data["name"].lower().replace(" ", "_")

        create_data = DeviceCreate(
            name=dev_data["name"],
            type=dev_data["type"],
            protocol=dev_data["protocol"],
            protocol_config=protocol_config,
            state=dev_data.get("state", {}),
            capabilities=dev_data.get("capabilities", []),
            room=dev_data.get("room", ""),
            icon="",
            auto_report_interval=60,
        )

        device = await device_manager.create_device(create_data)
        created_ids.append(device["id"])

    # Cleanup session
    _sessions.pop(req.session_id, None)

    return ImportExecuteResponse(
        created_devices=created_ids,
        count=len(created_ids),
    )
