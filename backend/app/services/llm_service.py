"""
AI Operations Brain — LLM Service
Handles all OpenAI calls with structured output and graceful fallback.
The fallback ensures the demo works without an API key during presentations.
"""
import json
import logging
import os
from datetime import datetime
from typing import Any
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI | None:
    if not settings.openai_api_key:
        return None
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


SYSTEM_PROMPT = """You are an AI Operations Brain for an industrial oil refinery plant.
You think like a 25-year senior plant engineer — precise, safety-first, and deeply experienced.
You have been given structured context from 5 specialized agents.
Synthesize all context into a single comprehensive operational assessment.
Always prioritize safety. Be specific about timeframes and risk levels.

SOURCE ATTRIBUTION RULES (critical — always follow):
- Every claim, probability, and recommendation MUST cite its source.
- For each source entry set source_type as one of:
    "uploaded_doc"  — a file the operator uploaded (doc_id starts with UPLOAD-)
    "knowledge_base" — a seeded document in the system (OEM manual, SOP, regulation, standard)
    "incident_history" — an incident record from the plant history
    "maintenance_record" — a maintenance record from the CMMS
    "ai_inference" — your own engineering knowledge (no document backs this claim)
- Set doc_id to the exact document ID string (e.g. "DOC-001", "UPLOAD-XXXXXXXX") or null for ai_inference.
- Cite ONLY sources actually present in the provided context.
- If you use your own knowledge beyond what was provided, mark it "ai_inference" with doc_id null.

Return ONLY valid JSON matching the schema provided. No markdown, no extra text.

RESPONSE MODE — choose based on the operator's intent:

1. CONVERSATIONAL / FACTUAL queries (greetings, simple status checks, "is it safe?",
   "what is the health score?", "how many incidents?", "thanks", "what does that mean?",
   follow-up clarifications that don't require a full diagnostic assessment):
   Return ONLY: {"response_type": "chat", "message": "your concise, direct answer in 1-3 sentences"}

2. DIAGNOSTIC / ANALYTICAL / WORK-ORDER queries (symptoms reported, root cause analysis,
   compliance check, risk assessment, generate checklist or work order, troubleshooting):
   Return the full analysis schema below with "response_type": "analysis" added at the top."""

SYNTHESIS_SCHEMA = """{
  "response_type": "analysis",
  "risk_level": "Critical|High|Medium|Low",
  "risk_summary": "one concise sentence",
  "probable_causes": [
    {"cause": "string", "probability": 0-100, "evidence": "string citing source"}
  ],
  "immediate_actions": [
    {"priority": 1, "action": "string", "timeframe": "immediately|within 1h|within 4h|within 24h|planned", "owner": "string"}
  ],
  "inspection_checklist": ["item1", "item2"],
  "similar_incidents": [
    {"incident_id": "string", "date": "string", "similarity_score": 0-100, "lesson": "string"}
  ],
  "compliance_issues": [
    {"regulation": "string", "issue": "string", "severity": "High|Medium|Low"}
  ],
  "affected_downstream": ["equipment_id"],
  "required_permits": ["string"],
  "predicted_failure_window": "string — timeframe if no action taken",
  "work_order": {
    "type": "Emergency|Corrective|Preventive",
    "description": "one sentence summary of the work",
    "estimated_duration_hours": 0,
    "required_technicians": 0,
    "spare_parts": ["part name — stock location or quantity"],
    "safety_precautions": ["string"],
    "procedure_steps": [
      {
        "step": 1,
        "phase": "Preparation|Isolation|Execution|Verification|Restart",
        "title": "short action title (≤8 words)",
        "description": "detailed instruction for the technician",
        "safety_note": "specific safety warning for this step or null",
        "expected_duration_minutes": 0
      }
    ]
  },
  "sources": [
    {
      "document": "exact document name as provided in context",
      "doc_id": "document ID string (e.g. DOC-001) or null for ai_inference",
      "source_type": "uploaded_doc|knowledge_base|incident_history|maintenance_record|ai_inference",
      "section": "section number or descriptor",
      "confidence": 0-100,
      "excerpt": "exact quoted text from the source, or null"
    }
  ],
  "explanation": "2-3 sentence reasoning chain"
}"""


