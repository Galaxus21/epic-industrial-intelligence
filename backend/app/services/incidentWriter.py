"""
EPIC — The one way an incident is written: its row, then its semantic-search entry.

Similar-incident search asks Qdrant first and reads PostgreSQL only when Qdrant finds nothing
(vector_service.search_similar_incidents), so an incident that is stored but not indexed stays invisible whenever any
indexed incident matches. Every writer (the demo seed, work-order lessons, document extraction) goes through here.
"""
from __future__ import annotations

from typing import Any

from app.services import db_service as db
from app.services import vector_service as vs

SEARCHABLE_FIELDS = ("symptom", "root_cause", "lessons_learned")


async def saveIncident(incident: dict[str, Any]) -> None:
    """Upsert the incident row and index it; indexing is skipped, with a warning, while embeddings are unavailable."""
    await db.upsert_incident(incident)
    await vs.index_incident(
        incident_id=incident["id"], title=incident["title"], description=incidentSearchText(incident),
        equipment_id=incident["equipment_id"], severity=incident.get("severity") or "",
        date=incident.get("date") or "",
    )


def incidentSearchText(incident: dict[str, Any]) -> str:
    return " ".join(text for text in (incident.get(field) for field in SEARCHABLE_FIELDS) if text)
