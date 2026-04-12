"""HTTP protocol handler - Philips Hue + LIFX API emulation."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from protocols.base import ProtocolHandler
from core.event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter()

# Global reference set by the handler on start
_handler_instance: "HTTPHandler | None" = None


class HTTPHandler(ProtocolHandler):
    name = "http"

    def __init__(self, config: dict[str, Any], device_manager: Any):
        super().__init__(config, device_manager)
        self._devices: dict[str, dict[str, Any]] = {}
        self._hue_token = "sds-test-token"
        self._hue_light_index: dict[str, int] = {}  # device_id -> hue index
        self._next_hue_index = 1

    async def start(self):
        global _handler_instance
        _handler_instance = self
        self.is_running = True
        self.status = "connected"
        self.status_message = "HTTP handler active"
        await event_bus.emit("protocol_status", {
            "protocol": "http",
            "status": "connected",
            "message": self.status_message,
        })

    async def stop(self):
        global _handler_instance
        _handler_instance = None
        self.is_running = False
        self.status = "stopped"

    async def register_device(self, device: dict[str, Any]):
        self._devices[device["id"]] = device
        protocol = device.get("protocol", "")
        if protocol in ("http_hue", "http"):
            if device["id"] not in self._hue_light_index:
                self._hue_light_index[device["id"]] = self._next_hue_index
                self._next_hue_index += 1

    async def unregister_device(self, device: dict[str, Any]):
        self._devices.pop(device["id"], None)
        self._hue_light_index.pop(device["id"], None)

    async def publish_state(self, device: dict[str, Any]):
        # HTTP is pull-based, no push needed
        self._devices[device["id"]] = device

    def get_hue_light_id(self, device_id: str) -> int | None:
        return self._hue_light_index.get(device_id)

    def find_device_by_hue_id(self, hue_id: int) -> dict[str, Any] | None:
        for dev_id, idx in self._hue_light_index.items():
            if idx == hue_id:
                return self._devices.get(dev_id)
        return None

    def _state_to_hue(self, device: dict[str, Any]) -> dict[str, Any]:
        state = device.get("state", {})
        hue_state = {
            "on": state.get("state") == "ON",
            "bri": state.get("brightness", 254),
            "ct": state.get("color_temp", 300),
            "alert": "none",
            "colormode": state.get("color_mode", "ct"),
            "reachable": device.get("is_online", True),
        }
        color = state.get("color", {})
        if color:
            hue_state["hue"] = 0
            hue_state["sat"] = 0
        return hue_state

    def _device_to_hue(self, device: dict[str, Any], hue_id: int) -> dict[str, Any]:
        config = device.get("protocol_config", {})
        return {
            "state": self._state_to_hue(device),
            "type": "Extended color light",
            "name": device["name"],
            "modelid": config.get("model_id", "LCT016"),
            "manufacturername": config.get("manufacturer", "Signify"),
            "uniqueid": f"00:17:88:01:00:{hue_id:06d}-0b",
            "swversion": "1.0.0",
        }

    def _state_to_lifx(self, device: dict[str, Any]) -> dict[str, Any]:
        state = device.get("state", {})
        return {
            "id": device["id"],
            "label": device["name"],
            "power": "on" if state.get("state") == "ON" else "off",
            "brightness": state.get("brightness", 254) / 254.0,
            "color": {
                "hue": 0,
                "saturation": 0,
                "kelvin": int(1000000 / max(state.get("color_temp", 300), 1)),
            },
            "connected": device.get("is_online", True),
        }


# ---- Hue API routes ----

@router.get("/api/{token}/lights")
async def hue_get_lights(token: str):
    h = _handler_instance
    if not h:
        return JSONResponse({})
    result = {}
    for dev_id, device in h._devices.items():
        if device.get("protocol") in ("http_hue", "http"):
            hue_id = h.get_hue_light_id(dev_id)
            if hue_id:
                result[str(hue_id)] = h._device_to_hue(device, hue_id)
    h.stats["messages_sent"] += 1
    return JSONResponse(result)


@router.get("/api/{token}/lights/{light_id}")
async def hue_get_light(token: str, light_id: int):
    h = _handler_instance
    if not h:
        return JSONResponse({"error": "not found"}, status_code=404)
    device = h.find_device_by_hue_id(light_id)
    if not device:
        return JSONResponse({"error": "not found"}, status_code=404)
    h.stats["messages_sent"] += 1
    return JSONResponse(h._device_to_hue(device, light_id))


@router.put("/api/{token}/lights/{light_id}/state")
async def hue_set_light_state(token: str, light_id: int, request: Request):
    h = _handler_instance
    if not h:
        return JSONResponse({"error": "not found"}, status_code=404)
    device = h.find_device_by_hue_id(light_id)
    if not device:
        return JSONResponse({"error": "not found"}, status_code=404)

    body = await request.json()
    h.stats["messages_received"] += 1

    state_changes = {}
    if "on" in body:
        state_changes["state"] = "ON" if body["on"] else "OFF"
    if "bri" in body:
        state_changes["brightness"] = body["bri"]
    if "ct" in body:
        state_changes["color_temp"] = body["ct"]
    if "hue" in body or "sat" in body:
        state_changes["color_mode"] = "color"

    await h.device_manager.set_state(device["id"], state_changes, source="http_hue_command")

    await event_bus.emit("protocol_event", {
        "protocol": "http_hue",
        "direction": "received",
        "topic": f"/api/.../lights/{light_id}/state",
        "payload": json.dumps(body),
        "device_id": device["id"],
    })

    success = [{"success": {f"/lights/{light_id}/state/{k}": v}} for k, v in body.items()]
    return JSONResponse(success)


@router.get("/api/{token}/groups")
async def hue_get_groups(token: str):
    return JSONResponse({})


@router.post("/api/{token}/groups/{group_id}/action")
async def hue_group_action(token: str, group_id: int, request: Request):
    return JSONResponse([{"success": True}])


@router.get("/api/{token}/config")
async def hue_get_config(token: str):
    return JSONResponse({
        "name": "SDS Hue Bridge",
        "datastoreversion": "100",
        "swversion": "1953188020",
        "apiversion": "1.53.0",
        "mac": "00:17:88:00:00:01",
        "bridgeid": "001788FFFE000001",
        "modelid": "BSB002",
    })


# ---- LIFX API routes ----

@router.get("/v1/lights")
async def lifx_get_lights():
    h = _handler_instance
    if not h:
        return JSONResponse([])
    result = []
    for dev_id, device in h._devices.items():
        if device.get("protocol") in ("http_lifx", "http"):
            result.append(h._state_to_lifx(device))
    return JSONResponse(result)


@router.put("/v1/lights/{selector}/state")
async def lifx_set_state(selector: str, request: Request):
    h = _handler_instance
    if not h:
        return JSONResponse({"error": "not found"}, status_code=404)

    body = await request.json()
    h.stats["messages_received"] += 1

    # Find device by selector (id or label)
    target = None
    for device in h._devices.values():
        if device["id"] == selector or device["name"] == selector:
            target = device
            break

    if not target:
        return JSONResponse({"error": "not found"}, status_code=404)

    state_changes = {}
    if "power" in body:
        state_changes["state"] = "ON" if body["power"] == "on" else "OFF"
    if "brightness" in body:
        state_changes["brightness"] = int(body["brightness"] * 254)
    if "color" in body:
        state_changes["color_mode"] = "color"

    await h.device_manager.set_state(target["id"], state_changes, source="http_lifx_command")
    return JSONResponse({"results": [{"status": "ok", "id": target["id"]}]})


@router.post("/v1/lights/{selector}/toggle")
async def lifx_toggle(selector: str):
    h = _handler_instance
    if not h:
        return JSONResponse({"error": "not found"}, status_code=404)

    for device in h._devices.values():
        if device["id"] == selector or device["name"] == selector:
            await h.device_manager.execute_command(device["id"], "toggle", {}, source="http_lifx_command")
            return JSONResponse({"results": [{"status": "ok"}]})

    return JSONResponse({"error": "not found"}, status_code=404)


# ---- Generic REST routes ----

@router.get("/devices/{device_id}/state")
async def generic_get_state(device_id: str):
    h = _handler_instance
    if not h:
        return JSONResponse({"error": "not found"}, status_code=404)
    device = h._devices.get(device_id)
    if not device:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(device.get("state", {}))


@router.post("/devices/{device_id}/command")
async def generic_command(device_id: str, request: Request):
    h = _handler_instance
    if not h:
        return JSONResponse({"error": "not found"}, status_code=404)
    device = h._devices.get(device_id)
    if not device:
        return JSONResponse({"error": "not found"}, status_code=404)

    body = await request.json()
    command = body.get("command", "")
    params = body.get("params", {})
    await h.device_manager.execute_command(device_id, command, params, source="http_command")
    return JSONResponse({"status": "ok"})
