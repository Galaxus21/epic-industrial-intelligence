"""
AI Operations Brain — Slack Integration Service
Reads messages from maintenance/ops Slack channels and answers slash commands.
Falls back to rich mock data so the demo works without a real Slack workspace.

Real usage:
  1. Create a Slack App at api.slack.com/apps
  2. Add scopes: channels:read, channels:history, chat:write, commands
  3. Set env vars SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_ENABLED=true
  4. The bot listens to #maintenance and #plant-ops channels
  5. Slash command: /opsbrain <equipment_id> <question>
"""
from datetime import datetime
from typing import Any

# ── Mock Slack messages ──────────────────────────────────────────────────────

MOCK_SLACK_MESSAGES: list[dict[str, Any]] = [
    {
        "id": "SLACK-001",
        "channel": "#maintenance-cdu",
        "user": "rajesh.kumar",
        "user_display": "Rajesh Kumar",
        "user_avatar": "RK",
        "text": "P-101 vibration is reading 7.2 mm/s on DCS. Alarm threshold is 7.1. Should we shut it down or can we wait till morning shift?",
        "timestamp": "2026-07-20T10:05:00",
        "thread_replies": [
            {
                "user": "opsbrain-bot",
                "text": "Based on INC-2022-034 (Aug 2022), P-101 with the same vibration signature failed 18 hours after alarm. OISD-117 requires shutdown within 2 hours. Recommend controlled shutdown now and switch to P-103. Full analysis: /opsbrain P-101",
                "timestamp": "2026-07-20T10:05:12",
            }
        ],
        "equipment_mentions": ["P-101", "P-103"],
        "action_required": True,
        "severity": "High",
        "source": "slack",
        "ingested_at": "2026-07-20T10:05:05",
    },
    {
        "id": "SLACK-002",
        "channel": "#plant-ops",
        "user": "s.venkataraman",
        "user_display": "S. Venkataraman",
        "user_avatar": "SV",
        "text": "Team - P-101 situation: Rajesh is preparing PTW. P-103 is ready for switchover (commissioned 18 Jul, vib 2.1 mm/s). Target switchover by 14:00 today. Keep me posted.",
        "timestamp": "2026-07-20T10:20:00",
        "thread_replies": [],
        "equipment_mentions": ["P-101", "P-103"],
        "action_required": False,
        "severity": "Info",
        "source": "slack",
        "ingested_at": "2026-07-20T10:20:05",
    },
    {
        "id": "SLACK-003",
        "channel": "#maintenance-cdu",
        "user": "amit.shah",
        "user_display": "Amit Shah",
        "user_avatar": "AS",
        "text": "Checked bearing lubrication records. P-101 last lubrication was 10-May-2026. We are 12 DAYS OVERDUE on the 14-day schedule. This could be the root cause. Same thing happened in 2022.",
        "timestamp": "2026-07-20T10:10:00",
        "thread_replies": [],
        "equipment_mentions": ["P-101"],
        "action_required": True,
        "severity": "High",
        "source": "slack",
        "ingested_at": "2026-07-20T10:10:05",
    },
    {
        "id": "SLACK-004",
        "channel": "#cmms-alerts",
        "user": "sap-pm-bot",
        "user_display": "SAP PM Bot",
        "user_avatar": "SAP",
        "text": "[AUTO] PM Order OVERDUE: P-101 Biweekly Lubrication (WO PM-2026-10044). Due 08-Jul-2026. Overdue: 12 days. Assigned: Rajesh Kumar. Priority: HIGH.",
        "timestamp": "2026-07-20T08:00:00",
        "thread_replies": [],
        "equipment_mentions": ["P-101"],
        "action_required": True,
        "severity": "High",
        "source": "slack",
        "ingested_at": "2026-07-20T08:00:05",
    },
    {
        "id": "SLACK-005",
        "channel": "#maintenance-cdu",
        "user": "priya.nair",
        "user_display": "Priya Nair",
        "user_avatar": "PN",
        "text": "P-103 is fully commissioned and standby-ready. Vibration baseline 2.1 mm/s, bearing temp 43°C. MOV-103A/B tested. Switchover per SOP-P003 Step 4 when P-101 is taken offline.",
        "timestamp": "2026-07-20T07:15:00",
        "thread_replies": [],
        "equipment_mentions": ["P-101", "P-103"],
        "action_required": False,
        "severity": "Info",
        "source": "slack",
        "ingested_at": "2026-07-20T07:15:05",
    },
    {
        "id": "SLACK-006",
        "channel": "#maintenance-cdu",
        "user": "rajesh.kumar",
        "user_display": "Rajesh Kumar",
        "user_avatar": "RK",
        "text": "PTW submitted: PTW-2026-0892 (Class C - Mechanical). LOTO on P-101 motor MCC panel confirmed with electricians. Bearing replacement to start after switchover. ETA: 12 hours.",
        "timestamp": "2026-07-20T10:45:00",
        "thread_replies": [],
        "equipment_mentions": ["P-101"],
        "action_required": False,
        "severity": "Info",
        "source": "slack",
        "ingested_at": "2026-07-20T10:45:05",
    },
    {
        "id": "SLACK-007",
        "channel": "#opsbrain-queries",
        "user": "field.tech.02",
        "user_display": "Field Tech (CDU)",
        "user_avatar": "FT",
        "text": "/opsbrain P-101 What are the exact steps to switch from P-101 to P-103?",
        "timestamp": "2026-07-20T11:00:00",
        "thread_replies": [
            {
                "user": "opsbrain-bot",
                "text": "Switchover P-101 → P-103 per SOP-P003 Step 4:\n1. Verify P-103 MOV-103A/B functional\n2. Start P-103 from DCS\n3. Confirm pressure and flow (60 sec)\n4. Slowly close P-101 MOV-101B over 2 min\n5. Close P-101 MOV-101A\n6. Allow P-101 to coast to stop\nSources: SOP-P003 Rev 3, PID-CDU-001 Rev 5",
                "timestamp": "2026-07-20T11:00:08",
            }
        ],
        "equipment_mentions": ["P-101", "P-103"],
        "action_required": False,
        "severity": "Info",
        "source": "slack",
        "ingested_at": "2026-07-20T11:00:05",
    },
]


