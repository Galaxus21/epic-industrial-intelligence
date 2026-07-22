"""
AI Operations Brain — FastAPI Application Entry Point
Registers all routers, CORS, and startup events.
"""
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.core.config import settings
from app.api import equipment, agents, documents, knowledge_graph, compliance, integrations, work_orders
from app.api import rca, plant, safety, forms, sensors
from app.api import audit, reports, dashboards
from app.api import projects, users, permits, procedures, inspections, managed_work_orders, incident_reports
from app.api import drawings_mgmt
from app.api import admin
from app.api import spare_parts
from app.api import maintenance
from app.services.threshold_monitor import run_threshold_monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure DB tables exist, then serve from DB.
    Demo data seeding has been removed — the DB starts empty and is populated
    only by real user actions.
    """
    # Create tables if they don't exist (schema-only, no demo data)
    from app.db.database import engine, Base
    from app.db import models  # noqa: F401 — registers all ORM models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add new nullable columns to incident_reports if the table already existed
        for col_ddl in (
            "ALTER TABLE incident_reports ADD COLUMN IF NOT EXISTS downtime_hours FLOAT",
            "ALTER TABLE incident_reports ADD COLUMN IF NOT EXISTS cost_usd FLOAT",
            "ALTER TABLE incident_reports ADD COLUMN IF NOT EXISTS root_cause_category VARCHAR",
        ):
            try:
                await conn.execute(text(col_ddl))
            except Exception:
                pass  # column already exists or DB doesn't support IF NOT EXISTS
    # Launch autonomous threshold monitor in the background
    monitor_task = asyncio.create_task(run_threshold_monitor())
    yield
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="AI Operations Brain",
    description="Industrial knowledge graph + multi-agent AI for plant operations",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(equipment.router,               prefix="/api/v1/equipment",           tags=["equipment"])
app.include_router(agents.router,                  prefix="/api/v1/agents",               tags=["agents"])
app.include_router(documents.router,               prefix="/api/v1/documents",            tags=["documents"])
app.include_router(knowledge_graph.router,         prefix="/api/v1/knowledge-graph",      tags=["knowledge-graph"])
app.include_router(compliance.router,              prefix="/api/v1/compliance",           tags=["compliance"])
app.include_router(integrations.router,            prefix="/api/v1/integrations",         tags=["integrations"])
app.include_router(work_orders.router,             prefix="/api/v1/ops",                  tags=["work-orders"])
app.include_router(rca.router,                     prefix="/api/v1/rca",                  tags=["rca"])
app.include_router(plant.router,                   prefix="/api/v1/plant",                tags=["plant"])
app.include_router(safety.router,                  prefix="/api/v1/safety",               tags=["safety"])
app.include_router(forms.router,                   prefix="/api/v1/forms",                tags=["forms"])
app.include_router(sensors.router,                 prefix="/api/v1/sensors",              tags=["sensors"])
app.include_router(audit.router,                   prefix="/api/v1/audit",                tags=["audit"])
app.include_router(reports.router,                 prefix="/api/v1/reports",              tags=["reports"])
app.include_router(dashboards.router,              prefix="/api/v1/dashboards",           tags=["dashboards"])
# ── Project Management ────────────────────────────────────────────────────────
app.include_router(projects.router,                prefix="/api/v1/pm",                   tags=["project-management"])
app.include_router(users.router,                   prefix="/api/v1/users",                tags=["users"])
app.include_router(permits.router,                 prefix="/api/v1/permits",              tags=["permits"])
app.include_router(procedures.router,              prefix="/api/v1/procedures",           tags=["procedures"])
app.include_router(inspections.router,             prefix="/api/v1/inspections",          tags=["inspections"])
app.include_router(drawings_mgmt.router,           prefix="/api/v1/drawings",             tags=["drawings"])
app.include_router(admin.router,                   prefix="/api/v1/admin",               tags=["admin"])
app.include_router(managed_work_orders.router,     prefix="/api/v1/work-orders",          tags=["managed-work-orders"])
app.include_router(incident_reports.router,        prefix="/api/v1/incidents",            tags=["incidents"])
app.include_router(spare_parts.router,             prefix="/api/v1/spare-parts",          tags=["spare-parts"])
app.include_router(maintenance.router,             prefix="/api/v1/maintenance",          tags=["maintenance"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "AI Operations Brain"}
