"""mDNS/DNS-SD handler using zeroconf."""

import logging
import socket
from typing import Any

from zeroconf import Zeroconf, ServiceInfo
from zeroconf.asyncio import AsyncZeroconf

from protocols.base import ProtocolHandler
from core.event_bus import event_bus

logger = logging.getLogger(__name__)

# Service type mapping by device protocol/type
SERVICE_TYPES = {
    "http_hue": "_hue._tcp.local.",
    "shelly": "_shelly._tcp.local.",
    "miio": "_miio._udp.local.",
    "coap": "_coap._udp.local.",
    "http": "_http._tcp.local.",
    "http_lifx": "_lifx._tcp.local.",
    "zigbee2mqtt": None,  # Z2M devices don't announce via mDNS
    "mqtt": None,
    "ha_websocket": "_home-assistant._tcp.local.",
}

DEVICE_TYPE_SERVICE = {
    "speaker": "_googlecast._tcp.local.",
}


class MDNSHandler(ProtocolHandler):
    name = "mdns"

    def __init__(self, config: dict[str, Any], device_manager: Any):
        super().__init__(config, device_manager)
        self._zeroconf: AsyncZeroconf | None = None
        self._registered_services: dict[str, ServiceInfo] = {}  # device_id -> ServiceInfo
        self.enabled = config.get("enabled", True)

    async def start(self):
        if not self.enabled:
            self.status = "disabled"
            return

        try:
            self._zeroconf = AsyncZeroconf()
            self.is_running = True
            self.status = "connected"
            self.status_message = "mDNS responder active"
            logger.info("mDNS handler started")
            await event_bus.emit("protocol_status", {
                "protocol": "mdns",
                "status": "connected",
                "message": self.status_message,
            })
        except Exception as e:
            self.status = "error"
            self.status_message = str(e)
            logger.exception("Failed to start mDNS handler")

    async def stop(self):
        if self._zeroconf:
            # Unregister all services
            for service_info in self._registered_services.values():
                try:
                    await self._zeroconf.async_unregister_service(service_info)
                except Exception:
                    pass
            self._registered_services.clear()
            await self._zeroconf.async_close()
            self._zeroconf = None
        self.is_running = False
        self.status = "stopped"

    async def register_device(self, device: dict[str, Any]):
        if not self._zeroconf or not self.enabled:
            return

        service_type = self._get_service_type(device)
        if not service_type:
            return

        config = device.get("protocol_config", {})
        device_name = device["name"].replace(" ", "-")
        service_name = f"{device_name}.{service_type}"

        try:
            ip_addr = socket.inet_aton(self._get_local_ip())
        except Exception:
            ip_addr = socket.inet_aton("127.0.0.1")

        port = config.get("port", 80)
        if device.get("protocol") == "http_hue":
            port = 7000
        elif device.get("protocol") == "miio":
            port = 54321

        properties = {
            "id": device["id"],
            "model": config.get("model_id", "SDS_Virtual"),
            "fw": "1.0.0",
        }

        try:
            info = ServiceInfo(
                service_type,
                service_name,
                addresses=[ip_addr],
                port=port,
                properties=properties,
            )
            await self._zeroconf.async_register_service(info)
            self._registered_services[device["id"]] = info
            self.stats["messages_sent"] += 1
            logger.info("mDNS: registered %s as %s", device["name"], service_type)
        except Exception:
            logger.exception("mDNS: failed to register %s", device["name"])
            self.stats["errors"] += 1

    async def unregister_device(self, device: dict[str, Any]):
        if not self._zeroconf:
            return

        info = self._registered_services.pop(device["id"], None)
        if info:
            try:
                await self._zeroconf.async_unregister_service(info)
            except Exception:
                pass

    async def publish_state(self, device: dict[str, Any]):
        # mDNS doesn't publish state, only discovery
        pass

    def _get_service_type(self, device: dict) -> str | None:
        # Check device type first
        dtype = device.get("type", "")
        if dtype in DEVICE_TYPE_SERVICE:
            return DEVICE_TYPE_SERVICE[dtype]

        # Then protocol
        protocol = device.get("protocol", "")
        return SERVICE_TYPES.get(protocol)

    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
