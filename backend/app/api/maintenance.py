"""
AI Operations Brain — Maintenance Records API

Endpoints:
  GET  /api/v1/maintenance          List all maintenance records (filterable)
"""
import logging

from fastapi import APIRouter

from app.services.db_service import list_all_maintenance_records

logger = logging.getLogger(__name__)
router = APIRouter()


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("")
async def list_maintenance(
    equipment_id: str | None = None,
    status: str | None = None,
    type: str | None = None,
):
    """Return all maintenance records, newest first. Optionally filter."""
    records = await list_all_maintenance_records(
        equipment_id=equipment_id,
        status=status,
        type_filter=type,
    )
    return records
