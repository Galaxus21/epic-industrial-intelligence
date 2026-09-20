"""
EPIC — Audit Core Module (re-export of app.services.audit)
Provides record, audit, and background task retention.
"""
from app.services.audit import record, audit, get_background_tasks, _background_tasks, create_audit_log

__all__ = ["record", "audit", "create_audit_log", "get_background_tasks", "_background_tasks"]
