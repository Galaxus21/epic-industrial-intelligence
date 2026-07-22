"""
AI Operations Brain — Documents API
Full processing pipeline:
  1. Save file to disk
  2. Extract text (PyMuPDF for PDF, python-docx for DOCX, raw for txt/csv)
  3. LLM entity extraction (equipment IDs, people, regulations, symptoms)
  4. Knowledge graph update (append new entities to in-memory graph)
  5. Mark document as processed

Uses FastAPI BackgroundTasks so the upload returns immediately and steps
run asynchronously; the frontend polls GET /documents/{id} for progress.
"""
import hashlib
import os
import re
import uuid
import asyncio
import logging
from datetime import date
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.services import db_service as db
from app.services.llm_service import _get_client
from app.services import drawing_extractor
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".ppm", ".bmp", ".tiff", ".tif",
    ".gif", ".webp", ".xlsx", ".docx", ".txt", ".csv",
    ".json", ".pptx",
    # CAD / engineering drawing formats
    ".dxf", ".dwg", ".step", ".stp", ".iges", ".igs",
}

PIPELINE_STEPS = [
    ("saved",      "File saved"),
    ("extracted",  "Text extracted"),
    ("entities",   "Entities extracted"),
    ("drawing",    "Drawing extracted"),
    ("graph",      "Knowledge graph updated"),
    ("indexed",    "Vector index updated"),
]


class DocumentNameUpdate(BaseModel):
    name: str


class GenerateDocumentRequest(BaseModel):
    doc_type: str              # maintenance_record | safety_procedure | inspection_report | operating_instruction | project_file | incident_report
    equipment_id: str
    description: str           # user's natural language context
    extra_fields: dict = {}    # optional type-specific hints (e.g. technician, date)


class SaveGeneratedDocumentRequest(BaseModel):
    doc_type: str
    equipment_id: str
    title: str
    sections: dict             # section_key -> content string
    entities: dict             # equipment_ids, people, regulations, summary …


# ── Text extraction ──────────────────────────────────────────────────────────

def _extract_text(path: str, ext: str) -> str:
    """Extract raw text from an uploaded file. Returns up to 8 000 chars."""
    try:
        if ext == ".pdf":
            import fitz  # PyMuPDF
            doc = fitz.open(path)
            text = "\n".join(page.get_text() for page in doc)
            return text[:8000]
        if ext == ".docx":
            from docx import Document
            doc = Document(path)
            text = "\n".join(p.text for p in doc.paragraphs)
            return text[:8000]
        if ext in {".txt", ".csv"}:
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read(8000)
        if ext in {".png", ".jpg", ".jpeg", ".ppm", ".bmp", ".tiff", ".tif", ".gif", ".webp"}:
            # No embedded text in raster images — return a sentinel so the
            # pipeline can note the file type and proceed to filename-based
            # entity extraction.
            size_kb = os.path.getsize(path) // 1024
            return f"[IMAGE FILE — {ext.upper()[1:]} — {size_kb} KB — visual content only]"
        if ext == ".dxf":
            try:
                import ezdxf
                dxf_doc = ezdxf.readfile(path)
                lines: list[str] = []
                for entity in dxf_doc.modelspace():
                    if entity.dxftype() == "TEXT" and hasattr(entity.dxf, "text"):
                        t = (entity.dxf.text or "").strip()
                        if t:
                            lines.append(t)
                    elif entity.dxftype() == "MTEXT":
                        t = re.sub(r'\\[A-Za-z0-9;.]+|[{}]', "", entity.text or "").strip()
                        if t:
                            lines.append(t)
                layer_names = [la.dxf.name for la in dxf_doc.layers if not la.dxf.name.startswith("0")]
                lines.extend(layer_names[:20])
                return ("\n".join(lines) or f"[DXF CAD FILE — {os.path.getsize(path) // 1024} KB]")[:8000]
            except Exception:
                pass
            return f"[DXF CAD FILE — unreadable]"
        if ext == ".dwg":
            size_kb = os.path.getsize(path) // 1024
            return f"[DWG CAD FILE — {size_kb} KB — AutoCAD binary, entities inferred from filename]"
        if ext in {".step", ".stp"}:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    raw = f.read(4000)
                products = re.findall(r"PRODUCT\('([^']+)'", raw)
                header   = re.findall(r"FILE_DESCRIPTION\(\('([^']+)'", raw)
                info = "[STEP 3D CAD FILE]\n"
                if header:
                    info += f"Description: {header[0]}\n"
                if products:
                    info += "Products: " + ", ".join(products[:10]) + "\n"
                return (info + raw[:3000])[:8000]
            except Exception:
                pass
            return f"[STEP/STP 3D CAD FILE — {os.path.getsize(path) // 1024} KB]"
        if ext in {".iges", ".igs"}:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    raw_lines = [f.readline() for _ in range(30)]
                return ("[IGES 3D CAD FILE]\n" + "".join(raw_lines))[:8000]
            except Exception:
                pass
            return f"[IGES/IGS 3D CAD FILE — {os.path.getsize(path) // 1024} KB]"
        if ext == ".xlsx":
            try:
                import openpyxl
                wb = openpyxl.load_workbook(path, data_only=True)
                rows: list[str] = []
                for ws in wb.worksheets:
                    for row in ws.iter_rows(values_only=True):
                        rows.append("\t".join(str(c) for c in row if c is not None))
                return "\n".join(rows)[:8000]
            except Exception:
                pass
        if ext == ".json":
            try:
                import json as _json
                with open(path, encoding="utf-8", errors="replace") as f:
                    raw = f.read(8000)
                # Pretty-print up to 8 000 chars so the LLM can parse it
                obj = _json.loads(raw)
                return _json.dumps(obj, indent=2)[:8000]
            except Exception:
                try:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        return f.read(8000)
                except Exception:
                    pass
        if ext == ".pptx":
            try:
                from pptx import Presentation
                prs = Presentation(path)
                lines: list[str] = []
                for slide_num, slide in enumerate(prs.slides, 1):
                    lines.append(f"--- Slide {slide_num} ---")
                    for shape in slide.shapes:
                        if hasattr(shape, "text") and shape.text.strip():
                            lines.append(shape.text.strip())
                return "\n".join(lines)[:8000]
            except Exception:
                size_kb = os.path.getsize(path) // 1024
                return f"[PPTX PRESENTATION — {size_kb} KB — text extraction failed]"
    except Exception as exc:
        logger.warning("Text extraction failed for %s: %s", path, exc)
    return ""


