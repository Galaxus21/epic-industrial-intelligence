"""
AI Operations Brain — Engineering Drawings API
Full CRUD for project-scoped engineering drawings with:
  • Multi-format upload  (PNG, JPG, TIFF, BMP, WebP, GIF, PDF, SVG, DXF, DWG, STEP, IGES, IFC, DGN)
  • Async SVG extraction (GPT-4V vision for images/PDF; ezdxf for DXF/DWG)
  • Per-plant/site analytics (incidents, active PTWs, open work orders, inspections)
  • Hierarchy filtering: all | by project_id | by plant_id

Endpoints
─────────
GET    /                              list drawings (filter by project_id / plant_id)
POST   /upload                        multipart file upload → starts background extraction
GET    /{id}                          drawing detail
PATCH  /{id}                          update metadata
DELETE /{id}                          delete drawing + stored files
GET    /{id}/view                     serve the extracted SVG (or original if SVG/image)
GET    /{id}/analytics                live analytics for the drawing's plant
POST   /{id}/extract                  re-trigger SVG extraction
GET    /projects/tree                 project → plant tree (for navigation)
"""
import asyncio
import os
import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db import models as m
from app.services.drawing_service import (
    detect_format,
    original_path,
    svg_path,
    process_drawing,
    compute_analytics,
    ENG_DRAWINGS_DIR,
    THREED_EXTS,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class DrawingUpdate(BaseModel):
    title: Optional[str] = None
    drawing_number: Optional[str] = None
    revision: Optional[str] = None
    drawing_type: Optional[str] = None
    discipline: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    project_id: Optional[str] = None
    plant_id: Optional[str] = None


def _row_to_dict(row: m.Drawing) -> dict:
    return {
        "id":                  row.id,
        "drawing_number":      row.drawing_number,
        "title":               row.title,
        "revision":            row.revision,
        "drawing_type":        row.drawing_type,
        "discipline":          row.discipline,
        "description":         row.description,
        "tags":                row.tags or [],
        "project_id":          row.project_id,
        "plant_id":            row.plant_id,
        "original_filename":   row.original_filename,
        "file_format":         row.file_format,
        "file_size":           row.file_size,
        "status":              row.status,
        "extraction_status":   row.extraction_status,
        "extraction_error":    row.extraction_error,
        "has_svg":             bool(row.extracted_svg_path and os.path.exists(row.extracted_svg_path)),
        "analytics":           row.analytics,
        "analytics_updated_at": row.analytics_updated_at.isoformat() if row.analytics_updated_at else None,
        "created_by":          row.created_by,
        "created_at":          row.created_at.isoformat(),
        "updated_at":          row.updated_at.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# List
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_drawings(
    project_id: Optional[str] = Query(None),
    plant_id:   Optional[str] = Query(None),
):
    async with AsyncSessionLocal() as db:
        q = select(m.Drawing)
        if plant_id:
            q = q.where(m.Drawing.plant_id == plant_id)
        elif project_id:
            q = q.where(m.Drawing.project_id == project_id)
        q = q.order_by(m.Drawing.created_at.desc())
        rows = (await db.execute(q)).scalars().all()
    return [_row_to_dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Project → Plant tree  (for hierarchy navigator)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects/tree")
async def get_projects_tree():
    """Return [{id, code, name, plants:[{id, code, name, drawing_count}]}]."""
    async with AsyncSessionLocal() as db:
        projects = (await db.execute(select(m.Project).order_by(m.Project.name))).scalars().all()
        plants   = (await db.execute(select(m.Plant).order_by(m.Plant.name))).scalars().all()
        drawings = (await db.execute(select(m.Drawing.plant_id))).scalars().all()

    plant_drawing_count: dict[str, int] = {}
    for pid in drawings:
        if pid:
            plant_drawing_count[pid] = plant_drawing_count.get(pid, 0) + 1

    plant_by_project: dict[str, list] = {}
    for pl in plants:
        key = pl.project_id or "__unassigned__"
        plant_by_project.setdefault(key, []).append({
            "id":            pl.id,
            "code":          pl.code,
            "name":          pl.name,
            "drawing_count": plant_drawing_count.get(pl.id, 0),
        })

    result = []
    for proj in projects:
        result.append({
            "id":     proj.id,
            "code":   proj.code,
            "name":   proj.name,
            "plants": plant_by_project.get(proj.id, []),
        })
    # Unassigned plants
    if "__unassigned__" in plant_by_project:
        result.append({
            "id":     "__unassigned__",
            "code":   "—",
            "name":   "Unassigned",
            "plants": plant_by_project["__unassigned__"],
        })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/upload", status_code=201)
async def upload_drawing(
    background_tasks: BackgroundTasks,
    file:           UploadFile = File(...),
    drawing_number: str        = Form(...),
    title:          str        = Form(...),
    revision:       str        = Form("A"),
    drawing_type:   str        = Form("general"),
    discipline:     str        = Form(None),
    description:    str        = Form(None),
    tags:           str        = Form(""),       # comma-separated
    project_id:     str        = Form(None),
    plant_id:       str        = Form(None),
    created_by:     str        = Form(None),
):
    fmt = detect_format(file.filename or "")
    if fmt == "unknown":
        raise HTTPException(422, f"Unsupported file format: {file.filename}")

    drawing_id = str(uuid.uuid4())
    dest_path  = original_path(drawing_id, fmt)

    # Save file to disk
    os.makedirs(ENG_DRAWINGS_DIR, exist_ok=True)
    contents = await file.read()
    with open(dest_path, "wb") as fh:
        fh.write(contents)

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    async with AsyncSessionLocal() as db:
        row = m.Drawing(
            id=drawing_id,
            drawing_number=drawing_number.strip(),
            title=title.strip(),
            revision=revision or "A",
            drawing_type=drawing_type or "general",
            discipline=discipline or None,
            description=description or None,
            tags=tag_list,
            project_id=project_id or None,
            plant_id=plant_id or None,
            original_filename=file.filename or "",
            file_path=dest_path,
            file_format=fmt,
            file_size=len(contents),
            status="uploaded",
            extraction_status="pending",
            created_by=created_by or None,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        data = _row_to_dict(row)

    # Kick off extraction in background
    background_tasks.add_task(process_drawing, drawing_id)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Get / Update / Delete
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{drawing_id}")
async def get_drawing(drawing_id: str):
    async with AsyncSessionLocal() as db:
        row = await db.get(m.Drawing, drawing_id)
    if not row:
        raise HTTPException(404, "Drawing not found")
    return _row_to_dict(row)


@router.patch("/{drawing_id}")
async def update_drawing(drawing_id: str, body: DrawingUpdate):
    async with AsyncSessionLocal() as db:
        row = await db.get(m.Drawing, drawing_id)
        if not row:
            raise HTTPException(404, "Drawing not found")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(row, field, value)
        row.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(row)
        return _row_to_dict(row)


@router.delete("/{drawing_id}", status_code=204)
async def delete_drawing(drawing_id: str):
    async with AsyncSessionLocal() as db:
        row = await db.get(m.Drawing, drawing_id)
        if not row:
            raise HTTPException(404, "Drawing not found")
        # Remove stored files
        for path in [row.file_path, row.extracted_svg_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        await db.delete(row)
        await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# View  (serve SVG / image)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{drawing_id}/view")
async def view_drawing(drawing_id: str):
    """
    Serve the best available visual for a drawing:
    1. Extracted SVG (all formats after processing)
    2. Original file if it is already an SVG or raster image
    3. A processing-state placeholder SVG
    """
    async with AsyncSessionLocal() as db:
        row = await db.get(m.Drawing, drawing_id)
    if not row:
        raise HTTPException(404, "Drawing not found")

    # 1. Extracted SVG
    if row.extracted_svg_path and os.path.exists(row.extracted_svg_path):
        return FileResponse(row.extracted_svg_path, media_type="image/svg+xml")

    # 2. Original SVG
    if row.file_format == "svg" and row.file_path and os.path.exists(row.file_path):
        return FileResponse(row.file_path, media_type="image/svg+xml")

    # 3. Original raster image (serve directly so the viewer shows something)
    raster_map = {
        "png": "image/png", "jpg": "image/jpeg", "tiff": "image/tiff",
        "bmp": "image/bmp", "webp": "image/webp", "gif": "image/gif",
    }
    if row.file_format in raster_map and row.file_path and os.path.exists(row.file_path):
        return FileResponse(row.file_path, media_type=raster_map[row.file_format])

    # 4. Placeholder while processing
    status_labels = {
        "pending":    "Queued for extraction…",
        "processing": "Extracting drawing…",
        "failed":     f"Extraction failed: {row.extraction_error or 'unknown error'}",
        "unsupported": "Format not supported for preview",
    }
    msg   = status_labels.get(row.extraction_status, "Preparing drawing…")
    safe  = row.title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_msg = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    svg   = f"""<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500"
     style="background:#0f0f0f; font-family: 'Courier New', monospace;">
  <defs>
    <pattern id="g" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1a1a1a" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="800" height="500" fill="url(#g)"/>
  <text x="400" y="220" text-anchor="middle" font-size="20" font-weight="bold" fill="#f9f9f9">{safe}</text>
  <text x="400" y="260" text-anchor="middle" font-size="13" fill="#6b7280">{safe_msg}</text>
  <text x="400" y="295" text-anchor="middle" font-size="11" fill="#374151">{row.file_format.upper()} · {row.drawing_number}</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")


# ─────────────────────────────────────────────────────────────────────────────
# Analytics
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{drawing_id}/analytics")
async def get_drawing_analytics(drawing_id: str):
    async with AsyncSessionLocal() as db:
        row = await db.get(m.Drawing, drawing_id)
    if not row:
        raise HTTPException(404, "Drawing not found")

    data = await compute_analytics(row.plant_id, row.project_id)

    # Cache result in drawing record
    async with AsyncSessionLocal() as db:
        row2 = await db.get(m.Drawing, drawing_id)
        if row2:
            row2.analytics = data
            row2.analytics_updated_at = datetime.utcnow()
            await db.commit()

    return data


# ─────────────────────────────────────────────────────────────────────────────
# Re-extract
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{drawing_id}/extract")
async def re_extract_drawing(drawing_id: str, background_tasks: BackgroundTasks):
    async with AsyncSessionLocal() as db:
        row = await db.get(m.Drawing, drawing_id)
        if not row:
            raise HTTPException(404, "Drawing not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(422, "Original file not found on disk")
        row.status = "uploaded"
        row.extraction_status = "pending"
        row.extraction_error = None
        await db.commit()

    background_tasks.add_task(process_drawing, drawing_id)
    return {"message": "Extraction queued", "drawing_id": drawing_id}
