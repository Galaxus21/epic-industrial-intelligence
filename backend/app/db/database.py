"""
AI Operations Brain — Async Database Engine
SQLAlchemy 2.0 async engine for PostgreSQL (Docker) / SQLite (local dev).
"""
import os

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import settings

# asyncpg binds every connection to the event loop that was running when it
# was opened and refuses to reuse it from another one ("attached to a
# different loop"). Under pytest a single process runs test bodies across
# several distinct loops — pytest-asyncio's default per-function test loop
# differs from its per-session fixture loop, and starlette's TestClient runs
# the ASGI app on yet another loop of its own in a background thread. A
# pooled connection opened on one of those and checked out on another
# crashes, or worse, gets silently reused mid-request against the wrong
# session. PYTEST_VERSION is set by pytest
# itself for the whole run, so this needs no test-only flag of our own.
# aiosqlite has no such loop affinity, so this only bites on Postgres, but
# NullPool is harmless for SQLite too.
_pool_kwargs = {"poolclass": NullPool} if "PYTEST_VERSION" in os.environ else {"pool_pre_ping": True}

engine = create_async_engine(settings.database_url, echo=False, **_pool_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# SQLite does not enforce FOREIGN KEY constraints by default, and the pragma is
# per-connection — a caller issuing "PRAGMA foreign_keys=ON" on its own session
# only affects the one pooled connection it happens to hold, not every
# connection the pool later hands to other sessions. Register it on every new
# DBAPI connection instead, so enforcement cannot depend on which connection
# the pool reuses (without this, foreign keys were enforced on some pooled
# connections and not others).
# PostgreSQL enforces foreign keys natively and has no such pragma.
if engine.dialect.name == "sqlite":
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class Base(DeclarativeBase):
    pass