async def get_slack_messages(equipment_filter: str | None = None, channel: str | None = None) -> list[dict[str, Any]]:
    results = MOCK_SLACK_MESSAGES
    if equipment_filter:
        results = [m for m in results if equipment_filter in m.get("equipment_mentions", [])]
    if channel:
        results = [m for m in results if m["channel"] == channel]
    return results


async def get_slack_summary() -> dict[str, Any]:
    channels = list({m["channel"] for m in MOCK_SLACK_MESSAGES})
    return {
        "provider": "Slack Bolt SDK",
        "status": "connected",
        "total_ingested": len(MOCK_SLACK_MESSAGES),
        "action_required": sum(1 for m in MOCK_SLACK_MESSAGES if m["action_required"]),
        "last_checked": "2026-07-20T11:00:05",
        "monitored_channels": channels,
        "slash_commands": ["/opsbrain <equipment_id> <question>"],
        "bot_name": "opsbrain-bot",
    }


def get_slack_config_stub() -> dict[str, str]:
    return {
        "bot_token": "xoxb-*** (set SLACK_BOT_TOKEN env var)",
        "app_token": "xapp-*** (set SLACK_APP_TOKEN env var)",
        "monitored_channels": "#maintenance-cdu, #plant-ops, #cmms-alerts, #opsbrain-queries",
        "slash_command": "/opsbrain",
        "trigger_keywords": "P-101, P-103, vibration, bearing, alarm, maintenance, CMMS",
    }


# ── DB config loader ──────────────────────────────────────────────────────────

import re as _re
_EQ_PATTERN = _re.compile(r"\b([A-Z]-\d{3}[A-Z]?|[A-Z]{1,3}-\d{2,4})\b")


async def _load_slack_config() -> dict | None:
    try:
        from sqlalchemy import select
        from app.db.database import AsyncSessionLocal
        from app.db import models as mdl
        async with AsyncSessionLocal() as s:
            row = (await s.execute(
                select(mdl.IntegrationConfig).where(mdl.IntegrationConfig.id == "slack")
            )).scalar_one_or_none()
        if row and row.enabled and row.config:
            return row.config
    except Exception:
        pass
    return None


# ── Real Slack SDK fetch ──────────────────────────────────────────────────────

