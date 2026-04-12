"""MQTT protocol handler using aiomqtt."""

import asyncio
import json
import logging
from typing import Any

import aiomqtt

from protocols.base import ProtocolHandler
from core.event_bus import event_bus

logger = logging.getLogger(__name__)


class MQTTHandler(ProtocolHandler):
    name = "mqtt"

    def __init__(self, config: dict[str, Any], device_manager: Any):
        super().__init__(config, device_manager)
        self._client: aiomqtt.Client | None = None
        self._devices: dict[str, dict[str, Any]] = {}  # device_id -> device
        self._subscriptions: dict[str, str] = {}  # topic -> device_id
        self._task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self.broker_host = config.get("broker_host", "mosquitto")
        self.broker_port = config.get("broker_port", 1883)
        self.client_id = config.get("client_id", "sds_simulator")

    async def start(self):
        self._task = asyncio.create_task(self._run())
        self.is_running = True
        self.status = "connecting"
        self.status_message = f"Connecting to {self.broker_host}:{self.broker_port}"

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
                    identifier=self.client_id,
                ) as client:
                    self._client = client
                    self.status = "connected"
                    self.status_message = f"Connected to {self.broker_host}:{self.broker_port}"
                    logger.info("MQTT connected to %s:%d", self.broker_host, self.broker_port)

                    await event_bus.emit("protocol_status", {
                        "protocol": "mqtt",
                        "status": "connected",
                        "message": self.status_message,
                    })

                    # Resubscribe for all registered devices
                    for topic in list(self._subscriptions.keys()):
                        await client.subscribe(topic)

                    async for message in client.messages:
                        await self._handle_message(message)

            except aiomqtt.MqttError as e:
                self.status = "disconnected"
                self.status_message = str(e)
                self.stats["errors"] += 1
                logger.warning("MQTT disconnected: %s. Reconnecting in 5s...", e)
                await event_bus.emit("protocol_status", {
                    "protocol": "mqtt",
                    "status": "disconnected",
                    "message": str(e),
                })
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("MQTT unexpected error")
                await asyncio.sleep(5)

        self._client = None

    async def _handle_message(self, message: aiomqtt.Message):
        topic = str(message.topic)
        try:
            payload = message.payload.decode() if isinstance(message.payload, bytes) else str(message.payload)
        except Exception:
            payload = str(message.payload)

        self.stats["messages_received"] += 1

        # Find device by subscription topic
        device_id = self._subscriptions.get(topic)
        if not device_id:
            # Try prefix match for command topics
            for sub_topic, dev_id in self._subscriptions.items():
                if topic.startswith(sub_topic.rstrip("#").rstrip("+")):
                    device_id = dev_id
                    break

        if device_id:
            device = self._devices.get(device_id)
            if device:
                await self._process_command(device, topic, payload)

        await event_bus.emit("protocol_event", {
            "protocol": "mqtt",
            "direction": "received",
            "topic": topic,
            "payload": payload,
            "device_id": device_id,
            "timestamp": None,
        })

    async def _process_command(self, device: dict[str, Any], topic: str, payload: str):
        """Process incoming MQTT command for a device."""
        try:
            # Try JSON payload
            try:
                data = json.loads(payload)
            except (json.JSONDecodeError, ValueError):
                data = {"state": payload}

            # Tasmota command topics
            if topic.startswith("cmnd/"):
                if topic.endswith("/POWER"):
                    state = {"state": "ON" if payload.upper() in ("ON", "1", "TOGGLE") else "OFF"}
                    if payload.upper() == "TOGGLE":
                        await self.device_manager.execute_command(device["id"], "toggle", {}, source="mqtt_command")
                    else:
                        await self.device_manager.set_state(device["id"], state, source="mqtt_command")
                return

            # Shelly command topics
            if "/command" in topic:
                state = {"state": "ON" if payload.lower() in ("on", "1") else "OFF"}
                await self.device_manager.set_state(device["id"], state, source="mqtt_command")
                return

            # Generic MQTT: treat as state update
            if isinstance(data, dict):
                await self.device_manager.set_state(device["id"], data, source="mqtt_command")

        except Exception:
            logger.exception("Error processing MQTT command on %s", topic)

    async def register_device(self, device: dict[str, Any]):
        self._devices[device["id"]] = device
        config = device.get("protocol_config", {})
        protocol = device.get("protocol", "mqtt")

        topics_to_subscribe = []
        topics_to_publish = []

        if protocol == "mqtt":
            # Generic MQTT or Tasmota/Shelly based on config
            scheme = config.get("topic_scheme", "generic")

            if scheme == "tasmota":
                device_name = config.get("device_name", device["name"].replace(" ", "_"))
                topics_to_subscribe.append(f"cmnd/{device_name}/#")
                # Publish initial state
                topics_to_publish.append((f"stat/{device_name}/POWER", device["state"].get("state", "OFF")))
            elif scheme == "shelly":
                device_name = config.get("device_name", device["name"].replace(" ", "_"))
                topics_to_subscribe.append(f"shellies/{device_name}/relay/0/command")
                topics_to_publish.append((f"shellies/{device_name}/relay/0", device["state"].get("state", "OFF")))
            else:
                base = config.get("base_topic", f"sds/{device['id']}")
                topics_to_subscribe.append(f"{base}/set")
                topics_to_publish.append((base, json.dumps(device["state"])))

        for topic in topics_to_subscribe:
            self._subscriptions[topic] = device["id"]
            if self._client:
                try:
                    await self._client.subscribe(topic)
                except Exception:
                    logger.exception("Failed to subscribe to %s", topic)

        # Publish initial state as retained
        for topic, payload in topics_to_publish:
            await self._publish(topic, payload, retain=True)

    async def unregister_device(self, device: dict[str, Any]):
        device_id = device["id"]
        self._devices.pop(device_id, None)
        topics_to_remove = [t for t, d in self._subscriptions.items() if d == device_id]
        for topic in topics_to_remove:
            self._subscriptions.pop(topic, None)
            if self._client:
                try:
                    await self._client.unsubscribe(topic)
                except Exception:
                    pass

    async def publish_state(self, device: dict[str, Any]):
        config = device.get("protocol_config", {})
        protocol = device.get("protocol", "mqtt")
        state = device["state"]

        if protocol == "mqtt":
            scheme = config.get("topic_scheme", "generic")
            if scheme == "tasmota":
                device_name = config.get("device_name", device["name"].replace(" ", "_"))
                await self._publish(f"stat/{device_name}/POWER", state.get("state", "OFF"), retain=True)
                await self._publish(f"tele/{device_name}/STATE", json.dumps(state))
            elif scheme == "shelly":
                device_name = config.get("device_name", device["name"].replace(" ", "_"))
                val = "on" if state.get("state") == "ON" else "off"
                await self._publish(f"shellies/{device_name}/relay/0", val, retain=True)
            else:
                base = config.get("base_topic", f"sds/{device['id']}")
                await self._publish(base, json.dumps(state), retain=True)

    async def _publish(self, topic: str, payload: str, retain: bool = False):
        if self._client:
            try:
                await self._client.publish(topic, payload, retain=retain)
                self.stats["messages_sent"] += 1
                await event_bus.emit("protocol_event", {
                    "protocol": "mqtt",
                    "direction": "sent",
                    "topic": topic,
                    "payload": payload,
                    "device_id": None,
                })
            except Exception:
                logger.exception("Failed to publish to %s", topic)
                self.stats["errors"] += 1

    def get_client(self) -> aiomqtt.Client | None:
        return self._client

    def get_subscriptions(self) -> dict[str, str]:
        return dict(self._subscriptions)
