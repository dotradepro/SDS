"""HTTP protocol handler - Philips Hue + LIFX API emulation.
Exposes ALL SDS devices through Hue and LIFX APIs."""

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

    async def unregister_device(self, device: dict[str, Any]):
        self._devices.pop(device["id"], None)
        self._hue_light_index.pop(device["id"], None)

    async def publish_state(self, device: dict[str, Any]):
        self._devices[device["id"]] = device

    def _ensure_hue_id(self, device_id: str) -> int:
        """Assign a Hue light ID to a device if it doesn't have one."""
        if device_id not in self._hue_light_index:
            self._hue_light_index[device_id] = self._next_hue_index
            self._next_hue_index += 1
        return self._hue_light_index[device_id]

    async def _get_all_devices(self) -> list[dict[str, Any]]:
        """Get ALL devices from device_manager."""
        return await self.device_manager.get_all_devices()

    async def _find_device_by_hue_id(self, hue_id: int) -> dict[str, Any] | None:
        """Find any SDS device by Hue ID."""
        for dev_id, idx in self._hue_light_index.items():
            if idx == hue_id:
                return await self.device_manager.get_device(dev_id)
        return None

    def _state_to_hue(self, device: dict[str, Any]) -> dict[str, Any]:
        state = device.get("state", {})
        hue_state = {
            "on": state.get("state") in ("ON", "on", "playing", "cleaning"),
            "bri": int(state.get("brightness", 254)) if "brightness" in state else 254,
            "ct": int(state.get("color_temp", 300)) if "color_temp" in state else 300,
            "alert": "none",
            "colormode": state.get("color_mode", "ct"),
            "reachable": device.get("is_online", True),
        }
        if state.get("color"):
            hue_state["hue"] = 0
            hue_state["sat"] = 0
        return hue_state

    def _device_to_hue(self, device: dict[str, Any], hue_id: int) -> dict[str, Any]:
        config = device.get("protocol_config", {})
        dtype = device.get("type", "light")
        hue_type_map = {
            "light": "Extended color light",
            "switch": "On/Off plug-in unit",
            "climate": "ZLLTemperature",
            "sensor": "ZLLPresence",
            "cover": "Window covering device",
            "lock": "On/Off plug-in unit",
            "media_player": "Extended color light",
            "vacuum": "On/Off plug-in unit",
            "speaker": "Extended color light",
            "camera": "ZLLPresence",
        }
        return {
            "state": self._state_to_hue(device),
            "type": hue_type_map.get(dtype, "Extended color light"),
            "name": device["name"],
            "modelid": config.get("model_id", config.get("model", "SDS_Virtual")),
            "manufacturername": config.get("manufacturer", "SDS Simulator"),
            "uniqueid": f"00:17:88:01:00:{hue_id:06d}-0b",
            "swversion": "1.0.0",
        }

    def _state_to_lifx(self, device: dict[str, Any]) -> dict[str, Any]:
        state = device.get("state", {})
        ct = max(state.get("color_temp", 300), 1)
        return {
            "id": device["id"],
            "label": device["name"],
            "power": "on" if state.get("state") in ("ON", "on", "playing") else "off",
            "brightness": state.get("brightness", 254) / 254.0 if "brightness" in state else 1.0,
            "color": {
                "hue": 0,
                "saturation": 0,
                "kelvin": int(1000000 / ct),
            },
            "connected": device.get("is_online", True),
            "group": {"name": device.get("room", "")},
            "product": {
                "name": device.get("protocol_config", {}).get("model", device.get("type", "")),
                "company": device.get("protocol_config", {}).get("manufacturer", "SDS"),
            },
        }


# ---- Hue API routes (expose ALL SDS devices) ----

@router.get("/api/{token}/lights")
async def hue_get_lights(token: str):
    h = _handler_instance
    if not h:
        return JSONResponse({})
    all_devices = await h._get_all_devices()
    result = {}
    for device in all_devices:
        hue_id = h._ensure_hue_id(device["id"])
        result[str(hue_id)] = h._device_to_hue(device, hue_id)
    h.stats["messages_sent"] += 1
    return JSONResponse(result)


