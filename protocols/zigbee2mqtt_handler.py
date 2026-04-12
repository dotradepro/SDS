"""Zigbee2MQTT protocol handler - operates on top of MQTT."""

import asyncio
import json
import logging
import random
from typing import Any

import aiomqtt

from protocols.base import ProtocolHandler
from core.event_bus import event_bus

logger = logging.getLogger(__name__)


def generate_ieee_address() -> str:
    return "0x" + "".join(f"{random.randint(0, 255):02x}" for _ in range(8))


class Zigbee2MQTTHandler(ProtocolHandler):
    name = "zigbee2mqtt"

    def __init__(self, config: dict[str, Any], device_manager: Any):
        super().__init__(config, device_manager)
        self._client: aiomqtt.Client | None = None
        self._devices: dict[str, dict[str, Any]] = {}  # device_id -> device
        self._groups: dict[int, dict[str, Any]] = {}  # group_id -> group info
        self._next_group_id = 1
        self._task: asyncio.Task | None = None
        self.broker_host = config.get("broker_host", "mosquitto")
        self.broker_port = config.get("broker_port", 1883)
        self.prefix = config.get("bridge_prefix", "zigbee2mqtt")

    async def start(self):
        self._task = asyncio.create_task(self._run())
        self.is_running = True
        self.status = "connecting"

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.status = "stopped"

    async def _run(self):
        while self.is_running:
            try:
                async with aiomqtt.Client(
                    hostname=self.broker_host,
                    port=self.broker_port,
                    identifier="sds_zigbee2mqtt",
                ) as client:
                    self._client = client
                    self.status = "connected"
                    self.status_message = "Zigbee2MQTT bridge online"
                    logger.info("Zigbee2MQTT handler connected")

                    # Publish bridge state
                    await client.publish(f"{self.prefix}/bridge/state", "online", retain=True)

                    # Subscribe to command topics
                    await client.subscribe(f"{self.prefix}/+/set")
                    await client.subscribe(f"{self.prefix}/+/get")
                    await client.subscribe(f"{self.prefix}/bridge/request/#")

                    # Publish devices list
                    await self._publish_bridge_devices()
                    await self._publish_bridge_groups()

                    await event_bus.emit("protocol_status", {
                        "protocol": "zigbee2mqtt",
                        "status": "connected",
                        "message": self.status_message,
                    })

                    async for message in client.messages:
                        await self._handle_message(message)

            except aiomqtt.MqttError as e:
                self.status = "disconnected"
                self.status_message = str(e)
                self.stats["errors"] += 1
                logger.warning("Z2M disconnected: %s. Reconnecting in 5s...", e)
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Z2M unexpected error")
                await asyncio.sleep(5)

        self._client = None

    async def _handle_message(self, message: aiomqtt.Message):
        topic = str(message.topic)
        try:
            payload = message.payload.decode() if isinstance(message.payload, bytes) else str(message.payload)
        except Exception:
            payload = str(message.payload)

        self.stats["messages_received"] += 1

        await event_bus.emit("protocol_event", {
            "protocol": "zigbee2mqtt",
            "direction": "received",
            "topic": topic,
            "payload": payload,
            "device_id": None,
        })

        # Handle /set commands for devices
        if topic.endswith("/set"):
            friendly_name = topic.replace(f"{self.prefix}/", "").replace("/set", "")
            await self._handle_set_command(friendly_name, payload)

        # Handle /get commands
        elif topic.endswith("/get"):
            friendly_name = topic.replace(f"{self.prefix}/", "").replace("/get", "")
            await self._handle_get_command(friendly_name)

        # Handle bridge requests
        elif "/bridge/request/" in topic:
            await self._handle_bridge_request(topic, payload)

    async def _handle_set_command(self, friendly_name: str, payload: str):
        """Handle a /set command from Selena or other client."""
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            data = {"state": payload}

        # Check if it's a group command
        group = self._find_group_by_name(friendly_name)
        if group:
            await self._handle_group_set(group, data)
            return

        # Find device by friendly_name
        device = self._find_device_by_friendly_name(friendly_name)
        if not device:
            logger.warning("Z2M: unknown device '%s'", friendly_name)
            return

        # Map Z2M payload to state changes
        state_changes = {}
        if "state" in data:
            state_changes["state"] = data["state"]
        if "brightness" in data:
            state_changes["brightness"] = data["brightness"]
            state_changes["state"] = "ON"
        if "color_temp" in data:
            state_changes["color_temp"] = data["color_temp"]
            state_changes["state"] = "ON"
        if "color" in data:
            state_changes["color"] = data["color"]
            state_changes["state"] = "ON"
            state_changes["color_mode"] = "color"
        if "temperature" in data:
            state_changes["target_temperature"] = data["temperature"]
        if "target_temperature" in data:
            state_changes["target_temperature"] = data["target_temperature"]
        if "hvac_mode" in data:
            state_changes["hvac_mode"] = data["hvac_mode"]
        if "position" in data:
            state_changes["position"] = data["position"]
            state_changes["state"] = "open" if data["position"] > 0 else "closed"

        # Additional generic fields
        for k, v in data.items():
            if k not in state_changes:
                state_changes[k] = v

        if state_changes:
            await self.device_manager.set_state(device["id"], state_changes, source="zigbee2mqtt_command")

    async def _handle_get_command(self, friendly_name: str):
        """Handle a /get command - publish current state."""
        device = self._find_device_by_friendly_name(friendly_name)
        if device:
            await self.publish_state(device)

    async def _handle_bridge_request(self, topic: str, payload: str):
        """Handle bridge management requests."""
        try:
            data = json.loads(payload) if payload else {}
        except (json.JSONDecodeError, ValueError):
            data = {}

        if topic.endswith("/permit_join"):
            value = data.get("value", True)
            response = {"data": {"value": value}, "status": "ok"}
            if self._client:
                await self._client.publish(
                    f"{self.prefix}/bridge/response/permit_join",
                    json.dumps(response), retain=False
                )

        elif topic.endswith("/group/add"):
            await self._handle_group_add(data)

        elif topic.endswith("/group/remove"):
            await self._handle_group_remove(data)

        elif topic.endswith("/group/members/add"):
            await self._handle_group_member_add(data)

        elif topic.endswith("/group/members/remove"):
            await self._handle_group_member_remove(data)

    # ---- Group management ----

    async def _handle_group_add(self, data: dict[str, Any]):
        friendly_name = data.get("friendly_name", f"group_{self._next_group_id}")
        group_id = data.get("id", self._next_group_id)
        self._next_group_id = max(self._next_group_id, group_id + 1)

        group = {
            "id": group_id,
            "friendly_name": friendly_name,
            "members": [],
        }
        self._groups[group_id] = group
        await self._publish_bridge_groups()

        if self._client:
            await self._client.publish(
                f"{self.prefix}/bridge/response/group/add",
                json.dumps({"data": group, "status": "ok"}),
            )

    async def _handle_group_remove(self, data: dict[str, Any]):
        group_id = data.get("id")
        friendly_name = data.get("friendly_name")

        removed = None
        if group_id and group_id in self._groups:
            removed = self._groups.pop(group_id)
        elif friendly_name:
            for gid, g in list(self._groups.items()):
                if g["friendly_name"] == friendly_name:
                    removed = self._groups.pop(gid)
                    break

        if removed:
            await self._publish_bridge_groups()

    async def _handle_group_member_add(self, data: dict[str, Any]):
        group_name = data.get("group")
        device_name = data.get("device")
        endpoint = data.get("endpoint", 1)

        group = self._find_group_by_name(group_name)
        if not group:
            return

        device = self._find_device_by_friendly_name(device_name)
        if not device:
            return

        ieee = device.get("protocol_config", {}).get("ieee_address", "")
        member = {"ieee_address": ieee, "endpoint": endpoint}

        # Avoid duplicates
        existing = [m for m in group["members"] if m["ieee_address"] == ieee]
        if not existing:
            group["members"].append(member)
            await self._publish_bridge_groups()

    async def _handle_group_member_remove(self, data: dict[str, Any]):
        group_name = data.get("group")
        device_name = data.get("device")

        group = self._find_group_by_name(group_name)
        if not group:
            return

        device = self._find_device_by_friendly_name(device_name)
        if not device:
            return

        ieee = device.get("protocol_config", {}).get("ieee_address", "")
        group["members"] = [m for m in group["members"] if m["ieee_address"] != ieee]
        await self._publish_bridge_groups()

    async def _handle_group_set(self, group: dict[str, Any], data: dict[str, Any]):
        """Apply a command to all devices in a group."""
        for member in group["members"]:
            ieee = member["ieee_address"]
            device = self._find_device_by_ieee(ieee)
            if device:
                state_changes = {}
                if "state" in data:
                    state_changes["state"] = data["state"]
                if "brightness" in data:
                    state_changes["brightness"] = data["brightness"]
                    state_changes["state"] = "ON"
                if "color_temp" in data:
                    state_changes["color_temp"] = data["color_temp"]
                for k, v in data.items():
                    if k not in state_changes:
                        state_changes[k] = v
                if state_changes:
                    await self.device_manager.set_state(device["id"], state_changes, source="zigbee2mqtt_group_command")

        # Publish aggregated group state
        await self._publish_group_state(group)

    async def _publish_group_state(self, group: dict[str, Any]):
        """Publish aggregated state for a group."""
        if not self._client:
            return

        states = []
        for member in group["members"]:
            device = self._find_device_by_ieee(member["ieee_address"])
            if device:
                state = await self.device_manager.get_state(device["id"])
                if state:
                    states.append(state)

        if not states:
            return

        # Aggregate: if any ON -> ON, average brightness, etc.
        aggregated = {}
        if any(s.get("state") == "ON" for s in states):
            aggregated["state"] = "ON"
        else:
            aggregated["state"] = "OFF"

        brightness_vals = [s["brightness"] for s in states if "brightness" in s]
        if brightness_vals:
            aggregated["brightness"] = int(sum(brightness_vals) / len(brightness_vals))

        color_temp_vals = [s["color_temp"] for s in states if "color_temp" in s]
        if color_temp_vals:
            aggregated["color_temp"] = int(sum(color_temp_vals) / len(color_temp_vals))

        topic = f"{self.prefix}/{group['friendly_name']}"
        await self._client.publish(topic, json.dumps(aggregated), retain=True)

    # ---- Device registration ----

    async def register_device(self, device: dict[str, Any]):
        config = device.get("protocol_config", {})
        if not config.get("ieee_address"):
            config["ieee_address"] = generate_ieee_address()
            device["protocol_config"] = config

        self._devices[device["id"]] = device

        # Subscribe to device-specific topics
        friendly_name = config.get("friendly_name", device["name"].replace(" ", "_").lower())
        if self._client:
            try:
                await self._client.subscribe(f"{self.prefix}/{friendly_name}/set")
                await self._client.subscribe(f"{self.prefix}/{friendly_name}/get")
            except Exception:
                logger.exception("Failed to subscribe Z2M topics for %s", friendly_name)

        # Publish state
        await self.publish_state(device)
        # Update bridge/devices
        await self._publish_bridge_devices()

        # Emit join event
        if self._client:
            event = {
                "type": "device_joined",
                "data": {
                    "friendly_name": friendly_name,
                    "ieee_address": config["ieee_address"],
                }
            }
            await self._client.publish(f"{self.prefix}/bridge/event", json.dumps(event))

    async def unregister_device(self, device: dict[str, Any]):
        self._devices.pop(device["id"], None)
        await self._publish_bridge_devices()

        # Emit leave event
        config = device.get("protocol_config", {})
        if self._client:
            event = {
                "type": "device_leave",
                "data": {
                    "friendly_name": config.get("friendly_name", ""),
                    "ieee_address": config.get("ieee_address", ""),
                }
            }
            await self._client.publish(f"{self.prefix}/bridge/event", json.dumps(event))

    async def publish_state(self, device: dict[str, Any]):
        if not self._client:
            return

        config = device.get("protocol_config", {})
        friendly_name = config.get("friendly_name", device["name"].replace(" ", "_").lower())
        state = device.get("state", {})

        topic = f"{self.prefix}/{friendly_name}"
        payload = json.dumps(state)

        try:
            await self._client.publish(topic, payload, retain=True)
            self.stats["messages_sent"] += 1
            await event_bus.emit("protocol_event", {
                "protocol": "zigbee2mqtt",
                "direction": "sent",
                "topic": topic,
                "payload": payload,
                "device_id": device["id"],
            })
        except Exception:
            logger.exception("Failed to publish Z2M state for %s", friendly_name)

    async def _publish_bridge_devices(self):
        """Publish ALL SDS devices to bridge/devices (not just zigbee2mqtt ones)."""
        if not self._client:
            return

        devices_list = []
        all_devices = await self.device_manager.get_all_devices()
        for device in all_devices:
            config = device.get("protocol_config", {})
            friendly_name = config.get("friendly_name", device["name"].replace(" ", "_").lower())

            # Ensure ieee_address exists
            ieee = config.get("ieee_address", "")
            if not ieee:
                ieee = generate_ieee_address()

            # Build exposes based on device type
            exposes = self._build_exposes(device)

            entry = {
                "ieee_address": ieee,
                "friendly_name": friendly_name,
                "model_id": config.get("model_id", config.get("model", "SDS_Virtual")),
                "manufacturer": config.get("manufacturer", "SDS Simulator"),
                "type": "Router",
                "supported": True,
                "definition": {
                    "exposes": exposes,
                },
            }
            devices_list.append(entry)

        await self._client.publish(
            f"{self.prefix}/bridge/devices",
            json.dumps(devices_list),
            retain=True,
        )

    async def _publish_bridge_groups(self):
        """Publish all groups to bridge/groups."""
        if not self._client:
            return

        groups_list = list(self._groups.values())
        await self._client.publish(
            f"{self.prefix}/bridge/groups",
            json.dumps(groups_list),
            retain=True,
        )

    def _build_exposes(self, device: dict[str, Any]) -> list[dict]:
        dtype = device["type"]
        caps = device.get("capabilities", [])

        if dtype == "light":
            features = [{"name": "state", "type": "binary"}]
            if "brightness" in caps:
                features.append({"name": "brightness", "type": "numeric", "value_min": 0, "value_max": 254})
            if "color_temp" in caps:
                features.append({"name": "color_temp", "type": "numeric", "value_min": 153, "value_max": 500})
            if "color" in caps:
                features.append({"name": "color_xy", "type": "composite"})
            return [{"type": "light", "features": features}]

        elif dtype == "switch":
            return [{"type": "switch", "features": [{"name": "state", "type": "binary"}]}]

        elif dtype == "climate":
            features = [
                {"name": "local_temperature", "type": "numeric"},
                {"name": "occupied_heating_setpoint", "type": "numeric"},
                {"name": "system_mode", "type": "enum", "values": ["off", "heat", "cool", "auto"]},
            ]
            return [{"type": "climate", "features": features}]

        elif dtype == "sensor":
            features = []
            if "temperature" in caps:
                features.append({"name": "temperature", "type": "numeric"})
            if "humidity" in caps:
                features.append({"name": "humidity", "type": "numeric"})
            if "occupancy" in caps:
                features.append({"name": "occupancy", "type": "binary"})
            if "contact" in caps:
                features.append({"name": "contact", "type": "binary"})
            if "battery" in caps:
                features.append({"name": "battery", "type": "numeric"})
            if "illuminance" in caps:
                features.append({"name": "illuminance", "type": "numeric"})
            return features

        elif dtype == "cover":
            return [{"type": "cover", "features": [
                {"name": "state", "type": "enum", "values": ["OPEN", "CLOSE", "STOP"]},
                {"name": "position", "type": "numeric", "value_min": 0, "value_max": 100},
            ]}]

        elif dtype == "lock":
            return [{"type": "lock", "features": [
                {"name": "state", "type": "enum", "values": ["LOCK", "UNLOCK"]},
            ]}]

        return []

    def _find_device_by_friendly_name(self, name: str) -> dict[str, Any] | None:
        """Search ALL SDS devices by friendly_name (not just zigbee2mqtt ones)."""
        # First check registered devices (faster)
        for device in self._devices.values():
            config = device.get("protocol_config", {})
            fn = config.get("friendly_name", device["name"].replace(" ", "_").lower())
            if fn == name:
                return device
        # Then check all device_manager devices
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in async context — use sync access to cached devices
                for device in self.device_manager._devices.values():
                    config = device.get("protocol_config", {})
                    fn = config.get("friendly_name", device["name"].replace(" ", "_").lower())
                    if fn == name:
                        return device
        except Exception:
            pass
        return None

    def _find_device_by_ieee(self, ieee: str) -> dict[str, Any] | None:
        for device in self._devices.values():
            config = device.get("protocol_config", {})
            if config.get("ieee_address") == ieee:
                return device
        return None

    def _find_group_by_name(self, name: str) -> dict[str, Any] | None:
        for group in self._groups.values():
            if group["friendly_name"] == name:
                return group
        return None

    # Public group management API
    async def create_group(self, friendly_name: str) -> dict[str, Any]:
        gid = self._next_group_id
        self._next_group_id += 1
        group = {"id": gid, "friendly_name": friendly_name, "members": []}
        self._groups[gid] = group
        await self._publish_bridge_groups()

        # Subscribe to group set topic
        if self._client:
            await self._client.subscribe(f"{self.prefix}/{friendly_name}/set")

        return group

    async def delete_group(self, group_id: int) -> bool:
        if group_id in self._groups:
            self._groups.pop(group_id)
            await self._publish_bridge_groups()
            return True
        return False

    async def add_group_member(self, group_id: int, device_id: str, endpoint: int = 1) -> bool:
        group = self._groups.get(group_id)
        device = self._devices.get(device_id)
        if not group or not device:
            return False

        ieee = device.get("protocol_config", {}).get("ieee_address", "")
        existing = [m for m in group["members"] if m["ieee_address"] == ieee]
        if not existing:
            group["members"].append({"ieee_address": ieee, "endpoint": endpoint})
            await self._publish_bridge_groups()
        return True

    async def remove_group_member(self, group_id: int, device_id: str) -> bool:
        group = self._groups.get(group_id)
        device = self._devices.get(device_id)
        if not group or not device:
            return False

        ieee = device.get("protocol_config", {}).get("ieee_address", "")
        group["members"] = [m for m in group["members"] if m["ieee_address"] != ieee]
        await self._publish_bridge_groups()
        return True

    def get_groups(self) -> list[dict[str, Any]]:
        return list(self._groups.values())