async def _fetch_real_slack(cfg: dict, equipment_filter: str | None = None,
                             channel: str | None = None) -> list[dict[str, Any]]:
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
    except ImportError:
        return []

    token = cfg.get("bot_token", "")
    raw_channels = cfg.get("channels", "#maintenance,#plant-ops")
    channel_list = [c.strip() for c in raw_channels.split(",")]

    client = WebClient(token=token)
    results: list[dict[str, Any]] = []

    for ch_name in channel_list:
        if channel and channel != ch_name:
            continue
        try:
            # Resolve channel name to ID
            ch_id = ch_name
            if not ch_name.startswith("C"):
                resp = client.conversations_list(types="public_channel,private_channel", limit=200)
                for c in (resp.get("channels") or []):
                    if c["name"] == ch_name.lstrip("#"):
                        ch_id = c["id"]
                        break

            hist = client.conversations_history(channel=ch_id, limit=50)
            for msg in (hist.get("messages") or []):
                text = msg.get("text", "")
                eq_mentions = list(dict.fromkeys(_EQ_PATTERN.findall(text)))
                if equipment_filter and equipment_filter not in eq_mentions:
                    continue
                ts_raw = msg.get("ts", "0")
                try:
                    from datetime import timezone
                    dt = datetime.fromtimestamp(float(ts_raw), tz=timezone.utc).isoformat()
                except Exception:
                    dt = datetime.utcnow().isoformat()

                user_id = msg.get("user", "unknown")
                results.append({
                    "id": f"REAL-SLACK-{ch_name}-{ts_raw}",
                    "channel": ch_name if ch_name.startswith("#") else f"#{ch_name}",
                    "user": user_id,
                    "user_display": user_id,
                    "user_avatar": user_id[:2].upper(),
                    "text": text[:1000],
                    "timestamp": dt,
                    "thread_replies": [],
                    "equipment_mentions": eq_mentions,
                    "action_required": any(w in text.lower() for w in [
                        "urgent", "alarm", "overdue", "shutdown", "critical", "immediate"
                    ]),
                    "severity": "High" if "urgent" in text.lower() or "alarm" in text.lower() else "Info",
                    "source": "slack",
                    "ingested_at": datetime.utcnow().isoformat(),
                })
        except Exception:
            continue

    return results


async def test_slack_connection(cfg: dict) -> tuple[bool, str]:
    """Test Slack bot token. Returns (ok, message)."""
    try:
        from slack_sdk import WebClient
    except ImportError:
        return False, "slack-sdk package not installed"
    try:
        token = cfg.get("bot_token", "")
        client = WebClient(token=token)
        resp = client.auth_test()
        bot = resp.get("bot_id", "")
        team = resp.get("team", "")
        return True, f"Connected as bot {bot} in workspace '{team}'."
    except Exception as e:
        return False, f"Slack auth failed: {e}"


# ── Public API (real when configured, mock otherwise) ─────────────────────────

async def get_slack_messages(equipment_filter: str | None = None,
                              channel: str | None = None) -> list[dict[str, Any]]:
    cfg = await _load_slack_config()
    if cfg:
        try:
            messages = await _fetch_real_slack(cfg, equipment_filter, channel)
            # Ingest real messages into DB (async, non-blocking on error)
            try:
                from app.services.integrations.slack_ingestor import ingest_slack_messages
                await ingest_slack_messages(messages)
            except Exception:
                pass
            return messages
        except Exception:
            pass
    results = MOCK_SLACK_MESSAGES
    if equipment_filter:
        results = [m for m in results if equipment_filter in m.get("equipment_mentions", [])]
    if channel:
        results = [m for m in results if m["channel"] == channel]
    return results


async def get_slack_summary() -> dict[str, Any]:
    cfg = await _load_slack_config()
    if cfg:
        return {
            "provider": "Slack SDK",
            "status": "live",
            "channels": cfg.get("channels", ""),
            "mode": "real",
        }
    channels = list({m["channel"] for m in MOCK_SLACK_MESSAGES})
    return {
        "provider": "Slack Bolt SDK",
        "status": "demo",
        "total_ingested": len(MOCK_SLACK_MESSAGES),
        "action_required": sum(1 for m in MOCK_SLACK_MESSAGES if m["action_required"]),
        "last_checked": "2026-07-20T11:00:05",
        "monitored_channels": channels,
        "slash_commands": ["/opsbrain <equipment_id> <question>"],
        "bot_name": "opsbrain-bot",
        "mode": "mock",
    }

