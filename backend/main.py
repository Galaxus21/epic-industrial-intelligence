"""
EPIC — FastAPI Application Entry Point
Registers all routers, CORS, and startup events.
"""
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api import admin, agents, documents, equipment, knowledge_graph, maintenance, sensors, users, work_orders
from app.services.demoAccount import ensureDemoAccounts, refuseActiveDemoAccountInProduction
from app.services.threshold_monitor import run_threshold_monitor

# Values a deployment inherits by leaving the built-in default or copying .env.example unedited.
PLACEHOLDER_SECRET_KEYS = frozenset({"dev-insecure-secret-change-me", "change-me-generate-a-real-secret"})


def _verify_schema_is_migrated() -> None:
    """Fail fast if the schema wasn't brought up to date by Alembic.

    Schema creation moved from an app-startup create_all() to tracked Alembic
    revisions (backend/alembic/versions/), applied by backend/entrypoint.sh
    before this process starts. A mismatch here means either the entrypoint
    was bypassed or code shipped without a matching migration — both are
    startup-blocking configuration errors, not conditions to serve through.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, text

    alembic_cfg = Config("alembic.ini")
    head_revision = ScriptDirectory.from_config(alembic_cfg).get_current_head()

    sync_url = settings.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")
    sync_engine = create_engine(sync_url)
    try:
        with sync_engine.connect() as conn:
            if not conn.dialect.has_table(conn, "alembic_version"):
                raise RuntimeError(
                    "Database has no alembic_version table — migrations were never applied. "
                    "Run 'alembic upgrade head' (the container entrypoint does this "
                    "automatically; a bypassed or host-run process must do it manually)."
                )
            current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    finally:
        sync_engine.dispose()

    if current != head_revision:
        raise RuntimeError(
            f"Database schema is at revision '{current}' but the code expects "
            f"'{head_revision}'. Run 'alembic upgrade head' before starting the app."
        )


def _validate_production_config() -> None:
    """Fail fast on unsafe production configuration instead of starting quietly."""
    if settings.environment != "production":
        return
    problems: list[str] = []
    if settings.secret_key in PLACEHOLDER_SECRET_KEYS:
        problems.append("SECRET_KEY is still a placeholder (built-in default or .env.example value)")
    if settings.database_url.startswith("sqlite"):
        problems.append("DATABASE_URL points at SQLite — use PostgreSQL in production")
    if problems:
        raise RuntimeError(
            "Refusing to start in production with unsafe configuration: " + "; ".join(problems)
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify the schema is migrated, make sure the demo sign-in matches the environment, then serve."""
    _validate_production_config()
    _verify_schema_is_migrated()
    await refuseActiveDemoAccountInProduction()
    await ensureDemoAccounts()
    # Launch autonomous threshold monitor in the background
    monitor_task = asyncio.create_task(run_threshold_monitor())
    yield
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="EPIC — Enterprise Platform for Industrial Cognition",
    description="Equipment-aware question answering over plant records, documents and live telemetry",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Cookie",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],
)

app.include_router(equipment.router,               prefix="/api/v1/equipment",           tags=["equipment"])
app.include_router(agents.router,                  prefix="/api/v1/agents",               tags=["agents"])
app.include_router(documents.router,               prefix="/api/v1/documents",            tags=["documents"])
app.include_router(knowledge_graph.router,         prefix="/api/v1/knowledge-graph",      tags=["knowledge-graph"])
app.include_router(work_orders.router,             prefix="/api/v1/ops",                  tags=["work-orders"])
app.include_router(sensors.router,                 prefix="/api/v1/sensors",              tags=["sensors"])
app.include_router(users.router,                   prefix="/api/v1/users",                tags=["users"])
app.include_router(admin.router,                   prefix="/api/v1/admin",               tags=["admin"])
app.include_router(maintenance.router,             prefix="/api/v1/maintenance",          tags=["maintenance"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "EPIC"}
