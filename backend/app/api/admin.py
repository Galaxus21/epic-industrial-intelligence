"""
AI Operations Brain — Admin / Data Management API
Bulk-purge for every purgeable entity type, including equipment and sensors.

DELETE /api/v1/admin/purge?entity=<key>   — purge one entity type (and the search-index points that mirror it)
DELETE /api/v1/admin/purge?entity=all     — full database reset
POST   /api/v1/admin/generate-demo        — demo dataset covering every kept entity type

Entity keys
───────────
Assets            : equipment, maintenance, sensors, spare_parts, technicians
Operations        : incidents, saved_work_orders
System            : documents, graph, compliance
                    (audit_logs is append-only and can never be purged)
"""
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select, func

from app.core.auth import require_roles
from app.core.roles import ADMIN_ROLES
from app.db.database import AsyncSessionLocal
from app.db import models as m
from app.services import vector_service as vs
from app.services.audit import record as audit_record
from app.services.demoSeed import seedDemoDataset

logger = logging.getLogger(__name__)
router = APIRouter()

# Each key maps to one or more ORM model classes.
_ENTITY_MAP: dict[str, list] = {
    # ── Assets ───────────────────────────────────────────────────────────────
    "equipment":         [m.Equipment],
    "maintenance":       [m.MaintenanceRecord],
    "sensors":           [m.SensorHistory],
    "spare_parts":       [m.SparePart],
    "technicians":       [m.Technician],
    # ── Operations ───────────────────────────────────────────────────────────
    "incidents":         [m.Incident],
    "saved_work_orders": [m.SavedWorkOrder],
    # ── System ───────────────────────────────────────────────────────────────
    "documents":         [m.DocumentRecord],
    # NOTE: audit_logs is intentionally NOT purgeable — the audit trail is
    # append-only evidence and must survive administrative resets.
    "graph":             [m.GraphNode, m.GraphLink],
    "compliance":        [m.Compliance],
}

# The Qdrant collections that copy an entity's rows, cleared with them so search cannot cite a purged row.
# Purging equipment clears incidents too: incidents.equipment_id is ON DELETE CASCADE.
_INDEX_MIRRORS = {
    "incidents": vs.clear_incident_index,
    "equipment": vs.clear_incident_index,
    "documents": vs.clear_document_index,
}


async def _purge_one(entity: str, db) -> tuple[int, list[str]]:
    """Delete all DB rows for the given entity key.
    Returns (count_deleted, files_to_remove_after_commit).
    Files are NOT removed here — caller must remove them after a successful commit.
    """
    models = _ENTITY_MAP.get(entity, [])
    total = 0
    pending_files: list[str] = []

    for model in models:
        n = await db.scalar(select(func.count()).select_from(model)) or 0
        await db.execute(delete(model))
        total += n

    # Collect file paths to delete AFTER the DB commit succeeds
    if entity == "documents":
        if os.path.isdir("uploads"):
            for fname in os.listdir("uploads"):
                fpath = os.path.join("uploads", fname)
                if os.path.isfile(fpath):
                    pending_files.append(fpath)

    return total, pending_files


# ─── Purge endpoint ───────────────────────────────────────────────────────────

@router.delete("/purge")
async def purge_entity(
    entity: str = Query(..., description="Entity key to purge, or 'all' for full reset"),
    user: m.UserProfile = Depends(require_roles(*ADMIN_ROLES)),
):
    """Delete ALL records for the given entity type, or 'all' for everything.

    Manager-only. Audit logs are never purgeable, and the purge itself is
    written to the audit trail before any rows are deleted.
    """
    if entity == "audit_logs":
        raise HTTPException(403, "Audit logs are append-only and cannot be purged")
    if entity == "all":
        keys = list(_ENTITY_MAP.keys())
    elif entity not in _ENTITY_MAP:
        raise HTTPException(
            400,
            f"Unknown entity '{entity}'. Valid keys: {list(_ENTITY_MAP)} or 'all'",
        )
    else:
        keys = [entity]

    # Record intent before deleting so the purge cannot erase its own evidence
    await audit_record("purge", "system", entity, actor=user.name, actor_type="user",
                       notes=f"Admin purge requested for entity '{entity}'")

    total = 0
    all_pending_files: list[str] = []
    async with AsyncSessionLocal() as db:
        for key in keys:
            count, pending = await _purge_one(key, db)
            total += count
            all_pending_files.extend(pending)
        # Commit DB changes first — only remove files if commit succeeds
        await db.commit()

    # Remove files AFTER successful DB commit (prevents orphaned files on rollback)
    for fpath in all_pending_files:
        try:
            os.remove(fpath)
        except OSError:
            pass

    indexPointsDeleted = 0
    for clearIndex in {_INDEX_MIRRORS[key] for key in keys if key in _INDEX_MIRRORS}:
        indexPointsDeleted += await clearIndex()

    logger.info("Admin purge: entity=%s deleted=%d rows, %d index points", entity, total, indexPointsDeleted)
    return {"entity": entity, "deleted": total, "index_points_deleted": indexPointsDeleted, "status": "ok"}



# ─── Demo doc download endpoint ──────────────────────────────────────────────

@router.get("/demo-docs/{filename}")
async def download_demo_doc(filename: str):
    """Download a generated sample document for manual upload."""
    from fastapi.responses import FileResponse
    from app.services.demo_docs import UPLOADS_DIR
    safe_name = os.path.basename(filename)
    fpath = os.path.join(UPLOADS_DIR, safe_name)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail=f"Demo doc '{safe_name}' not found. Run generate-demo first.")
    return FileResponse(fpath, filename=safe_name, media_type="application/octet-stream")


# ─── Full demo dataset generator ─────────────────────────────────────────────

@router.post("/generate-demo")
async def generate_full_demo(user: m.UserProfile = Depends(require_roles(*ADMIN_ROLES))):
    """
    Seed the demo plant (app/services/demoSeed.py), dated from this moment.
    Safe to call multiple times — every row has a fixed ID, so a second call updates rather than duplicates.
    """
    return await seedDemoDataset()
