"""
AI Operations Brain — Email Integration Service
Reads maintenance-related emails via IMAP (Gmail / Outlook / Exchange).
Falls back to rich mock data so the demo works without a real mailbox.

Real usage:
  Configure via frontend Integrations page → Email → enter IMAP credentials → Save → Test.
  The service loads credentials from the DB and polls in real-time.
"""
import asyncio
import email
import email.header
import email.message
import email.utils
import imaplib
import re
from datetime import datetime
from typing import Any

# ── Mock data (fallback when no real IMAP is configured) ─────────────────────

MOCK_EMAILS: list[dict[str, Any]] = [
    {
        "id": "EMAIL-001",
        "uid": "4421",
        "from": "rajesh.kumar@refinery.com",
        "to": "maintenance@refinery.com",
        "subject": "URGENT: P-101 Bearing Making Grinding Noise - Vib 7.2 mm/s",
        "date": "2026-07-20T10:15:00",
        "body": (
            "Team,\n\n"
            "I did rounds at 10:00 and noticed an unusual grinding noise from P-101 drive-end bearing. "
            "Checked the DCS and vibration VT-101A is reading 7.2 mm/s, which is above our alarm of 7.1 mm/s.\n\n"
            "History: Last lubrication was 10-May-2026 (MR-2026-012). We are now 12 days overdue on the biweekly schedule.\n\n"
            "This matches the exact precursor pattern from INC-2022-034 where the bearing failed 18 hours after alarm.\n\n"
            "I recommend we plan a controlled shutdown within 4 hours and switch to P-103 (standby).\n"
            "Spare parts confirmed: SKF 6311 x3 in Warehouse A Rack 4 Bin 12.\n\n"
            "Please advise. PTW application submitted (PTW-2026-0892).\n\n"
            "Rajesh Kumar\n"
            "Sr. Maintenance Technician | CDU Unit 4 | Ext: 4512"
        ),
        "equipment_mentions": ["P-101", "P-103", "VT-101A"],
        "action_required": True,
        "extracted_entities": {
            "equipment": "P-101",
            "symptom": "grinding noise, vibration 7.2 mm/s above alarm",
            "severity": "High",
            "action": "controlled shutdown, switch to P-103",
            "spare_parts": ["SKF 6311"],
            "ptw_number": "PTW-2026-0892",
        },
        "source": "email",
        "ingested_at": "2026-07-20T10:17:00",
        "processed": True,
    },
    {
        "id": "EMAIL-002",
        "uid": "4418",
        "from": "amit.shah@refinery.com",
        "to": "stores@refinery.com",
        "cc": "rajesh.kumar@refinery.com",
        "subject": "Spare Parts Requisition - Bearing SKF 6311 x2 for P-101/P-103",
        "date": "2026-07-20T09:30:00",
        "body": (
            "Hi Stores,\n\n"
            "Please reserve the following spare parts for planned maintenance on P-101 and P-103:\n\n"
            "1. SKF Bearing 6311-2RS    Qty: 2    Location: WH-A Rack 4 Bin 12\n"
            "2. SKF LGMT 2 Grease 400g  Qty: 4    Location: WH-A Rack 2 Bin 1\n\n"
            "Work order: WO-2026-0445 (P-101 preventive maintenance)\n"
            "Required by: 21-Jul-2026 08:00\n\n"
            "Regards,\nAmit Shah\nMaintenance Technician | Ext: 4514"
        ),
        "equipment_mentions": ["P-101", "P-103"],
        "action_required": False,
        "extracted_entities": {
            "equipment": ["P-101", "P-103"],
            "spare_parts": ["SKF 6311-2RS x2", "SKF LGMT 2 x4"],
            "work_order": "WO-2026-0445",
        },
        "source": "email",
        "ingested_at": "2026-07-20T09:32:00",
        "processed": True,
    },
    {
        "id": "EMAIL-003",
        "uid": "4410",
        "from": "cmms-noreply@plant-sap.com",
        "to": "maintenance@refinery.com",
        "subject": "SAP PM Notification: Overdue PM Order - P-101 Lubrication",
        "date": "2026-07-20T08:00:00",
        "body": (
            "AUTOMATED NOTIFICATION FROM SAP PM\n\n"
            "The following preventive maintenance order is OVERDUE:\n\n"
            "Equipment Tag  : P-101 (Crude Oil Feed Pump)\n"
            "Work Order     : PM-2026-10044\n"
            "Description    : Biweekly lubrication and vibration check\n"
            "Planned Date   : 2026-07-08\n"
            "Overdue By     : 12 days\n"
            "Assigned To    : Rajesh Kumar\n"
            "Priority       : HIGH\n\n"
            "Please complete this order immediately or escalate to supervisor.\n\n"
            "SAP Plant Maintenance System | Automated Alert"
        ),
        "equipment_mentions": ["P-101"],
        "action_required": True,
        "extracted_entities": {
            "equipment": "P-101",
            "work_order": "PM-2026-10044",
            "overdue_days": 12,
            "task": "biweekly lubrication",
        },
        "source": "email",
        "ingested_at": "2026-07-20T08:02:00",
        "processed": True,
    },
    {
        "id": "EMAIL-004",
        "uid": "4390",
        "from": "flowserve.support@flowserve.com",
        "to": "rajesh.kumar@refinery.com",
        "subject": "RE: P-101 PVXM-100 Technical Query - High Vibration",
        "date": "2026-07-19T16:45:00",
        "body": (
            "Dear Rajesh,\n\n"
            "Thank you for contacting Flowserve Technical Support regarding your PVXM-100 pump (S/N FS-2018-4412).\n\n"
            "In response to your query about sustained vibration above 7.1 mm/s:\n\n"
            "RECOMMENDATION:\n"
            "Based on the operating history and symptoms described, the most probable cause is bearing wear "
            "due to the lubrication interval being exceeded. Our service data shows that PVXM-100 pumps "
            "operating in crude oil service with the SKF 6311 bearing show accelerated wear when lubrication "
            "intervals exceed 14-21 days.\n\n"
            "DO NOT continue operating above alarm setpoint. Initiate shutdown within 2 hours per your site SOP.\n\n"
            "Recommended action:\n"
            "1. Shutdown pump\n"
            "2. Inspect bearing - expect grease hardening / inadequate film\n"
            "3. Replace SKF 6311 bearing (both DE and NDE recommended)\n"
            "4. Resume 14-day lubrication schedule strictly\n\n"
            "Service bulletin SB-PVXM-2023-04 applies - attached.\n\n"
            "Best regards,\n"
            "James Wilson | Flowserve Global Technical Support | Case: CS-2026-88341"
        ),
        "equipment_mentions": ["P-101"],
        "action_required": True,
        "extracted_entities": {
            "equipment": "P-101",
            "manufacturer": "Flowserve",
            "root_cause": "bearing wear due to lubrication interval exceeded",
            "recommendation": "shutdown within 2 hours, replace SKF 6311 bearing",
            "service_bulletin": "SB-PVXM-2023-04",
        },
        "source": "email",
        "ingested_at": "2026-07-19T16:47:00",
        "processed": True,
    },
    {
        "id": "EMAIL-005",
        "uid": "4405",
        "from": "priya.nair@refinery.com",
        "to": "maintenance@refinery.com",
        "subject": "P-103 Commissioning Complete - Standby Ready for P-101",
        "date": "2026-07-20T07:00:00",
        "body": (
            "Team,\n\n"
            "P-103 commissioning was completed on 18-Jul. Key results:\n"
            "- Vibration DE: 2.1 mm/s (well within normal)\n"
            "- Bearing temp: 43 degC\n"
            "- Discharge pressure: 8.6 bar (normal)\n"
            "- All 15 pre-commissioning checklist items passed (except AI system update - pending)\n\n"
            "P-103 is ready to take over from P-101 immediately if needed.\n"
            "Switchover procedure: SOP-P003 Step 4.\n\n"
            "IMPORTANT: If P-101 vibration continues to rise, initiate switchover ASAP.\n\n"
            "Priya Nair\nInspection Engineer | Ext: 4521"
        ),
        "equipment_mentions": ["P-101", "P-103"],
        "action_required": False,
        "extracted_entities": {
            "equipment": ["P-101", "P-103"],
            "p103_status": "ready for switchover",
            "sop_reference": "SOP-P003",
        },
        "source": "email",
        "ingested_at": "2026-07-20T07:02:00",
        "processed": True,
    },
]


