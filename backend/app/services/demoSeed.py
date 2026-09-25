"""
EPIC — Writes the demo plant (POST /api/v1/admin/generate-demo).

Every row has a fixed ID, so seeding again updates the same rows and re-dates the story to the new seed moment
instead of adding copies. A demo user whose employee ID already belongs to another account is left out rather than
failing the seed, and a demo user's password and active flag are never touched.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.db import models as m
from app.db.database import AsyncSessionLocal
from app.services import db_service as db
from app.services import demoTimeline as timeline
from app.services.complianceScore import complianceScore
from app.services.demo_docs import generate_demo_documents
from app.services.demoAssets import demoCompliance, demoEquipment, demoSpareParts
from app.services.demoHistory import demoIncidents, demoMaintenanceRecords
from app.services.demoPeople import demoTechnicians, demoUsers
from app.services.demoSensorSeries import demoSensorSeries
from app.services.demoWorkOrders import demoWorkOrders
from app.services.incidentWriter import saveIncident

EQUIPMENT_NODE_SIZE = 18
INCIDENT_NODE_SIZE = 14
WORK_ORDER_NODE_SIZE = 12
TECHNICIAN_NODE_SIZE = 10
SPARE_PART_NODE_SIZE = 8
DEMO_QUERY_HINT = "Open Query, select P-101 and ask: 'Pump vibration increased today. Can I continue operating?'"
# Links between records the graph cannot infer from a foreign key.
STORY_LINKS = (("P-101", "HX-201", "FEEDS"), ("HX-201", "V-301", "FEEDS"), ("G-101", "K-401", "COOLS"),
               ("INC-2022-034", "INC-2023-067", "SIMILAR_PATTERN"))


async def seedDemoDataset(now: datetime | None = None) -> dict[str, Any]:
    """Write the whole demo plant dated from `now` (default: this moment) and say what was written."""
    now = now or timeline.seedMoment()
    equipment = demoEquipment()
    incidents = demoIncidents(now)
    workOrders = demoWorkOrders(now)
    created = {
        "users": await _seedUsers(),
        "technicians": await _mergeRows(m.Technician, demoTechnicians()),
        "equipment": await _seedEquipment(equipment, now),
        "spare_parts": await _mergeRows(m.SparePart, demoSpareParts()),
        "incidents": await _seedIncidents(incidents),
        "maintenance_records": await _seedMaintenance(now),
        "work_orders": await _mergeRows(m.SavedWorkOrder, workOrders),
        "sensor_series": await _seedSensorSeries(now, equipment),
        "graph_links": await _seedGraph(equipment, incidents, workOrders, now),
    }
    documents = generate_demo_documents(now)
    return {
        "status": "ok",
        "seeded_at": now.isoformat(),
        "created": created,
        "total_entities": sum(created.values()),
        "demo_query": DEMO_QUERY_HINT,
        "highlights": _storyHighlights(now, incidents, workOrders),
        "demo_doc_files": [{"doc_id": document["id"], "filename": document["name"]} for document in documents],
    }


def _storyHighlights(now: datetime, incidents: list[dict[str, Any]], workOrders: list[dict[str, Any]]) -> list[str]:
    completed = sum(1 for workOrder in workOrders if workOrder["status"] == "completed")
    return [
        f"P-101: DE vibration above the alarm since {timeline.P101_ALARM_CLOCK_TIME}; DE bearing damage found "
        f"{timeline.P101_SPECTRUM_CHECK_DAYS_AGO} days ago; no installed spare",
        f"K-401: discharge pressure has fallen again in the {timeline.K401_FILTER_CHANGE_DAYS_AGO} days since a filter change; "
        f"intercooler fouling suspected ({timeline.k401IntercoolerWorkOrderId(now)})",
        f"{len(incidents)} past incidents, including a P-101 bearing failure and a look-alike P-202 cavitation case",
        f"{len(workOrders)} work orders ({completed} completed with outcome feedback); the threshold monitor adds "
        "one for P-101 on its next pass",
    ]


async def _seedUsers() -> int:
    written = 0
    async with AsyncSessionLocal() as session:
        for user in demoUsers():
            holder = await session.scalar(select(m.UserProfile).where(m.UserProfile.employee_id == user["employee_id"]))
            if holder is not None and holder.id != user["id"]:
                continue
            await session.merge(m.UserProfile(**user))
            written += 1
        await session.commit()
    return written


async def _mergeRows(model: type, rows: list[dict[str, Any]]) -> int:
    async with AsyncSessionLocal() as session:
        for row in rows:
            await session.merge(model(**row))
        await session.commit()
    return len(rows)


async def _seedEquipment(equipment: list[dict[str, Any]], now: datetime) -> int:
    scores = {}
    for record in demoCompliance(now):
        score, status = complianceScore(record["issues"])
        scores[record["equipment_id"]] = score
        await db.upsert_compliance({**record, "overall_score": score, "status": status})
    for asset in equipment:
        await db.upsert_equipment({**asset, "compliance_score": float(scores[asset["id"]])})
    return len(equipment)


async def _seedIncidents(incidents: list[dict[str, Any]]) -> int:
    for incident in incidents:
        await saveIncident(incident)
    return len(incidents)


async def _seedMaintenance(now: datetime) -> int:
    records = demoMaintenanceRecords(now)
    for record in records:
        await db.upsert_maintenance_record(record)
    return len(records)


async def _seedSensorSeries(now: datetime, equipment: list[dict[str, Any]]) -> int:
    series = demoSensorSeries(now, equipment)
    for equipmentId, sensorKey, readings in series:
        await db.upsert_sensor_history(equipmentId, sensorKey, readings)
    return len(series)


async def _seedGraph(equipment: list[dict[str, Any]], incidents: list[dict[str, Any]],
                     workOrders: list[dict[str, Any]], now: datetime) -> int:
    links: list[tuple[str, str, str]] = list(STORY_LINKS)
    links.append(("INC-2024-015", timeline.k401IncidentId(now), "RECURRED_AS"))
    for asset in equipment:
        await db.upsert_graph_node({"id": asset["id"], "name": f"{asset['id']}\n{asset['name']}",
                                    "type": "equipment", "val": EQUIPMENT_NODE_SIZE})
    for incident in incidents:
        await db.upsert_graph_node({"id": incident["id"], "name": f"{incident['id']}\n{incident['title']}",
                                    "type": "incident", "val": INCIDENT_NODE_SIZE})
        links.append((incident["equipment_id"], incident["id"], "HAS_INCIDENT"))
    for workOrder in workOrders:
        await db.upsert_graph_node({"id": workOrder["id"], "name": f"{workOrder['id']}\n{workOrder['description']}",
                                    "type": "work_order", "val": WORK_ORDER_NODE_SIZE})
        links.append((workOrder["equipment_id"], workOrder["id"], "HAS_WORK_ORDER"))
    links += await _seedPeopleAndPartNodes()
    for source, target, label in links:
        await db.add_graph_link(source, target, label)
    return len(links)


async def _seedPeopleAndPartNodes() -> list[tuple[str, str, str]]:
    links = []
    for technician in demoTechnicians():
        await db.upsert_graph_node({"id": technician["id"], "name": f"{technician['name']}\n{technician['role']}",
                                    "type": "technician", "val": TECHNICIAN_NODE_SIZE})
        links += [(equipmentId, technician["id"], "MAINTAINED_BY") for equipmentId in technician["equipment_ids"]]
    for part in demoSpareParts():
        await db.upsert_graph_node({"id": part["id"], "name": f"{part['part_number']}\n{part['name']}",
                                    "type": "spare_part", "val": SPARE_PART_NODE_SIZE})
        links += [(equipmentId, part["id"], "USES_PART") for equipmentId in part["equipment_ids"]]
    return links
