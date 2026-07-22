"""
AI Operations Brain — Engineering Drawing Service
Handles upload storage, format detection, async SVG extraction,
and live analytics computation per plant/site.

Supported input formats
────────────────────────
Raster images : PNG, JPG/JPEG, TIFF/TIF, BMP, WebP, GIF
Vector        : SVG (served as-is)
Document      : PDF  (first page rasterised with PyMuPDF → GPT-4V)
CAD vector    : DXF  (ezdxf → dark-theme SVG)
CAD native    : DWG  (ezdxf best-effort; placeholder if unsupported)
3-D / BIM     : STEP, STP, IGES, IGS, IFC, DGN (info-only placeholder)

Extraction pipeline
────────────────────
1. detect_format(filename) → canonical format string
2. process_drawing(drawing_id, file_path, format) → updates DB record
   a. SVG  → copy to extracted_svg_path as-is
   b. DXF  → _dxf_to_svg()  → dark P&ID SVG
   c. Image/PDF → drawing_extractor.extract_drawing_as_svg()
   d. Other → _info_placeholder_svg()
3. compute_analytics(plant_id) → dict of incident/PTW/WO counts
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select

from app.db.database import AsyncSessionLocal
from app.db import models as m

logger = logging.getLogger(__name__)

# ─── storage paths ─────────────────────────────────────────────────────────────
ENG_DRAWINGS_DIR = "uploads/eng_drawings"
os.makedirs(ENG_DRAWINGS_DIR, exist_ok=True)

# ─── format taxonomy ───────────────────────────────────────────────────────────
RASTER_EXTS     = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp", ".gif"}
VECTOR_SVG      = {".svg"}
PDF_EXT         = {".pdf"}
DXF_EXT         = {".dxf"}
DWG_EXT         = {".dwg"}
THREED_EXTS     = {".step", ".stp", ".iges", ".igs", ".ifc", ".dgn"}
ALL_SUPPORTED   = RASTER_EXTS | VECTOR_SVG | PDF_EXT | DXF_EXT | DWG_EXT | THREED_EXTS


def detect_format(filename: str) -> str:
    """Return a canonical lowercase format string (without leading dot)."""
    ext = os.path.splitext(filename)[1].lower()
    mapping = {
        ".png": "png", ".jpg": "jpg", ".jpeg": "jpg",
        ".tiff": "tiff", ".tif": "tiff", ".bmp": "bmp",
        ".webp": "webp", ".gif": "gif",
        ".svg": "svg",
        ".pdf": "pdf",
        ".dxf": "dxf",
        ".dwg": "dwg",
        ".step": "step", ".stp": "step",
        ".iges": "iges", ".igs": "iges",
        ".ifc": "ifc",
        ".dgn": "dgn",
    }
    return mapping.get(ext, "unknown")


def original_path(drawing_id: str, fmt: str) -> str:
    """Filesystem path for storing the original uploaded file."""
    return os.path.join(ENG_DRAWINGS_DIR, f"{drawing_id}_orig.{fmt}")


def svg_path(drawing_id: str) -> str:
    """Filesystem path for the extracted/rendered SVG."""
    return os.path.join(ENG_DRAWINGS_DIR, f"{drawing_id}.svg")


# ─── async extraction entry point ──────────────────────────────────────────────

async def process_drawing(drawing_id: str) -> None:
    """
    Background task: extract SVG from the uploaded drawing file and
    update the Drawing DB record with results.
    """
    async with AsyncSessionLocal() as db:
        row: Optional[m.Drawing] = await db.get(m.Drawing, drawing_id)
        if not row:
            return

        row.status = "processing"
        row.extraction_status = "processing"
        await db.commit()

        try:
            svg_out = await _extract_svg(row)
            if svg_out and os.path.exists(svg_out):
                row.extracted_svg_path = svg_out
                row.extraction_status = "done"
                row.status = "ready"
            else:
                row.extraction_status = "failed"
                row.extraction_error = "Extraction returned no output"
                row.status = "failed"
        except Exception as exc:
            logger.exception("Drawing extraction failed for %s", drawing_id)
            row.extraction_status = "failed"
            row.extraction_error = str(exc)[:400]
            row.status = "failed"

        row.updated_at = datetime.utcnow()
        await db.commit()


async def _extract_svg(row: m.Drawing) -> Optional[str]:
    """Dispatch to the right extractor for the given format."""
    fmt  = row.file_format
    src  = row.file_path
    dest = svg_path(row.id)

    if not src or not os.path.exists(src):
        raise FileNotFoundError(f"Source file not found: {src}")

    # ── SVG: copy as-is ──────────────────────────────────────────────────────
    if fmt == "svg":
        shutil.copy2(src, dest)
        return dest

    # ── DXF: ezdxf → SVG ─────────────────────────────────────────────────────
    if fmt == "dxf":
        return await asyncio.to_thread(_dxf_to_svg, src, dest)

    # ── DWG: try ezdxf recovery; fall back to placeholder ────────────────────
    if fmt == "dwg":
        try:
            return await asyncio.to_thread(_dwg_to_svg, src, dest, row.title)
        except Exception as exc:
            logger.warning("DWG conversion failed, using placeholder: %s", exc)
            _write_svg(dest, _info_placeholder_svg(row.title, "DWG", "Native DWG — limited preview"))
            return dest

    # ── 3-D / BIM formats: info placeholder ──────────────────────────────────
    if fmt in {"step", "iges", "ifc", "dgn"}:
        label = fmt.upper()
        _write_svg(dest, _info_placeholder_svg(row.title, label, f"{label} 3-D / BIM format — viewer not available"))
        return dest

    # ── Raster images + PDF: reuse drawing_extractor (GPT-4V vision) ─────────
    if fmt in {*{f.lstrip(".") for f in RASTER_EXTS}, "pdf"}:
        ext = "." + fmt if fmt != "jpg" else ".jpg"
        # Map canonical format back to a dot-extension
        fmt_to_ext = {
            "png": ".png", "jpg": ".jpg", "tiff": ".tiff",
            "bmp": ".bmp", "webp": ".webp", "gif": ".gif", "pdf": ".pdf",
        }
        dot_ext = fmt_to_ext.get(fmt, "." + fmt)
        from app.services.drawing_extractor import extract_drawing_as_svg
        result = await extract_drawing_as_svg(
            file_path=src,
            ext=dot_ext,
            doc_id=row.id,
            doc_name=row.title,
            doc_type=row.drawing_type or "drawing",
        )
        # drawing_extractor saves to uploads/drawings/{id}.svg; we copy to our dir
        if result and os.path.exists(result):
            shutil.copy2(result, dest)
        elif result:
            return result
        return dest if os.path.exists(dest) else result

    # ── Unknown format ────────────────────────────────────────────────────────
    _write_svg(dest, _info_placeholder_svg(row.title, fmt.upper(), f"Format {fmt.upper()} — preview not supported"))
    return dest


# ─── DXF → SVG via ezdxf ──────────────────────────────────────────────────────

def _dxf_to_svg(src: str, dest: str) -> str:
    """Convert a DXF file to a dark-themed SVG using ezdxf 1.4.x API."""
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend, layout as dxf_layout
    from ezdxf.addons.drawing.svg import SVGBackend
    from ezdxf.addons.drawing.config import Configuration

    doc = ezdxf.readfile(src)
    msp = doc.modelspace()

    backend = SVGBackend()
    config  = Configuration.defaults()
    ctx     = RenderContext(doc)
    fe      = Frontend(ctx, backend, config=config)
    fe.draw_layout(msp, finalize=True)

    # ezdxf 1.4.x: get_string(page) replaces the old get_xml_document()
    page    = dxf_layout.Page.from_dxf_layout(msp)
    raw_svg = backend.get_string(page)

    _apply_dark_theme(raw_svg, dest_path=dest)
    return dest


def _dwg_to_svg(src: str, dest: str, title: str) -> str:
    """Attempt DWG via ezdxf ODA recovery; raises if unavailable."""
    import ezdxf
    doc = ezdxf.readfile(src)
    msp = doc.modelspace()

    from ezdxf.addons.drawing import RenderContext, Frontend, layout as dxf_layout
    from ezdxf.addons.drawing.svg import SVGBackend
    from ezdxf.addons.drawing.config import Configuration

    backend = SVGBackend()
    ctx     = RenderContext(doc)
    fe      = Frontend(ctx, backend, config=Configuration.defaults())
    fe.draw_layout(msp, finalize=True)

    # ezdxf 1.4.x: get_string(page) replaces get_xml_document()
    page    = dxf_layout.Page.from_dxf_layout(msp)
    raw_svg = backend.get_string(page)
    _apply_dark_theme(raw_svg, dest_path=dest)
    return dest


def _apply_dark_theme(raw_svg: str, dest_path: str) -> str:
    """
    Wrap the ezdxf-produced SVG in a dark container and save.
    Returns dest_path.
    """
def _apply_dark_theme(raw_svg: str, dest_path: str) -> str:
    """
    Inject dark theme CSS into a complete SVG produced by ezdxf.
    ezdxf 1.4.x returns a full <?xml…><svg …>…</svg> document.
    We insert a <style> block and a background rect after the opening <svg> tag.
    """
    dark_style = (
        '<style>'
        'svg{background:#0f0f0f}'
        'line,path,polyline,rect:not(.bg),circle,ellipse{'
        'stroke:#d4d4d4;fill:none}'
        'text{fill:#d4d4d4;font-family:monospace}'
        'polygon{stroke:#d4d4d4;fill:none}'
        '</style>'
    )

    # Insert the <style> block right after the opening <svg …> tag
    # Find the first closing '>' that ends the <svg ...> tag
    insert_pos = raw_svg.find(">", raw_svg.find("<svg"))
    if insert_pos != -1:
        themed = raw_svg[:insert_pos + 1] + dark_style + raw_svg[insert_pos + 1:]
    else:
        themed = raw_svg  # fallback — shouldn't happen

    _write_svg(dest_path, themed)
    return dest_path


# ─── placeholder SVGs ──────────────────────────────────────────────────────────

def _info_placeholder_svg(title: str, fmt: str, note: str) -> str:
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_note  = note.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_fmt   = fmt.replace("&", "&amp;")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500"
     style="background:#0f0f0f; font-family: 'Courier New', monospace;">
  <!-- Grid background -->
  <defs>
    <pattern id="g" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1a1a1a" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="800" height="500" fill="url(#g)"/>

  <!-- Format badge -->
  <rect x="20" y="20" width="80" height="30" rx="6" fill="#1f1f1f" stroke="#3b82f6" stroke-width="1.5"/>
  <text x="60" y="40" text-anchor="middle" font-size="13" font-weight="bold" fill="#3b82f6">{safe_fmt}</text>

  <!-- Title -->
  <text x="400" y="200" text-anchor="middle" font-size="22" font-weight="bold" fill="#f9f9f9">{safe_title}</text>

  <!-- Note -->
  <text x="400" y="240" text-anchor="middle" font-size="13" fill="#6b7280">{safe_note}</text>

  <!-- Icon -->
  <rect x="340" y="280" width="120" height="100" rx="8" fill="none" stroke="#374151" stroke-width="1.5"/>
  <text x="400" y="350" text-anchor="middle" font-size="48" fill="#374151">&#128196;</text>
</svg>"""


