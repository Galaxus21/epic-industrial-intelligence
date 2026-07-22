"""
AI Operations Brain — Integration Router
Merges events from all sources (email, Slack, CMMS, DCS, webhook, etc.)
into a unified ingestion feed. Every item gets classified, tagged with
equipment IDs, and made available to the agent pipeline.
"""
from datetime import datetime
from typing import Any

# ── All integration source definitions ───────────────────────────────────────

_CATALOG_BASE: list[dict[str, Any]] = [
    {
        "id": "email",
        "name": "Email (IMAP / Gmail / Outlook)",
        "category": "Communication",
        "icon": "Mail",
        "description": "Reads maintenance alerts, OEM support replies, vendor notices, and shift handover emails. Extracts equipment mentions, symptoms, and action items.",
        "status": "configure",
        "item_count": 0,
        "action_required": 0,
        "last_sync": None,
        "setup_fields": [
            {"key": "host",     "label": "IMAP Host",     "placeholder": "imap.gmail.com",   "env": "EMAIL_HOST"},
            {"key": "port",     "label": "Port",          "placeholder": "993",              "env": "EMAIL_PORT"},
            {"key": "user",     "label": "Username",      "placeholder": "you@company.com",  "env": "EMAIL_USER"},
            {"key": "password", "label": "Password",      "placeholder": "••••••••",         "env": "EMAIL_PASSWORD", "secret": True},
            {"key": "folder",   "label": "Folder",        "placeholder": "INBOX",            "env": "EMAIL_FOLDER"},
        ],
        "tags": ["realtime", "nlp", "action-items"],
    },
    {
        "id": "slack",
        "name": "Slack Channels",
        "category": "Communication",
        "icon": "MessageSquare",
        "description": "Monitors #maintenance, #plant-ops, and custom channels. Answers /opsbrain slash commands in real-time. Threads AI responses directly in Slack.",
        "status": "configure",
        "item_count": 0,
        "action_required": 0,
        "last_sync": None,
        "setup_fields": [
            {"key": "bot_token",   "label": "Bot Token",   "placeholder": "xoxb-...", "env": "SLACK_BOT_TOKEN",  "secret": True},
            {"key": "app_token",   "label": "App Token",   "placeholder": "xapp-...", "env": "SLACK_APP_TOKEN",  "secret": True},
            {"key": "channels",    "label": "Channels",    "placeholder": "#maintenance,#plant-ops", "env": "SLACK_CHANNELS"},
        ],
        "tags": ["realtime", "slash-command", "thread-replies"],
    },
    {
        "id": "sap_pm",
        "name": "SAP Plant Maintenance (CMMS)",
        "category": "CMMS / ERP",
        "icon": "ClipboardList",
        "description": "Syncs work orders, PM schedules, equipment master data, and overdue maintenance alerts from SAP PM in real-time via RFC or REST API.",
        "status": "configure",
        "item_count": 0,
        "action_required": 0,
        "last_sync": None,
        "setup_fields": [
            {"key": "host",      "label": "SAP Host",      "placeholder": "sap-prod.plant.com", "env": "SAP_HOST"},
            {"key": "client",    "label": "SAP Client",    "placeholder": "100",                "env": "SAP_CLIENT"},
            {"key": "user",      "label": "RFC User",      "placeholder": "OPSBRAIN_RFC",        "env": "SAP_USER"},
            {"key": "password",  "label": "Password",      "placeholder": "••••••••",            "env": "SAP_PASSWORD", "secret": True},
            {"key": "plant",     "label": "Plant Code",    "placeholder": "1000",                "env": "SAP_PLANT"},
        ],
        "tags": ["work-orders", "pm-schedule", "asset-master", "bidirectional"],
    },
    {
        "id": "dcs_scada",
        "name": "DCS / SCADA (OPC-UA / REST)",
        "category": "Process Control",
        "icon": "Activity",
        "description": "Real-time sensor data from Honeywell Experion, ABB, Siemens PCS 7, or any OPC-UA compatible DCS. Feeds live vibration, temperature, pressure trends.",
        "status": "configure",
        "item_count": 0,
        "action_required": 0,
        "last_sync": None,
        "setup_fields": [
            {"key": "opc_url",   "label": "OPC-UA Endpoint", "placeholder": "opc.tcp://dcs-server:4840", "env": "OPC_UA_URL"},
            {"key": "namespace", "label": "Namespace URI",   "placeholder": "urn:plant:dcs",              "env": "OPC_NAMESPACE"},
            {"key": "poll_sec",  "label": "Poll Interval (s)","placeholder": "30",                       "env": "OPC_POLL_SECONDS"},
        ],
        "tags": ["realtime", "sensor-data", "timeseries", "opc-ua"],
    },
    {
        "id": "pi_historian",
        "name": "OSIsoft PI Historian",
        "category": "Process Control",
        "icon": "TrendingUp",
        "description": "Historical and real-time process data from OSIsoft PI System via PI Web API. Enables trend analysis, anomaly detection, and AI-powered predictions.",
        "status": "configure",
        "item_count": 0,
        "action_required": 0,
        "last_sync": None,
        "setup_fields": [
            {"key": "piwebapi_url", "label": "PI Web API URL", "placeholder": "https://pi-server/piwebapi", "env": "PI_WEBAPI_URL"},
            {"key": "user",         "label": "Username",       "placeholder": "PIWEBAPI_USER",              "env": "PI_USER"},
            {"key": "password",     "label": "Password",       "placeholder": "••••••••",                   "env": "PI_PASSWORD", "secret": True},
            {"key": "asset_db",     "label": "Asset Database", "placeholder": "REFINERY",                   "env": "PI_ASSET_DB"},
        ],
        "tags": ["timeseries", "historian", "analytics", "osisoft-pi"],
    },
    {
        "id": "sharepoint",
        "name": "SharePoint / MS Teams",
        "category": "Document Management",
        "icon": "FolderOpen",
        "description": "Ingests documents from SharePoint document libraries and Teams channels: P&IDs, SOPs, inspection reports, engineering drawings, manuals.",
        "status": "configure",
        "item_count": 0,
        "action_required": 0,
        "last_sync": None,
        "setup_fields": [
            {"key": "tenant_id",  "label": "Tenant ID",     "placeholder": "your-tenant-id",  "env": "MS_TENANT_ID"},
            {"key": "client_id",  "label": "Client ID",     "placeholder": "app-client-id",   "env": "MS_CLIENT_ID"},
            {"key": "secret",     "label": "Client Secret", "placeholder": "••••••••",         "env": "MS_CLIENT_SECRET", "secret": True},
            {"key": "site_url",   "label": "SharePoint URL","placeholder": "https://company.sharepoint.com/sites/plant", "env": "MS_SHAREPOINT_URL"},
        ],
        "tags": ["documents", "ms-graph", "ocr-pipeline", "bidirectional"],
    },
    {
        "id": "iot_mqtt",
        "name": "IoT / MQTT Broker",
        "category": "IoT & Sensors",
        "icon": "Radio",
        "description": "Direct IoT sensor integration via MQTT. Receives vibration sensors, temperature loggers, ultrasonic thickness gauges, and smart lubrication devices.",
        "status": "configure",
        "item_count": 0,
        "action_required": 0,
        "last_sync": None,
        "setup_fields": [
            {"key": "broker",    "label": "Broker Host",   "placeholder": "mqtt.plant.com",  "env": "MQTT_BROKER"},
            {"key": "port",      "label": "Port",          "placeholder": "1883",            "env": "MQTT_PORT"},
            {"key": "topic",     "label": "Topic Filter",  "placeholder": "plant/cdu/#",     "env": "MQTT_TOPIC"},
            {"key": "user",      "label": "Username",      "placeholder": "iot-reader",      "env": "MQTT_USER"},
        ],
        "tags": ["realtime", "iot", "mqtt", "sensor-fusion"],
    },
    {
        "id": "webhook",
        "name": "Generic Webhook",
        "category": "API & Integration",
        "icon": "Webhook",
        "description": "Universal inbound webhook endpoint. Any system (Maximo, Prometheus, PagerDuty, custom scripts) can POST structured data to push events into the AI brain.",
        "status": "active",
        "item_count": 0,
        "action_required": 0,
        "last_sync": None,
        "webhook_url": "http://localhost:8000/api/v1/integrations/webhook/ingest",
        "setup_fields": [],
        "tags": ["webhook", "api", "universal", "push"],
    },
    {
        "id": "whatsapp",
        "name": "WhatsApp Business API",
        "category": "Communication",
        "icon": "Smartphone",
        "description": "Field technicians send equipment photos, voice notes, and symptom descriptions via WhatsApp. AI processes the message and updates the knowledge graph.",
        "status": "configure",
        "item_count": 0,
        "action_required": 0,
        "last_sync": None,
        "setup_fields": [
            {"key": "phone_id",   "label": "Phone Number ID",    "placeholder": "12345678",   "env": "WHATSAPP_PHONE_ID"},
            {"key": "token",      "label": "Access Token",       "placeholder": "EAAx...",    "env": "WHATSAPP_TOKEN", "secret": True},
            {"key": "verify_tok", "label": "Webhook Verify Token","placeholder": "my-secret", "env": "WHATSAPP_VERIFY_TOKEN"},
        ],
        "tags": ["mobile", "voice", "image-ocr", "field-ops"],
    },
    {
        "id": "ms_teams",
        "name": "Microsoft Teams",
        "category": "Communication",
        "icon": "Users",
        "description": "Teams bot for maintenance channels. Answers queries, sends alerts, and allows /opsbrain commands inside Teams.",
        "status": "configure",
        "item_count": 0,
        "action_required": 0,
        "last_sync": None,
        "setup_fields": [
            {"key": "tenant_id",  "label": "Tenant ID",     "placeholder": "your-tenant",   "env": "TEAMS_TENANT_ID"},
            {"key": "bot_id",     "label": "Bot App ID",    "placeholder": "app-id",        "env": "TEAMS_BOT_ID"},
            {"key": "bot_secret", "label": "Bot Secret",    "placeholder": "••••••••",       "env": "TEAMS_BOT_SECRET", "secret": True},
        ],
        "tags": ["teams-bot", "channels", "adaptive-cards"],
    },
]

