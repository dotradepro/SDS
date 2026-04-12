"""REST API endpoints for scenarios."""

from fastapi import APIRouter, HTTPException
from typing import Any

from core.scheduler import scheduler
from models.scenario import ScenarioCreate, ScenarioUpdate

router = APIRouter(prefix="/api/v1", tags=["scenarios"])


@router.get("/scenarios")
async def list_scenarios() -> list[dict[str, Any]]:
    return await scheduler.get_all_scenarios()


@router.post("/scenarios")
async def create_scenario(data: ScenarioCreate) -> dict[str, Any]:
    return await scheduler.create_scenario(data)


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str) -> dict[str, Any]:
    scenario = await scheduler.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@router.put("/scenarios/{scenario_id}")
async def update_scenario(scenario_id: str, data: ScenarioUpdate) -> dict[str, Any]:
    scenario = await scheduler.update_scenario(scenario_id, data)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: str):
    ok = await scheduler.delete_scenario(scenario_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"status": "deleted"}


@router.post("/scenarios/{scenario_id}/start")
async def start_scenario(scenario_id: str):
    ok = await scheduler.start_scenario(scenario_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"status": "started"}


@router.post("/scenarios/{scenario_id}/stop")
async def stop_scenario(scenario_id: str):
    await scheduler.stop_scenario(scenario_id)
    return {"status": "stopped"}
