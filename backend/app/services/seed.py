"""
AI Operations Brain — Database Seed
Populates PostgreSQL tables from demo_data on first start if tables are empty.
After seeding, all runtime reads come from the DB; demo_data is never touched again.
"""
from __future__ import annotations

import logging
from sqlalchemy import select, func
from app.db.database import AsyncSessionLocal
from app.db import models as m

logger = logging.getLogger(__name__)


async def _table_empty(session, model) -> bool:
    result = await session.execute(select(func.count()).select_from(model))
    return result.scalar_one() == 0


async def seed_db_from_demo() -> None:
    """
    Seed all PostgreSQL tables from demo_data if they are empty.
    Safe to call on every startup — skips silently if data already exists.
    """
    from app.services import demo_data as dd
    from app.services.db_service import (
        upsert_equipment, upsert_incident, upsert_maintenance_record,
        upsert_document, upsert_compliance, upsert_spare_part,
        upsert_technician, upsert_graph_node, add_graph_link,
        upsert_sensor_history,
    )
    from app.db.database import engine
    from app.db.database import Base
    from app.db import models  # noqa: F401  — registers all models including SavedWorkOrder

    # Ensure tables exist (including new ones added after initial seed)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as s:
        already_seeded = not await _table_empty(s, m.Equipment)

    if already_seeded:
        logger.info("DB already seeded — skipping demo data seed")
        # Still seed new project management entities if they're missing
        await _seed_project_entities()
        return

    logger.info("Seeding PostgreSQL from demo_data…")

    # ── Equipment ────────────────────────────────────────────────────────────
    for eq in dd.EQUIPMENT.values():
        await upsert_equipment(eq)

    # ── Incidents ────────────────────────────────────────────────────────────
    for inc in dd.INCIDENTS:
        await upsert_incident(inc)

    # ── Maintenance Records ───────────────────────────────────────────────────
    for mr in dd.MAINTENANCE_RECORDS:
        await upsert_maintenance_record(mr)

    # ── Documents ────────────────────────────────────────────────────────────
    for doc in dd.DOCUMENTS:
        doc_data = dict(doc)
        doc_data.setdefault("status", "processed")
        doc_data.setdefault("pipeline_steps", {})
        await upsert_document(doc_data)

    # ── Compliance ────────────────────────────────────────────────────────────
    for equipment_id, status in dd.COMPLIANCE.items():
        await upsert_compliance({"equipment_id": equipment_id, **status})

    # ── Spare Parts ───────────────────────────────────────────────────────────
    for sp in dd.SPARE_PARTS:
        await upsert_spare_part(sp)

    # ── Technicians ───────────────────────────────────────────────────────────
    for tech in dd.TECHNICIANS:
        await upsert_technician(tech)

    # ── Graph Nodes ───────────────────────────────────────────────────────────
    for node in dd.GRAPH_NODES:
        await upsert_graph_node(node)

    # ── Graph Links ───────────────────────────────────────────────────────────
    for link in dd.GRAPH_LINKS:
        await add_graph_link(link["source"], link["target"], link["label"])

    # ── Sensor History ────────────────────────────────────────────────────────
    for equipment_id, sensors in dd.SENSOR_HISTORY.items():
        for sensor_key, readings in sensors.items():
            await upsert_sensor_history(equipment_id, sensor_key, readings)

    logger.info("DB seed complete — seeding project management entities...")
    await _seed_project_entities()
    logger.info("All seed data loaded")


async def _seed_project_entities() -> None:
    """Seed Projects, Plants, Users, Permits, Procedures, MWOs, Incidents, Inspections, Actions."""
    from app.services import project_seed as ps
    from sqlalchemy import select

    async with AsyncSessionLocal() as s:
        # Skip if already seeded (check users table)
        existing = (await s.execute(select(func.count()).select_from(m.UserProfile))).scalar_one()
        if existing > 0:
            logger.info("Project entities already seeded — skipping")
            return

    # ── Users ──────────────────────────────────────────────────────────────
    for u in ps.USERS:
        async with AsyncSessionLocal() as s:
            obj = m.UserProfile(**u)
            s.add(obj)
            try:
                await s.commit()
            except Exception:
                await s.rollback()

    # ── Projects ───────────────────────────────────────────────────────────
    for p in ps.PROJECTS:
        async with AsyncSessionLocal() as s:
            obj = m.Project(**p)
            s.add(obj)
            try:
                await s.commit()
            except Exception:
                await s.rollback()

    # ── Plants ─────────────────────────────────────────────────────────────
    for p in ps.PLANTS:
        async with AsyncSessionLocal() as s:
            obj = m.Plant(**p)
            s.add(obj)
            try:
                await s.commit()
            except Exception:
                await s.rollback()

    # ── Permits ────────────────────────────────────────────────────────────
    for p in ps.PERMITS:
        async with AsyncSessionLocal() as s:
            obj = m.PermitToWork(**p)
            s.add(obj)
            try:
                await s.commit()
            except Exception:
                await s.rollback()

    # ── Safety Procedures ──────────────────────────────────────────────────
    for p in ps.PROCEDURES:
        async with AsyncSessionLocal() as s:
            obj = m.SafetyProcedure(**p)
            s.add(obj)
            try:
                await s.commit()
            except Exception:
                await s.rollback()

    # ── Managed Work Orders ────────────────────────────────────────────────
    for w in ps.MANAGED_WORK_ORDERS:
        async with AsyncSessionLocal() as s:
            obj = m.ManagedWorkOrder(**w)
            s.add(obj)
            try:
                await s.commit()
            except Exception:
                await s.rollback()

    # ── Incident Reports ───────────────────────────────────────────────────
    for i in ps.INCIDENT_REPORTS:
        async with AsyncSessionLocal() as s:
            obj = m.IncidentReport(**i)
            s.add(obj)
            try:
                await s.commit()
            except Exception:
                await s.rollback()

    # ── Quality Inspections ────────────────────────────────────────────────
    for i in ps.QUALITY_INSPECTIONS:
        async with AsyncSessionLocal() as s:
            obj = m.QualityInspection(**i)
            s.add(obj)
            try:
                await s.commit()
            except Exception:
                await s.rollback()

    # ── Action Items ───────────────────────────────────────────────────────
    for a in ps.ACTION_ITEMS:
        async with AsyncSessionLocal() as s:
            obj = m.ActionItem(**a)
            s.add(obj)
            try:
                await s.commit()
            except Exception:
                await s.rollback()

    logger.info("Project management entities seeded")
