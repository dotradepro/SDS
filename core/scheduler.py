"""Scenario scheduler: runs automated device state changes."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import async_session, ScenarioRow
from core.event_bus import event_bus
from models.scenario import ScenarioCreate, ScenarioUpdate, ScenarioTrigger, ScenarioStep

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        self._scenarios: dict[str, dict[str, Any]] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._device_manager = None

    def set_device_manager(self, dm):
        self._device_manager = dm

    async def load_from_db(self):
        async with async_session() as session:
            result = await session.execute(select(ScenarioRow))
            rows = result.scalars().all()
            for row in rows:
                scenario = self._row_to_dict(row)
                self._scenarios[row.id] = scenario
                if scenario["is_active"]:
                    await self.start_scenario(row.id)
        logger.info("Loaded %d scenarios from database", len(self._scenarios))

    async def create_scenario(self, data: ScenarioCreate) -> dict[str, Any]:
        from models.device import gen_id
        scenario_id = gen_id()
        now = datetime.now(timezone.utc)

        scenario = {
            "id": scenario_id,
            "name": data.name,
            "description": data.description,
            "is_active": False,
            "triggers": [t.model_dump() for t in data.triggers],
            "steps": [s.model_dump() for s in data.steps],
            "created_at": now,
            "updated_at": now,
        }

        async with async_session() as session:
            row = ScenarioRow(
                id=scenario_id,
                name=data.name,
                description=data.description,
                is_active=False,
                triggers=json.dumps(scenario["triggers"]),
                steps=json.dumps(scenario["steps"]),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.commit()

        self._scenarios[scenario_id] = scenario
        return scenario

    async def get_scenario(self, scenario_id: str) -> Optional[dict[str, Any]]:
        return self._scenarios.get(scenario_id)

    async def get_all_scenarios(self) -> list[dict[str, Any]]:
        return list(self._scenarios.values())

    async def update_scenario(self, scenario_id: str, data: ScenarioUpdate) -> Optional[dict[str, Any]]:
        scenario = self._scenarios.get(scenario_id)
        if not scenario:
            return None

        updates = data.model_dump(exclude_none=True)
        if "triggers" in updates:
            updates["triggers"] = [t if isinstance(t, dict) else t.model_dump() for t in updates["triggers"]]
        if "steps" in updates:
            updates["steps"] = [s if isinstance(s, dict) else s.model_dump() for s in updates["steps"]]

        scenario.update(updates)
        scenario["updated_at"] = datetime.now(timezone.utc)

        async with async_session() as session:
            result = await session.execute(
                select(ScenarioRow).where(ScenarioRow.id == scenario_id)
            )
            row = result.scalar_one_or_none()
            if row:
                row.name = scenario["name"]
                row.description = scenario["description"]
                row.is_active = scenario["is_active"]
                row.triggers = json.dumps(scenario["triggers"])
                row.steps = json.dumps(scenario["steps"])
                row.updated_at = scenario["updated_at"]
                await session.commit()

        return scenario

    async def delete_scenario(self, scenario_id: str) -> bool:
        await self.stop_scenario(scenario_id)
        scenario = self._scenarios.pop(scenario_id, None)
        if not scenario:
            return False

        async with async_session() as session:
            from sqlalchemy import delete
            await session.execute(delete(ScenarioRow).where(ScenarioRow.id == scenario_id))
            await session.commit()
        return True

    async def start_scenario(self, scenario_id: str) -> bool:
        scenario = self._scenarios.get(scenario_id)
        if not scenario:
            return False

        await self.stop_scenario(scenario_id)
        scenario["is_active"] = True

        task = asyncio.create_task(self._run_scenario(scenario))
        self._running_tasks[scenario_id] = task
        logger.info("Started scenario %s", scenario["name"])
        return True

    async def stop_scenario(self, scenario_id: str) -> bool:
        task = self._running_tasks.pop(scenario_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        scenario = self._scenarios.get(scenario_id)
        if scenario:
            scenario["is_active"] = False
        return True

    async def _run_scenario(self, scenario: dict[str, Any]):
        """Execute scenario based on triggers."""
        try:
            triggers = scenario.get("triggers", [])
            if not triggers:
                await self._execute_steps(scenario)
                return

            trigger = triggers[0]  # Use first trigger
            trigger_type = trigger.get("type", "manual")

            if trigger_type == "time_once":
                delay = trigger.get("delay_seconds", 0)
                await asyncio.sleep(delay)
                await self._execute_steps(scenario)

            elif trigger_type == "time_interval":
                interval = trigger.get("interval_seconds", 60)
                while True:
                    await self._execute_steps(scenario)
                    await asyncio.sleep(interval)

            elif trigger_type == "manual":
                await self._execute_steps(scenario)

            else:
                await self._execute_steps(scenario)

        except asyncio.CancelledError:
            logger.info("Scenario %s cancelled", scenario["name"])
        except Exception:
            logger.exception("Error in scenario %s", scenario["name"])

    async def _execute_steps(self, scenario: dict[str, Any]):
        """Execute all steps in a scenario sequentially."""
        if not self._device_manager:
            return

        for step in scenario.get("steps", []):
            delay = step.get("delay_seconds", 0)
            if delay > 0:
                await asyncio.sleep(delay)

            device_id = step.get("device_id")
            action = step.get("action", "set_state")
            state = step.get("state", {})
            params = step.get("params", {})

            if action == "set_state" and state:
                await self._device_manager.set_state(device_id, state, source="scenario")
            elif action == "toggle":
                await self._device_manager.execute_command(device_id, "toggle", {}, source="scenario")
            elif action in ("turn_on", "turn_off"):
                await self._device_manager.execute_command(device_id, action, params, source="scenario")
            else:
                await self._device_manager.execute_command(device_id, action, params, source="scenario")

    def _row_to_dict(self, row: ScenarioRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description or "",
            "is_active": row.is_active,
            "triggers": json.loads(row.triggers) if row.triggers else [],
            "steps": json.loads(row.steps) if row.steps else [],
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }


# Global singleton
scheduler = Scheduler()