@router.get("/api/{token}/lights/{light_id}")
async def hue_get_light(token: str, light_id: int):
    h = _handler_instance
    if not h:
        return JSONResponse({"error": "not found"}, status_code=404)
    device = await h._find_device_by_hue_id(light_id)
    if not device:
        return JSONResponse({"error": "not found"}, status_code=404)
    h.stats["messages_sent"] += 1
    return JSONResponse(h._device_to_hue(device, light_id))


@router.put("/api/{token}/lights/{light_id}/state")
async def hue_set_light_state(token: str, light_id: int, request: Request):
    h = _handler_instance
    if not h:
        return JSONResponse({"error": "not found"}, status_code=404)
    device = await h._find_device_by_hue_id(light_id)
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

    success = [{"success": {f"/lights/{light_id}/state/{k}": v}} for k, v in body.items()]
    return JSONResponse(success)


@router.post("/api")
async def hue_create_user(request: Request):
    """Simulate Hue Bridge user registration — always succeeds, returns a token."""
    import uuid
    token = uuid.uuid4().hex[:20]
    return JSONResponse([{"success": {"username": token}}])


@router.get("/api/{token}/groups")
async def hue_get_groups(token: str):
    return JSONResponse({})


@router.post("/api/{token}/groups/{group_id}/action")
async def hue_group_action(token: str, group_id: int, request: Request):
    return JSONResponse([{"success": True}])


@router.get("/api/{token}/config")
async def hue_get_config(token: str):
    h = _handler_instance
    device_count = 0
    if h:
        all_devices = await h._get_all_devices()
        device_count = len(all_devices)
    return JSONResponse({
        "name": "SDS Hue Bridge",
        "datastoreversion": "100",
        "swversion": "1953188020",
        "apiversion": "1.53.0",
        "mac": "00:17:88:00:00:01",
        "bridgeid": "001788FFFE000001",
        "modelid": "BSB002",
        "zigbeechannel": 15,
        "devicecount": device_count,
    })


# ---- LIFX API routes (expose ALL SDS devices) ----

@router.get("/v1/lights")
async def lifx_get_lights():
    h = _handler_instance
    if not h:
        return JSONResponse([])
    all_devices = await h._get_all_devices()
    result = [h._state_to_lifx(device) for device in all_devices]
    return JSONResponse(result)


@router.put("/v1/lights/{selector}/state")
async def lifx_set_state(selector: str, request: Request):
    h = _handler_instance
    if not h:
        return JSONResponse({"error": "not found"}, status_code=404)

    body = await request.json()
    h.stats["messages_received"] += 1

    # Find device by id or name among ALL devices
    target = await h.device_manager.get_device(selector)
    if not target:
        all_devices = await h._get_all_devices()
        for device in all_devices:
            if device["name"] == selector:
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

    target = await h.device_manager.get_device(selector)
    if not target:
        all_devices = await h._get_all_devices()
        for device in all_devices:
            if device["name"] == selector:
                target = device
                break

    if not target:
        return JSONResponse({"error": "not found"}, status_code=404)

    await h.device_manager.execute_command(target["id"], "toggle", {}, source="http_lifx_command")
    return JSONResponse({"results": [{"status": "ok"}]})


# ---- Generic REST routes (search ALL devices) ----

@router.get("/devices/{device_id}/state")
async def generic_get_state(device_id: str):
    h = _handler_instance
    if not h:
        return JSONResponse({"error": "not found"}, status_code=404)
    device = await h.device_manager.get_device(device_id)
    if not device:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(device.get("state", {}))


@router.post("/devices/{device_id}/command")
async def generic_command(device_id: str, request: Request):
    h = _handler_instance
    if not h:
        return JSONResponse({"error": "not found"}, status_code=404)
    device = await h.device_manager.get_device(device_id)
    if not device:
        return JSONResponse({"error": "not found"}, status_code=404)

    body = await request.json()
    command = body.get("command", "")
    params = body.get("params", {})
    await h.device_manager.execute_command(device_id, command, params, source="http_command")
    return JSONResponse({"status": "ok"})
