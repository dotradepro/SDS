"""WebSocket endpoint for real-time UI updates."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.event_bus import event_bus
from core.device_manager import device_manager

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._device_subscriptions: dict[WebSocket, set[str]] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)
        self._device_subscriptions[ws] = set()

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)
        self._device_subscriptions.pop(ws, None)

    def subscribe_device(self, ws: WebSocket, device_id: str):
        if ws in self._device_subscriptions:
            self._device_subscriptions[ws].add(device_id)

    def unsubscribe_device(self, ws: WebSocket, device_id: str):
        if ws in self._device_subscriptions:
            self._device_subscriptions[ws].discard(device_id)

    async def broadcast(self, message: dict[str, Any]):
        """Send message to all connected clients."""
        data = json.dumps(message, default=str)
        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)

    async def send_to_device_subscribers(self, device_id: str, message: dict[str, Any]):
        """Send message only to clients subscribed to a specific device."""
        data = json.dumps(message, default=str)
        disconnected = []
        for ws, subs in self._device_subscriptions.items():
            if not subs or device_id in subs:  # empty subs = subscribed to all
                try:
                    await ws.send_text(data)
                except Exception:
                    disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)


manager = ConnectionManager()


async def _on_event(event: dict[str, Any]):
    """Forward all events to WebSocket clients."""
    await manager.broadcast(event)


def setup_event_forwarding():
    """Subscribe to all event bus events and forward to WS clients."""
    event_bus.subscribe_all(_on_event)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                continue

            msg_type = msg.get("type", "")

            if msg_type == "subscribe":
                device_id = msg.get("device_id")
                if device_id:
                    manager.subscribe_device(ws, device_id)

            elif msg_type == "unsubscribe":
                device_id = msg.get("device_id")
                if device_id:
                    manager.unsubscribe_device(ws, device_id)

            elif msg_type == "get_all_states":
                devices = await device_manager.get_all_devices()
                await ws.send_text(json.dumps({
                    "type": "all_states",
                    "devices": devices,
                }, default=str))

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
    finally:
        manager.disconnect(ws)
