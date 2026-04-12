"""Abstract base class for protocol handlers."""

import abc
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProtocolHandler(abc.ABC):
    """Base class for all protocol handlers."""

    name: str = "base"

    def __init__(self, config: dict[str, Any], device_manager: Any):
        self.config = config
        self.device_manager = device_manager
        self.is_running = False
        self.status = "stopped"
        self.status_message = ""
        self.stats = {"messages_sent": 0, "messages_received": 0, "errors": 0}

    @abc.abstractmethod
    async def start(self):
        """Start the protocol handler."""
        pass

    @abc.abstractmethod
    async def stop(self):
        """Stop the protocol handler."""
        pass

    @abc.abstractmethod
    async def register_device(self, device: dict[str, Any]):
        """Register a device with this protocol."""
        pass

    @abc.abstractmethod
    async def unregister_device(self, device: dict[str, Any]):
        """Unregister a device from this protocol."""
        pass

    @abc.abstractmethod
    async def publish_state(self, device: dict[str, Any]):
        """Publish device state via this protocol."""
        pass

    def get_status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "is_running": self.is_running,
            "status": self.status,
            "message": self.status_message,
            "stats": self.stats,
        }
