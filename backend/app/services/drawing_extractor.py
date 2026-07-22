"""
AI Operations Brain — Drawing Extractor Service (v2)
Two-pass pipeline for faithful P&ID / schematic SVG generation:

  Pass 1 — Structure extraction
    GPT-4.1 vision analyzes the image and returns structured JSON:
    equipment list, instrument bubbles, pipe connections, annotations.

  Pass 2 — Programmatic SVG rendering
    The JSON is converted to a high-quality dark-theme SVG using
    standard P&ID symbol shapes (pumps, vessels, HX, instruments …).

Fallback: entity-based placeholder when the LLM is unavailable.

SVGs are saved to  uploads/drawings/{doc_id}.svg
and served via     GET /api/v1/documents/{doc_id}/drawing
"""
import base64
import io
import json
import logging
import math
import os
from typing import Optional

logger = logging.getLogger(__name__)

DRAWINGS_DIR = "uploads/drawings"
os.makedirs(DRAWINGS_DIR, exist_ok=True)

DRAWING_TYPES = {"drawing", "pid", "schematic", "p&id", "cad"}
IMAGE_EXTS    = {".png", ".jpg", ".jpeg", ".webp", ".gif",
                 ".tiff", ".tif", ".bmp", ".ppm"}
CAD_EXTS      = {".dxf", ".dwg", ".step", ".stp", ".iges", ".igs"}

# ─── canvas geometry ──────────────────────────────────────────────────────────
_W, _H          = 1000, 640          # SVG canvas
_PAD_L, _PAD_R  = 50,   50
_PAD_T, _PAD_B  = 90,   60
_AW = _W - _PAD_L - _PAD_R          # usable width  = 900
_AH = _H - _PAD_T - _PAD_B          # usable height = 490


# ─── structure-extraction prompt ─────────────────────────────────────────────
_STRUCTURE_PROMPT = """\
You are an expert P&ID (Piping & Instrumentation Diagram) analyzer.
Carefully study the engineering drawing and extract its key structural elements.

Return ONLY valid JSON — no markdown, no explanation — matching this exact schema:
{
  "title": "visible drawing title or null",
  "drawing_type": "pid|pfd|schematic|electrical|hvac|mechanical|other",
  "equipment": [
    {
      "id":    "visible equipment tag (e.g. P-101); generate E-N if none found",
      "type":  "pump|compressor|vessel|heat_exchanger|column|tank|valve|reactor|filter|blower|other",
      "label": "human-readable label if visible, else null",
      "rx":    0.0,
      "ry":    0.0
    }
  ],
  "instruments": [
    {
      "id":   "instrument tag (FIC-101, PIC-201 …)",
      "type": "FIC|PIC|TIC|LIC|FT|PT|TT|LT|PDT|PSV|FCV|PCV|TCV|other",
      "rx":   0.0,
      "ry":   0.0
    }
  ],
  "connections": [
    {
      "from_id":  "source id",
      "to_id":    "destination id",
      "fluid":    "crude|water|steam|gas|oil|air|chemical|other",
      "line_type":"main|utility|drain|signal"
    }
  ],
  "key_annotations": ["up to 8 important text labels visible on the drawing"]
}

Rules:
- rx and ry are relative positions 0.0 (left/top) to 1.0 (right/bottom)
- Capture ALL visible equipment tags and instrument bubbles
- Only include connections you can clearly see traced in the drawing
- If this is not an engineering drawing return:
  {"drawing_type":"other","equipment":[],"instruments":[],"connections":[],\
"key_annotations":["not a technical drawing"]}
"""


def svg_path_for(doc_id: str) -> str:
    return os.path.join(DRAWINGS_DIR, f"{doc_id}.svg")


def should_extract(ext: str, doc_type: str) -> bool:
    return (
        doc_type.lower() in DRAWING_TYPES
        or ext.lower() in IMAGE_EXTS
        or ext.lower() in CAD_EXTS
        or (ext.lower() == ".pdf" and doc_type.lower() in DRAWING_TYPES | {"other", "manual"})
    )


# ─── public entry point ───────────────────────────────────────────────────────

async def extract_drawing_as_svg(
    file_path: str,
    ext: str,
    doc_id: str,
    doc_name: str,
    doc_type: str,
    entities: Optional[dict] = None,
    text_content: str = "",
) -> Optional[str]:
    entities  = entities or {}
    structure = None
    svg       = None
    ext_lower = ext.lower()

    # ── CAD path ──────────────────────────────────────────────────────────────
    if ext_lower == ".dxf":
        try:
            structure = _parse_dxf_structure(file_path, doc_name)
        except Exception as exc:
            logger.warning("DXF parse failed for %s: %s", doc_id, exc)
    elif ext_lower in CAD_EXTS:
        # DWG / STEP / IGES — no open renderer; use a styled CAD placeholder
        svg = _cad_placeholder_svg(doc_name, ext_lower, entities)

    # ── LLM vision path (images / PDF) ────────────────────────────────────────
    if svg is None and structure is None:
        try:
            from app.services.llm_service import _get_client
            client = _get_client()
            if client and (ext_lower in IMAGE_EXTS or ext_lower == ".pdf"):
                img_b64, mime = await _to_image_b64(file_path, ext)
                if img_b64:
                    structure = await _extract_structure(client, img_b64, mime, doc_name)
        except Exception as exc:
            logger.warning("Structure extraction failed for %s: %s", doc_id, exc)

    if svg is None:
        if structure and (structure.get("equipment") or structure.get("instruments")):
            svg = _render_pid_svg(structure, doc_name, doc_type)
        else:
            svg = _placeholder_svg(doc_name, doc_type, entities, text_content)

    out = svg_path_for(doc_id)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    logger.info("Drawing SVG saved: %s", out)
    return out


