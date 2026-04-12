"""REST API endpoints for events."""

from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import select, delete, func
from core.database import async_session, EventRow

router = APIRouter(prefix="/api/v1", tags=["events"])


@router.get("/events")
async def list_events(
    device_id: Optional[str] = None,
    protocol: Optional[str] = None,
    direction: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
) -> list[dict]:
    async with async_session() as session:
        query = select(EventRow).order_by(EventRow.timestamp.desc())

        if device_id:
            query = query.where(EventRow.device_id == device_id)
        if protocol:
            query = query.where(EventRow.protocol == protocol)
        if direction:
            query = query.where(EventRow.direction == direction)

        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        rows = result.scalars().all()

        return [
            {
                "id": r.id,
                "device_id": r.device_id,
                "device_name": r.device_name,
                "protocol": r.protocol,
                "direction": r.direction,
                "event_type": r.event_type,
                "topic": r.topic,
                "payload": r.payload,
                "timestamp": r.timestamp.isoformat() if r.timestamp else "",
            }
            for r in rows
        ]


@router.delete("/events")
async def clear_events():
    async with async_session() as session:
        await session.execute(delete(EventRow))
        await session.commit()
    return {"status": "cleared"}
