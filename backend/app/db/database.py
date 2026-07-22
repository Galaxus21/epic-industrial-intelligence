"""
AI Operations Brain — Async Database Engine
SQLAlchemy 2.0 async engine for PostgreSQL (Docker) / SQLite (local dev).
All persistent data lives here; demo_data.py is used only for first-run seeding.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create all tables if they don't already exist."""
    from app.db import models  # noqa: F401 — registers models with Base metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
