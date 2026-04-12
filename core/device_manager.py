"""Device registry: CRUD, state management, protocol coordination."""

import json
import logging
import copy
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import async_session, DeviceRow, EventRow
from core.event_bus import event_bus
from core.state_machine import apply_state_change, execute_command
from models.device import DeviceCreate, DeviceUpdate, DeviceResponse, DEVICE_TEMPLATES, gen_id

logger = logging.getLogger(__name__)


class DeviceManager:
    """Central registry for all simulated devices."""

    def __init__(self):
        # In-memory cache: id -> device dict
        self._devices: dict[str, dict[str, Any]] = {}
        # Protocol handlers reference (set by main on startup)
        self._protocol_handlers: dict[str, Any] = {}

    def set_protocol_handlers(self, handlers: dict[str, Any]):
        self._protocol_handlers = handlers

    async def load_from_db(self):
        """Load all devices from database into memory."""
        async with async_session() as session:
            result = await session.execute(select(DeviceRow))
            rows = result.scalars().all()
            for row in rows:
                self._devices[row.id] = self._row_to_dict(row)
        logger.info("Loaded %d devices from database", len(self._devices))

    async def create_device(self, data: DeviceCreate) -> dict[str, Any]:
        device_id = gen_id()
        now = datetime.now(timezone.utc)

        # Merge with template defaults
        template = DEVICE_TEMPLATES.get(data.type, {})
        default_state = copy.deepcopy(template.get("default_state", {}))
        default_state.update(data.state)

        capabilities = data.capabilities or template.get("capabilities", [])

        device = {
            "id": device_id,
            "name": data.name,
            "type": data.type,
            "protocol": data.protocol,
            "protocol_config": data.protocol_config,
            "state": default_state,
            "capabilities": capabilities,
            "room": data.room,
            "icon": data.icon or template.get("icon", ""),
            "created_at": now,
            "updated_at": now,
            "is_online": True,
            "auto_report_interval": data.auto_report_interval,
        }

        # Save to DB
        async with async_session() as session:
            row = DeviceRow(
                id=device_id,
                name=data.name,
                type=data.type,
                protocol=data.protocol,
                protocol_config=json.dumps(data.protocol_config),
                state=json.dumps(default_state),
                capabilities=json.dumps(capabilities),
                room=data.room,
                icon=device["icon"],
                is_online=True,
                auto_report_interval=data.auto_report_interval,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.commit()

        self._devices[device_id] = device

        # Register with protocol handler
        await self._register_protocol(device)

        await event_bus.emit("device_added", {"device": device})
        return device

    async def get_device(self, device_id: str) -> Optional[dict[str, Any]]:
        return self._devices.get(device_id)

    async def get_all_devices(self) -> list[dict[str, Any]]:
        return list(self._devices.values())

    async def update_device(self, device_id: str, data: DeviceUpdate) -> Optional[dict[str, Any]]:
        device = self._devices.get(device_id)
        if not device:
            return None

        updates = data.model_dump(exclude_none=True)
        device.update(updates)
        device["updated_at"] = datetime.now(timezone.utc)

        await self._save_device(device)
        await event_bus.emit("device_updated", {"device": device})
        return device

    async def delete_device(self, device_id: str) -> bool:
        device = self._devices.pop(device_id, None)
        if not device:
            return False

        await self._unregister_protocol(device)

        async with async_session() as session:
            await session.execute(delete(DeviceRow).where(DeviceRow.id == device_id))
            await session.commit()

        await event_bus.emit("device_removed", {"device_id": device_id})
        return True

    async def get_state(self, device_id: str) -> Optional[dict[str, Any]]:
        device = self._devices.get(device_id)
        return device["state"] if device else None

    async def set_state(self, device_id: str, new_state: dict[str, Any], source: str = "api") -> Optional[dict[str, Any]]:
        device = self._devices.get(device_id)
        if not device:
            return None

        old_state = copy.deepcopy(device["state"])
        device["state"] = apply_state_change(device["state"], new_state, device["type"])
        device["updated_at"] = datetime.now(timezone.utc)

        await self._save_device(device)

        # Notify protocol handler to publish new state
        await self._publish_state(device)

        await event_bus.emit("state_changed", {
            "device_id": device_id,
            "device_name": device["name"],
            "old_state": old_state,
            "new_state": device["state"],
            "source": source,
            "timestamp": device["updated_at"].isoformat(),
        })

        # Log event
        await self._log_event(device, "state_changed", source, json.dumps(device["state"]))

        return device["state"]

    async def execute_command(self, device_id: str, command: str, params: dict[str, Any], source: str = "api") -> Optional[dict[str, Any]]:
        device = self._devices.get(device_id)
        if not device:
            return None

        old_state = copy.deepcopy(device["state"])
        device["state"] = execute_command(device["state"], command, params, device["type"])
        device["updated_at"] = datetime.now(timezone.utc)

        await self._save_device(device)
        await self._publish_state(device)

        await event_bus.emit("state_changed", {
            "device_id": device_id,
            "device_name": device["name"],
            "old_state": old_state,
            "new_state": device["state"],
            "source": source,
            "timestamp": device["updated_at"].isoformat(),
        })

        await self._log_event(device, f"command:{command}", source, json.dumps({"command": command, "params": params}))

        return device["state"]

    async def set_online(self, device_id: str, is_online: bool):
        device = self._devices.get(device_id)
        if device:
            device["is_online"] = is_online
            device["updated_at"] = datetime.now(timezone.utc)
            await self._save_device(device)
            await event_bus.emit("device_online_changed", {
                "device_id": device_id,
                "is_online": is_online,
            })

    async def restart_protocol(self, device_id: str):
        device = self._devices.get(device_id)
        if device:
            await self._unregister_protocol(device)
            await self._register_protocol(device)

    async def get_history(self, device_id: str, limit: int = 100) -> list[dict]:
        async with async_session() as session:
            result = await session.execute(
                select(EventRow)
                .where(EventRow.device_id == device_id)
                .order_by(EventRow.timestamp.desc())
                .limit(limit)
            )
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "event_type": r.event_type,
                    "protocol": r.protocol,
                    "direction": r.direction,
                    "topic": r.topic,
                    "payload": r.payload,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                }
                for r in rows
            ]

    # ---- internal ----

    async def _register_protocol(self, device: dict[str, Any]):
        handler = self._protocol_handlers.get(device["protocol"])
        if handler and hasattr(handler, "register_device"):
            try:
                await handler.register_device(device)
            except Exception:
                logger.exception("Failed to register device %s with protocol %s", device["id"], device["protocol"])

    async def _unregister_protocol(self, device: dict[str, Any]):
        handler = self._protocol_handlers.get(device["protocol"])
        if handler and hasattr(handler, "unregister_device"):
            try:
                await handler.unregister_device(device)
            except Exception:
                logger.exception("Failed to unregister device %s", device["id"])

    async def _publish_state(self, device: dict[str, Any]):
        handler = self._protocol_handlers.get(device["protocol"])
        if handler and hasattr(handler, "publish_state"):
            try:
                await handler.publish_state(device)
            except Exception:
                logger.exception("Failed to publish state for %s", device["id"])

    async def _save_device(self, device: dict[str, Any]):
        async with async_session() as session:
            result = await session.execute(
                select(DeviceRow).where(DeviceRow.id == device["id"])
            )
            row = result.scalar_one_or_none()
            if row:
                row.name = device["name"]
                row.protocol_config = json.dumps(device["protocol_config"])
                row.state = json.dumps(device["state"])
                row.capabilities = json.dumps(device["capabilities"])
                row.room = device["room"]
                row.icon = device["icon"]
                row.is_online = device["is_online"]
                row.auto_report_interval = device["auto_report_interval"]
                row.updated_at = device["updated_at"]
                await session.commit()

    async def _log_event(self, device: dict[str, Any], event_type: str, source: str, payload: str):
        async with async_session() as session:
            row = EventRow(
                device_id=device["id"],
                device_name=device["name"],
                protocol=device["protocol"],
                direction="internal" if source == "api" else source,
                event_type=event_type,
                payload=payload,
                timestamp=datetime.now(timezone.utc),
            )
            session.add(row)
            await session.commit()

    def _row_to_dict(self, row: DeviceRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "type": row.type,
            "protocol": row.protocol,
            "protocol_config": json.loads(row.protocol_config) if row.protocol_config else {},
            "state": json.loads(row.state) if row.state else {},
            "capabilities": json.loads(row.capabilities) if row.capabilities else [],
            "room": row.room or "",
            "icon": row.icon or "",
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "is_online": row.is_online,
            "auto_report_interval": row.auto_report_interval or 60,
        }


# Global singleton
device_manager = DeviceManager()
