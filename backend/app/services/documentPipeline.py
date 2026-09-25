"""
EPIC — What happens to an uploaded document after the upload returns: saved, extracted, entities, graph, indexed.

Each step records its progress on the document row, which the web client polls (GET /api/v1/documents/{id}). The
equipment the uploader picked stays linked whatever tags the text names, and the chunks are indexed under registered
equipment only.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from app.services import db_service as db
from app.services import doc_entity_mapper
from app.services import vector_service as vs
from app.services.documentEntities import extractEntities
from app.services.documentText import extractText
from app.services.extractionGrounding import DEFAULT_DOCUMENT_TYPE

logger = logging.getLogger(__name__)

PIPELINE_STEPS = [
    ("saved",      "File saved"),
    ("extracted",  "Text extracted"),
    ("entities",   "Entities extracted"),
    ("graph",      "Knowledge graph updated"),
    ("indexed",    "Vector index updated"),
]
CHUNK_CHARS = 600
MAX_INDEXED_CHUNKS = 10
# A short pause before each step, so the upload panel shows the steps one after another.
STEP_PAUSE_SECONDS = {"saved": 0.3, "extracted": 0.5, "entities": 0.8, "graph": 0.4, "indexed": 0.3}
# extractText marks a file it could not read with a bracketed note, which is not document content.
UNREADABLE_NOTE_START = "["
INDEX_SKIPPED_DETAIL = "Vector index skipped (Qdrant unavailable)"


async def runPipeline(docId: str, filePath: str, ext: str, filename: str, pickedEquipmentId: str = "") -> None:
    """Run every step for the uploaded document; a failure marks the document failed with its error."""
    progress = _Progress(docId)
    try:
        await _pause("saved")
        await progress.advance("saved", f"Saved {os.path.getsize(filePath):,} bytes")
        text = await _extractStep(docId, filePath, ext, progress)
        entities = await _entitiesStep(docId, text, filename, progress)
        linked = {**entities, "equipment_ids": withPickedEquipment(entities.get("equipment_ids"), pickedEquipmentId)}
        await _graphStep(docId, filename, linked, progress)
        documentType = entities.get("document_type", DEFAULT_DOCUMENT_TYPE)
        known, unresolved = await splitKnownEquipment(linked["equipment_ids"])
        await _indexStep(docId, filename, text or entities.get("summary", ""), known, documentType, progress)
        await db.save_document({
            "id": docId, "status": "processed", "type": documentType, "current_step": "done",
            "equipment_ids": known, "unresolved_equipment_ids": unresolved,
        })
    except Exception as exc:
        logger.error("Pipeline failed for %s: %s", docId, exc)
        await db.save_document({"id": docId, "status": "failed", "extra": {"error": str(exc)}})


async def splitKnownEquipment(equipmentIds: list[str]) -> tuple[list[str], list[str]]:
    """(known, unresolved): a tag a model extracted links a document only if that equipment exists (F40)."""
    known: list[str] = []
    unresolved: list[str] = []
    for equipmentId in equipmentIds:
        (known if await db.get_equipment(equipmentId) else unresolved).append(equipmentId)
    return known, unresolved


def withPickedEquipment(extractedIds: Any, pickedEquipmentId: str) -> list[str]:
    """The equipment a document is about: the one the uploader picked, then every tag extracted from its text."""
    extracted = [str(eqId) for eqId in extractedIds if eqId] if isinstance(extractedIds, list) else []
    return list(dict.fromkeys(([pickedEquipmentId] if pickedEquipmentId else []) + extracted))


class _Progress:
    """The document row's record of which steps are done, written after each one."""

    def __init__(self, docId: str) -> None:
        self.docId = docId
        self.completed: set[str] = set()

    async def advance(self, step: str, detail: str = "") -> None:
        self.completed.add(step)
        update: dict[str, Any] = {"id": self.docId, "current_step": step, "pipeline_steps": self._steps()}
        if detail:
            # step_detail is not a column, so save_document merges it into extra and keeps content_hash there.
            update["step_detail"] = detail
        await db.save_document(update)

    async def skipIndexing(self) -> None:
        self.completed.add("indexed")
        await db.save_document({
            "id": self.docId, "current_step": "indexed",
            "pipeline_steps": {**self._steps(), "indexed": "skipped"}, "step_detail": INDEX_SKIPPED_DETAIL,
        })

    def _steps(self) -> dict[str, str]:
        return {step: "done" if step in self.completed else "pending" for step, _ in PIPELINE_STEPS}


async def _extractStep(docId: str, filePath: str, ext: str, progress: _Progress) -> str:
    await _pause("extracted")
    text = await asyncio.to_thread(extractText, filePath, ext)
    # The text is kept as sections too, so keyword search still finds the document when the vector index is down.
    sections = {f"chunk_{index}": chunk for index, chunk in enumerate(_chunks(text))} if _isContent(text) else {}
    await db.save_document({"id": docId, "char_count": len(text), "sections": sections})
    await progress.advance("extracted", f"{len(text):,} characters extracted")
    return text


async def _entitiesStep(docId: str, text: str, filename: str, progress: _Progress) -> dict[str, Any]:
    await _pause("entities")
    entities = await extractEntities(text, filename)
    await db.save_document({"id": docId, "entities": entities})
    await progress.advance("entities", f"{len(entities.get('equipment_ids', []))} equipment tag(s), "
                                       f"{len(entities.get('regulations', []))} regulation(s)")
    return entities


async def _graphStep(docId: str, filename: str, linked: dict[str, Any], progress: _Progress) -> None:
    await _pause("graph")
    counts = await doc_entity_mapper.map_and_store(docId, filename, linked)
    await db.update_graph_with_document(docId, filename, linked)
    await progress.advance("graph", doc_entity_mapper.format_summary(counts))


async def _indexStep(docId: str, filename: str, text: str, equipmentIds: list[str], documentType: str,
                     progress: _Progress) -> None:
    await _pause("indexed")
    chunks = _chunks(text)[:MAX_INDEXED_CHUNKS] if _isContent(text) else []
    for index, chunk in enumerate(chunks):
        await vs.index_document_section(doc_id=docId, doc_name=filename, section_id=f"chunk_{index}", text=chunk,
                                        equipment_ids=equipmentIds, doc_type=documentType)
    if await vs.is_active():
        await progress.advance("indexed", f"Vector indexed {len(chunks)} chunk(s) via Qdrant")
    else:
        await progress.skipIndexing()


def _chunks(text: str) -> list[str]:
    return [text[start:start + CHUNK_CHARS] for start in range(0, len(text), CHUNK_CHARS)]


def _isContent(text: str) -> bool:
    return bool(text) and not text.startswith(UNREADABLE_NOTE_START)


async def _pause(step: str) -> None:
    await asyncio.sleep(STEP_PAUSE_SECONDS[step])
