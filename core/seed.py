"""Demo device seeding for fresh SDS installs.

When SDS starts against an empty database and ``SDS_SEED_DEMO`` is not
explicitly disabled, we create one device per ``(type × protocol)`` pair
from ``DEVICE_TEMPLATES``. That gives new users a fully populated UI and
a realistic corpus for Selena (or any other client) to discover over
every supported protocol, without a manual POST /devices dance.

Opt out:

    SDS_SEED_DEMO=false

Idempotent — once any devices exist in the DB, the seeder is a no-op.
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from models.device import DEVICE_TEMPLATES, DeviceCreate

if TYPE_CHECKING:
    from core.device_manager import DeviceManager
    from protocols.mdns_handler import MDNSHandler

logger = logging.getLogger(__name__)

# Human-readable labels; falls back to ``type.title()`` for unknown types.
_TYPE_LABELS = {
    "light": "Light",
    "switch": "Switch",
    "climate": "Thermostat",
    "sensor": "Sensor",
    "media_player": "Media Player",
    "lock": "Lock",
    "cover": "Blind",
    "camera": "Camera",
    "vacuum": "Vacuum",
    "speaker": "Speaker",
}

_DISABLED = {"false", "0", "no", "off"}


def build_demo_device_specs() -> list[DeviceCreate]:
    """Return one ``DeviceCreate`` per ``(type, supported_protocol)`` pair.

    Pulled live from ``DEVICE_TEMPLATES`` so new types/protocols added to
    ``models/device.py`` are picked up automatically on the next restart.
    """
    specs: list[DeviceCreate] = []
    for typ, tpl in DEVICE_TEMPLATES.items():
        label = _TYPE_LABELS.get(typ, typ.replace("_", " ").title())
        for proto in tpl.get("supported_protocols", []):
            specs.append(
                DeviceCreate(
                    name=f"{label} via {proto}",
                    type=typ,
                    protocol=proto,
                    room=f"{label}s",
                )
            )
    return specs


async def seed_demo_if_empty(
    device_manager: "DeviceManager",
    mdns_handler: "MDNSHandler | None" = None,
) -> int:
    """Create the demo device set when the DB is empty. Returns count."""
    flag = os.environ.get("SDS_SEED_DEMO", "true").strip().lower()
    if flag in _DISABLED:
        logger.info("Demo seeding disabled (SDS_SEED_DEMO=%s)", flag)
        return 0

    existing = await device_manager.get_all_devices()
    if existing:
        return 0

    specs = build_demo_device_specs()
    for spec in specs:
        try:
            device = await device_manager.create_device(spec)
        except Exception:
            logger.exception("Failed to seed %s/%s", spec.type, spec.protocol)
            continue
        if mdns_handler is not None:
            try:
                await mdns_handler.register_device(device)
            except Exception:
                logger.exception("mDNS register failed for %s", device["id"])

    logger.info(
        "Seeded %d demo devices (SDS_SEED_DEMO=%s, DB was empty)",
        len(specs),
        flag,
    )
    return len(specs)
