"""Xiaomi Mi Home (miio) protocol handler - UDP port 54321."""

import asyncio
import hashlib
import json
import logging
import struct
import time
from typing import Any

from Crypto.Cipher import AES

from protocols.base import ProtocolHandler
from core.event_bus import event_bus

logger = logging.getLogger(__name__)

MIIO_PORT = 54321
MAGIC = b"\x21\x31"
HELLO_BYTES = bytes.fromhex("21310020ffffffffffffffffffffffffffffffffffffffffffffffffffffffff")


def md5(data: bytes) -> bytes:
    return hashlib.md5(data).digest()


def pad(data: bytes) -> bytes:
    pad_len = 16 - (len(data) % 16)
    return data + bytes([pad_len] * pad_len)


def unpad(data: bytes) -> bytes:
    pad_len = data[-1]
    return data[:-pad_len]


class MiioDevice:
    def __init__(self, device: dict[str, Any]):
        self.device = device
        self.device_id = device["id"]
        config = device.get("protocol_config", {})
        self.token = bytes.fromhex(config.get("token", "0" * 32))
        self.did = int.from_bytes(md5(self.device_id.encode())[:4], "big")
        self.key = md5(self.token)
        self.iv = md5(self.key + self.token)

    def encrypt(self, plaintext: bytes) -> bytes:
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        return cipher.encrypt(pad(plaintext))

    def decrypt(self, ciphertext: bytes) -> bytes:
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        return unpad(cipher.decrypt(ciphertext))

    def build_response(self, request_data: dict, result: Any) -> dict:
        return {"id": request_data.get("id", 0), "result": result}


