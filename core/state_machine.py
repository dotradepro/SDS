"""State transition logic for devices."""

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)


def apply_state_change(current_state: dict[str, Any], changes: dict[str, Any], device_type: str) -> dict[str, Any]:
    """Apply state changes with validation based on device type."""
    new_state = copy.deepcopy(current_state)
    new_state.update(changes)

    # Clamp numeric values based on device type
    if device_type == "light":
        if "brightness" in new_state:
            new_state["brightness"] = max(0, min(254, int(new_state["brightness"])))
        if "color_temp" in new_state:
            new_state["color_temp"] = max(153, min(500, int(new_state["color_temp"])))
        if "color" in new_state and isinstance(new_state["color"], dict):
            for k in ("r", "g", "b"):
                if k in new_state["color"]:
                    new_state["color"][k] = max(0, min(255, int(new_state["color"][k])))

    elif device_type == "climate":
        if "target_temperature" in new_state:
            new_state["target_temperature"] = max(5.0, min(35.0, float(new_state["target_temperature"])))
        if "humidity" in new_state:
            new_state["humidity"] = max(0, min(100, int(new_state["humidity"])))

    elif device_type == "cover":
        if "position" in new_state:
            new_state["position"] = max(0, min(100, int(new_state["position"])))
        if "tilt_position" in new_state:
            new_state["tilt_position"] = max(0, min(100, int(new_state["tilt_position"])))

    elif device_type == "media_player":
        if "volume_level" in new_state:
            new_state["volume_level"] = max(0.0, min(1.0, float(new_state["volume_level"])))

    elif device_type == "vacuum":
        if "battery" in new_state:
            new_state["battery"] = max(0, min(100, int(new_state["battery"])))

    return new_state


def execute_command(current_state: dict[str, Any], command: str, params: dict[str, Any], device_type: str) -> dict[str, Any]:
    """Execute a command and return the new state."""
    changes: dict[str, Any] = {}

    if command == "turn_on":
        changes["state"] = "ON"
        changes.update(params)
    elif command == "turn_off":
        changes["state"] = "OFF"
    elif command == "toggle":
        changes["state"] = "OFF" if current_state.get("state") == "ON" else "ON"
    elif command == "set_brightness":
        changes["brightness"] = params.get("brightness", 127)
        changes["state"] = "ON"
    elif command == "set_color_temp":
        changes["color_temp"] = params.get("color_temp", 300)
        changes["state"] = "ON"
    elif command == "set_color":
        changes["color"] = params.get("color", {"r": 255, "g": 255, "b": 255})
        changes["state"] = "ON"
        changes["color_mode"] = "color"
    elif command == "set_temperature":
        changes["target_temperature"] = params.get("temperature", 22.0)
    elif command == "set_hvac_mode":
        changes["hvac_mode"] = params.get("hvac_mode", "auto")
    elif command == "set_fan_mode":
        changes["fan_mode"] = params.get("fan_mode", "auto")
    elif command == "set_preset":
        changes["preset"] = params.get("preset", "none")
    elif command == "lock":
        changes["state"] = "locked"
    elif command == "unlock":
        changes["state"] = "unlocked"
    elif command == "open_cover":
        changes["state"] = "open"
        changes["position"] = 100
    elif command == "close_cover":
        changes["state"] = "closed"
        changes["position"] = 0
    elif command == "stop_cover":
        changes["state"] = "stopped"
    elif command == "set_position":
        pos = params.get("position", 50)
        changes["position"] = pos
        changes["state"] = "open" if pos > 0 else "closed"
    elif command == "play":
        changes["state"] = "playing"
    elif command == "pause":
        changes["state"] = "paused"
    elif command == "stop":
        changes["state"] = "idle"
    elif command == "set_volume":
        changes["volume_level"] = params.get("volume_level", 0.5)
    elif command == "volume_up":
        vol = current_state.get("volume_level", 0.5)
        changes["volume_level"] = min(1.0, vol + 0.1)
    elif command == "volume_down":
        vol = current_state.get("volume_level", 0.5)
        changes["volume_level"] = max(0.0, vol - 0.1)
    elif command == "mute":
        changes["is_volume_muted"] = not current_state.get("is_volume_muted", False)
    elif command == "start":
        changes["state"] = "cleaning"
    elif command == "return_to_base":
        changes["state"] = "returning"
    elif command == "set_fan_speed":
        changes["fan_speed"] = params.get("fan_speed", "standard")
    elif command == "locate":
        pass  # No state change, just triggers event
    else:
        # Generic: merge params into state
        changes.update(params)

    return apply_state_change(current_state, changes, device_type)
