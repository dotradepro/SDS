"""Pydantic models for devices."""

from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


def gen_id() -> str:
    return str(uuid.uuid4())


class DeviceCreate(BaseModel):
    name: str
    type: str
    protocol: str
    protocol_config: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    room: str = ""
    icon: str = ""
    auto_report_interval: int = 60


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    protocol_config: Optional[dict[str, Any]] = None
    capabilities: Optional[list[str]] = None
    room: Optional[str] = None
    icon: Optional[str] = None
    auto_report_interval: Optional[int] = None


class DeviceResponse(BaseModel):
    id: str
    name: str
    type: str
    protocol: str
    protocol_config: dict[str, Any]
    state: dict[str, Any]
    capabilities: list[str]
    room: str
    icon: str
    created_at: datetime
    updated_at: datetime
    is_online: bool
    auto_report_interval: int

    model_config = {"from_attributes": True}


class DeviceStateUpdate(BaseModel):
    state: dict[str, Any]


class DeviceCommand(BaseModel):
    command: str
    params: dict[str, Any] = Field(default_factory=dict)


# Device templates per type
DEVICE_TEMPLATES: dict[str, dict[str, Any]] = {
    "light": {
        "default_state": {
            "state": "OFF",
            "brightness": 254,
            "color_temp": 300,
            "color": {"r": 255, "g": 255, "b": 255},
            "color_mode": "color_temp",
        },
        "capabilities": ["brightness", "color_temp", "color"],
        "icon": "lightbulb",
        "supported_protocols": ["zigbee2mqtt", "mqtt", "http_hue", "http_lifx", "tuya", "miio"],
        "commands": ["turn_on", "turn_off", "toggle", "set_brightness", "set_color_temp", "set_color"],
    },
    "switch": {
        "default_state": {
            "state": "OFF",
            "power_consumption": 0.0,
            "voltage": 220.0,
            "current": 0.0,
        },
        "capabilities": ["power_monitoring"],
        "icon": "power",
        "supported_protocols": ["zigbee2mqtt", "mqtt", "http", "tuya", "miio"],
        "commands": ["turn_on", "turn_off", "toggle"],
    },
    "climate": {
        "default_state": {
            "current_temperature": 20.5,
            "target_temperature": 22.0,
            "hvac_mode": "off",
            "fan_mode": "auto",
            "preset": "none",
            "humidity": 45,
        },
        "capabilities": ["temperature", "humidity", "fan_mode", "preset"],
        "icon": "thermostat",
        "supported_protocols": ["zigbee2mqtt", "mqtt", "http"],
        "commands": ["set_temperature", "set_hvac_mode", "set_fan_mode", "set_preset"],
    },
    "sensor": {
        "default_state": {
            "temperature": 22.0,
            "humidity": 45,
            "battery": 100,
        },
        "capabilities": ["temperature", "humidity", "battery"],
        "icon": "sensor",
        "supported_protocols": ["zigbee2mqtt", "mqtt", "coap"],
        "commands": [],
        "subtypes": {
            "temperature_humidity": {
                "default_state": {"temperature": 22.0, "humidity": 45, "battery": 100},
                "capabilities": ["temperature", "humidity", "battery"],
            },
            "motion": {
                "default_state": {"occupancy": False, "battery": 100, "illuminance": 0},
                "capabilities": ["occupancy", "battery", "illuminance"],
            },
            "door_window": {
                "default_state": {"contact": True, "battery": 100, "tamper": False},
                "capabilities": ["contact", "battery"],
            },
            "smoke": {
                "default_state": {"smoke": False, "battery": 100, "test": False},
                "capabilities": ["smoke", "battery"],
            },
            "water_leak": {
                "default_state": {"water_leak": False, "battery": 100},
                "capabilities": ["water_leak", "battery"],
            },
            "illuminance": {
                "default_state": {"illuminance": 0, "illuminance_lux": 0, "battery": 100},
                "capabilities": ["illuminance", "battery"],
            },
        },
    },
    "media_player": {
        "default_state": {
            "state": "idle",
            "volume_level": 0.5,
            "is_volume_muted": False,
            "media_title": "",
            "media_artist": "",
            "media_content_type": "music",
            "source": "",
        },
        "capabilities": ["volume", "media_control", "source"],
        "icon": "media_player",
        "supported_protocols": ["http", "ha_websocket"],
        "commands": ["play", "pause", "stop", "next_track", "prev_track", "volume_up", "volume_down", "mute", "set_volume"],
    },
    "lock": {
        "default_state": {
            "state": "locked",
            "battery": 85,
            "door_state": "closed",
        },
        "capabilities": ["battery"],
        "icon": "lock",
        "supported_protocols": ["zigbee2mqtt", "mqtt", "http"],
        "commands": ["lock", "unlock"],
    },
    "cover": {
        "default_state": {
            "state": "closed",
            "position": 0,
            "tilt_position": 0,
        },
        "capabilities": ["position", "tilt"],
        "icon": "cover",
        "supported_protocols": ["zigbee2mqtt", "mqtt"],
        "commands": ["open_cover", "close_cover", "stop_cover", "set_position", "set_tilt_position"],
    },
    "camera": {
        "default_state": {
            "state": "idle",
            "motion_detected": False,
        },
        "capabilities": ["snapshot", "motion_detection"],
        "icon": "camera",
        "supported_protocols": ["http"],
        "commands": [],
    },
    "vacuum": {
        "default_state": {
            "state": "docked",
            "battery": 100,
            "fan_speed": "standard",
            "cleaned_area": 0.0,
            "cleaning_time": 0,
        },
        "capabilities": ["battery", "fan_speed"],
        "icon": "vacuum",
        "supported_protocols": ["miio", "mqtt"],
        "commands": ["start", "pause", "return_to_base", "set_fan_speed", "locate"],
    },
    "speaker": {
        "default_state": {
            "state": "idle",
            "volume": 50,
            "do_not_disturb": False,
        },
        "capabilities": ["volume"],
        "icon": "speaker",
        "supported_protocols": ["http", "ha_websocket"],
        "commands": ["set_volume", "mute"],
    },
}