# ── LLM entity extraction ────────────────────────────────────────────────────

_ENTITY_PROMPT = """You are an industrial document intelligence agent.
Extract ALL entities from the following industrial document text.
Return ONLY valid JSON — no markdown, no extra text.

Schema (include only arrays/objects actually present in the document; omit empty arrays):
{
  "equipment_ids": ["P-101"],
  "incident_ids":  ["INC-2022-034"],
  "people":        ["Rajesh Kumar"],
  "regulations":   ["OISD-117"],
  "symptoms":      ["vibration"],
  "measurements":  ["7.2 mm/s"],
  "dates":         ["2026-07-20"],
  "document_type": "manual|sop|inspection_report|incident_report|commissioning|drawing|work_order|project_file|other",
  "summary":       "one sentence summary",

  "equipment": [
    {"id": "P-101", "name": "Crude Oil Feed Pump", "type": "Centrifugal Pump",
     "location": "CDU Area", "status": "Operating|Shutdown|Standby|Fault",
     "manufacturer": "", "model": ""}
  ],
  "plants": [
    {"code": "CDU-01", "name": "Crude Distillation Unit",
     "type": "Process Unit", "location": "", "area": "", "project_code": ""}
  ],
  "projects": [
    {"code": "PRJ-001", "name": "Refinery Upgrade",
     "type": "Industrial|Shutdown|Turnaround", "phase": "Planning|Execution|Operations"}
  ],
  "incidents": [
    {"ref": "INC-2022-034", "title": "Pump bearing failure",
     "incident_type": "near_miss|first_aid|medical_treatment|lost_time|fatality|environmental|property_damage|fire|spill|other",
     "severity": "P1|P2|P3|P4|P5",
     "description": "", "equipment_ids": ["P-101"], "occurred_at": ""}
  ],
  "work_orders": [
    {"ref": "WO-2024-001", "title": "Bearing replacement",
     "category": "preventive|corrective|predictive|emergency|shutdown|modification",
     "priority": "low|medium|high|critical",
     "description": "", "equipment_ids": ["P-101"]}
  ],
  "inspections": [
    {"ref": "QI-2024-001", "title": "Quarterly pump inspection",
     "inspection_type": "equipment|process|safety_audit|environmental|contractor|pre_startup",
     "equipment_ids": ["P-101"], "scheduled_date": "", "findings": ""}
  ],
  "safety_procedures": [
    {"code": "SOP-PUMP-001", "title": "Pump isolation procedure",
     "doc_type": "SOP|JSA|SWMS|MSDS|ERP|Checklist|Work_Instruction",
     "category": "Mechanical|Electrical|Process|Civil",
     "risk_level": "Low|Medium|High|Critical", "equipment_ids": ["P-101"]}
  ],
  "defects": [
    {"description": "Seal leaking on P-101", "severity": "critical|major|minor",
     "equipment_id": "P-101", "location": ""}
  ],
  "sensors": [
    {"equipment_id": "P-101", "parameter": "vibration",
     "value": "7.2", "unit": "mm/s", "timestamp": ""}
  ]
}

DOCUMENT TEXT:
"""