# ── Unified feed of all ingested items, sorted by time ───────────────────────

async def get_integration_catalog() -> list[dict[str, Any]]:
    """Return catalog with live enabled/status from DB."""
    from sqlalchemy import select
    from app.db.database import AsyncSessionLocal
    from app.db import models as mdl
    db_configs: dict[str, mdl.IntegrationConfig] = {}
    try:
        async with AsyncSessionLocal() as s:
            rows = (await s.execute(select(mdl.IntegrationConfig))).scalars().all()
            db_configs = {r.id: r for r in rows}
    except Exception:
        pass

    result = []
    for entry in _CATALOG_BASE:
        e = dict(entry)
        row = db_configs.get(e["id"])
        if row:
            if row.enabled:
                e["status"] = "connected" if row.last_test_ok else "error"
            else:
                e["status"] = "configure"
            e["enabled"] = row.enabled
            if row.last_test_msg:
                e["last_test_msg"] = row.last_test_msg
        result.append(e)
    return result


async def get_unified_feed(limit: int = 30) -> list[dict[str, Any]]:
    from app.services.integrations.email_service import get_emails
    from app.services.integrations.slack_service import get_slack_messages
    emails = await get_emails()
    slacks = await get_slack_messages()
    items: list[dict[str, Any]] = []
    for e in emails:
        items.append({
            "id": e["id"],
            "source": "email",
            "source_label": "Email",
            "icon": "Mail",
            "color": "#3b82f6",
            "from": e["from"],
            "title": e["subject"],
            "preview": e["body"][:120] + "...",
            "equipment": e.get("equipment_mentions", []),
            "action_required": e["action_required"],
            "severity": "High" if e["action_required"] else "Info",
            "timestamp": e.get("ingested_at", ""),
            "channel": e.get("to", "email"),
        })
    for m in slacks:
        items.append({
            "id": m["id"],
            "source": "slack",
            "source_label": "Slack",
            "icon": "MessageSquare",
            "color": "#a855f7",
            "from": m["user_display"],
            "title": f"{m['channel']}  —  {m['user_display']}",
            "preview": m["text"][:120] + ("..." if len(m["text"]) > 120 else ""),
            "equipment": m.get("equipment_mentions", []),
            "action_required": m["action_required"],
            "severity": m["severity"],
            "timestamp": m.get("ingested_at", ""),
            "channel": m["channel"],
            "has_ai_reply": len(m.get("thread_replies", [])) > 0,
        })
    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return items[:limit]


async def get_integration_stats() -> dict[str, Any]:
    catalog = await get_integration_catalog()
    active = sum(1 for i in catalog if i["status"] in ("connected", "active"))
    total_items = sum(i.get("item_count", 0) for i in catalog)
    total_actions = sum(i.get("action_required", 0) for i in catalog)
    return {
        "total_integrations": len(catalog),
        "active_integrations": active,
        "pending_configuration": len(catalog) - active,
        "total_items_ingested": total_items,
        "action_required": total_actions,
    }

