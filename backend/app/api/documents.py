"""
AI Operations Brain — Documents API
Upload, list, search, rename and delete documents, and draft new ones with the chat model.

An upload returns at once; FastAPI BackgroundTasks runs the processing pipeline (app/services/documentPipeline.py:
saved, extracted, entities, graph, indexed) and the frontend polls GET /documents/{id} for progress. The file's text
is read by documentText.py and its entities by documentEntities.py; the request bodies are in documentRequests.py.
"""
import hashlib
import os
import uuid
import logging
from datetime import date
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from app.api.documentRequests import (
    AI_DRAFT_ORIGIN, MAX_DRAFT_SECTION_CHARS, DocumentNameUpdate, GenerateDocumentRequest,
    SaveGeneratedDocumentRequest,
)
from app.api.eventStream import eventStreamResponse
from app.core.auth import get_current_user, require_roles
from app.core.roles import APPROVER_ROLES
from app.db import models as m
from app.services import db_service as db
from app.services.documentCleanup import removeDocumentIncidents, renameDocumentOnEquipment
from app.services.documentEntities import extractEntities as _extract_entities
from app.services.documentPipeline import PIPELINE_STEPS
from app.services.documentPipeline import runPipeline as _run_pipeline
from app.services.documentPipeline import splitKnownEquipment as _splitKnownEquipment
from app.services.documentText import extractText as _extract_text
from app.services.kb_ingestion import appWrittenPipelineSteps
from app.services.sensorReadings import removeDocumentReadings

# Names this module exported before the pipeline, text and entity code moved out; callers still import them here.
__all__ = [
    "router", "AI_DRAFT_ORIGIN", "MAX_DRAFT_SECTION_CHARS", "MAX_UPLOAD_BYTES", "PIPELINE_STEPS", "UPLOAD_DIR",
    "GenerateDocumentRequest", "SaveGeneratedDocumentRequest", "_extract_entities", "_extract_text", "_run_pipeline",
    "_splitKnownEquipment",
]

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".csv", ".json",
}

BYTES_PER_MB = 1024 * 1024
MAX_UPLOAD_BYTES = 50 * BYTES_PER_MB

generationUnavailableMessage = (
    "AI is unavailable: set OPENAI_API_KEY, or run Ollama with OLLAMA_CHAT_MODEL pulled, to generate documents. "
    "Nothing was generated."
)
generatedNotIndexedDetail = "Generated documents are not added to the vector index"


# ── API endpoints ────────────────────────────────────────────────────────────

@router.get("")
async def list_documents():
    """Return all documents from the database."""
    docs = await db.list_all_documents()
    return [
        {
            "id": d["id"], "name": d["name"], "type": d["type"],
            "equipment_ids": d.get("equipment_ids") or [],
            "status": d.get("status", "processed"),
            "date": d.get("date", ""),
        }
        for d in docs
    ]


@router.get("/search")
async def search_documents(
    query: str,
    equipment_id: str | None = None,
    limit: int = 6,
):
    """Semantic search for document sections with explicit degradation payload."""
    from app.services import vector_service as vs
    return await vs.search_relevant_docs(query, equipment_id=equipment_id, limit=limit)


@router.get("/check-duplicate")
async def check_duplicate_document(filename: str = "", content_hash: str = ""):
    """Return existing documents that share the same filename or SHA-256 content hash."""
    docs = await db.list_all_documents()
    fname_lower = filename.strip().lower()
    matches = []
    for doc in docs:
        doc_name = (doc.get("name") or "").strip().lower()
        doc_hash = doc.get("content_hash", "")
        name_match = bool(fname_lower and doc_name == fname_lower)
        hash_match = bool(content_hash and doc_hash and doc_hash == content_hash)
        if name_match or hash_match:
            matches.append({
                "id": doc["id"],
                "name": doc.get("name", ""),
                "type": doc.get("type", "other"),
                "date": doc.get("date", ""),
                "match_reason": "content" if hash_match else "name",
            })
    return {"matches": matches}


@router.post("/generate")
async def generate_document_endpoint(
    req: "GenerateDocumentRequest",
    user: m.UserProfile = Depends(get_current_user),
):
    """Stream AI document generation as Server-Sent Events.
    Steps: context → generating → complete (the document JSON), or error when no model answered.
    """
    eq = await db.get_equipment(req.equipment_id)
    if not eq:
        raise HTTPException(status_code=404, detail=f"Equipment '{req.equipment_id}' not found")

    from app.services.llm_service import generate_document as llm_generate

    async def _stream():
        import json as _json
        yield f"data: {_json.dumps({'step': 'context', 'message': 'Loading equipment context…'})}\n\n"
        brain = await db.get_equipment_brain(req.equipment_id)
        yield f"data: {_json.dumps({'step': 'generating', 'message': 'AI is drafting the document…'})}\n\n"
        generated = await llm_generate(
            doc_type=req.doc_type,
            equipment_context=brain,
            user_description=req.description,
            extra_fields=req.extra_fields or {},
        )
        if generated is None:
            yield f"data: {_json.dumps({'step': 'error', 'message': generationUnavailableMessage})}\n\n"
        else:
            yield f"data: {_json.dumps({'step': 'complete', 'document': generated})}\n\n"
        yield "data: [DONE]\n\n"

    return eventStreamResponse(_stream())


@router.post("/save-generated", status_code=201)
async def save_generated_document(
    req: "SaveGeneratedDocumentRequest",
    user: m.UserProfile = Depends(get_current_user),
):
    doc_id = f"GEN-{uuid.uuid4().hex[:8].upper()}"
    today = date.today().isoformat()
    eq_ids = req.entities.get("equipment_ids") or ([req.equipment_id] if req.equipment_id else [])
    if not isinstance(eq_ids, list):
        raise HTTPException(status_code=422, detail="entities.equipment_ids must be a list")

    # Only equipment that exists is linked: a draft is never allowed to register equipment, whatever
    # AUTO_REGISTER_ENTITIES says, because registration is a supervisor or manager action (POST /api/v1/equipment).
    knownEqIds, unresolvedEqIds = await _splitKnownEquipment([str(eqId) for eqId in eq_ids])
    await db.update_graph_with_document(doc_id, req.title, {**req.entities, "equipment_ids": knownEqIds})
    await db.save_document({
        "id": doc_id,
        "name": req.title,
        "type": req.doc_type,
        "equipment_ids": knownEqIds,
        "unresolved_equipment_ids": unresolvedEqIds,
        "date": today,
        "status": "processed",
        "sections": req.sections,
        "entities": req.entities,
        "origin": AI_DRAFT_ORIGIN,
        "saved_by": user.name,
        "pipeline_steps": dict(appWrittenPipelineSteps),
        "current_step": "done",
        "step_detail": generatedNotIndexedDetail,
        "char_count": sum(len(v) for v in req.sections.values()),
    })

    return {"id": doc_id, "name": req.title, "type": req.doc_type, "status": "processed", "date": today}


@router.get("/{doc_id}")
async def get_document_status(doc_id: str):
    doc = await db.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.patch("/{doc_id}")
async def update_document_name(
    doc_id: str,
    body: DocumentNameUpdate,
    user: m.UserProfile = Depends(require_roles(*APPROVER_ROLES)),
):
    """Rename a document, and the filename its equipment lists it under (source_documents)."""
    doc = await db.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    newName = body.name.strip()
    await db.save_document({"id": doc_id, "name": newName})
    await renameDocumentOnEquipment(doc.get("name", ""), newName, doc.get("equipment_ids") or [])
    return await db.get_document(doc_id)


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    user: m.UserProfile = Depends(require_roles(*APPROVER_ROLES)),
):
    """Delete the document record, its file, its vector index points, its graph node and links, its filename on
    linked equipment, the incidents and defects it created (with their graph nodes and vectors) and the sensor
    readings extracted from it, so search can no longer cite it and no chart shows its figures."""
    doc = await db.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    # ── Vector index cleanup (Qdrant points must not outlive the source) ─────
    from app.services import vector_service as vs
    await vs.delete_document_points(doc_id)
    # ── Knowledge graph cleanup ──────────────────────────────────────────────
    await db.remove_graph_node_and_links(doc_id)
    await removeDocumentIncidents(doc_id)
    await removeDocumentReadings(doc_id)
    doc_name = doc.get("name", "")
    eq_ids = doc.get("equipment_ids") or []
    if doc_name and eq_ids:
        await db.remove_document_from_equipment(doc_name, eq_ids)
    # ── File cleanup ─────────────────────────────────────────────────────────
    file_path = doc.get("file_path")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass
    await db.delete_document(doc_id)


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    equipment_id: str = Form(""),
    user: m.UserProfile = Depends(get_current_user),
):
    """Store a document and process it in the background. `equipment_id`, a form field beside the file, names the
    registered equipment the document is about; it stays linked whatever tags the text itself names."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not supported")
    if equipment_id and await db.get_equipment(equipment_id) is None:
        raise HTTPException(status_code=404, detail=f"Equipment '{equipment_id}' not found")

    doc_id = f"UPLOAD-{uuid.uuid4().hex[:8].upper()}"
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")

    content = await _boundedContent(file)
    with open(file_path, "wb") as f:
        f.write(content)

    await db.save_document({
        "id": doc_id,
        "name": file.filename or "unknown_file",
        "type": "uploaded",
        "equipment_ids": [equipment_id] if equipment_id else [],
        "status": "processing",
        "date": date.today().isoformat(),
        "current_step": "saved",
        "pipeline_steps": {s: "pending" for s, _ in PIPELINE_STEPS},
        "file_path": file_path,
        "entities": None,
        "content_hash": hashlib.sha256(content).hexdigest(),
    })

    background_tasks.add_task(_run_pipeline, doc_id, file_path, ext, file.filename or "", equipment_id)

    return {"doc_id": doc_id, "status": "processing", "message": "Pipeline started"}


async def _boundedContent(file: UploadFile) -> bytes:
    """The uploaded bytes; 413 when they exceed MAX_UPLOAD_BYTES, checked on the declared size first, then on what
    was actually read."""
    tooLarge = HTTPException(status_code=413,
                             detail=f"File exceeds maximum size of {MAX_UPLOAD_BYTES // BYTES_PER_MB} MB")
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise tooLarge
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise tooLarge
    return content

