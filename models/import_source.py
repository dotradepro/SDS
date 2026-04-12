"""Pydantic models for the import subsystem."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class AuthField(BaseModel):
    name: str
    label: str
    type: str = "text"  # text, password, url, number
    placeholder: str = ""
    required: bool = True
    default_value: str = ""


class ImportSourceInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    category: str  # local / cloud
    auth_type: str  # oauth2, button_press, psk, credentials
    auth_fields: list[AuthField]
    what_imports: str  # human-readable list of what gets imported


class ImportConnectRequest(BaseModel):
    source_id: str
    auth_data: dict[str, str] = Field(default_factory=dict)


class DiscoveredDevice(BaseModel):
    temp_id: str
    name: str
    type: str
    room: str
    manufacturer: str
    model: str
    protocol: str
    source_entity_id: str


class ImportConnectResponse(BaseModel):
    session_id: str
    status: str
    system_info: dict[str, Any]
    discovered_devices: list[DiscoveredDevice]


class ImportExecuteRequest(BaseModel):
    session_id: str
    selected_ids: list[str]


class ImportExecuteResponse(BaseModel):
    created_devices: list[str]
    count: int


# Source definitions
IMPORT_SOURCES: list[dict[str, Any]] = [
    {
        "id": "home_assistant",
        "name": "Home Assistant",
        "description": "Локальний сервер автоматизації",
        "icon": "home_assistant",
        "category": "local",
        "auth_type": "oauth2",
        "auth_fields": [
            {"name": "url", "label": "URL сервера", "type": "url", "placeholder": "http://homeassistant.local:8123", "required": True, "default_value": "http://homeassistant.local:8123"},
        ],
        "what_imports": "Пристрої, кімнати, автоматизації, сцени",
    },
    {
        "id": "philips_hue",
        "name": "Philips Hue",
        "description": "Hue Bridge в локальній мережі",
        "icon": "philips_hue",
        "category": "local",
        "auth_type": "button_press",
        "auth_fields": [],
        "what_imports": "Лампи, групи, сцени",
    },
    {
        "id": "ikea_tradfri",
        "name": "IKEA TRÅDFRI",
        "description": "IKEA шлюз розумного дому",
        "icon": "ikea",
        "category": "local",
        "auth_type": "psk",
        "auth_fields": [],
        "what_imports": "Лампи, групи, жалюзі",
    },
    {
        "id": "mqtt_broker",
        "name": "MQTT Broker",
        "description": "Імпорт топіків як пристроїв",
        "icon": "mqtt",
        "category": "local",
        "auth_type": "credentials",
        "auth_fields": [
            {"name": "host", "label": "Хост", "type": "text", "placeholder": "192.168.1.100", "required": True, "default_value": "localhost"},
            {"name": "port", "label": "Порт", "type": "text", "placeholder": "1883", "required": True, "default_value": "1883"},
            {"name": "username", "label": "Логін", "type": "text", "placeholder": "mqtt_user", "required": False, "default_value": ""},
            {"name": "password", "label": "Пароль", "type": "password", "placeholder": "", "required": False, "default_value": ""},
        ],
        "what_imports": "Топіки як пристрої (Tasmota, Shelly, Sonoff)",
    },
    {
        "id": "tuya",
        "name": "Tuya / SmartLife",
        "description": "Хмарний сервіс Tuya",
        "icon": "tuya",
        "category": "cloud",
        "auth_type": "oauth2",
        "auth_fields": [],
        "what_imports": "Пристрої, кімнати, DP коди команд",
    },
    {
        "id": "smartthings",
        "name": "Samsung SmartThings",
        "description": "Хмарна платформа Samsung",
        "icon": "smartthings",
        "category": "cloud",
        "auth_type": "oauth2",
        "auth_fields": [],
        "what_imports": "Пристрої, кімнати",
    },
]