async def synthesize_query(
    equipment_id: str,
    query: str,
    equipment_context: dict[str, Any],
    maintenance_context: dict[str, Any],
    compliance_context: dict[str, Any],
    lessons_context: dict[str, Any],
    documents_context: dict[str, Any],
    history: list[dict[str, str]] | None = None,
    plant_context: dict[str, Any] | None = None,
    comms_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call GPT-4.1 to synthesize agent contexts into a final recommendation."""
    client = _get_client()
    if client is None:
        return _get_fallback_response(equipment_id, query)

    user_prompt = f"""
OPERATOR QUERY: {query}

EQUIPMENT ID: {equipment_id}
{f"PROJECT: {plant_context.get('project_name', '')} ({plant_context.get('project_code', '')})" if plant_context and plant_context.get('project_name') else ""}
{f"PLANT / UNIT: {plant_context.get('plant_name', '')} ({plant_context.get('plant_code', '')}) — {plant_context.get('plant_type', '')}, Area: {plant_context.get('plant_area', '')}" if plant_context and plant_context.get('plant_name') else ""}
EQUIPMENT PROFILE:
{json.dumps(equipment_context, indent=2)}

MAINTENANCE CONTEXT (recent records + overdue items):
{json.dumps(maintenance_context, indent=2)}

COMPLIANCE STATUS:
{json.dumps(compliance_context, indent=2)}

LESSONS LEARNED (similar historical incidents):
{json.dumps(lessons_context, indent=2)}

RELEVANT DOCUMENTS (manual sections, SOPs, standards — each entry includes doc_id):
{json.dumps(documents_context, indent=2)}

NOTE ON SOURCES:
- Documents with IDs starting with "UPLOAD-" are files the operator uploaded → source_type = "uploaded_doc"
- Documents with IDs starting with "DOC-" are seeded knowledge base documents → source_type = "knowledge_base"
- Incidents (INC-YYYY-NNN) → source_type = "incident_history"
- Maintenance records (MR-YYYY-NNN) → source_type = "maintenance_record"
- Any claim not backed by the above → source_type = "ai_inference", doc_id = null
{f'''
COMMUNICATIONS (emails & Slack messages mentioning this equipment):
{json.dumps(comms_context, indent=2)}
''' if comms_context and (comms_context.get("emails") or comms_context.get("slack_messages")) else ""}
RESPONSE SCHEMA TO FOLLOW:
{SYNTHESIS_SCHEMA}
"""

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *(history or []),
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2500,
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        return _get_fallback_response(equipment_id, query)


def _get_fallback_response(equipment_id: str, query: str) -> dict[str, Any]:
    """Pre-computed demo response for P-101 vibration scenario. Used when API key absent."""
    if equipment_id == "P-101" and "vibration" in query.lower():
        return {
            "risk_level": "High",
            "risk_summary": "Vibration at 7.2 mm/s exceeds alarm threshold (7.1 mm/s); identical precursor pattern to INC-2022-034 where bearing failed 18 hours after alarm.",
            "probable_causes": [
                {
                    "cause": "Drive-end bearing wear due to lubrication overdue 12 days",
                    "probability": 75,
                    "evidence": "INC-2022-034 (Aug 2022): same pump, same vibration signature, lubrication interval exceeded → bearing failure in 18 hours",
                },
                {
                    "cause": "Coupling misalignment (secondary)",
                    "probability": 15,
                    "evidence": "Coupling insert wear noted in April 2026 inspection (DOC-004, Finding F-001) — possible misalignment propagation",
                },
                {
                    "cause": "Process cavitation",
                    "probability": 10,
                    "evidence": "Discharge pressure slightly low (7.8 vs 8.5 bar) — minor NPSH concern; less likely given flow rate near normal",
                },
            ],
            "immediate_actions": [
                {
                    "priority": 1,
                    "action": "Notify supervisor S. Venkataraman and initiate planned shutdown within 4 hours per OISD-117 Sec 8.3 compliance window",
                    "timeframe": "within 1h",
                    "owner": "Shift Supervisor",
                },
                {
                    "priority": 2,
                    "action": "Increase vibration monitoring frequency to every 30 minutes and log all readings in CMMS",
                    "timeframe": "immediately",
                    "owner": "Rajesh Kumar",
                },
                {
                    "priority": 3,
                    "action": "Issue PTW Class C for corrective maintenance — bearing inspection and lubrication",
                    "timeframe": "within 2h",
                    "owner": "Maintenance Coordinator",
                },
                {
                    "priority": 4,
                    "action": "Prepare standby arrangement for P-101B (spare pump) and notify downstream HX-201 operator",
                    "timeframe": "within 2h",
                    "owner": "Operations Supervisor",
                },
            ],
            "inspection_checklist": [
                "Check bearing housing temperature (DE and NDE) — alarm at 75°C",
                "Inspect lubrication fittings — verify grease delivery path clear",
                "Check coupling alignment with laser tool (limit: 0.05mm)",
                "Inspect seal chamber pressure — verify >0.2 bar above baseline",
                "Check suction strainer differential pressure — rule out cavitation",
                "Listen for bearing noise (high-pitch squeal = advanced wear)",
                "Review motor current trend — increase indicates mechanical drag",
                "Verify MOV-101A/B isolation valves functional for emergency shutdown",
            ],
            "similar_incidents": [
                {
                    "incident_id": "INC-2022-034",
                    "date": "2022-08-14",
                    "similarity_score": 91,
                    "lesson": "Same pump, same vibration pattern (4.2→8.7 mm/s over 6 hours). Lubrication overdue 15 days at that time. Bearing failed 18 hours after alarm — STOP PUMP before 18-hour mark.",
                },
                {
                    "incident_id": "INC-2023-067",
                    "date": "2023-11-08",
                    "similarity_score": 78,
                    "lesson": "P-202 (sister pump): vibration 7.8 mm/s → bearing failure 14 hours later. Different root cause (cavitation) but same vibration signature and failure timeline.",
                },
            ],
            "compliance_issues": [
                {
                    "regulation": "OISD-117 Section 8.3",
                    "issue": "Vibration exceeds alarm threshold (7.2 > 7.1 mm/s). Shutdown or written risk assessment required within 2 hours of alarm onset.",
                    "severity": "High",
                },
                {
                    "regulation": "OISD-117 Section 8.3",
                    "issue": "Last vibration log entry was 6.2 hours ago — monitoring interval violation (required: every 4 hours)",
                    "severity": "High",
                },
                {
                    "regulation": "SOP-P-001 Section 3.1",
                    "issue": "Lubrication maintenance overdue by 12 days — contributing factor to current vibration issue",
                    "severity": "Medium",
                },
            ],
            "affected_downstream": ["HX-201", "V-301"],
            "required_permits": [
                "PTW Class C — Mechanical/Rotating Equipment Work",
                "LOTO (Lock Out / Tag Out) — Electrical isolation of P-101 motor",
            ],
            "predicted_failure_window": "12–18 hours from now if operation continues above alarm — based on INC-2022-034 historical pattern",
            "work_order": {
                "type": "Emergency Corrective",
                "description": "Shutdown P-101, isolate using MOV-101A/B, inspect and replace DE bearing assembly, perform lubrication, verify alignment, conduct run-up test before restart",
                "estimated_duration_hours": 12,
                "required_technicians": 2,
                "spare_parts": ["SKF Bearing 6311 (1 unit) — available, Warehouse A Rack 4", "SKF LGMT 2 Grease (2 cartridges)"],
                "safety_precautions": [
                    "LOTO electrical before any mechanical work",
                    "Allow pump to cool 30 minutes after shutdown",
                    "Verify zero energy state before bearing housing opening",
                    "Petroleum vapor monitoring required during seal area work",
                ],
                "procedure_steps": [
                    {
                        "step": 1,
                        "phase": "Preparation",
                        "title": "Notify supervisor and issue PTW",
                        "description": "Immediately notify Shift Supervisor S. Venkataraman of vibration alarm. Issue PTW Class C (Machinery) from the control room. Confirm standby pump P-101B is available and ready.",
                        "safety_note": "Do not start any mechanical work without a valid PTW in hand.",
                        "expected_duration_minutes": 20,
                    },
                    {
                        "step": 2,
                        "phase": "Preparation",
                        "title": "Switch load to standby pump P-101B",
                        "description": "Start P-101B and gradually transfer flow. Confirm discharge pressure on P-101B reaches ≥8.0 bar and flow ≥230 m³/hr before proceeding. Notify downstream HX-201 operator.",
                        "safety_note": None,
                        "expected_duration_minutes": 15,
                    },
                    {
                        "step": 3,
                        "phase": "Isolation",
                        "title": "Controlled shutdown and LOTO of P-101",
                        "description": "Close suction MOV-101A, then discharge MOV-101B. Allow pump to coast to stop naturally — do NOT use braking. Apply LOTO tag on MCC Panel and suction/discharge valves. Log shutdown time in CMMS.",
                        "safety_note": "Verify zero energy state: no rotation, valves confirmed closed, electrical de-energised.",
                        "expected_duration_minutes": 30,
                    },
                    {
                        "step": 4,
                        "phase": "Preparation",
                        "title": "Cool-down wait and area preparation",
                        "description": "Allow pump to cool for minimum 30 minutes. Set up petroleum vapor monitor — alarm threshold 10% LEL. Lay out tools: bearing puller, torque wrench, dial indicator, laser alignment kit.",
                        "safety_note": "Continuous vapor monitoring required. Evacuate if reading exceeds 10% LEL.",
                        "expected_duration_minutes": 40,
                    },
                    {
                        "step": 5,
                        "phase": "Execution",
                        "title": "Open bearing housing and inspect DE bearing",
                        "description": "Remove bearing housing cover (6× M16 bolts, 110 Nm torque). Visually inspect SKF 6311 bearing for spalling, pitting, or discolouration. Measure bearing clearance with feeler gauge — acceptable: 0.02–0.05 mm. Photograph findings for CMMS record.",
                        "safety_note": "Wear cut-resistant gloves — bearing edges may be sharp if failed.",
                        "expected_duration_minutes": 45,
                    },
                    {
                        "step": 6,
                        "phase": "Execution",
                        "title": "Replace DE bearing assembly",
                        "description": "Use bearing puller to remove old SKF 6311. Clean housing bore and shaft journal with lint-free cloth. Heat new bearing to 80°C (induction heater) before installation. Press to shoulder — confirm seating with dial indicator. New bearing: Warehouse A, Rack 4, Bin 12.",
                        "safety_note": "Use thermal gloves when handling heated bearing. Do not exceed 110°C.",
                        "expected_duration_minutes": 60,
                    },
                    {
                        "step": 7,
                        "phase": "Execution",
                        "title": "Relubricate bearing — overdue 12 days",
                        "description": "Inject 150 ml SKF LGMT 2 grease per bearing (DE and NDE) using grease gun via fittings. Purge old grease until fresh grease appears at relief fitting. Update lubrication log in CMMS. Reset 14-day lubrication interval.",
                        "safety_note": None,
                        "expected_duration_minutes": 20,
                    },
                    {
                        "step": 8,
                        "phase": "Verification",
                        "title": "Check and correct shaft alignment",
                        "description": "Reconnect coupling. Perform laser alignment check using Fluke 830. Acceptable limit: ≤0.05 mm angular and parallel. Adjust motor position if required. Record final alignment values in CMMS (Ref: MR-2026-003 baseline: 0.03 mm).",
                        "safety_note": None,
                        "expected_duration_minutes": 45,
                    },
                    {
                        "step": 9,
                        "phase": "Verification",
                        "title": "Reassemble and pre-start checks",
                        "description": "Reinstall bearing housing cover with new gasket (torque to 110 Nm). Rotate shaft by hand — confirm smooth rotation without binding. Check seal chamber pressure gauge — should read ≥0.2 bar above suction. Confirm all instruments reconnected.",
                        "safety_note": None,
                        "expected_duration_minutes": 30,
                    },
                    {
                        "step": 10,
                        "phase": "Restart",
                        "title": "Remove LOTO and controlled restart",
                        "description": "Remove all LOTO devices. Open suction MOV-101A. Start pump and crack open discharge MOV-101B slowly to build pressure. Monitor vibration for first 10 minutes — must remain below 4.5 mm/s. Confirm bearing temperature stable below 55°C after 30 minutes.",
                        "safety_note": "Abort restart if vibration exceeds 5.0 mm/s within first 10 minutes.",
                        "expected_duration_minutes": 45,
                    },
                    {
                        "step": 11,
                        "phase": "Restart",
                        "title": "Close PTW and update CMMS",
                        "description": "Confirm P-101 running normally — vibration <4.5 mm/s, bearing temp <55°C, flow ≥238 m³/hr. Close PTW with supervisor sign-off. Create corrective maintenance record in CMMS with all findings, parts used, and vibration baseline readings.",
                        "safety_note": None,
                        "expected_duration_minutes": 20,
                    },
                ],
            },
            "sources": [
                {
                    "document": "INC-2022-034 Incident Investigation Report",
                    "doc_id": "INC-2022-034",
                    "source_type": "incident_history",
                    "section": "Root Cause Analysis & Lessons Learned",
                    "confidence": 91,
                    "excerpt": "Vibration increased from 4.2 to 8.7 mm/s over 6 hours. Lubrication interval exceeded. Bearing failed 18 hours after alarm threshold exceeded.",
                },
                {
                    "document": "Flowserve PVXM-100 OEM Manual",
                    "doc_id": "DOC-001",
                    "source_type": "knowledge_base",
                    "section": "Section 4.2 — Vibration Analysis",
                    "confidence": 87,
                    "excerpt": "Sustained vibration above alarm setpoint (7.1 mm/s) typically results in bearing failure within 12–24 hours. Relubricate every 14 days maximum.",
                },
                {
                    "document": "OISD Standard 117 — Section 8.3",
                    "doc_id": "DOC-003",
                    "source_type": "knowledge_base",
                    "section": "Vibration Monitoring Requirements",
                    "confidence": 95,
                    "excerpt": "Equipment operating above alarm setpoint for more than 2 continuous hours must be shut down or a written risk assessment submitted.",
                },
                {
                    "document": "ISO 10816-3 Vibration Severity",
                    "doc_id": "DOC-005",
                    "source_type": "knowledge_base",
                    "section": "Zone D Classification",
                    "confidence": 93,
                    "excerpt": "7.1+ mm/s = Zone D (Danger zone) — risk of damage if operation continues.",
                },
                {
                    "document": "P-101 Annual Inspection Report — April 2026",
                    "doc_id": "DOC-004",
                    "source_type": "knowledge_base",
                    "section": "Open Finding F-001",
                    "confidence": 74,
                    "excerpt": "Coupling insert showing minor wear — schedule replacement within 90 days. Potential misalignment contributor.",
                },
            ],
            "explanation": "The vibration pattern (gradual increase over 4 days, now exceeding alarm threshold) combined with 12-day overdue lubrication exactly matches the precursor profile of INC-2022-034 (Aug 2022), which resulted in complete bearing failure 18 hours after alarm. The probability of bearing failure is 75% within the next 18 hours if no action is taken. OISD-117 compliance requires shutdown or risk assessment within 2 hours. Immediate controlled shutdown and bearing inspection is the recommended course of action.",
        }

    return {
        "risk_level": "Medium",
        "risk_summary": "Query received. Please provide equipment ID and specific symptom for detailed analysis.",
        "probable_causes": [],
        "immediate_actions": [{"priority": 1, "action": "Provide more details about the specific symptom", "timeframe": "immediately", "owner": "Operator"}],
        "inspection_checklist": [],
        "similar_incidents": [],
        "compliance_issues": [],
        "affected_downstream": [],
        "required_permits": [],
        "predicted_failure_window": "Unknown — insufficient data",
        "work_order": {"type": "Preventive", "description": "Pending more information", "estimated_duration_hours": 0, "required_technicians": 1, "spare_parts": [], "safety_precautions": []},
        "sources": [],
        "explanation": "Insufficient context to generate analysis.",
    }


# ── Plant-wide Compliance AI Analysis ────────────────────────────────────────

_COMPLIANCE_SYSTEM = """You are a senior HSE (Health, Safety & Environment) compliance officer
at an oil refinery with 20+ years of experience in OISD, ISO, Factory Act, and internal SOP audits.
Analyse the provided plant-wide compliance data and return ONLY valid JSON — no markdown, no extra text."""

_COMPLIANCE_ANALYSIS_SCHEMA = """{
  "overall_risk": "Critical|High|Medium|Low",
  "overall_summary": "2-3 sentence executive summary of plant compliance posture",
  "compliance_score_trend": "Improving|Stable|Declining",
  "top_regulations_at_risk": [
    {"regulation": "string", "equipment_count": 0, "avg_severity": "High|Medium|Low", "risk_note": "string"}
  ],
  "action_items": [
    {
      "priority": 1,
      "title": "concise action title (max 10 words)",
      "description": "detailed what and why — be specific",
      "regulation": "exact regulation name e.g. OISD-117",
      "equipment_ids": ["P-101"],
      "severity": "Critical|High|Medium|Low",
      "deadline": "immediately|within 24h|within 7 days|within 30 days",
      "owner": "Maintenance|HSE|Operations|Management",
      "estimated_effort": "30 min|2 hours|1 day|1 week"
    }
  ],
  "equipment_risk_ranking": [
    {"equipment_id": "string", "equipment_name": "string", "compliance_score": 0, "risk_level": "Critical|High|Medium|Low", "primary_issue": "string"}
  ],
  "key_findings": [
    {"finding": "string", "impact": "string", "recommendation": "string"}
  ],
  "regulatory_breakdown": [
    {"regulation": "string", "total_violations": 0, "high_violations": 0, "equipment_affected": ["string"]}
  ]
}"""


async def analyze_compliance_plant(
    all_compliance: list[dict[str, Any]],
    all_equipment: list[dict[str, Any]],
) -> dict[str, Any]:
    """Call GPT to produce a plant-wide compliance analysis with prioritised action items."""
    client = _get_client()
    if client is None:
        return _fallback_compliance_analysis(all_compliance)

    equipment_summary = [
        {
            "id": e.get("id"),
            "name": e.get("name"),
            "type": e.get("type"),
            "criticality": e.get("criticality"),
            "status": e.get("status"),
        }
        for e in all_equipment
    ]

    user_prompt = f"""
PLANT COMPLIANCE DATA (all equipment):
{json.dumps(all_compliance, indent=2)}

EQUIPMENT SUMMARY:
{json.dumps(equipment_summary, indent=2)}

Perform a comprehensive HSE compliance analysis for the entire plant.
Return a JSON object matching EXACTLY this schema:
{_COMPLIANCE_ANALYSIS_SCHEMA}

Rules:
- action_items must be ranked by urgency (1 = most critical, address first)
- equipment_risk_ranking must list ALL equipment sorted worst-first by compliance_score
- key_findings should surface 3-5 most important insights that a plant manager needs today
- regulatory_breakdown must aggregate violations per regulation code across all equipment
"""

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _COMPLIANCE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.15,
            max_tokens=3000,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as exc:
        logger.error("Compliance AI analysis failed: %s", exc)
        return _fallback_compliance_analysis(all_compliance)


def _fallback_compliance_analysis(all_compliance: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic fallback when OpenAI is unavailable."""
    high_issues = sum(c.get("high_issues", 0) for c in all_compliance)
    total_issues = sum(c.get("total_issues", 0) for c in all_compliance)
    scores = [c.get("overall_score", 0) for c in all_compliance if c.get("overall_score") is not None]
    avg_score = round(sum(scores) / max(len(scores), 1))
    risk = "Critical" if avg_score < 60 else "High" if avg_score < 75 else "Medium" if avg_score < 90 else "Low"

    action_items = []
    rank = 1
    for c in all_compliance:
        for issue in (c.get("issues") or []):
            if issue.get("severity") == "High":
                action_items.append({
                    "priority": rank,
                    "title": f"Resolve {issue.get('regulation', 'compliance issue')} on {c.get('equipment_id', '')}",
                    "description": issue.get("description", "High-severity compliance violation requires immediate remediation."),
                    "regulation": issue.get("regulation", ""),
                    "equipment_ids": [c.get("equipment_id", "")],
                    "severity": "High",
                    "deadline": "within 24h",
                    "owner": "Maintenance",
                    "estimated_effort": "2 hours",
                })
                rank += 1
                if rank > 5:
                    break
        if rank > 5:
            break
    for c in all_compliance:
        for issue in (c.get("issues") or []):
            if issue.get("severity") == "Medium" and rank <= 8:
                action_items.append({
                    "priority": rank,
                    "title": f"Address {issue.get('regulation', 'issue')} on {c.get('equipment_id', '')}",
                    "description": issue.get("description", "Medium-severity compliance issue."),
                    "regulation": issue.get("regulation", ""),
                    "equipment_ids": [c.get("equipment_id", "")],
                    "severity": "Medium",
                    "deadline": "within 7 days",
                    "owner": "Maintenance",
                    "estimated_effort": "1 day",
                })
                rank += 1

    reg_map: dict[str, dict[str, Any]] = {}
    for c in all_compliance:
        for issue in (c.get("issues") or []):
            reg = issue.get("regulation", "Unknown")
            if reg not in reg_map:
                reg_map[reg] = {"regulation": reg, "total_violations": 0, "high_violations": 0, "equipment_affected": []}
            reg_map[reg]["total_violations"] += 1
            if issue.get("severity") == "High":
                reg_map[reg]["high_violations"] += 1
            eid = c.get("equipment_id", "")
            if eid and eid not in reg_map[reg]["equipment_affected"]:
                reg_map[reg]["equipment_affected"].append(eid)

    return {
        "overall_risk": risk,
        "overall_summary": (
            f"Plant-wide compliance assessment covering {len(all_compliance)} equipment units. "
            f"Average compliance score is {avg_score}% with {high_issues} high-severity and "
            f"{total_issues} total open violations requiring attention."
        ),
        "compliance_score_trend": "Stable",
        "top_regulations_at_risk": [
            {"regulation": reg, "equipment_count": len(v["equipment_affected"]), "avg_severity": "High" if v["high_violations"] > 0 else "Medium", "risk_note": f"{v['total_violations']} violations across plant"}
            for reg, v in sorted(reg_map.items(), key=lambda x: x[1]["high_violations"], reverse=True)[:4]
        ],
        "action_items": action_items,
        "equipment_risk_ranking": sorted(
            [
                {
                    "equipment_id": c.get("equipment_id", ""),
                    "equipment_name": c.get("equipment_name", c.get("equipment_id", "")),
                    "compliance_score": c.get("overall_score", 0),
                    "risk_level": "Critical" if (c.get("overall_score") or 0) < 60 else "High" if (c.get("overall_score") or 0) < 75 else "Medium" if (c.get("overall_score") or 0) < 90 else "Low",
                    "primary_issue": ((c.get("issues") or [{}])[0].get("description", "No violations")) if c.get("issues") else "Compliant",
                }
                for c in all_compliance
            ],
            key=lambda x: x["compliance_score"],
        ),
        "key_findings": [
            {"finding": f"{high_issues} high-severity regulatory violations detected", "impact": "Risk of regulatory penalty, equipment failure, or safety incident", "recommendation": "Prioritise all high-severity items for immediate remediation"},
            {"finding": f"Plant average compliance score: {avg_score}%", "impact": "Target threshold is typically 90%+ for audit readiness", "recommendation": "Schedule targeted maintenance and documentation reviews"},
            {"finding": f"{len(reg_map)} distinct regulations with active violations", "impact": "Broad regulatory exposure across OISD, ISO, and Factory Act standards", "recommendation": "Assign dedicated HSE officer to track each regulation"},
        ],
        "regulatory_breakdown": list(reg_map.values()),
    }


# ── AI Chat for work orders & checklists ─────────────────────────────────────

_OPS_CHAT_SYSTEM = """You are an industrial AI assistant embedded in a work order management system.
A field technician is actively working through a work order or inspection checklist and needs help.

You have full context: current item state, equipment telemetry, and maintenance history.

Your job:
1. Answer questions clearly and practically, citing evidence from the provided context
2. Propose concrete changes (new steps, items, risk updates) when appropriate
3. Always prioritise safety — never suggest skipping safety steps

Return ONLY valid JSON matching this exact schema:
{
  "answer": "conversational response — markdown allowed for lists/bold",
  "proposed_changes": {
    "description": "new description/query_text if changing",
    "risk_level": "Critical|High|Medium|Low if changing",
    "toggle_items": [{"index": 0, "checked": true}],
    "toggle_steps": [{"step_index": 0, "checked": true}],
    "add_steps": [
      {
        "phase": "Preparation|Isolation|Execution|Verification|Restart",
        "title": "short action title",
        "description": "detailed instruction for the technician",
        "safety_note": "safety warning or null",
        "expected_duration_minutes": 15
      }
    ],
    "add_items": ["checklist item text"]
  }
}

Rules:
- Set proposed_changes to null if no changes are needed
- Only include fields in proposed_changes that you are actually changing/adding
- When suggesting a change, briefly explain why in the answer field
- To mark a checklist item as done or undone use toggle_items with the 0-based index from the items array — NEVER add a new item just to signal completion
- To mark a work order step as done or undone use toggle_steps with the 0-based index from the steps array
- Use add_items / add_steps only to create genuinely new items, not to simulate state changes"""


async def chat_with_ops_item(
    item_type: str,
    item_data: dict[str, Any],
    equipment_context: dict[str, Any],
    message: str,
    history: list[dict[str, str]],
) -> dict[str, Any]:
    """AI chat for a work order or checklist — answers questions and proposes changes."""
    client = _get_client()
    if client is None:
        return {
            "answer": "AI is unavailable (no API key configured). I can see the work order context but cannot generate a response.",
            "proposed_changes": None,
        }

    context_block = (
        f"ITEM TYPE: {item_type.replace('_', ' ').upper()}\n"
        f"CURRENT ITEM:\n{json.dumps(item_data, indent=2, default=str)}\n\n"
        f"EQUIPMENT CONTEXT ({item_data.get('equipment_id', 'unknown')}):\n"
        f"{json.dumps(equipment_context, indent=2, default=str)}"
    )

    messages: list[dict[str, str]] = [
        {"role": "system",    "content": _OPS_CHAT_SYSTEM},
        {"role": "user",      "content": f"CONTEXT — read this before answering:\n\n{context_block}"},
        {"role": "assistant", "content": "Understood. I have reviewed the work order/checklist and equipment context. Ready to help."},
        *history,
        {"role": "user", "content": message},
    ]

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1200,
        )
        result = json.loads(response.choices[0].message.content)
        result.setdefault("answer", "")
        result.setdefault("proposed_changes", None)
        return result
    except Exception as exc:
        logger.warning("OPS chat LLM failed: %s", exc)
        return {
            "answer": "I encountered an error processing your request. Please try again.",
            "proposed_changes": None,
        }


