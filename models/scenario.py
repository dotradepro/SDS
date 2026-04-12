"""Pydantic models for scenarios."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ScenarioStep(BaseModel):
    delay_seconds: float = 0
    device_id: str
    action: str
    state: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class ScenarioTrigger(BaseModel):
    type: str  # time_interval, cron, time_once, manual, device_trigger
    interval_seconds: Optional[float] = None
    cron: Optional[str] = None
    delay_seconds: Optional[float] = None
    device_id: Optional[str] = None
    condition: Optional[dict[str, Any]] = None


class ScenarioCreate(BaseModel):
    name: str
    description: str = ""
    triggers: list[ScenarioTrigger] = Field(default_factory=list)
    steps: list[ScenarioStep] = Field(default_factory=list)


class ScenarioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    triggers: Optional[list[ScenarioTrigger]] = None
    steps: Optional[list[ScenarioStep]] = None


class ScenarioResponse(BaseModel):
    id: str
    name: str
    description: str
    is_active: bool
    triggers: list[ScenarioTrigger]
    steps: list[ScenarioStep]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
