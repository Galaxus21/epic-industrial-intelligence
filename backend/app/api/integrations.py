"""
AI Operations Brain — Integrations API
REST endpoints for all external data source integrations.
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db import models as m
from app.services.integrations.email_service import (
    get_emails, get_email_summary, get_imap_connection_stub, test_imap_connection,
)
from app.services.integrations.slack_service import (
    get_slack_messages, get_slack_summary, get_slack_config_stub, test_slack_connection,
)
from app.services.integrations.ingestion_router import (
    get_integration_catalog, get_unified_feed, get_integration_stats,
)

router = APIRouter()

_MASK = "••••••••"
_SECRET_KEYS = {"password", "bot_token", "app_token", "api_key", "secret"}


def _mask_config(cfg: dict | None) -> dict:
    if not cfg:
        return {}
    return {k: (_MASK if k in _SECRET_KEYS else v) for k, v in cfg.items()}


# ── Overview ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_integrations():
    """Return all integration sources with live status from DB."""
    return await get_integration_catalog()


@router.get("/stats")
async def integration_stats():
    return await get_integration_stats()


@router.get("/feed")
async def unified_feed(limit: int = 30, equipment: str | None = None):
    """Return unified chronological feed of all ingested items."""
    items = await get_unified_feed(limit)
    if equipment:
        items = [i for i in items if equipment in i.get("equipment", [])]
    return items


# ── Integration config CRUD ───────────────────────────────────────────────────

class IntegrationConfigBody(BaseModel):
    integration_id: str
    enabled: bool = False
    config: dict[str, Any] = {}


@router.get("/{integration_id}/config")
async def get_integration_config(integration_id: str):
    """Return saved config for an integration (secrets masked)."""
    async with AsyncSessionLocal() as s:
        row = (await s.execute(
            select(m.IntegrationConfig).where(m.IntegrationConfig.id == integration_id)
        )).scalar_one_or_none()
    if not row:
        return {"integration_id": integration_id, "enabled": False, "config": {}}
    return {
        "integration_id": row.id,
        "enabled": row.enabled,
        "config": _mask_config(row.config),
        "last_test_ok": row.last_test_ok,
        "last_test_msg": row.last_test_msg,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.post("/config")
async def save_integration_config(body: IntegrationConfigBody):
    """Save (upsert) credentials for an integration."""
    async with AsyncSessionLocal() as s:
        row = (await s.execute(
            select(m.IntegrationConfig).where(m.IntegrationConfig.id == body.integration_id)
        )).scalar_one_or_none()

        # Merge — don't overwrite masked secrets with the mask placeholder
        merged_cfg: dict[str, Any] = {}
        if row and row.config:
            merged_cfg = dict(row.config)
        for k, v in body.config.items():
            if k in _SECRET_KEYS and v == _MASK:
                pass  # keep existing secret
            else:
                merged_cfg[k] = v

        if row:
            row.enabled = body.enabled
            row.config = merged_cfg
            row.updated_at = datetime.utcnow()
        else:
            row = m.IntegrationConfig(
                id=body.integration_id,
                enabled=body.enabled,
                config=merged_cfg,
                updated_at=datetime.utcnow(),
            )
            s.add(row)
        await s.commit()
    return {"status": "saved", "integration_id": body.integration_id, "enabled": body.enabled}


@router.post("/{integration_id}/test")
async def test_integration_connection(integration_id: str):
    """Test the saved connection for an integration and persist the result."""
    async with AsyncSessionLocal() as s:
        row = (await s.execute(
            select(m.IntegrationConfig).where(m.IntegrationConfig.id == integration_id)
        )).scalar_one_or_none()

    if not row or not row.config:
        raise HTTPException(400, "No configuration saved for this integration. Save credentials first.")

    cfg = row.config
    ok, msg = False, "Unknown integration"

    if integration_id == "email":
        ok, msg = await test_imap_connection(cfg)
    elif integration_id == "slack":
        ok, msg = await test_slack_connection(cfg)
    else:
        raise HTTPException(400, f"Test not supported for integration '{integration_id}'")

    # Persist test result
    async with AsyncSessionLocal() as s:
        row2 = (await s.execute(
            select(m.IntegrationConfig).where(m.IntegrationConfig.id == integration_id)
        )).scalar_one_or_none()
        if row2:
            row2.last_test_ok = ok
            row2.last_test_msg = msg
            row2.updated_at = datetime.utcnow()
            await s.commit()

    return {"ok": ok, "message": msg}


# ── Email ─────────────────────────────────────────────────────────────────────

@router.get("/email")
async def email_overview():
    return {
        "summary": await get_email_summary(),
        "config": get_imap_connection_stub(),
        "messages": await get_emails(),
    }


@router.get("/email/messages")
async def list_emails(equipment: str | None = None):
    return await get_emails(equipment_filter=equipment)


@router.post("/email/ingest")
async def ingest_email_now():
    """
    Pull current emails and classify/store them in DB + knowledge base.
    Returns a summary of what was ingested.
    """
    from app.services.integrations.email_ingestor import ingest_emails
    emails = await get_emails()
    counts = await ingest_emails(emails)
    return {"status": "ok", "ingested": counts}


# ── Slack ─────────────────────────────────────────────────────────────────────

@router.get("/slack")
async def slack_overview():
    return {
        "summary": await get_slack_summary(),
        "config": get_slack_config_stub(),
        "messages": await get_slack_messages(),
    }


@router.get("/slack/messages")
async def list_slack_messages(equipment: str | None = None, channel: str | None = None):
    return await get_slack_messages(equipment_filter=equipment, channel=channel)


@router.post("/slack/ingest")
async def ingest_slack_now():
    """
    Pull current Slack messages and classify/store them in the DB.
    Returns a summary of what was ingested.
    """
    from app.services.integrations.slack_ingestor import ingest_slack_messages
    messages = await get_slack_messages()
    counts = await ingest_slack_messages(messages)
    return {"status": "ok", "ingested": counts}


# ── Generic Webhook Receiver ──────────────────────────────────────────────────

class WebhookPayload(BaseModel):
    source: str
    equipment_id: str
    event_type: str
    data: dict[str, Any]
    timestamp: str | None = None


_webhook_events: list[dict[str, Any]] = []


@router.post("/webhook/ingest")
async def receive_webhook(payload: WebhookPayload):
    event = {
        "id": f"WEBHOOK-{len(_webhook_events)+1:04d}",
        "source": payload.source,
        "equipment_id": payload.equipment_id,
        "event_type": payload.event_type,
        "data": payload.data,
        "timestamp": payload.timestamp or datetime.utcnow().isoformat(),
        "ingested_at": datetime.utcnow().isoformat(),
    }
    _webhook_events.append(event)

    # Auto-ingest Slack-like payloads into DB objects
    if payload.source == "slack" and payload.event_type == "message":
        try:
            from app.services.integrations.slack_ingestor import ingest_slack_messages
            synthetic_msg = {
                "id": event["id"],
                "text": payload.data.get("text", ""),
                "user_display": payload.data.get("user", "webhook"),
                "channel": payload.data.get("channel", "#webhook"),
                "timestamp": event["timestamp"],
                "equipment_mentions": [payload.equipment_id] if payload.equipment_id != "UNKNOWN" else [],
            }
            await ingest_slack_messages([synthetic_msg])
        except Exception:
            pass

    return {"status": "accepted", "event_id": event["id"]}


@router.get("/webhook/events")
async def list_webhook_events():
    return _webhook_events