def _write_svg(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


# ─── analytics ────────────────────────────────────────────────────────────────

async def compute_analytics(plant_id: Optional[str], project_id: Optional[str]) -> dict:
    """
    Return live counts of operational events for a plant / project scope.
    Returns all-zero dict when no scope is provided (no plant_id or project_id).
    """
    # Bug fix: return zeros immediately when no scope filter is available
    # Without a filter, queries would count ALL records in the DB (wrong)
    if not plant_id and not project_id:
        return {
            "incident_count": 0, "open_incident_count": 0,
            "high_severity_incidents": 0, "last_incident_date": None,
            "active_ptw_count": 0, "total_ptw_count": 0,
            "open_wo_count": 0, "open_inspection_count": 0,
            "risk_score": 0, "computed_at": datetime.utcnow().isoformat(),
        }

    async with AsyncSessionLocal() as db:
        filters_plant   = [m.IncidentReport.plant_id == plant_id]   if plant_id   else []
        filters_proj    = [m.IncidentReport.project_id == project_id] if project_id else []
        base_filter     = filters_plant or filters_proj

        # ── incident counts ──────────────────────────────────────────────────
        inc_total = await db.scalar(
            select(func.count(m.IncidentReport.id)).where(*base_filter)
        ) or 0

        inc_open = await db.scalar(
            select(func.count(m.IncidentReport.id)).where(
                *(filters_plant or filters_proj),
                m.IncidentReport.status.notin_(["closed"])
            )
        ) or 0

        inc_p1p2 = await db.scalar(
            select(func.count(m.IncidentReport.id)).where(
                *(filters_plant or filters_proj),
                m.IncidentReport.severity.in_(["P1", "P2"])
            )
        ) or 0

        # Latest incident date
        last_inc_row = await db.scalar(
            select(m.IncidentReport.occurred_at).where(
                *(filters_plant or filters_proj)
            ).order_by(m.IncidentReport.occurred_at.desc()).limit(1)
        )

        # ── active PTWs ──────────────────────────────────────────────────────
        ptw_filter = (
            [m.PermitToWork.plant_id == plant_id] if plant_id
            else [m.PermitToWork.project_id == project_id] if project_id
            else []
        )
        active_ptw = await db.scalar(
            select(func.count(m.PermitToWork.id)).where(
                *ptw_filter,
                m.PermitToWork.status.in_(["issued", "active"])
            )
        ) or 0 if ptw_filter else 0

        total_ptw = await db.scalar(
            select(func.count(m.PermitToWork.id)).where(*ptw_filter)
        ) or 0 if ptw_filter else 0

        # ── open work orders ─────────────────────────────────────────────────
        wo_filter = (
            [m.ManagedWorkOrder.plant_id == plant_id] if plant_id
            else [m.ManagedWorkOrder.project_id == project_id] if project_id
            else []
        )
        open_wo = await db.scalar(
            select(func.count(m.ManagedWorkOrder.id)).where(
                *wo_filter,
                m.ManagedWorkOrder.status.notin_(["closed", "cancelled", "verified"])
            )
        ) or 0 if wo_filter else 0

        # ── open inspections ─────────────────────────────────────────────────
        insp_filter = (
            [m.QualityInspection.plant_id == plant_id] if plant_id
            else [m.QualityInspection.project_id == project_id] if project_id
            else []
        )
        open_insp = await db.scalar(
            select(func.count(m.QualityInspection.id)).where(
                *insp_filter,
                m.QualityInspection.status.notin_(
                    ["closed_satisfactory", "closed_with_findings", "rejected"]
                )
            )
        ) or 0 if insp_filter else 0

    # Risk score: simple heuristic (0–100)
    risk = min(100, inc_p1p2 * 20 + inc_open * 5 + active_ptw * 3)

    return {
        "incident_count":        inc_total,
        "open_incident_count":   inc_open,
        "high_severity_incidents": inc_p1p2,
        "last_incident_date":    last_inc_row,
        "active_ptw_count":      active_ptw,
        "total_ptw_count":       total_ptw,
        "open_wo_count":         open_wo,
        "open_inspection_count": open_insp,
        "risk_score":            risk,
        "computed_at":           datetime.utcnow().isoformat(),
    }