# ─── image conversion & compression ──────────────────────────────────────────

async def _to_image_b64(file_path: str, ext: str) -> tuple[Optional[str], str]:
    ext = ext.lower()
    try:
        raw: Optional[bytes] = None

        if ext == ".pdf":
            import fitz
            doc  = fitz.open(file_path)
            if not doc:
                return None, ""
            page = doc[0]
            # 200 DPI for sharp text/symbols
            pix  = page.get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72))
            raw  = pix.tobytes("png")

        elif ext in {".jpg", ".jpeg"}:
            with open(file_path, "rb") as f:
                raw = f.read()

        elif ext in {".png", ".webp", ".gif"}:
            with open(file_path, "rb") as f:
                raw = f.read()

        else:
            try:
                from PIL import Image as PILImage
                img = PILImage.open(file_path).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                raw = buf.getvalue()
            except Exception:
                return None, ""

        if raw is None:
            return None, ""

        # Resize/compress: cap at 1800px wide, encode as JPEG ≤ 90% quality
        raw = _resize_and_compress(raw, max_dim=1800)
        return base64.b64encode(raw).decode(), "image/jpeg"

    except Exception as exc:
        logger.warning("Image conversion failed for %s: %s", file_path, exc)
    return None, ""


def _resize_and_compress(raw: bytes, max_dim: int = 1800) -> bytes:
    """Resize to max_dim on longest side and re-encode as JPEG for API efficiency."""
    try:
        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(raw)).convert("RGB")
        w, h = img.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            img   = img.resize((int(w * scale), int(h * scale)), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
    except Exception:
        return raw          # return original if Pillow unavailable


# ─── pass 1 — structure extraction ───────────────────────────────────────────

async def _extract_structure(
    client, img_b64: str, mime: str, doc_name: str
) -> Optional[dict]:
    from app.core.config import settings
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": f"Document: {doc_name}\n\n{_STRUCTURE_PROMPT}"},
                    {"type": "image_url",
                     "image_url": {
                         "url": f"data:{mime};base64,{img_b64}",
                         "detail": "high",
                     }},
                ],
            }],
            response_format={"type": "json_object"},
            max_tokens=2000,
            temperature=0,
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception as exc:
        logger.warning("_extract_structure error: %s", exc)
    return None


# ─── pass 2 — programmatic P&ID SVG renderer ─────────────────────────────────

# Equipment type → (color, symbol_fn_name)
_EQ_STYLE: dict[str, tuple[str, str]] = {
    "pump":           ("#f59e0b", "pump"),
    "compressor":     ("#a855f7", "compressor"),
    "vessel":         ("#3b82f6", "vessel"),
    "heat_exchanger": ("#06b6d4", "heat_exchanger"),
    "column":         ("#3b82f6", "column"),
    "tank":           ("#3b82f6", "tank"),
    "valve":          ("#f97316", "valve"),
    "reactor":        ("#10b981", "reactor"),
    "filter":         ("#f59e0b", "filter"),
    "blower":         ("#a855f7", "pump"),      # same shape as pump
    "other":          ("#6b7280", "generic"),
}

_FLUID_COLOR: dict[str, str] = {
    "crude":    "#f59e0b",
    "oil":      "#f59e0b",
    "steam":    "#ef4444",
    "water":    "#3b82f6",
    "gas":      "#10b981",
    "air":      "#a0a0a0",
    "chemical": "#a855f7",
    "signal":   "#10b981",
    "other":    "#4b5563",
}