_ENTITY_MOCK_PATTERNS = {
    "equipment_ids": re.compile(r"\b([A-Z]-\d{3}[A-Z]?)\b"),
    "incident_ids":  re.compile(r"\b(INC-\d{4}-\d{3})\b"),
    "measurements":  re.compile(r"\b(\d+\.?\d*\s*(?:mm/s|bar|kW|RPM|m3/hr|degC|°C|m3|A|kPa))\b"),
    "regulations":   re.compile(r"\b(OISD-\d+|ISO\s*\d+|API\s*\d+|SOP-[A-Z]-\d+)\b"),
}


async def _extract_entities(text: str, filename: str) -> dict:
    """Call GPT-4.1 for entity extraction; fall back to regex if unavailable."""
    if text and _get_client():
        try:
            client = _get_client()
            resp = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You extract structured entities from industrial documents."},
                    {"role": "user", "content": _ENTITY_PROMPT + text[:6000]},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=2000,
            )
            import json
            return json.loads(resp.choices[0].message.content)
        except Exception as exc:
            logger.warning("LLM entity extraction failed: %s", exc)

    # Regex fallback
    equipment = list({m.group(1) for m in _ENTITY_MOCK_PATTERNS["equipment_ids"].finditer(text)})
    incidents  = list({m.group(1) for m in _ENTITY_MOCK_PATTERNS["incident_ids"].finditer(text)})
    measures   = list({m.group(1) for m in _ENTITY_MOCK_PATTERNS["measurements"].finditer(text)})[:6]
    regs       = list({m.group(1) for m in _ENTITY_MOCK_PATTERNS["regulations"].finditer(text)})

    # Infer doc type from filename
    fname = filename.lower()
    if any(k in fname for k in ("sop", "procedure", "operation")):
        doc_type = "sop"
    elif any(k in fname for k in ("pid", "drawing", "p&id", "schematic",
                                   ".dxf", ".dwg", ".stp", ".iges", ".igs")):
        doc_type = "drawing"
    elif any(k in fname for k in ("incident", "inc-", "rca")):
        doc_type = "incident_report"
    elif any(k in fname for k in ("commission", "startup", "handover")):
        doc_type = "commissioning"
    elif any(k in fname for k in ("inspection", "survey")):
        doc_type = "inspection_report"
    elif any(k in fname for k in ("manual", "oem", "vendor")):
        doc_type = "manual"
    elif any(k in fname for k in ("work_order", "workorder", "wo-")):
        doc_type = "work_order"
    elif any(k in fname for k in ("project", "prj-")):
        doc_type = "project_file"
    else:
        doc_type = "other"

    # Build structured entity lists from regex matches for the new entity types
    equipment_objs = [{"id": eid} for eid in equipment]
    incidents_objs = [
        {"ref": iid, "incident_type": "other", "severity": "P5", "equipment_ids": equipment}
        for iid in incidents
    ]
    sensor_objs = [
        {"equipment_id": equipment[0], "parameter": "reading", "value": m, "unit": ""}
        for m in measures[:3] if equipment
    ]

    return {
        "equipment_ids": equipment,
        "incident_ids":  incidents,
        "people":        [],
        "regulations":   regs,
        "symptoms":      [],
        "measurements":  measures,
        "dates":         [],
        "document_type": doc_type,
        "summary":       f"Document extracted via pattern matching. {len(equipment)} equipment tag(s), {len(regs)} regulation(s) found.",
        # Structured entities for the entity mapper
        "equipment":          equipment_objs,
        "plants":             [],
        "projects":           [],
        "incidents":          incidents_objs,
        "work_orders":        [],
        "inspections":        [] if doc_type != "inspection_report" else [
            {"title": filename, "inspection_type": "equipment", "equipment_ids": equipment}
        ],
        "safety_procedures":  [] if doc_type != "sop" else [
            {"code": re.sub(r"[^A-Z0-9\-]", "", filename.upper())[:20] or "SOP-DOC",
             "title": filename, "doc_type": "SOP", "equipment_ids": equipment}
        ],
        "defects":            [],
        "sensors":            sensor_objs,
    }


