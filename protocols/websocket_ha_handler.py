"""Home Assistant WebSocket API emulation."""

import asyncio
import json
import logging
from typing import Any

import websockets
from websockets.server import serve

from protocols.base import ProtocolHandler
from core.event_bus import event_bus

logger = logging.getLogger(__name__)


class HomeAssistantWSHandler(ProtocolHandler):
    name = "ha_websocket"

    def __init__(self, config: dict[str, Any], device_manager: Any):
        super().__init__(config, device_manager)
        self._devices: dict[str, dict[str, Any]] = {}
        self._clients: set = set()
        self._subscriptions: dict = {}  # ws -> {id: event_type}
        self._server = None
        self._task: asyncio.Task | None = None
        self.port = config.get("port", 8123)
        self.token = config.get("token", "test_token_for_selena")

    async def start(self):
        self._task = asyncio.create_task(self._run_server())
        self.is_running = True
        self.status = "connected"
        self.status_message = f"HA WS API listening on port {self.port}"
        await event_bus.emit("protocol_status", {
            "protocol": "ha_websocket",
            "status": "connected",
            "message": self.status_message,
        })

        # Listen for state changes to broadcast
        event_bus.subscribe("state_changed", self._on_state_changed)

    async def stop(self):
        event_bus.unsubscribe("state_changed", self._on_state_changed)
        self.is_running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.status = "stopped"

    async def _run_server(self):
        try:
            self._server = await serve(self._handle_client, "0.0.0.0", self.port)
            logger.info("HA WS API server listening on port %d", self.port)
            await self._server.serve_forever()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("HA WS server error")

    async def _handle_client(self, websocket):
        self._clients.add(websocket)
        self._subscriptions[websocket] = {}
        try:
            # Auth handshake
            await websocket.send(json.dumps({"type": "auth_required", "ha_version": "2024.1.0"}))

            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    continue

                msg_type = msg.get("type", "")
                msg_id = msg.get("id")

                if msg_type == "auth":
                    token = msg.get("access_token", "")
                    if token == self.token:
                        await websocket.send(json.dumps({"type": "auth_ok", "ha_version": "2024.1.0"}))
                    else:
                        await websocket.send(json.dumps({"type": "auth_invalid", "message": "Invalid token"}))
                        break

                elif msg_type == "subscribe_events":
                    event_type = msg.get("event_type", "state_changed")
                    self._subscriptions[websocket][msg_id] = event_type
                    await websocket.send(json.dumps({
                        "id": msg_id,
                        "type": "result",
                        "success": True,
                        "result": None,
                    }))

                elif msg_type == "unsubscribe_events":
                    sub_id = msg.get("subscription")
                    self._subscriptions[websocket].pop(sub_id, None)
                    await websocket.send(json.dumps({
                        "id": msg_id,
                        "type": "result",
                        "success": True,
                    }))

                elif msg_type == "get_states":
                    states = await self._get_all_states()
                    await websocket.send(json.dumps({
                        "id": msg_id,
                        "type": "result",
                        "success": True,
                        "result": states,
                    }))

                elif msg_type == "call_service":
                    await self._handle_call_service(websocket, msg)

                elif msg_type == "ping":
                    await websocket.send(json.dumps({"id": msg_id, "type": "pong"}))

                self.stats["messages_received"] += 1

        except websockets.ConnectionClosed:
            pass
        except Exception:
            logger.exception("HA WS client error")
        finally:
            self._clients.discard(websocket)
            self._subscriptions.pop(websocket, None)

    async def _handle_call_service(self, websocket, msg: dict):
        msg_id = msg.get("id")
        domain = msg.get("domain", "")
        service = msg.get("service", "")
        target = msg.get("target", {})
        service_data = msg.get("service_data", {})

        entity_ids = target.get("entity_id", [])
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]

        for entity_id in entity_ids:
            device = await self._find_device_by_entity_id(entity_id)
            if not device:
                continue

            # Map HA service calls to commands
            if service == "turn_on":
                await self.device_manager.execute_command(
                    device["id"], "turn_on", service_data, source="ha_ws_command"
                )
            elif service == "turn_off":
                await self.device_manager.execute_command(
                    device["id"], "turn_off", {}, source="ha_ws_command"
                )
            elif service == "toggle":
                await self.device_manager.execute_command(
                    device["id"], "toggle", {}, source="ha_ws_command"
                )
            else:
                await self.device_manager.execute_command(
                    device["id"], service, service_data, source="ha_ws_command"
                )

        await websocket.send(json.dumps({
            "id": msg_id,
            "type": "result",
            "success": True,
            "result": None,
        }))
        self.stats["messages_sent"] += 1

    async def _on_state_changed(self, event_data: dict):
        """Broadcast state_changed events for ALL devices to subscribed WS clients."""
        device_id = event_data.get("device_id")
        device = await self.device_manager.get_device(device_id)
        if not device:
            return

        entity_id = self._device_to_entity_id(device)
        ha_event = {
            "event_type": "state_changed",
            "data": {
                "entity_id": entity_id,
                "old_state": self._state_to_ha(device, event_data.get("old_state", {})),
                "new_state": self._state_to_ha(device, event_data.get("new_state", {})),
            },
        }

        for ws, subs in list(self._subscriptions.items()):
            for sub_id, event_type in subs.items():
                if event_type == "state_changed":
                    try:
                        await ws.send(json.dumps({
                            "id": sub_id,
                            "type": "event",
                            "event": ha_event,
                        }))
                        self.stats["messages_sent"] += 1
                    except Exception:
                        pass

    async def _get_all_states(self) -> list[dict]:
        """Return ALL SDS devices as HA entities."""
        states = []
        all_devices = await self.device_manager.get_all_devices()
        for device in all_devices:
            state = device.get("state", {})
            states.append(self._state_to_ha(device, state))
        return states

    def _state_to_ha(self, device: dict, state: dict) -> dict:
        entity_id = self._device_to_entity_id(device)
        dtype = device.get("type", "")

        ha_state = state.get("state", "unknown")
        if dtype == "light":
            ha_state = "on" if state.get("state") == "ON" else "off"
        elif dtype == "switch":
            ha_state = "on" if state.get("state") == "ON" else "off"

        return {
            "entity_id": entity_id,
            "state": ha_state,
            "attributes": {
                "friendly_name": device["name"],
                **{k: v for k, v in state.items() if k != "state"},
            },
            "last_changed": device.get("updated_at", "").isoformat() if hasattr(device.get("updated_at", ""), "isoformat") else "",
            "last_updated": device.get("updated_at", "").isoformat() if hasattr(device.get("updated_at", ""), "isoformat") else "",
        }

    def _device_to_entity_id(self, device: dict) -> str:
        dtype = device.get("type", "sensor")
        name = device.get("name", "unknown").lower().replace(" ", "_")
        return f"{dtype}.{name}"

    async def _find_device_by_entity_id(self, entity_id: str) -> dict | None:
        """Search ALL SDS devices by entity_id."""
        all_devices = await self.device_manager.get_all_devices()
        for device in all_devices:
            if self._device_to_entity_id(device) == entity_id:
                return device
        return None

    async def register_device(self, device: dict[str, Any]):
        self._devices[device["id"]] = device

    async def unregister_device(self, device: dict[str, Any]):
        self._devices.pop(device["id"], None)

    async def publish_state(self, device: dict[str, Any]):
        self._devices[device["id"]] = device
        # Broadcast is handled via event_bus subscription