async def get_emails(equipment_filter: str | None = None) -> list[dict[str, Any]]:
    """Return mock emails, optionally filtered by equipment tag."""
    if equipment_filter:
        return [
            e for e in MOCK_EMAILS
            if equipment_filter in e.get("equipment_mentions", [])
        ]
    return MOCK_EMAILS


async def get_email_summary() -> dict[str, Any]:
    return {
        "provider": "IMAP / Gmail",
        "status": "connected",
        "total_ingested": len(MOCK_EMAILS),
        "action_required": sum(1 for e in MOCK_EMAILS if e["action_required"]),
        "last_checked": "2026-07-20T10:17:00",
        "monitored_folders": ["INBOX", "Maintenance-Alerts", "SAP-Notifications"],
        "filter_keywords": ["P-101", "P-103", "vibration", "bearing", "alarm", "maintenance", "CMMS"],
    }


def get_imap_connection_stub() -> dict[str, str]:
    """Return connection configuration template for UI display."""
    return {
        "host": "imap.gmail.com",
        "port": "993",
        "user": "maintenance@yourplant.com",
        "password": "*** (set EMAIL_PASSWORD env var)",
        "folder": "INBOX",
        "poll_interval_minutes": "5",
    }


# ── DB config loader ──────────────────────────────────────────────────────────

