"""
EPIC — What deleting or renaming a document must change beyond the document row.

With AUTO_REGISTER_ENTITIES=true a document writes incidents and defects of its own (doc_entity_mapper: ids
INC-DOC-… and DEF-DOC-…, with the document id in source_document). Deleting the document deletes them, their graph
nodes and their similar-incident vectors; otherwise search keeps citing a document the user removed. Equipment lists
the documents that name it by filename (source_documents) and a delete removes the current filename, so a rename
renames that entry too.
"""
from __future__ import annotations

from sqlalchemy import delete, or_, select

from app.db import models as m
from app.db.database import AsyncSessionLocal
from app.services import db_service as db
from app.services import vector_service as vs
from app.services.doc_entity_mapper import DOCUMENT_DEFECT_PREFIX, DOCUMENT_INCIDENT_PREFIX

SOURCE_DOCUMENT_KEY = "source_document"


async def removeDocumentIncidents(docId: str) -> list[str]:
    """Delete the incidents and defects the document created, with their graph nodes and vectors. Returns their ids."""
    async with AsyncSessionLocal() as session:
        documentRows = (await session.execute(select(m.Incident).where(or_(
            m.Incident.id.startswith(f"{DOCUMENT_INCIDENT_PREFIX}-"),
            m.Incident.id.startswith(f"{DOCUMENT_DEFECT_PREFIX}-"),
        )))).scalars().all()
        incidentIds = [row.id for row in documentRows if (row.extra or {}).get(SOURCE_DOCUMENT_KEY) == docId]
        if incidentIds:
            await session.execute(delete(m.Incident).where(m.Incident.id.in_(incidentIds)))
            await session.commit()
    for incidentId in incidentIds:
        await db.remove_graph_node_and_links(incidentId)
    await vs.delete_incident_points(incidentIds)
    return incidentIds


async def renameDocumentOnEquipment(oldName: str, newName: str, equipmentIds: list[str]) -> None:
    """Replace the document's filename in each linked equipment's source_documents."""
    async with AsyncSessionLocal() as session:
        for equipmentId in equipmentIds:
            row = await session.get(m.Equipment, equipmentId)
            if row is not None and oldName in (row.source_documents or []):
                row.source_documents = [newName if name == oldName else name for name in row.source_documents]
        await session.commit()