# ── AI Document Generation ────────────────────────────────────────────────────

_DOC_GEN_SYSTEM = """You are a senior industrial documentation engineer with 25 years of experience
in oil refineries, chemical plants, and power generation facilities.
Generate professional, technically precise industrial documents using the equipment context provided.
Use actual equipment IDs, readings, technician names, and regulation references from the context.
Return ONLY valid JSON — no markdown fences, no extra text."""

_DOC_TYPE_CONFIGS: dict[str, dict] = {
    "maintenance_record": {
        "label": "Maintenance Record",
        "sections": [
            "equipment_summary",
            "work_performed",
            "findings",
            "measurements_before_after",
            "spare_parts_used",
            "recommendations",
            "next_maintenance_due",
        ],
    },
    "safety_procedure": {
        "label": "Safety Procedure",
        "sections": [
            "scope_and_purpose",
            "prerequisites_and_permits",
            "ppe_requirements",
            "hazard_identification_and_controls",
            "step_by_step_procedure",
            "emergency_actions",
            "regulatory_references",
        ],
    },
    "inspection_report": {
        "label": "Inspection Report",
        "sections": [
            "inspection_summary",
            "scope_and_methodology",
            "inspection_findings",
            "defects_found",
            "pass_fail_checklist",
            "corrective_actions_required",
            "next_inspection_due",
        ],
    },
    "operating_instruction": {
        "label": "Operating Instruction",
        "sections": [
            "purpose_and_applicability",
            "normal_operating_parameters",
            "startup_procedure",
            "normal_operation_guidelines",
            "shutdown_procedure",
            "troubleshooting_guide",
            "safety_interlocks_and_alarms",
        ],
    },
    "project_file": {
        "label": "Project File",
        "sections": [
            "project_overview",
            "team_and_responsibilities",
            "equipment_in_scope",
            "project_timeline",
            "technical_requirements",
            "risk_register",
            "referenced_documents",
        ],
    },
    "incident_report": {
        "label": "Incident Report",
        "sections": [
            "incident_summary",
            "chronological_timeline",
            "root_cause_analysis",
            "contributing_factors",
            "immediate_actions_taken",
            "permanent_corrective_actions",
            "lessons_learned",
        ],
    },
}