class MiioHandler(ProtocolHandler):
    name = "miio"

    def __init__(self, config: dict[str, Any], device_manager: Any):
        super().__init__(config, device_manager)
        self._devices: dict[str, MiioDevice] = {}  # device_id -> MiioDevice
        self._device_data: dict[str, dict[str, Any]] = {}
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol_obj: asyncio.DatagramProtocol | None = None
        self.port = config.get("port", MIIO_PORT)
        self._did_to_device: dict[int, str] = {}  # did -> device_id

    async def start(self):
        loop = asyncio.get_event_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: MiioProtocol(self),
            local_addr=("0.0.0.0", self.port),
        )
        self._transport = transport
        self._protocol_obj = protocol
        self.is_running = True
        self.status = "connected"
        self.status_message = f"miio listening on UDP port {self.port}"
        logger.info("miio handler listening on UDP port %d", self.port)
        await event_bus.emit("protocol_status", {
            "protocol": "miio",
            "status": "connected",
            "message": self.status_message,
        })

    async def stop(self):
        self.is_running = False
        if self._transport:
            self._transport.close()
        self.status = "stopped"

    async def register_device(self, device: dict[str, Any]):
        miio_dev = MiioDevice(device)
        self._devices[device["id"]] = miio_dev
        self._device_data[device["id"]] = device
        self._did_to_device[miio_dev.did] = device["id"]

    async def unregister_device(self, device: dict[str, Any]):
        miio_dev = self._devices.pop(device["id"], None)
        self._device_data.pop(device["id"], None)
        if miio_dev:
            self._did_to_device.pop(miio_dev.did, None)

    async def publish_state(self, device: dict[str, Any]):
        self._device_data[device["id"]] = device

    async def handle_packet(self, data: bytes, addr: tuple) -> bytes | None:
        """Process an incoming miio packet and return response bytes."""
        if len(data) < 32:
            return None

        # Check magic
        if data[:2] != MAGIC:
            return None

        # Hello packet
        if data == HELLO_BYTES or (len(data) == 32 and data[4:8] == b"\xff\xff\xff\xff"):
            return self._build_hello_response()

        # Find device by DID in header
        did = struct.unpack(">I", data[8:12])[0]
        device_id = self._did_to_device.get(did)

        if not device_id:
            # Try first registered device
            if self._devices:
                device_id = next(iter(self._devices))
            else:
                return None

        miio_dev = self._devices.get(device_id)
        if not miio_dev:
            return None

        device = self._device_data.get(device_id)
        if not device:
            return None

        self.stats["messages_received"] += 1

        # Decrypt payload
        encrypted_payload = data[32:]
        if not encrypted_payload:
            return self._build_hello_response_for_device(miio_dev)

        try:
            decrypted = miio_dev.decrypt(encrypted_payload)
            request = json.loads(decrypted.decode("utf-8"))
        except Exception:
            logger.warning("miio: failed to decrypt/parse packet from %s", addr)
            self.stats["errors"] += 1
            return None

        await event_bus.emit("protocol_event", {
            "protocol": "miio",
            "direction": "received",
            "topic": f"miio/{device['name']}",
            "payload": json.dumps(request),
            "device_id": device_id,
        })

        # Process command
        result = await self._process_command(device, request)
        response = miio_dev.build_response(request, result)

        # Encrypt response
        response_json = json.dumps(response).encode("utf-8")
        encrypted_response = miio_dev.encrypt(response_json)

        # Build packet
        packet = self._build_packet(miio_dev.did, encrypted_response)
        self.stats["messages_sent"] += 1
        return packet

    async def _process_command(self, device: dict[str, Any], request: dict) -> Any:
        method = request.get("method", "")
        params = request.get("params", [])
        state = device.get("state", {})
        device_type = device.get("type", "")

        # Xiaomi lamp/plug commands
        if method == "get_prop":
            return [state.get(p, None) for p in params]

        elif method == "set_power":
            power = params[0] if params else "on"
            new_state = "ON" if power == "on" else "OFF"
            await self.device_manager.set_state(device["id"], {"state": new_state}, source="miio_command")
            return ["ok"]

        elif method == "set_bright":
            brightness = params[0] if params else 100
            await self.device_manager.set_state(
                device["id"],
                {"brightness": int(brightness * 254 / 100), "state": "ON"},
                source="miio_command",
            )
            return ["ok"]

        elif method == "set_ct_abx":
            ct = params[0] if params else 4000
            await self.device_manager.set_state(
                device["id"],
                {"color_temp": ct, "state": "ON"},
                source="miio_command",
            )
            return ["ok"]

        elif method == "set_rgb":
            rgb = params[0] if params else 16777215
            r = (rgb >> 16) & 0xFF
            g = (rgb >> 8) & 0xFF
            b = rgb & 0xFF
            await self.device_manager.set_state(
                device["id"],
                {"color": {"r": r, "g": g, "b": b}, "color_mode": "color", "state": "ON"},
                source="miio_command",
            )
            return ["ok"]

        # Roborock vacuum commands
        elif method == "get_status":
            robo_state = self._state_to_roborock(state)
            return [robo_state]

        elif method == "app_start":
            await self.device_manager.set_state(device["id"], {"state": "cleaning"}, source="miio_command")
            return ["ok"]

        elif method == "app_pause":
            await self.device_manager.set_state(device["id"], {"state": "paused"}, source="miio_command")
            return ["ok"]

        elif method == "app_stop":
            await self.device_manager.set_state(device["id"], {"state": "docked"}, source="miio_command")
            return ["ok"]

        elif method == "app_charge":
            await self.device_manager.set_state(device["id"], {"state": "returning"}, source="miio_command")
            return ["ok"]

        elif method == "set_custom_mode":
            fan_power = params[0] if params else 101
            fan_map = {38: "quiet", 60: "standard", 75: "turbo", 100: "max", 101: "standard"}
            speed = fan_map.get(fan_power, "standard")
            await self.device_manager.set_state(device["id"], {"fan_speed": speed}, source="miio_command")
            return ["ok"]

        elif method == "find_me":
            await event_bus.emit("protocol_event", {
                "protocol": "miio",
                "direction": "received",
                "topic": f"miio/{device['name']}/find_me",
                "payload": "locate",
                "device_id": device["id"],
            })
            return ["ok"]

        return ["ok"]

    def _state_to_roborock(self, state: dict) -> dict:
        state_map = {
            "docked": 8, "cleaning": 5, "returning": 6,
            "paused": 10, "error": 12, "charging": 1,
        }
        fan_map = {"quiet": 38, "standard": 60, "turbo": 75, "max": 100}
        return {
            "state": state_map.get(state.get("state", "docked"), 8),
            "battery": state.get("battery", 100),
            "clean_time": state.get("cleaning_time", 0),
            "clean_area": int(state.get("cleaned_area", 0) * 1000000),
            "error_code": 0,
            "map_present": 1,
            "in_cleaning": 1 if state.get("state") == "cleaning" else 0,
            "fan_power": fan_map.get(state.get("fan_speed", "standard"), 60),
            "dnd_enabled": 0,
        }

    def _build_hello_response(self) -> bytes:
        # Generic hello response
        ts = int(time.time())
        header = MAGIC
        header += struct.pack(">H", 32)  # length
        header += b"\x00\x00\x00\x00"  # unknown
        header += struct.pack(">I", 0)  # device id
        header += struct.pack(">I", ts)  # timestamp
        header += b"\x00" * 16  # checksum placeholder
        return header

    def _build_hello_response_for_device(self, miio_dev: MiioDevice) -> bytes:
        ts = int(time.time())
        header = MAGIC
        header += struct.pack(">H", 32)
        header += b"\x00\x00\x00\x00"
        header += struct.pack(">I", miio_dev.did)
        header += struct.pack(">I", ts)
        header += miio_dev.token
        return header

    def _build_packet(self, did: int, encrypted_payload: bytes) -> bytes:
        length = 32 + len(encrypted_payload)
        ts = int(time.time())

        header = MAGIC
        header += struct.pack(">H", length)
        header += b"\x00\x00\x00\x00"
        header += struct.pack(">I", did)
        header += struct.pack(">I", ts)

        # Checksum
        checksum_data = header + b"\x00" * 16 + encrypted_payload
        checksum = md5(checksum_data)
        packet = header + checksum + encrypted_payload
        return packet


class MiioProtocol(asyncio.DatagramProtocol):
    def __init__(self, handler: MiioHandler):
        self.handler = handler
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        asyncio.create_task(self._handle(data, addr))

    async def _handle(self, data: bytes, addr: tuple):
        response = await self.handler.handle_packet(data, addr)
        if response and self.transport:
            self.transport.sendto(response, addr)

    def error_received(self, exc):
        logger.warning("miio UDP error: %s", exc)
