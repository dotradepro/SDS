"""SQLite database via SQLAlchemy async."""

import datetime
from sqlalchemy import Column, String, Text, Boolean, Float, DateTime, Integer, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "sqlite+aiosqlite:///data/sds.db"


class Base(DeclarativeBase):
    pass


class DeviceRow(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    protocol = Column(String, nullable=False)
    protocol_config = Column(Text, default="{}")  # JSON
    state = Column(Text, default="{}")  # JSON
    capabilities = Column(Text, default="[]")  # JSON array
    room = Column(String, default="")
    icon = Column(String, default="")
    is_online = Column(Boolean, default=True)
    auto_report_interval = Column(Integer, default=60)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class EventRow(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, nullable=True)
    device_name = Column(String, default="")
    protocol = Column(String, default="")
    direction = Column(String, default="")  # sent / received
    event_type = Column(String, default="")
    topic = Column(String, default="")
    payload = Column(Text, default="")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


class ScenarioRow(Base):
    __tablename__ = "scenarios"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    is_active = Column(Boolean, default=False)
    triggers = Column(Text, default="[]")  # JSON
    steps = Column(Text, default="[]")  # JSON
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
