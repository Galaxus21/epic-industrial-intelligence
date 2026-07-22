"""
AI Operations Brain — Projects & Plants API
Manage project hierarchy: Projects → Plants → Equipment.
Supports full CRUD plus assignment of plants/equipment to projects.
"""
import uuid
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db import models as m

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    type: str = "Industrial"
    phase: str = "Operations"
    status: str = "Active"
    location: str | None = None
    plant_ids: list[str] = []
    equipment_ids: list[str] = []
    manager_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    tags: list[str] = []
    created_by: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    phase: str | None = None
    status: str | None = None
    location: str | None = None
    plant_ids: list[str] | None = None
    equipment_ids: list[str] | None = None
    manager_id: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    tags: list[str] | None = None


class PlantCreate(BaseModel):
    code: str
    name: str
    project_id: str | None = None
    type: str = "Process Unit"
    location: str | None = None
    area: str | None = None
    description: str | None = None
    equipment_ids: list[str] = []
    status: str = "Operational"
    responsible_person_id: str | None = None


class PlantUpdate(BaseModel):
    name: str | None = None
    project_id: str | None = None
    type: str | None = None
    location: str | None = None
    area: str | None = None
    description: str | None = None
    equipment_ids: list[str] | None = None
    status: str | None = None
    responsible_person_id: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _row(obj) -> dict[str, Any]:
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _audit(trail: list | None, action: str, user: str, comments: str = "") -> list:
    trail = trail or []
    trail.append({
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "user": user,
        "comments": comments,
    })
    return trail


# ─────────────────────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects")
async def list_projects():
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(m.Project).order_by(m.Project.created_at.desc()))).scalars().all()
    return [_row(r) for r in rows]


@router.post("/projects", status_code=201)
async def create_project(body: ProjectCreate):
    pid = f"PRJ-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as s:
        # Ensure code is unique
        existing = (await s.execute(select(m.Project).where(m.Project.code == body.code))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail=f"Project code '{body.code}' already exists")
        obj = m.Project(id=pid, **body.model_dump())
        s.add(obj)
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.Project).where(m.Project.id == project_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Project not found")
    return _row(obj)


@router.patch("/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.Project).where(m.Project.id == project_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Project not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(obj, k, v)
        obj.updated_at = datetime.utcnow()
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.Project).where(m.Project.id == project_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Project not found")
        await s.delete(obj)
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Plants
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/plants")
async def list_plants(project_id: str | None = None):
    async with AsyncSessionLocal() as s:
        q = select(m.Plant)
        if project_id:
            q = q.where(m.Plant.project_id == project_id)
        rows = (await s.execute(q.order_by(m.Plant.created_at.desc()))).scalars().all()
    return [_row(r) for r in rows]


@router.post("/plants", status_code=201)
async def create_plant(body: PlantCreate):
    pid = f"PLT-{uuid.uuid4().hex[:8].upper()}"
    async with AsyncSessionLocal() as s:
        obj = m.Plant(id=pid, **body.model_dump())
        s.add(obj)
        # If a project is specified, add plant to project's plant_ids
        if body.project_id:
            proj = (await s.execute(select(m.Project).where(m.Project.id == body.project_id))).scalar_one_or_none()
            if proj:
                ids = list(proj.plant_ids or [])
                if pid not in ids:
                    ids.append(pid)
                proj.plant_ids = ids
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.get("/plants/{plant_id}")
async def get_plant(plant_id: str):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.Plant).where(m.Plant.id == plant_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Plant not found")
    return _row(obj)


@router.patch("/plants/{plant_id}")
async def update_plant(plant_id: str, body: PlantUpdate):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.Plant).where(m.Plant.id == plant_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Plant not found")
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(obj, k, v)
        await s.commit()
        await s.refresh(obj)
    return _row(obj)


@router.delete("/plants/{plant_id}", status_code=204)
async def delete_plant(plant_id: str):
    async with AsyncSessionLocal() as s:
        obj = (await s.execute(select(m.Plant).where(m.Plant.id == plant_id))).scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Plant not found")
        await s.delete(obj)
        await s.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Summary stats
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def project_stats():
    async with AsyncSessionLocal() as s:
        projects = (await s.execute(select(m.Project))).scalars().all()
        plants = (await s.execute(select(m.Plant))).scalars().all()
    return {
        "projects": len(projects),
        "plants": len(plants),
        "projects_by_status": _count_by(projects, "status"),
        "plants_by_status": _count_by(plants, "status"),
    }


def _count_by(rows, field: str) -> dict:
    counts: dict[str, int] = {}
    for r in rows:
        v = getattr(r, field, "Unknown") or "Unknown"
        counts[v] = counts.get(v, 0) + 1
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Hierarchy — Project → Plants → Equipment
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/hierarchy")
async def get_hierarchy():
    """
    Return the full Project → Plant → Equipment tree.
    Used by the AI Query interface to populate cascading selectors.
    """
    async with AsyncSessionLocal() as s:
        projects  = (await s.execute(select(m.Project).order_by(m.Project.name))).scalars().all()
        plants    = (await s.execute(select(m.Plant).order_by(m.Plant.name))).scalars().all()
        equipment = (
            await s.execute(
                select(m.Equipment)
                .where(m.Equipment.discovered == False)  # noqa: E712
                .order_by(m.Equipment.name)
            )
        ).scalars().all()

    eq_by_id: dict[str, dict] = {
        e.id: {
            "id": e.id, "name": e.name, "type": e.type,
            "status": e.status, "criticality": e.criticality,
            "health_score": e.health_score,
        }
        for e in equipment
    }
    plant_by_id = {p.id: p for p in plants}
    assigned_eq_ids: set[str] = set()

    result = []
    for proj in projects:
        proj_plants = []
        for plant_id in (proj.plant_ids or []):
            plant = plant_by_id.get(plant_id)
            if plant is None:
                continue
            plant_equipment = [
                eq_by_id[eid] for eid in (plant.equipment_ids or []) if eid in eq_by_id
            ]
            for eid in (plant.equipment_ids or []):
                assigned_eq_ids.add(eid)
            proj_plants.append({
                "id": plant.id, "name": plant.name, "code": plant.code,
                "status": plant.status, "equipment": plant_equipment,
            })
        result.append({
            "id": proj.id, "name": proj.name, "code": proj.code,
            "status": proj.status, "plants": proj_plants,
        })

    unassigned = [eq_by_id[e.id] for e in equipment if e.id not in assigned_eq_ids]
    return {"projects": result, "unassigned_equipment": unassigned}
