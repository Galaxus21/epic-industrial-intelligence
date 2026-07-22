"""
AI Operations Brain — Custom Dashboards API
CRUD for user-defined widget dashboards.
Each dashboard stores a widget list; the frontend renders live data per widget.

Endpoints:
  GET    /api/v1/dashboards           — list all dashboards
  POST   /api/v1/dashboards           — create dashboard
  GET    /api/v1/dashboards/{id}      — get one dashboard
  PATCH  /api/v1/dashboards/{id}      — update name/description/widgets
  DELETE /api/v1/dashboards/{id}      — delete dashboard
  GET    /api/v1/dashboards/widgets   — catalogue of available widget types
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.database import AsyncSessionLocal
from app.db import models as m
from sqlalchemy import select, func

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Widget catalogue ──────────────────────────────────────────────────────────

WIDGET_CATALOGUE = [
    {
        "type":        "plant_health",
        "label":       "Plant Health KPIs",
        "description": "Overall plant health score, alarm count, overdue maintenance",
        "icon":        "factory",
        "config_fields": [],
        "col_span":    1,
    },
    {
        "type":        "equipment_health",
        "label":       "Equipment Health Card",
        "description": "Health ring, status, and key metrics for one equipment",
        "icon":        "cog",
        "config_fields": [{"id": "equipment_id", "label": "Equipment ID", "type": "equipment_select"}],
        "col_span":    1,
    },
    {
        "type":        "sensor_chart",
        "label":       "Sensor Trend Chart",
        "description": "30-day history line chart with alarm/trip thresholds",
        "icon":        "activity",
        "config_fields": [
            {"id": "equipment_id", "label": "Equipment ID", "type": "equipment_select"},
            {"id": "sensor_key",   "label": "Sensor",       "type": "sensor_select"},
        ],
        "col_span":    2,
    },
    {
        "type":        "sensor_grid",
        "label":       "Sensor Readings Grid",
        "description": "All current sensor readings for one equipment with status indicators",
        "icon":        "gauge",
        "config_fields": [{"id": "equipment_id", "label": "Equipment ID", "type": "equipment_select"}],
        "col_span":    2,
    },
    {
        "type":        "work_order_kpi",
        "label":       "Work Order KPIs",
        "description": "Open, completed, and solution-rate metrics",
        "icon":        "wrench",
        "config_fields": [],
        "col_span":    1,
    },
    {
        "type":        "incident_kpi",
        "label":       "Incident Analytics",
        "description": "Total incidents, severity breakdown, high+critical count",
        "icon":        "alert-triangle",
        "config_fields": [],
        "col_span":    1,
    },
    {
        "type":        "maintenance_kpi",
        "label":       "Maintenance KPIs",
        "description": "Compliance rate, overdue count, recent activity",
        "icon":        "clipboard-list",
        "config_fields": [],
        "col_span":    1,
    },
    {
        "type":        "safety_kpi",
        "label":       "Safety & Compliance",
        "description": "Avg compliance score, PTW conflicts, equipment below threshold",
        "icon":        "shield-check",
        "config_fields": [],
        "col_span":    1,
    },
    {
        "type":        "incident_list",
        "label":       "Recent Incidents",
        "description": "Latest incidents across the plant or for one equipment",
        "icon":        "zap",
        "config_fields": [{"id": "equipment_id", "label": "Equipment (optional)", "type": "equipment_select", "required": False}],
        "col_span":    2,
    },
    {
        "type":        "work_order_list",
        "label":       "Open Work Orders",
        "description": "All open and in-progress work orders",
        "icon":        "clipboard-check",
        "config_fields": [],
        "col_span":    2,
    },
    {
        "type":        "alert_feed",
        "label":       "Live Alarm Feed",
        "description": "Sensors currently in alarm or trip state across all equipment",
        "icon":        "bell",
        "config_fields": [],
        "col_span":    2,
    },
    {
        "type":        "audit_feed",
        "label":       "Audit Activity Feed",
        "description": "Recent audit trail entries — who did what and when",
        "icon":        "clock",
        "config_fields": [],
        "col_span":    2,
    },
]

# ── Pre-built default dashboards (created on first startup) ───────────────────

DEFAULT_DASHBOARDS = [
    {
        "id": "DASH-OPERATIONS",
        "name": "Operations Overview",
        "description": "Shift handover dashboard — plant health, alarms, open work orders",
        "columns": 2,
        "widgets": [
            {"id": "w1", "type": "plant_health",     "title": "Plant Health",      "col_span": 1, "config": {}},
            {"id": "w2", "type": "work_order_kpi",   "title": "Work Orders",       "col_span": 1, "config": {}},
            {"id": "w3", "type": "alert_feed",        "title": "Live Alarms",       "col_span": 2, "config": {}},
            {"id": "w4", "type": "work_order_list",   "title": "Open Work Orders",  "col_span": 2, "config": {}},
        ],
    },
    {
        "id": "DASH-MAINTENANCE",
        "name": "Maintenance Dashboard",
        "description": "Maintenance planner view — KPIs, overdue tasks, recent records",
        "columns": 2,
        "widgets": [
            {"id": "w1", "type": "maintenance_kpi",   "title": "Maintenance KPIs", "col_span": 1, "config": {}},
            {"id": "w2", "type": "incident_kpi",      "title": "Incidents",        "col_span": 1, "config": {}},
            {"id": "w3", "type": "work_order_list",   "title": "Open Work Orders", "col_span": 2, "config": {}},
            {"id": "w4", "type": "incident_list",     "title": "Recent Incidents", "col_span": 2, "config": {}},
        ],
    },
    {
        "id": "DASH-P101",
        "name": "P-101 Equipment Monitor",
        "description": "Real-time monitoring for Crude Oil Feed Pump P-101",
        "columns": 2,
        "widgets": [
            {"id": "w1", "type": "equipment_health",  "title": "P-101 Health",       "col_span": 1, "config": {"equipment_id": "P-101"}},
            {"id": "w2", "type": "sensor_grid",       "title": "P-101 Sensors",      "col_span": 1, "config": {"equipment_id": "P-101"}},
            {"id": "w3", "type": "sensor_chart",      "title": "Vibration DE Trend", "col_span": 2, "config": {"equipment_id": "P-101", "sensor_key": "vibration_de"}},
        ],
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_dict(row: m.CustomDashboard) -> dict[str, Any]:
    return {
        "id":          row.id,
        "name":        row.name,
        "description": row.description,
        "widgets":     row.widgets or [],
        "columns":     row.columns,
        "created_by":  row.created_by,
        "created_at":  row.created_at.isoformat() if row.created_at else None,
        "updated_at":  row.updated_at.isoformat() if row.updated_at else None,
    }


async def _seed_defaults() -> None:
    """Create pre-built dashboards if the table is empty."""
    async with AsyncSessionLocal() as s:
        existing = (await s.execute(
            select(func.count()).select_from(m.CustomDashboard)
        )).scalar_one()
        if existing > 0:
            return
        for d in DEFAULT_DASHBOARDS:
            s.add(m.CustomDashboard(
                id=d["id"], name=d["name"], description=d.get("description"),
                widgets=d["widgets"], columns=d.get("columns", 2),
                created_by="system",
            ))
        await s.commit()


# ── Schemas ───────────────────────────────────────────────────────────────────

class DashboardCreate(BaseModel):
    name: str
    description: str | None = None
    widgets: list[dict[str, Any]] = []
    columns: int = 2
    created_by: str | None = None


class DashboardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    widgets: list[dict[str, Any]] | None = None
    columns: int | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/widgets")
async def list_widget_catalogue():
    return WIDGET_CATALOGUE


@router.get("")
async def list_dashboards():
    await _seed_defaults()
    async with AsyncSessionLocal() as s:
        result = await s.execute(
            select(m.CustomDashboard).order_by(m.CustomDashboard.created_at)
        )
        return [_row_to_dict(r) for r in result.scalars().all()]


@router.post("", status_code=201)
async def create_dashboard(body: DashboardCreate):
    dash_id = f"DASH-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as s:
        row = m.CustomDashboard(
            id=dash_id, name=body.name, description=body.description,
            widgets=body.widgets, columns=body.columns, created_by=body.created_by,
        )
        s.add(row)
        await s.commit()
        await s.refresh(row)
    return _row_to_dict(row)


@router.get("/{dash_id}")
async def get_dashboard(dash_id: str):
    await _seed_defaults()
    async with AsyncSessionLocal() as s:
        row = await s.get(m.CustomDashboard, dash_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return _row_to_dict(row)


@router.patch("/{dash_id}")
async def update_dashboard(dash_id: str, body: DashboardUpdate):
    async with AsyncSessionLocal() as s:
        row = await s.get(m.CustomDashboard, dash_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        if body.name is not None:        row.name        = body.name
        if body.description is not None: row.description = body.description
        if body.widgets is not None:     row.widgets     = body.widgets
        if body.columns is not None:     row.columns     = body.columns
        row.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(row)
    return _row_to_dict(row)


@router.delete("/{dash_id}", status_code=204)
async def delete_dashboard(dash_id: str):
    async with AsyncSessionLocal() as s:
        row = await s.get(m.CustomDashboard, dash_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        await s.delete(row)
        await s.commit()