async def _load_email_config() -> dict | None:
    """Return the saved email config from DB if enabled, else None."""
    try:
        from sqlalchemy import select
        from app.db.database import AsyncSessionLocal
        from app.db import models as mdl
        async with AsyncSessionLocal() as s:
            row = (await s.execute(
                select(mdl.IntegrationConfig).where(mdl.IntegrationConfig.id == "email")
            )).scalar_one_or_none()
        if row and row.enabled and row.config:
            return row.config
    except Exception:
        pass
    return None


# ── Real IMAP fetch (runs in thread pool to avoid blocking) ───────────────────

_EQ_PATTERN = re.compile(r"\b([A-Z]-\d{3}[A-Z]?|[A-Z]{1,3}-\d{2,4})\b")

MAINT_KEYWORDS = [
    "vibration", "bearing", "lubrication", "seal", "alarm", "maintenance",
    "overdue", "inspection", "failure", "breakdown", "pump", "compressor",
    "leak", "pressure", "temperature", "work order", "ptw", "shutdown",
]


def _decode_header(h: str) -> str:
    parts = email.header.decode_header(h)
    return "".join(
        p.decode(enc or "utf-8") if isinstance(p, bytes) else p
        for p, enc in parts
    )


def _extract_body(msg: email.message.Message) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode(errors="replace")
                    break
                except Exception:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode(errors="replace")
        except Exception:
            pass
    return body[:3000]


