"""SDS - Smart Device Simulator: FastAPI application entry point."""

import asyncio
import logging
import os

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from core.database import init_db
from core.device_manager import device_manager
from core.scheduler import scheduler
from core.event_bus import event_bus
from core.seed import seed_demo_if_empty

from protocols.mqtt_handler import MQTTHandler
from protocols.zigbee2mqtt_handler import Zigbee2MQTTHandler
from protocols.http_handler import HTTPHandler, router as http_protocol_router
from protocols.websocket_ha_handler import HomeAssistantWSHandler
from protocols.miio_handler import MiioHandler
from protocols.mdns_handler import MDNSHandler

from api.devices import router as devices_router
from api.events import router as events_router
from api.scenarios import router as scenarios_router
from api.imports import router as imports_router
from api.websocket import router as ws_router, setup_event_forwarding

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sds")

# Load config
config_path = os.environ.get("SDS_CONFIG", "config.yaml")
try:
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
except FileNotFoundError:
    logger.warning("Config file %s not found, using defaults", config_path)
    config = {}

# Protocol handler instances
protocol_handlers: dict[str, object] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)

    # Init database
    await init_db()
    logger.info("Database initialized")

    # Create protocol handlers
    mqtt_config = config.get("mqtt", {})
    mqtt_config.setdefault("broker_host", os.environ.get("MQTT_BROKER", "mosquitto"))
    mqtt_config.setdefault("broker_port", int(os.environ.get("MQTT_PORT", "1883")))

    mqtt_handler = MQTTHandler(mqtt_config, device_manager)
    z2m_handler = Zigbee2MQTTHandler({**mqtt_config, **config.get("zigbee2mqtt", {})}, device_manager)
    http_handler = HTTPHandler(config.get("http", {}), device_manager)
    ha_ws_handler = HomeAssistantWSHandler(config.get("ha_websocket", {}), device_manager)
    miio_handler = MiioHandler(config.get("miio", {}), device_manager)
    mdns_handler = MDNSHandler(config.get("mdns", {}), device_manager)

    protocol_handlers["mqtt"] = mqtt_handler
    protocol_handlers["zigbee2mqtt"] = z2m_handler
    protocol_handlers["http"] = http_handler
    protocol_handlers["http_hue"] = http_handler
    protocol_handlers["http_lifx"] = http_handler
    protocol_handlers["ha_websocket"] = ha_ws_handler
    protocol_handlers["miio"] = miio_handler
    protocol_handlers["mdns"] = mdns_handler

    device_manager.set_protocol_handlers(protocol_handlers)
    scheduler.set_device_manager(device_manager)

    # Setup WebSocket event forwarding
    setup_event_forwarding()

    # Start protocols
    handlers_to_start = [mqtt_handler, z2m_handler, http_handler, ha_ws_handler, miio_handler, mdns_handler]
    for handler in handlers_to_start:
        try:
            await handler.start()
            logger.info("Protocol %s started", handler.name)
        except Exception:
            logger.exception("Failed to start protocol %s", handler.name)

    # Load devices from DB and register with protocols
    await device_manager.load_from_db()

    # Re-register all loaded devices with their protocol handlers
    for device in await device_manager.get_all_devices():
        handler = protocol_handlers.get(device["protocol"])
        if handler and hasattr(handler, "register_device"):
            try:
                await handler.register_device(device)
            except Exception:
                logger.exception("Failed to re-register device %s", device["id"])

    # Also register with mDNS for discovery
    for device in await device_manager.get_all_devices():
        try:
            await mdns_handler.register_device(device)
        except Exception:
            pass

    # Seed one demo device per (type × protocol) on fresh installs.
    # Controlled by SDS_SEED_DEMO env var (default "true"; set "false" to skip).
    await seed_demo_if_empty(device_manager, mdns_handler)

    # Load and start scenarios
    await scheduler.load_from_db()

    logger.info("SDS Backend started successfully")

    yield

    # Shutdown
    logger.info("Shutting down SDS Backend...")
    for handler in handlers_to_start:
        try:
            await handler.stop()
        except Exception:
            pass


app = FastAPI(
    title="Smart Device Simulator",
    description="SDS - Simulates smart home devices for testing Selena voice assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(devices_router)
app.include_router(events_router)
app.include_router(scenarios_router)
app.include_router(imports_router)
app.include_router(ws_router)

# HTTP protocol emulation routes (Hue, LIFX, generic)
app.include_router(http_protocol_router)


@app.get("/api/v1/health")
async def health():
    statuses = {}
    for name, handler in protocol_handlers.items():
        if name in ("http_hue", "http_lifx"):
            continue  # same as http
        if hasattr(handler, "get_status"):
            statuses[name] = handler.get_status()
    return {"status": "ok", "protocols": statuses}


@app.get("/api/v1/protocols")
async def list_protocols():
    result = []
    seen = set()
    for name, handler in protocol_handlers.items():
        if name in seen or name in ("http_hue", "http_lifx"):
            continue
        seen.add(name)
        if hasattr(handler, "get_status"):
            result.append(handler.get_status())
    return result


@app.post("/api/v1/protocols/{protocol_name}/restart")
async def restart_protocol(protocol_name: str):
    handler = protocol_handlers.get(protocol_name)
    if not handler:
        return {"error": "Protocol not found"}
    await handler.stop()
    await handler.start()
    return {"status": "restarted"}


# Z2M Groups API
@app.get("/api/v1/groups")
async def list_z2m_groups():
    handler = protocol_handlers.get("zigbee2mqtt")
    if handler and hasattr(handler, "get_groups"):
        return handler.get_groups()
    return []


@app.post("/api/v1/groups")
async def create_z2m_group(data: dict):
    handler = protocol_handlers.get("zigbee2mqtt")
    if not handler or not hasattr(handler, "create_group"):
        return {"error": "Zigbee2MQTT not available"}
    group = await handler.create_group(data.get("friendly_name", "new_group"))
    return group


@app.delete("/api/v1/groups/{group_id}")
async def delete_z2m_group(group_id: int):
    handler = protocol_handlers.get("zigbee2mqtt")
    if handler and hasattr(handler, "delete_group"):
        await handler.delete_group(group_id)
    return {"status": "deleted"}


@app.post("/api/v1/groups/{group_id}/members")
async def add_z2m_group_member(group_id: int, data: dict):
    handler = protocol_handlers.get("zigbee2mqtt")
    if handler and hasattr(handler, "add_group_member"):
        await handler.add_group_member(group_id, data.get("device_id", ""), data.get("endpoint", 1))
    return {"status": "added"}


@app.delete("/api/v1/groups/{group_id}/members/{device_id}")
async def remove_z2m_group_member(group_id: int, device_id: str):
    handler = protocol_handlers.get("zigbee2mqtt")
    if handler and hasattr(handler, "remove_group_member"):
        await handler.remove_group_member(group_id, device_id)
    return {"status": "removed"}