# ── Background pipeline ──────────────────────────────────────────────────────

async def _run_pipeline(doc_id: str, file_path: str, ext: str, filename: str):
    completed: set[str] = set()

    async def _advance(step: str, detail: str = ""):
        completed.add(step)
        update = {
            "id": doc_id,
            "current_step": step,
            # Mark all completed steps as "done", rest stay "pending"
            "pipeline_steps": {s: "done" if s in completed else "pending" for s, _ in PIPELINE_STEPS},
        }
        if detail:
            # Use a non-column key so _split_extra routes it through _apply_upsert's
            # merge path — preserves other extra fields (e.g. content_hash)
            update["step_detail"] = detail
        await db.save_document(update)

    try:
        await asyncio.sleep(0.3)
        await _advance("saved", f"Saved {os.path.getsize(file_path):,} bytes")

        await asyncio.sleep(0.5)
        text = _extract_text(file_path, ext)
        await db.save_document({"id": doc_id, "char_count": len(text)})
        await _advance("extracted", f"{len(text):,} characters extracted")

        await asyncio.sleep(0.8)
        entities = await _extract_entities(text, filename)
        eq_count = len(entities.get("equipment_ids", []))
        await db.save_document({"id": doc_id, "entities": entities})
        await _advance("entities", f"{eq_count} equipment tag(s), {len(entities.get('regulations', []))} regulation(s)")

        # ── Drawing extraction (async, non-blocking) ──────────────────────
        doc_type  = entities.get("document_type", "other")
        has_drawing = False
        if drawing_extractor.should_extract(ext, doc_type):
            try:
                svg_path = await drawing_extractor.extract_drawing_as_svg(
                    file_path=file_path,
                    ext=ext,
                    doc_id=doc_id,
                    doc_name=filename,
                    doc_type=doc_type,
                    entities=entities,
                    text_content=text,
                )
                has_drawing = svg_path is not None
                await _advance("drawing", "SVG drawing generated")
            except Exception as exc:
                logger.warning("Drawing extraction failed for %s: %s", doc_id, exc)
                await _advance("drawing", "Drawing extraction skipped")
        else:
            completed.add("drawing")  # mark skipped so pipeline looks complete

        await asyncio.sleep(0.4)
        # Map all structured entities to proper DB tables + graph relationships
        from app.services import doc_entity_mapper as _mapper
        mapping_counts = await _mapper.map_and_store(doc_id, filename, entities)
        # Also run the legacy path to ensure equipment_ids get linked (backward compat)
        await db.update_graph_with_document(doc_id, filename, entities)
        graph_detail = _mapper.format_summary(mapping_counts)
        await _advance("graph", graph_detail)

        await asyncio.sleep(0.3)
        # ── Qdrant vector indexing ────────────────────────────────────────
        from app.services import vector_service as vs
        eq_ids = entities.get("equipment_ids", [])
        doc_summary = entities.get("summary", "")
        # Index each section of the document for semantic retrieval
        idx_count = 0
        full_text = text or doc_summary
        if full_text and not full_text.startswith("["):
            # Split into ~600-char chunks and index each
            chunk_size = 600
            chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]
            for i, chunk in enumerate(chunks[:10]):  # cap at 10 chunks per doc
                await vs.index_document_section(
                    doc_id=doc_id,
                    doc_name=filename,
                    section_id=f"chunk_{i}",
                    text=chunk,
                    equipment_ids=eq_ids,
                    doc_type=doc_type,
                )
                idx_count += 1
        qdrant_active = await vs.is_active()
        await _advance("indexed", f"Vector indexed {idx_count} chunk(s) {'via Qdrant' if qdrant_active else '(Qdrant unavailable — skipped)'}")

        await db.save_document({
            "id": doc_id,
            "status": "processed",
            "type": doc_type,
            "current_step": "done",
            "equipment_ids": entities.get("equipment_ids", []),
            "has_drawing": has_drawing,
        })

    except Exception as exc:
        logger.error("Pipeline failed for %s: %s", doc_id, exc)
        await db.save_document({"id": doc_id, "status": "failed", "extra": {"error": str(exc)}})


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