def _fetch_imap_sync(cfg: dict) -> list[dict[str, Any]]:
    host    = cfg.get("host", "imap.gmail.com")
    port    = int(cfg.get("port", 993))
    user    = cfg.get("user", "")
    password = cfg.get("password", "")
    folder  = cfg.get("folder", "INBOX")

    conn = imaplib.IMAP4_SSL(host, port)
    conn.login(user, password)
    conn.select(folder, readonly=True)

    # Fetch last 30 messages
    _, data = conn.search(None, "ALL")
    uids = data[0].split()[-30:]
    results: list[dict[str, Any]] = []

    for uid in reversed(uids):
        try:
            _, msg_data = conn.fetch(uid, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            subject = _decode_header(msg.get("Subject", ""))
            from_   = _decode_header(msg.get("From", ""))
            date_str = msg.get("Date", "")
            body = _extract_body(msg)

            combined = f"{subject} {body}".lower()
            is_relevant = any(kw in combined for kw in MAINT_KEYWORDS)
            if not is_relevant:
                continue

            eq_mentions = list(dict.fromkeys(_EQ_PATTERN.findall(f"{subject} {body}")))

            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_str).isoformat()
            except Exception:
                dt = datetime.utcnow().isoformat()

            results.append({
                "id": f"REAL-EMAIL-{uid.decode()}",
                "uid": uid.decode(),
                "from": from_,
                "to": msg.get("To", ""),
                "subject": subject,
                "date": dt,
                "body": body,
                "equipment_mentions": eq_mentions,
                "action_required": any(w in combined for w in ["urgent", "alarm", "overdue", "immediate", "critical"]),
                "source": "email",
                "ingested_at": datetime.utcnow().isoformat(),
                "processed": True,
            })
        except Exception:
            continue

    conn.logout()
    return results


async def _fetch_real_emails(cfg: dict, equipment_filter: str | None = None) -> list[dict[str, Any]]:
    loop = asyncio.get_event_loop()
    emails = await loop.run_in_executor(None, _fetch_imap_sync, cfg)
    if equipment_filter:
        emails = [e for e in emails if equipment_filter in e.get("equipment_mentions", [])]
    return emails


async def test_imap_connection(cfg: dict) -> tuple[bool, str]:
    """Test IMAP credentials. Returns (ok, message)."""
    def _test():
        host    = cfg.get("host", "imap.gmail.com")
        port    = int(cfg.get("port", 993))
        user    = cfg.get("user", "")
        password = cfg.get("password", "")
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, password)
        conn.select("INBOX", readonly=True)
        _, data = conn.search(None, "ALL")
        count = len(data[0].split()) if data and data[0] else 0
        conn.logout()
        return count

    try:
        loop = asyncio.get_event_loop()
        count = await loop.run_in_executor(None, _test)
        return True, f"Connected successfully — {count} messages in INBOX."
    except imaplib.IMAP4.error as e:
        return False, f"IMAP auth failed: {e}"
    except Exception as e:
        return False, f"Connection error: {e}"


# ── Public API (real when configured, mock otherwise) ─────────────────────────

async def get_emails(equipment_filter: str | None = None) -> list[dict[str, Any]]:
    cfg = await _load_email_config()
    if cfg:
        try:
            messages = await _fetch_real_emails(cfg, equipment_filter)
            # Ingest real emails into DB + knowledge base
            try:
                from app.services.integrations.email_ingestor import ingest_emails
                await ingest_emails(messages)
            except Exception:
                pass
            return messages
        except Exception:
            pass
    result = MOCK_EMAILS
    if equipment_filter:
        result = [e for e in result if equipment_filter in e.get("equipment_mentions", [])]
    return result


async def get_email_summary() -> dict[str, Any]:
    cfg = await _load_email_config()
    if cfg:
        return {
            "provider": f"IMAP — {cfg.get('host', '')}",
            "status": "live",
            "user": cfg.get("user", ""),
            "folder": cfg.get("folder", "INBOX"),
            "mode": "real",
        }
    return {
        "provider": "IMAP / Gmail",
        "status": "demo",
        "total_ingested": len(MOCK_EMAILS),
        "action_required": sum(1 for e in MOCK_EMAILS if e["action_required"]),
        "last_checked": "2026-07-20T10:17:00",
        "mode": "mock",
    }