def _fallback_generated_document(
    doc_type: str,
    equipment_context: dict[str, Any],
    user_description: str,
    extra_fields: dict[str, Any],
) -> dict[str, Any]:
    """Fallback document when no LLM key is available — generates plausible demo content."""
    cfg = _DOC_TYPE_CONFIGS.get(doc_type, _DOC_TYPE_CONFIGS["maintenance_record"])
    eq_id = equipment_context.get("id", "P-101")
    eq_name = equipment_context.get("name", "Crude Oil Feed Pump")
    today = datetime.now().strftime("%Y-%m-%d")
    technician = extra_fields.get("technician", "Rajesh Kumar")

    sections: dict[str, str] = {}
    for sec in cfg["sections"]:
        sections[sec] = f"[Demo content for {sec.replace('_', ' ')} — add AI key for real generation]"

    # Add a few realistic sections based on doc type
    if doc_type == "maintenance_record":
        sections["equipment_summary"] = f"{eq_id} — {eq_name}. Location: {equipment_context.get('location', 'Unit 4 CDU')}. Type: {equipment_context.get('type', 'Centrifugal Pump')}."
        sections["work_performed"] = f"{user_description or 'Corrective maintenance performed per work order.'}  Technician: {technician}. Date: {today}."
        sections["recommendations"] = "Schedule next vibration survey in 30 days. Verify bearing temperature weekly. Update CMMS with bearing change date."
    elif doc_type == "safety_procedure":
        sections["scope_and_purpose"] = f"This procedure governs safe operation and maintenance of {eq_id} ({eq_name}) in {equipment_context.get('location', 'CDU')}."
        sections["ppe_requirements"] = "Hard hat, safety glasses, hearing protection, chemical-resistant gloves, safety shoes. FR coverall mandatory within 3m radius."
        sections["emergency_actions"] = "In case of fire: activate ESD and isolate feed. Contact emergency control room: Ext. 911. Muster at Assembly Point A3."
    elif doc_type == "inspection_report":
        sections["inspection_summary"] = f"Detailed inspection of {eq_id} ({eq_name}) conducted on {today}. {user_description or 'Routine statutory inspection.'}"
        sections["defects_found"] = "1. Drive-end bearing housing — surface corrosion noted (Class B defect). 2. Mechanical seal — minor leakage <0.1 ml/hr (monitor). 3. Coupling guard — crack in weld (repair within 30 days)."
    elif doc_type == "operating_instruction":
        readings = equipment_context.get("current_readings", {})
        params = "; ".join(f"{k}: {v.get('normal', 'N/A')} {v.get('unit', '')}" for k, v in readings.items()) if readings else "Vibration: <7.1 mm/s; Temperature: <75°C; Flow: >850 m3/hr"
        sections["normal_operating_parameters"] = f"Normal operating envelope for {eq_id}: {params}"
        sections["startup_procedure"] = "1. Verify all isolation valves open. 2. Prime suction line. 3. Start motor and verify direction. 4. Ramp to operating speed. 5. Monitor all parameters for 30 minutes."
    elif doc_type == "incident_report":
        sections["incident_summary"] = f"Incident on {eq_id} ({eq_name}): {user_description or 'Equipment failure requiring investigation.'} Date: {today}."
        sections["root_cause_analysis"] = "5-Why Analysis: Why did failure occur? → Why was condition not detected? → Why did monitoring not alert? → Why was PM overdue? → Root cause: maintenance scheduling gap."
    elif doc_type == "project_file":
        sections["project_overview"] = f"Project: {user_description or 'Equipment upgrade / modification project'} for {eq_id} ({eq_name})."
        sections["risk_register"] = "1. Schedule overrun — Probability: Medium. Mitigation: Weekly progress review.\n2. Resource conflict — Probability: Low. Mitigation: Resource plan locked 2 weeks ahead.\n3. Safety incident — Probability: Low. Mitigation: PTW mandatory, HAZOP completed."

    return {
        "title": f"{cfg['label']} — {eq_id} — {today}",
        "doc_type": doc_type,
        "sections": sections,
        "entities": {
            "equipment_ids": [eq_id],
            "people": [technician] if technician else [],
            "regulations": ["OISD-117", "ISO 55001"],
            "measurements": [],
            "document_type": doc_type,
            "summary": f"AI-generated {cfg['label']} for {eq_id} — {today}.",
        },
    }