@router.get("/drawings-list")
async def list_documents_with_drawings():
    """Return documents that have an extracted SVG drawing."""
    docs = await db.list_all_documents()
    result = []
    for d in docs:
        extra = d.get("extra") or {}
        has_drawing = d.get("has_drawing") or extra.get("has_drawing", False)
        svg_file = drawing_extractor.svg_path_for(d["id"])
        if has_drawing or os.path.exists(svg_file):
            result.append({
                "id":            d["id"],
                "name":          d["name"],
                "type":          d.get("type", "drawing"),
                "equipment_ids": d.get("equipment_ids") or [],
                "date":          d.get("date", ""),
            })
    return result


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
async def generate_document_endpoint(req: "GenerateDocumentRequest"):
    """Stream AI document generation as Server-Sent Events.
    Steps: context → generating → complete (returns full document JSON).
    """
    from app.services.llm_service import generate_document as llm_generate

    async def _stream():
        import json as _json
        yield f"data: {_json.dumps({'step': 'context', 'message': 'Loading equipment context…'})}\n\n"
        eq = await db.get_equipment(req.equipment_id) or {}
        records = await db.get_maintenance_records(req.equipment_id)
        maintenance_ctx = {
            "recent_records": records[:5],
            "health_score": eq.get("health_score"),
            "current_readings": eq.get("current_readings", {}),
        }
        yield f"data: {_json.dumps({'step': 'generating', 'message': 'AI is drafting the document…'})}\n\n"
        generated = await llm_generate(
            doc_type=req.doc_type,
            equipment_context=eq,
            maintenance_context=maintenance_ctx,
            user_description=req.description,
            extra_fields=req.extra_fields or {},
        )
        yield f"data: {_json.dumps({'step': 'complete', 'document': generated})}\n\n"
        yield "data: [DONE]\n\n"

    from fastapi.responses import StreamingResponse as _SR
    return _SR(_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


@router.post("/save-generated", status_code=201)
async def save_generated_document(req: "SaveGeneratedDocumentRequest"):
    """Persist an AI-generated document to the knowledge base.
    The document is immediately queryable by the agent pipeline.
    """
    doc_id = f"GEN-{uuid.uuid4().hex[:8].upper()}"
    today = date.today().isoformat()
    eq_ids = req.entities.get("equipment_ids") or ([req.equipment_id] if req.equipment_id else [])

    pipeline_done = {s: "done" for s, _ in PIPELINE_STEPS}

    await db.save_document({
        "id": doc_id,
        "name": req.title,
        "type": req.doc_type,
        "equipment_ids": eq_ids,
        "date": today,
        "status": "processed",
        "sections": req.sections,
        "entities": req.entities,
        "pipeline_steps": pipeline_done,
        "current_step": "done",
        "char_count": sum(len(v) for v in req.sections.values()),
    })
    await db.update_graph_with_document(doc_id, req.title, req.entities)

    return {"id": doc_id, "name": req.title, "type": req.doc_type, "status": "processed", "date": today}


@router.get("/{doc_id}")
async def get_document_status(doc_id: str):
    doc = await db.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.patch("/{doc_id}")
async def update_document_name(doc_id: str, body: DocumentNameUpdate):
    """Rename a document."""
    doc = await db.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.save_document({"id": doc_id, "name": body.name.strip()})
    return await db.get_document(doc_id)


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str):
    """Delete document record, files, and all knowledge graph nodes/links for this document."""
    doc = await db.get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    # ── Knowledge graph cleanup ──────────────────────────────────────────────
    await db.remove_graph_node_and_links(doc_id)
    doc_name = doc.get("name", "")
    eq_ids = doc.get("equipment_ids") or []
    if doc_name and eq_ids:
        await db.remove_document_from_equipment(doc_name, eq_ids)
    # ── File cleanup ─────────────────────────────────────────────────────────
    svg_path = drawing_extractor.svg_path_for(doc_id)
    if os.path.exists(svg_path):
        try:
            os.remove(svg_path)
        except OSError:
            pass
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
    equipment_id: str = "",
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not supported")

    doc_id = f"UPLOAD-{uuid.uuid4().hex[:8].upper()}"
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")

    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()
    with open(file_path, "wb") as f:
        f.write(content)

    initial = {
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
        "content_hash": content_hash,
    }
    await db.save_document(initial)

    background_tasks.add_task(_run_pipeline, doc_id, file_path, ext, file.filename or "")

    return {"doc_id": doc_id, "status": "processing", "message": "Pipeline started"}


@router.get("/{doc_id}/drawing")
async def get_document_drawing(doc_id: str):
    """Serve the extracted SVG drawing for a document."""
    svg_file = drawing_extractor.svg_path_for(doc_id)
    if not os.path.exists(svg_file):
        raise HTTPException(status_code=404, detail="No drawing found for this document")
    return FileResponse(
        svg_file,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )

