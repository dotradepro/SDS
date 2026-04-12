"""Pydantic models for events."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class EventCreate(BaseModel):
    device_id: Optional[str] = None
    device_name: str = ""
    protocol: str = ""
    direction: str = ""  # sent / received
    event_type: str = ""
    topic: str = ""
    payload: str = ""


class EventResponse(BaseModel):
    id: int
    device_id: Optional[str]
    device_name: str
    protocol: str
    direction: str
    event_type: str
    topic: str
    payload: str
    timestamp: datetime

    model_config = {"from_attributes": True}