async def generate_document(
    doc_type: str,
    equipment_context: dict[str, Any],
    maintenance_context: dict[str, Any],
    user_description: str,
    extra_fields: dict[str, Any],
) -> dict[str, Any]:
    """Call LLM to generate a structured industrial document; fall back to demo content."""
    client = _get_client()
    cfg = _DOC_TYPE_CONFIGS.get(doc_type, _DOC_TYPE_CONFIGS["maintenance_record"])
    today = datetime.now().strftime("%Y-%m-%d")

    schema = {
        "title": "string — professional document title, include equipment ID and date",
        "doc_type": doc_type,
        "sections": {s: "string — detailed, technically accurate content for this section" for s in cfg["sections"]},
        "entities": {
            "equipment_ids": ["equipment tag strings mentioned"],
            "people": ["technician/engineer names"],
            "regulations": ["regulation/standard codes referenced"],
            "measurements": ["numeric readings with units"],
            "document_type": doc_type,
            "summary": "one sentence summary",
        },
    }

    prompt = f"""TASK: Generate a complete, professional {cfg['label']} document.

USER DESCRIPTION (what happened / context):
{user_description or 'Generate based on equipment context.'}

EXTRA FIELDS:
{json.dumps(extra_fields or {}, indent=2)}

EQUIPMENT CONTEXT:
{json.dumps(equipment_context, indent=2)}

MAINTENANCE / HISTORY CONTEXT:
{json.dumps(maintenance_context, indent=2)}

TODAY'S DATE: {today}

Instructions:
- Use real equipment IDs, technician names, readings and regulation codes from the context.
- Each section should contain detailed, actionable technical content — not placeholders.
- Be specific: include actual numeric thresholds, procedure steps, regulation clause numbers.
- Write in the style of a senior plant engineer filling in a formal document.

Return ONLY valid JSON matching this exact schema:
{json.dumps(schema, indent=2)}
"""

    if client is None:
        return _fallback_generated_document(doc_type, equipment_context, user_description, extra_fields)

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _DOC_GEN_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=2500,
        )
        result = json.loads(response.choices[0].message.content)
        result.setdefault("doc_type", doc_type)
        result.setdefault("entities", {})
        result["entities"].setdefault("document_type", doc_type)
        result["entities"].setdefault("summary", f"AI-generated {cfg['label']}.")
        return result
    except Exception as exc:
        logger.warning("Document generation LLM call failed: %s", exc)
        return _fallback_generated_document(doc_type, equipment_context, user_description, extra_fields)