def _render_pid_svg(structure: dict, doc_name: str, doc_type: str) -> str:
    title   = structure.get("title") or doc_name
    equip   = structure.get("equipment",    [])[:16]
    instrs  = structure.get("instruments",  [])[:20]
    conns   = structure.get("connections",  [])
    annots  = structure.get("key_annotations", [])[:6]
    dtype   = (structure.get("drawing_type") or doc_type or "drawing").upper()

    # Build id → pixel position map
    pos: dict[str, tuple[float, float]] = {}
    for eq in equip:
        x = _PAD_L + float(eq.get("rx", 0.5)) * _AW
        y = _PAD_T + float(eq.get("ry", 0.5)) * _AH
        pos[eq["id"]] = (x, y)
    for ins in instrs:
        x = _PAD_L + float(ins.get("rx", 0.5)) * _AW
        y = _PAD_T + float(ins.get("ry", 0.5)) * _AH
        pos[ins["id"]] = (x, y)

    parts: list[str] = []

    # ── SVG header ────────────────────────────────────────────────────────────
    parts.append(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_W} {_H}" width="{_W}" height="{_H}">\n'
    )
    parts.append(
        '  <defs>\n'
        '    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">'
        '<path d="M40 0L0 0 0 40" fill="none" stroke="#1a1a1a" stroke-width="0.4"/></pattern>\n'
    )
    # One arrow marker per fluid color
    seen_colors: set[str] = set()
    for c in conns:
        col = _FLUID_COLOR.get(c.get("fluid", "other"), "#4b5563")
        if col not in seen_colors:
            mid = col.replace("#", "arr")
            parts.append(
                f'    <marker id="{mid}" markerWidth="8" markerHeight="6" '
                f'refX="7" refY="3" orient="auto">'
                f'<polygon points="0 0,8 3,0 6" fill="{col}"/></marker>\n'
            )
            seen_colors.add(col)
    parts.append('  </defs>\n')

    # background
    parts.append(
        f'  <rect width="{_W}" height="{_H}" fill="#0a0a0a"/>\n'
        f'  <rect width="{_W}" height="{_H}" fill="url(#grid)"/>\n'
    )

    # title bar
    t_esc = _esc(title[:70])
    parts.append(
        f'  <rect x="0" y="0" width="{_W}" height="68" fill="#111"/>\n'
        f'  <line x1="0" y1="68" x2="{_W}" y2="68" stroke="#2a2a2a" stroke-width="1"/>\n'
        f'  <text x="20" y="30" font-family="\'Courier New\',Courier,monospace" '
        f'font-size="15" font-weight="bold" fill="#f9f9f9" letter-spacing="1">{t_esc}</text>\n'
        f'  <text x="20" y="52" font-family="\'Courier New\',Courier,monospace" '
        f'font-size="9" fill="#4b5563" letter-spacing="2">{doc_name[:80]}</text>\n'
        f'  <rect x="{_W - 130}" y="10" width="110" height="26" rx="4" '
        f'fill="#181818" stroke="#f59e0b" stroke-width="1"/>\n'
        f'  <text x="{_W - 75}" y="28" text-anchor="middle" '
        f'font-family="\'Courier New\',Courier,monospace" font-size="9" font-weight="bold" '
        f'fill="#f59e0b" letter-spacing="2">{_esc(dtype[:12])}</text>\n'
    )

    # ── connections (drawn first so nodes appear on top) ──────────────────────
    for c in conns:
        fid, tid = c.get("from_id", ""), c.get("to_id", "")
        if fid not in pos or tid not in pos:
            continue
        x1, y1 = pos[fid]
        x2, y2 = pos[tid]
        fluid   = c.get("fluid", "other")
        ltype   = c.get("line_type", "main")
        col     = _FLUID_COLOR.get(fluid, "#4b5563")
        mid     = col.replace("#", "arr")
        dash    = "4,3" if ltype in ("utility", "drain") else ("2,2" if ltype == "signal" else "none")
        sw      = "1.5" if ltype == "main" else "1"
        da_attr = f' stroke-dasharray="{dash}"' if dash != "none" else ""
        # Orthogonal routing: go horizontal then vertical
        mx = (x1 + x2) / 2
        d  = f"M {x1:.1f} {y1:.1f} L {mx:.1f} {y1:.1f} L {mx:.1f} {y2:.1f} L {x2:.1f} {y2:.1f}"
        parts.append(
            f'  <path d="{d}" fill="none" stroke="{col}" stroke-width="{sw}"'
            f'{da_attr} marker-end="url(#{mid})" opacity="0.8"/>\n'
        )
        # fluid label at midpoint
        lbl = c.get("fluid", "")
        if lbl and lbl != "other":
            lx, ly = mx, (y1 + y2) / 2 - 5
            parts.append(
                f'  <text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                f'font-family="\'Courier New\',Courier,monospace" font-size="8" '
                f'fill="{col}" opacity="0.7">{_esc(lbl)}</text>\n'
            )

    # ── equipment symbols ─────────────────────────────────────────────────────
    for eq in equip:
        eid   = eq["id"]
        etype = eq.get("type", "other")
        label = eq.get("label") or eid
        col, sym = _EQ_STYLE.get(etype, ("#6b7280", "generic"))
        x, y  = pos[eid]
        parts.append(_draw_equipment(sym, x, y, col, eid, label[:18]))

    # ── instrument bubbles ────────────────────────────────────────────────────
    for ins in instrs:
        iid   = ins["id"]
        itype = ins.get("type", "other")
        x, y  = pos[iid]
        col   = "#10b981" if itype.endswith(("C", "V")) else "#34d399"
        parts.append(_draw_instrument(x, y, col, iid[:8]))

    # ── key annotations ───────────────────────────────────────────────────────
    for i, ann in enumerate(annots[:6]):
        ax = 20 + (i % 3) * 330
        ay = _H - _PAD_B + 14 + (i // 3) * 18
        parts.append(
            f'  <text x="{ax}" y="{ay}" font-family="\'Courier New\',Courier,monospace" '
            f'font-size="9" fill="#525252">{_esc(ann[:50])}</text>\n'
        )

    # ── legend ────────────────────────────────────────────────────────────────
    parts.append(_build_legend())

    # footer
    parts.append(
        f'  <text x="{_W // 2}" y="{_H - 6}" text-anchor="middle" '
        f'font-family="\'Courier New\',Courier,monospace" font-size="7" '
        f'fill="#222" letter-spacing="2">AI OPERATIONS BRAIN — DRAWING EXTRACTION</text>\n'
        f'</svg>'
    )
    return "".join(parts)


# ─── P&ID symbol renderers ────────────────────────────────────────────────────

def _draw_equipment(sym: str, cx: float, cy: float, col: str, tag: str, label: str) -> str:
    tag_e   = _esc(tag[:8])
    label_e = _esc(label)
    # Tag label above, description below
    header  = (
        f'  <text x="{cx:.1f}" y="{cy - 40:.1f}" text-anchor="middle" '
        f'font-family="\'Courier New\',Courier,monospace" font-size="10" font-weight="bold" '
        f'fill="{col}">{tag_e}</text>\n'
    )
    footer_ = (
        f'  <text x="{cx:.1f}" y="{cy + 42:.1f}" text-anchor="middle" '
        f'font-family="\'Courier New\',Courier,monospace" font-size="8" '
        f'fill="#6b7280">{label_e}</text>\n'
    )

    if sym == "pump":
        # Circle with internal right-pointing triangle
        r   = 26
        pts = (f"{cx},{cy - r * 0.55} "
               f"{cx + r * 0.6},{cy + r * 0.4} "
               f"{cx - r * 0.6},{cy + r * 0.4}")
        body = (
            f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" '
            f'fill="#181818" stroke="{col}" stroke-width="2"/>\n'
            f'  <polygon points="{pts}" fill="none" stroke="{col}" stroke-width="1.2"/>\n'
        )
    elif sym == "compressor":
        r    = 26
        body = (
            f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" '
            f'fill="#181818" stroke="{col}" stroke-width="2"/>\n'
            f'  <line x1="{cx-r*0.6:.1f}" y1="{cy-r*0.6:.1f}" '
            f'x2="{cx+r*0.6:.1f}" y2="{cy+r*0.6:.1f}" stroke="{col}" stroke-width="1.2"/>\n'
            f'  <line x1="{cx+r*0.6:.1f}" y1="{cy-r*0.6:.1f}" '
            f'x2="{cx-r*0.6:.1f}" y2="{cy+r*0.6:.1f}" stroke="{col}" stroke-width="1.2"/>\n'
        )
    elif sym == "heat_exchanger":
        w, h = 60, 36
        x0, y0 = cx - w / 2, cy - h / 2
        body = (
            f'  <rect x="{x0:.1f}" y="{y0:.1f}" width="{w}" height="{h}" '
            f'fill="#181818" stroke="{col}" stroke-width="2"/>\n'
            f'  <line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x0+w:.1f}" y2="{y0+h:.1f}" '
            f'stroke="{col}" stroke-width="1" opacity="0.5"/>\n'
            f'  <line x1="{x0+w:.1f}" y1="{y0:.1f}" x2="{x0:.1f}" y2="{y0+h:.1f}" '
            f'stroke="{col}" stroke-width="1" opacity="0.5"/>\n'
            # inlet/outlet nozzles
            f'  <line x1="{x0-10:.1f}" y1="{cy-8:.1f}" x2="{x0:.1f}" y2="{cy-8:.1f}" '
            f'stroke="{col}" stroke-width="1.5"/>\n'
            f'  <line x1="{x0+w:.1f}" y1="{cy+8:.1f}" x2="{x0+w+10:.1f}" y2="{cy+8:.1f}" '
            f'stroke="{col}" stroke-width="1.5"/>\n'
        )
    elif sym in ("vessel", "reactor"):
        w, h = 50, 60
        x0, y0 = cx - w / 2, cy - h / 2
        body = (
            f'  <rect x="{x0:.1f}" y="{y0:.1f}" width="{w}" height="{h}" rx="6" '
            f'fill="#181818" stroke="{col}" stroke-width="2"/>\n'
            f'  <ellipse cx="{cx:.1f}" cy="{y0:.1f}" rx="{w/2:.1f}" ry="8" '
            f'fill="#181818" stroke="{col}" stroke-width="1.5"/>\n'
            f'  <ellipse cx="{cx:.1f}" cy="{y0+h:.1f}" rx="{w/2:.1f}" ry="8" '
            f'fill="#181818" stroke="{col}" stroke-width="1.5"/>\n'
        )
    elif sym == "column":
        w, h = 32, 80
        x0, y0 = cx - w / 2, cy - h / 2
        body = (
            f'  <rect x="{x0:.1f}" y="{y0:.1f}" width="{w}" height="{h}" '
            f'fill="#181818" stroke="{col}" stroke-width="2"/>\n'
            f'  <ellipse cx="{cx:.1f}" cy="{y0:.1f}" rx="{w/2:.1f}" ry="7" '
            f'fill="#181818" stroke="{col}" stroke-width="1.5"/>\n'
            f'  <ellipse cx="{cx:.1f}" cy="{y0+h:.1f}" rx="{w/2:.1f}" ry="7" '
            f'fill="#181818" stroke="{col}" stroke-width="1.5"/>\n'
            # tray lines
            + "".join(
                f'  <line x1="{x0:.1f}" y1="{y0 + 16*i:.1f}" '
                f'x2="{x0+w:.1f}" y2="{y0 + 16*i:.1f}" '
                f'stroke="{col}" stroke-width="0.6" opacity="0.4"/>\n'
                for i in range(1, 5)
                if y0 + 16 * i < y0 + h
            )
        )
    elif sym in ("tank",):
        w, h = 60, 52
        x0, y0 = cx - w / 2, cy - h / 2
        body = (
            f'  <rect x="{x0:.1f}" y="{y0:.1f}" width="{w}" height="{h}" '
            f'fill="#181818" stroke="{col}" stroke-width="2"/>\n'
            f'  <ellipse cx="{cx:.1f}" cy="{y0:.1f}" rx="{w/2:.1f}" ry="9" '
            f'fill="#181818" stroke="{col}" stroke-width="1.5"/>\n'
        )
    elif sym == "valve":
        s  = 18
        pts = (f"{cx-s},{cy-s} {cx+s},{cy+s} {cx+s},{cy-s} {cx-s},{cy+s}")
        body = (
            f'  <polygon points="{pts}" fill="#181818" stroke="{col}" stroke-width="2"/>\n'
        )
    elif sym == "filter":
        w, h = 40, 32
        x0, y0 = cx - w / 2, cy - h / 2
        body = (
            f'  <rect x="{x0:.1f}" y="{y0:.1f}" width="{w}" height="{h}" rx="4" '
            f'fill="#181818" stroke="{col}" stroke-width="2"/>\n'
            + "".join(
                f'  <line x1="{x0 + 6*i:.1f}" y1="{y0:.1f}" '
                f'x2="{x0 + 6*i:.1f}" y2="{y0+h:.1f}" '
                f'stroke="{col}" stroke-width="0.8" opacity="0.5"/>\n'
                for i in range(1, 7)
            )
        )
    else:  # generic
        r    = 24
        body = (
            f'  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" '
            f'fill="#181818" stroke="{col}" stroke-width="1.8"/>\n'
        )

    return header + body + footer_


def _draw_instrument(x: float, y: float, col: str, tag: str) -> str:
    r = 16
    return (
        f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" '
        f'fill="#0f1a12" stroke="{col}" stroke-width="1.5" stroke-dasharray="4,2"/>\n'
        f'  <text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" '
        f'font-family="\'Courier New\',Courier,monospace" font-size="8" '
        f'fill="{col}">{_esc(tag)}</text>\n'
    )


def _build_legend() -> str:
    items = [
        ("#f59e0b", "Pump"),
        ("#06b6d4", "Heat Exchanger"),
        ("#3b82f6", "Vessel / Column"),
        ("#f97316", "Valve"),
        ("#10b981", "Instrument"),
        ("#a855f7", "Compressor"),
    ]
    y0 = _H - 44
    parts = [
        f'  <rect x="0" y="{y0 - 2}" width="{_W}" height="44" fill="#111"/>\n'
        f'  <line x1="0" y1="{y0 - 2}" x2="{_W}" y2="{y0 - 2}" '
        f'stroke="#2a2a2a" stroke-width="0.5"/>\n'
    ]
    for i, (col, lbl) in enumerate(items):
        lx = 30 + i * 162
        parts.append(
            f'  <circle cx="{lx + 6}" cy="{y0 + 14}" r="5" '
            f'fill="#181818" stroke="{col}" stroke-width="1.5"/>\n'
            f'  <text x="{lx + 16}" y="{y0 + 18}" '
            f'font-family="\'Courier New\',Courier,monospace" font-size="8" '
            f'fill="{col}">{lbl}</text>\n'
        )
    return "".join(parts)


# ─── entity-based placeholder (no LLM) ───────────────────────────────────────

_ACCENT: dict[str, str] = {
    "drawing": "#f59e0b", "pid": "#f97316", "schematic": "#3b82f6",
    "p&id": "#f97316",    "manual": "#a855f7", "sop": "#10b981",
    "inspection_report": "#ef4444", "incident_report": "#ef4444",
    "cad": "#06b6d4",
}


def _placeholder_svg(
    doc_name: str,
    doc_type: str,
    entities: dict,
    text_content: str = "",
) -> str:
    accent  = _ACCENT.get(doc_type.lower(), "#6b7280")
    equip   = entities.get("equipment_ids", [])[:8]
    regs    = entities.get("regulations",   [])[:4]
    summary = (entities.get("summary", "") or "")[:120]
    display = (doc_name[:56] + "…") if len(doc_name) > 56 else doc_name
    dtype   = doc_type.upper()

    # arrange equipment nodes
    nodes: list[tuple[str, float, float]] = []
    if equip:
        n  = len(equip)
        cx, cy = _W / 2, _H / 2 + 20
        if n == 1:
            nodes = [(equip[0], cx, cy)]
        elif n <= 5:
            for i, eq in enumerate(equip):
                x = _PAD_L + 60 + i * ((_AW - 60) / max(n - 1, 1))
                nodes.append((eq, x, cy))
        else:
            r = min(_AW, _AH) * 0.35
            for i, eq in enumerate(equip):
                a = -math.pi / 2 + 2 * math.pi * i / n
                nodes.append((eq, cx + r * math.cos(a), cy + r * math.sin(a)))

    parts: list[str] = []
    parts.append(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_W} {_H}" width="{_W}" height="{_H}">\n'
        f'  <defs>\n'
        f'    <marker id="arr" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">'
        f'<polygon points="0 0,8 3,0 6" fill="{accent}"/></marker>\n'
        f'    <pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse">'
        f'<circle cx="1" cy="1" r="0.7" fill="#1a1a1a"/></pattern>\n'
        f'  </defs>\n'
        f'  <rect width="{_W}" height="{_H}" fill="#0a0a0a"/>\n'
        f'  <rect width="{_W}" height="{_H}" fill="url(#dots)"/>\n'
    )

    # header
    parts.append(
        f'  <rect x="0" y="0" width="{_W}" height="68" fill="#111"/>\n'
        f'  <line x1="0" y1="68" x2="{_W}" y2="68" stroke="#2a2a2a" stroke-width="1"/>\n'
        f'  <text x="20" y="32" font-family="\'Courier New\',Courier,monospace" '
        f'font-size="14" font-weight="bold" fill="{accent}">{_esc(display)}</text>\n'
        f'  <rect x="{_W - 130}" y="10" width="110" height="26" rx="4" '
        f'fill="#181818" stroke="{accent}" stroke-width="1"/>\n'
        f'  <text x="{_W - 75}" y="28" text-anchor="middle" '
        f'font-family="\'Courier New\',Courier,monospace" '
        f'font-size="9" font-weight="bold" fill="{accent}" letter-spacing="2">{dtype}</text>\n'
    )

    if nodes:
        for i in range(len(nodes) - 1):
            x1, y1 = nodes[i][1], nodes[i][2]
            x2, y2 = nodes[i + 1][1], nodes[i + 1][2]
            parts.append(
                f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{accent}" stroke-width="1.5" marker-end="url(#arr)" opacity="0.5"/>\n'
            )
        for eq, x, y in nodes:
            r    = 30
            col  = _EQ_STYLE.get("other", ("#6b7280", "generic"))[0]
            parts.append(
                f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" '
                f'fill="#181818" stroke="{accent}" stroke-width="1.8"/>\n'
                f'  <text x="{x:.1f}" y="{y - 4:.1f}" text-anchor="middle" '
                f'font-family="\'Courier New\',Courier,monospace" font-size="11" font-weight="bold" '
                f'fill="{accent}">{_esc(eq[:8])}</text>\n'
                f'  <text x="{x:.1f}" y="{y + 14:.1f}" text-anchor="middle" '
                f'font-family="\'Courier New\',Courier,monospace" font-size="8" '
                f'fill="#6b7280">equipment</text>\n'
            )
    elif summary:
        for i, line in enumerate(_wrap(summary, 80)[:4]):
            parts.append(
                f'  <text x="{_W//2}" y="{300 + i * 22}" text-anchor="middle" '
                f'font-family="\'Courier New\',Courier,monospace" font-size="11" '
                f'fill="#a0a0a0">{_esc(line)}</text>\n'
            )

    if regs:
        for i, reg in enumerate(regs):
            bx = 30 + i * 200
            parts.append(
                f'  <rect x="{bx}" y="{_H - 50}" width="120" height="22" rx="4" '
                f'fill="#161616" stroke="#10b981" stroke-width="1"/>\n'
                f'  <text x="{bx + 60}" y="{_H - 34}" text-anchor="middle" '
                f'font-family="\'Courier New\',Courier,monospace" font-size="9" '
                f'fill="#10b981">{_esc(reg[:16])}</text>\n'
            )

    parts.append(
        f'  <text x="{_W//2}" y="{_H - 6}" text-anchor="middle" '
        f'font-family="\'Courier New\',Courier,monospace" font-size="7" '
        f'fill="#222" letter-spacing="2">AI OPERATIONS BRAIN — DRAWING EXTRACTION</text>\n'
        f'</svg>'
    )
    return "".join(parts)


# ─── CAD (DXF) parser ────────────────────────────────────────────────────────

def _parse_dxf_structure(file_path: str, doc_name: str) -> Optional[dict]:
    """Parse a DXF file with ezdxf; return a structure dict for _render_pid_svg."""
    import re as _re
    try:
        import ezdxf  # optional dependency
    except ImportError:
        logger.warning("ezdxf not installed — DXF files will use placeholder SVG")
        return None

    try:
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        _EQ         = _re.compile(r'\b([A-Z]{1,3}-\d{2,4}[A-Z]?)\b')
        _INST       = _re.compile(
            r'\b([FPTL][IT]C?-\d{2,4}|PSV-\d{2,4}|[FP]CV-\d{2,4}|PDT-\d{2,4})\b'
        )
        _MTEXT_STRIP = _re.compile(r'\\[A-Za-z0-9;.]+|[{}]')

        text_items:   list[dict] = []
        insert_items: list[dict] = []
        all_x: list[float] = []
        all_y: list[float] = []

        for entity in msp:
            try:
                dtype = entity.dxftype()
                if dtype == "TEXT":
                    content = str(entity.dxf.get("text", "")).strip()
                    pos = entity.dxf.insert
                    x, y = float(pos.x), float(pos.y)
                elif dtype == "MTEXT":
                    try:
                        content = entity.text or ""
                    except Exception:
                        content = str(entity.dxf.get("text", ""))
                    content = _MTEXT_STRIP.sub("", content).strip()
                    pos = entity.dxf.insert
                    x, y = float(pos.x), float(pos.y)
                elif dtype == "INSERT":
                    bname = str(entity.dxf.get("name", ""))
                    pos   = entity.dxf.insert
                    x, y  = float(pos.x), float(pos.y)
                    insert_items.append({"name": bname, "x": x, "y": y})
                    all_x.append(x); all_y.append(y)
                    continue
                else:
                    continue

                if content:
                    text_items.append({"content": content, "x": x, "y": y})
                all_x.append(x); all_y.append(y)
            except Exception:
                continue

        if not all_x:
            return None

        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        x_rng = max(x_max - x_min, 1e-9)
        y_rng = max(y_max - y_min, 1e-9)

        def nx(v: float) -> float: return (v - x_min) / x_rng
        def ny(v: float) -> float: return 1.0 - (v - y_min) / y_rng  # DXF Y is bottom-up

        equipment:   list[dict] = []
        instruments: list[dict] = []
        annotations: list[str]  = []
        seen_eq:     set[str]   = set()
        seen_inst:   set[str]   = set()

        for ti in text_items:
            c = ti["content"]
            for m in _INST.finditer(c):
                tag = m.group(1)
                if tag not in seen_inst:
                    seen_inst.add(tag)
                    instruments.append(
                        {"id": tag, "type": tag[:3].rstrip("-"),
                         "rx": nx(ti["x"]), "ry": ny(ti["y"])}
                    )
            for m in _EQ.finditer(c):
                tag = m.group(1)
                if tag not in seen_inst and tag not in seen_eq:
                    seen_eq.add(tag)
                    equipment.append(
                        {"id": tag, "type": _infer_eq_type_from_tag(tag),
                         "label": tag, "rx": nx(ti["x"]), "ry": ny(ti["y"])}
                    )
            if 3 < len(c) < 60:
                annotations.append(c)

        for ins in insert_items[:30]:
            for m in _EQ.finditer(ins["name"]):
                tag = m.group(1)
                if tag not in seen_eq and tag not in seen_inst:
                    seen_eq.add(tag)
                    equipment.append(
                        {"id": tag, "type": _infer_eq_type_from_tag(tag),
                         "label": tag, "rx": nx(ins["x"]), "ry": ny(ins["y"])}
                    )

        title: Optional[str] = None
        for hkey in ("$PROJECTNAME", "$LASTSAVEDBY"):
            try:
                val = doc.header.get(hkey)
                if val:
                    title = str(val); break
            except Exception:
                pass

        return {
            "title":           title or doc_name,
            "drawing_type":    "pid",
            "equipment":       equipment[:16],
            "instruments":     instruments[:20],
            "connections":     [],
            "key_annotations": list(dict.fromkeys(annotations))[:8],
        }

    except Exception as exc:
        logger.warning("DXF parse error for %s: %s", file_path, exc)
        return None


def _infer_eq_type_from_tag(tag: str) -> str:
    """Map equipment tag prefix to a P&ID type name."""
    prefix = tag.split("-")[0].upper()
    return {
        "P": "pump",   "G": "pump",   "K": "compressor",  "C": "compressor",
        "V": "vessel", "D": "vessel", "T": "tank",         "TK": "tank",
        "HX": "heat_exchanger",       "E": "heat_exchanger",
        "R": "reactor", "COL": "column",
        "F": "filter",  "FV": "valve",  "CV": "valve",     "XV": "valve",
        "BL": "blower",
    }.get(prefix, "other")


def _cad_placeholder_svg(doc_name: str, ext: str, entities: dict) -> str:
    """Styled placeholder SVG for DWG / STEP / IGES files that can't be rendered."""
    _FMT: dict[str, tuple[str, str, str]] = {
        ".dwg":  ("DWG",  "#f59e0b", "AutoCAD Binary Drawing — visual preview unavailable"),
        ".step": ("STEP", "#06b6d4", "ISO 10303 3D Model — entities extracted"),
        ".stp":  ("STEP", "#06b6d4", "ISO 10303 3D Model — entities extracted"),
        ".iges": ("IGES", "#a855f7", "IGES 3D Exchange — entities extracted"),
        ".igs":  ("IGES", "#a855f7", "IGES 3D Exchange — entities extracted"),
    }
    badge, accent, note = _FMT.get(ext.lower(), ("CAD", "#06b6d4", "CAD file received"))
    display = (doc_name[:56] + "\u2026") if len(doc_name) > 56 else doc_name
    equip   = entities.get("equipment_ids", [])[:8]

    parts: list[str] = [
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_W} {_H}" width="{_W}" height="{_H}">\n'
        f'  <defs>\n'
        f'    <pattern id="cad-grid" width="30" height="30" '
        f'patternUnits="userSpaceOnUse">'
        f'<path d="M30 0L0 0 0 30" fill="none" stroke="#161616" stroke-width="0.5"/>'
        f'</pattern>\n'
        f'  </defs>\n'
        f'  <rect width="{_W}" height="{_H}" fill="#0a0a0a"/>\n'
        f'  <rect width="{_W}" height="{_H}" fill="url(#cad-grid)"/>\n'
        # Header bar
        f'  <rect x="0" y="0" width="{_W}" height="68" fill="#111"/>\n'
        f'  <line x1="0" y1="68" x2="{_W}" y2="68" stroke="#2a2a2a" stroke-width="1"/>\n'
        f'  <text x="20" y="32" font-family="\'Courier New\',Courier,monospace" '
        f'font-size="14" font-weight="bold" fill="{accent}">{_esc(display)}</text>\n'
        f'  <rect x="{_W - 130}" y="10" width="110" height="26" rx="4" '
        f'fill="#181818" stroke="{accent}" stroke-width="1"/>\n'
        f'  <text x="{_W - 75}" y="28" text-anchor="middle" '
        f'font-family="\'Courier New\',Courier,monospace" font-size="9" font-weight="bold" '
        f'fill="{accent}" letter-spacing="2">{badge}</text>\n',
    ]

    # Corner L-brackets (CAD drafting style)
    for lx, ly, sx, sy in [
        (40, 86, 1, 1), (_W - 40, 86, -1, 1),
        (40, _H - 54, 1, -1), (_W - 40, _H - 54, -1, -1),
    ]:
        s = 18
        parts.append(
            f'  <path d="M{lx + sx * s},{ly} L{lx},{ly} L{lx},{ly + sy * s}" '
            f'fill="none" stroke="{accent}" stroke-width="1.5" opacity="0.35"/>\n'
        )

    # Central info box
    cx = _W / 2
    bx, by = cx - 220, 220
    parts.extend([
        f'  <rect x="{bx}" y="{by}" width="440" height="100" rx="8" '
        f'fill="#111" stroke="{accent}" stroke-width="1" opacity="0.7"/>\n',
        f'  <text x="{cx}" y="{by + 35}" text-anchor="middle" '
        f'font-family="\'Courier New\',Courier,monospace" font-size="20" font-weight="bold" '
        f'fill="{accent}">{badge} FILE RECEIVED</text>\n',
        f'  <text x="{cx}" y="{by + 60}" text-anchor="middle" '
        f'font-family="\'Courier New\',Courier,monospace" font-size="10" '
        f'fill="#6b7280">{_esc(note)}</text>\n',
        f'  <text x="{cx}" y="{by + 80}" text-anchor="middle" '
        f'font-family="\'Courier New\',Courier,monospace" font-size="9" '
        f'fill="#4b5563">Entities extracted and added to the knowledge graph</text>\n',
    ])

    # Equipment tag chips
    if equip:
        tag_y = by + 130
        parts.append(
            f'  <text x="{cx}" y="{tag_y}" text-anchor="middle" '
            f'font-family="\'Courier New\',Courier,monospace" font-size="9" '
            f'fill="#4b5563" letter-spacing="1">EXTRACTED TAGS</text>\n'
        )
        n   = len(equip)
        gap = min(110.0, (_W - 80.0) / max(n, 1))
        sx0 = cx - (n - 1) * gap / 2
        for i, eq in enumerate(equip):
            ex = sx0 + i * gap
            ey = tag_y + 26
            parts.extend([
                f'  <rect x="{ex - 38}" y="{ey - 13}" width="76" height="20" rx="4" '
                f'fill="#181818" stroke="{accent}" stroke-width="0.8"/>\n',
                f'  <text x="{ex}" y="{ey}" text-anchor="middle" '
                f'font-family="\'Courier New\',Courier,monospace" font-size="10" '
                f'font-weight="bold" fill="{accent}">{_esc(eq[:10])}</text>\n',
            ])

    parts.append(
        f'  <text x="{_W // 2}" y="{_H - 6}" text-anchor="middle" '
        f'font-family="\'Courier New\',Courier,monospace" font-size="7" '
        f'fill="#222" letter-spacing="2">AI OPERATIONS BRAIN \u2014 DRAWING EXTRACTION</text>\n'
        f'</svg>'
    )
    return "".join(parts)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


logger = logging.getLogger(__name__)

