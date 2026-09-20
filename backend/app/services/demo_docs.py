"""
EPIC — Demo Document Generator
Generates realistic industrial documents in multiple formats.
Called by: app/api/admin.py → generate_full_demo()

Formats:
  PDF   — Maintenance inspection report, Incident investigation report
  DOCX  — Safety SOP, Shift handover log
  XLSX  — Maintenance schedule, Spare parts inventory
  PPTX  — Safety toolbox talk presentation
  TXT   — Night shift handover notes
  CSV   — 30-day sensor data export
"""

import csv
import datetime
import io
import os

UPLOADS_DIR = os.path.join("uploads", "demo_samples")
os.makedirs(UPLOADS_DIR, exist_ok=True)

_TODAY = datetime.date.today().strftime("%d %b %Y")
_TODAY_ISO = datetime.date.today().isoformat()


def _d(days_ago: int) -> str:
    return (datetime.datetime.utcnow() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")


_PIPELINE_DONE = {
    "saved": "done",
    "extracted": "done",
    "entities": "done",
    "graph": "done",
    "indexed": "done",
}


def _s(text: str) -> str:
    """Sanitise to Latin-1 for fpdf2 core fonts."""
    return (
        text.replace("\u2014", " - ").replace("\u2013", " - ")
            .replace("\u2018", "'").replace("\u2019", "'")
            .replace("\u201c", '"').replace("\u201d", '"')
            .replace("\u00b0", " deg ").replace("\u2022", "*")
            .replace("\u03bc", "u").replace("\u2265", ">=").replace("\u2264", "<=")
            .encode("latin-1", errors="replace").decode("latin-1")
    )


# ─────────────────────────────────────────────────────────────────────────────
# PDF helpers (fpdf2)
# ─────────────────────────────────────────────────────────────────────────────

_AMBER = (245, 158, 11)
_GREEN = (16, 185, 129)
_RED   = (239, 68, 68)
_DARK  = (20, 20, 30)
_GREY  = (110, 110, 110)
_LGREY = (200, 200, 200)
_LIGHT = (240, 240, 240)
_WHITE = (255, 255, 255)
_BLACK = (15, 15, 15)
_BLUE  = (59, 130, 246)


def _pdf_header(pdf, title: str):
    from fpdf.enums import XPos, YPos
    pdf.set_fill_color(*_DARK)
    pdf.rect(0, 0, 210, 18, "F")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*_AMBER)
    pdf.set_xy(8, 4)
    pdf.cell(0, 10, _s(f"EPIC  |  {title}"))


def _pdf_footer(pdf, subtitle: str = "CONFIDENTIAL  |  Apex Refinery CDU Unit 4"):
    pdf.set_y(-14)
    pdf.set_fill_color(*_DARK)
    pdf.rect(0, pdf.get_y(), 210, 14, "F")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_AMBER)
    pdf.cell(0, 10, _s(f"{subtitle}  |  Page {pdf.page_no()}"), align="C")


def _pdf_section(pdf, title: str):
    from fpdf.enums import XPos, YPos
    pdf.ln(4)
    pdf.set_fill_color(*_DARK)
    pdf.set_text_color(*_AMBER)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 7, _s(f"  {title}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.ln(2)


def _pdf_kv(pdf, key: str, val: str, vcol=None):
    from fpdf.enums import XPos, YPos
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_GREY)
    pdf.cell(58, 5, _s(key), new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*(vcol or _BLACK))
    pdf.cell(0, 5, _s(val), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _pdf_table_header(pdf, cols: list[tuple[str, int]]):
    from fpdf.enums import XPos, YPos
    pdf.set_fill_color(*_DARK)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("Helvetica", "B", 7)
    for lbl, w in cols:
        pdf.cell(w, 6, _s(f" {lbl}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()


def _pdf_table_row(pdf, cells: list[tuple[str, int]], alt: bool = False, tcol=None):
    from fpdf.enums import XPos, YPos
    pdf.set_fill_color(*(_LIGHT if alt else _WHITE))
    pdf.set_text_color(*(tcol or _BLACK))
    pdf.set_font("Helvetica", "", 7)
    for val, w in cells:
        pdf.cell(w, 5, _s(f" {val}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()


def _pdf_title_block(pdf, title: str, subtitle: str):
    from fpdf.enums import XPos, YPos
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*_DARK)
    pdf.cell(0, 9, _s(title), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_GREY)
    pdf.cell(0, 5, _s(subtitle), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_draw_color(*_AMBER)
    pdf.set_line_width(0.7)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.ln(4)


# ─────────────────────────────────────────────────────────────────────────────
# DOC 1 — PDF: P-101 Maintenance Inspection Report
# ─────────────────────────────────────────────────────────────────────────────

def _gen_pdf_maintenance_report() -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.set_margins(12, 22, 12)
    pdf.set_auto_page_break(True, margin=18)

    # ── Page 1 ───────────────────────────────────────────────
    pdf.add_page()
    _pdf_header(pdf, "MAINTENANCE INSPECTION REPORT  -  P-101")
    _pdf_title_block(pdf, "P-101 CRUDE OIL FEED PUMP",
                     f"Bearing Inspection & Replacement Report  |  CDU Unit 4  |  {_TODAY}")

    _pdf_section(pdf, "EQUIPMENT IDENTIFICATION")
    _pdf_kv(pdf, "Equipment Tag:", "P-101")
    _pdf_kv(pdf, "Description:", "Crude Oil Feed Pump (Duty)")
    _pdf_kv(pdf, "Type:", "Centrifugal API 610 Type BB1")
    _pdf_kv(pdf, "Manufacturer:", "Flowserve Corporation — Model PVXM-100")
    _pdf_kv(pdf, "Serial Number:", "FS-2018-4412")
    _pdf_kv(pdf, "Location:", "CDU Unit 4 — Pump House A, North Process Area")
    _pdf_kv(pdf, "Installed:", "15 April 2018")
    _pdf_kv(pdf, "Criticality:", "CRITICAL — Failure stops CDU feed to distillation column", _RED)
    _pdf_kv(pdf, "Specification:", "Rated 250 m3/hr @ 85 m head, 75 kW motor, 2960 RPM")

    _pdf_section(pdf, "WORK ORDER & AUTHORIZATION")
    _pdf_kv(pdf, "Work Order No.:", "WO-2026-0042  (Corrective, Priority: HIGH)")
    _pdf_kv(pdf, "Trigger:", "Vibration alarm VT-101A = 7.4 mm/s (alarm 7.1, trip 11.2)")
    _pdf_kv(pdf, "Work Permit No:", "WP-2026-018 (Cold Work — Issued 22 Jul 2026 02:41)")
    _pdf_kv(pdf, "Lead Technician:", "Rajesh Kumar (EMP-001) — HAZOP certified")
    _pdf_kv(pdf, "Approved By:", "Ahmed Khan — Maintenance Supervisor (EMP-005)")
    _pdf_kv(pdf, "Date / Time:", f"{_TODAY}  03:45 AM IST")
    _pdf_kv(pdf, "Related Incident:", "INC-2026-0042 (Near Miss P2 — Under Investigation)")

    _pdf_section(pdf, "SENSOR READINGS AT TIME OF ALARM  (02:15 AM)")
    _pdf_table_header(pdf, [("Parameter", 52), ("Reading", 30), ("Normal", 30),
                             ("Alarm Hi", 26), ("Trip Hi", 26), ("Status", 22)])
    readings = [
        ("Vibration DE (VT-101A)",  "7.4 mm/s",  "< 4.5",   "7.1",  "11.2", "ALARM",  _RED),
        ("Vibration NDE (VT-101B)", "5.8 mm/s",  "< 4.5",   "7.1",  "11.2", "Elevated", _AMBER),
        ("Bearing Temp DE (TT-101)","78 deg C",  "55-65",   "75",   "90",   "ALARM",  _RED),
        ("Bearing Temp NDE (TT-102)","64 deg C", "55-65",   "75",   "90",   "Normal", _GREEN),
        ("Discharge Press (PT-101)", "8.2 bar",  "8.0-9.0", "9.5",  "10.5", "Normal", _GREEN),
        ("Suction Flow (FT-101)",    "242 m3/hr","230-270", "350",  "380",  "Normal", _GREEN),
        ("Motor Current",            "42.3 A",   "40-50",   "55",   "65",   "Normal", _GREEN),
    ]
    for i, r in enumerate(readings):
        _pdf_table_row(pdf, [(r[0], 52), (r[1], 30), (r[2], 30),
                              (r[3], 26), (r[4], 26)], alt=(i % 2 == 0))
        # status cell with colour
        pdf.set_fill_color(*(_LIGHT if i % 2 == 0 else _WHITE))
        pdf.set_text_color(*r[6])
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(22, 5, _s(f" {r[5]}"), fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    _pdf_section(pdf, "INSPECTION FINDINGS")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_BLACK)
    findings = [
        ("1", "DE Bearing (SKF 6311)", _RED, "REPLACE",
         "Radial play 0.15 mm (limit 0.08 mm). Grease darkened with iron-oxide particles. Bearing FAILED."),
        ("2", "NDE Bearing (SKF 6311)", _AMBER, "REGREASE",
         "Play 0.06 mm (within limits). Grease degraded — replenished with 2 cartridges LGMT-2 Shell."),
        ("3", "Shaft Coupling", _GREEN, "OK",
         "Flexible disc coupling — angular misalignment 0.3 mrad (limit 0.5 mrad). Acceptable."),
        ("4", "Mechanical Seal Plan 11", _GREEN, "OK",
         "Flush flow 12 L/min (normal 12-15). API chamber pressure 4.0 bar. Seal face acceptable."),
        ("5", "Lube Oil History", _RED, "OVERDUE",
         "Last oil change 214 days ago. SOP-P101-BEARING specifies 180-day maximum interval. Overdue 34 days."),
        ("6", "Motor Insulation (MegOhm)", _GREEN, "OK",
         "Insulation resistance 850 MOhm. Motor in good condition."),
    ]
    _pdf_table_header(pdf, [("No.", 10), ("Component", 50), ("Status", 22),
                             ("Finding", 104)])
    for i, (no, comp, col, status, finding) in enumerate(findings):
        pdf.set_fill_color(*(_LIGHT if i % 2 == 0 else _WHITE))
        pdf.set_text_color(*_BLACK)
        pdf.set_font("Helvetica", "", 7)
        pdf.cell(10, 5, _s(f" {no}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(50, 5, _s(f" {comp}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_text_color(*col)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(22, 5, _s(f" {status}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_text_color(*_BLACK)
        pdf.set_font("Helvetica", "", 7)
        pdf.cell(104, 5, _s(f" {finding[:95]}"), fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Page 2 ───────────────────────────────────────────────
    pdf.add_page()
    _pdf_header(pdf, "MAINTENANCE INSPECTION REPORT  -  P-101  (Page 2)")

    _pdf_section(pdf, "ROOT CAUSE ANALYSIS")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_BLACK)
    pdf.multi_cell(0, 5, _s(
        "PRIMARY ROOT CAUSE (Probability 82%): Lubrication interval overrun — last oil change 214 days ago vs 180-day "
        "SOP maximum. Degraded grease increased bearing metal-to-metal contact, elevating temperature (55 to 78 deg C) "
        "and accelerating wear. The vibration signature (4.5 to 7.4 mm/s over 6 days) matches the 2022 bearing failure "
        "incident INC-2022-034 (root cause: lube interval overrun 15 days).\n\n"
        "SECONDARY CONTRIBUTING FACTOR (Probability 34%): Possible coupling misalignment from piping work conducted "
        "under WP-0042 (March 2026). Misalignment measurement today was within limits (0.3 mrad) — likely not primary.\n\n"
        "SIMILAR HISTORICAL EVENTS:\n"
        "  - INC-2022-034 (P-101): Vibration 4.2 to 8.7 mm/s over 6 hrs. Bearing failure. 12h downtime. USD 14 200.\n"
        "  - INC-2023-067 (P-202): Vibration 7.8 mm/s. Bearing failure 14h later. 36h downtime. USD 31 000.\n\n"
        "COST AVOIDANCE: Catching this at alarm stage avoids estimated 18h unplanned shutdown. "
        "Replacement cost USD 14 200 vs lost production estimate USD 240 000 for 18h CDU outage."
    ))

    _pdf_section(pdf, "CORRECTIVE & PREVENTIVE ACTIONS")
    actions = [
        ("1", "COMPLETE",   "DE bearing (SKF 6311) replaced. New bearing clearance: 0.03 mm."),
        ("2", "COMPLETE",   "NDE bearing regrease with 2x LGMT-2 cartridges."),
        ("3", "COMPLETE",   "Alignment verified post-reassembly: 0.3 mrad angular / 0.02 mm parallel offset."),
        ("4", "IN PROGRESS","CMMS alert set for lubrication at 150 days (30-day buffer before 180-day limit)."),
        ("5", "RAISED",     "Compliance issue CI-P101-3 (lube overdue) flagged — to close after CMMS update verified."),
        ("6", "PLANNED",    "Vibration trend report to be reviewed at weekly plant shift handover meeting."),
    ]
    status_cols = {"COMPLETE": _GREEN, "IN PROGRESS": _AMBER, "RAISED": _BLUE, "PLANNED": _GREY}
    _pdf_table_header(pdf, [("No.", 10), ("Status", 30), ("Action", 146)])
    for i, (no, status, action) in enumerate(actions):
        pdf.set_fill_color(*(_LIGHT if i % 2 == 0 else _WHITE))
        pdf.set_text_color(*_BLACK)
        pdf.set_font("Helvetica", "", 7)
        pdf.cell(10, 5, _s(f" {no}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_text_color(*status_cols.get(status, _BLACK))
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(30, 5, _s(f" {status}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_text_color(*_BLACK)
        pdf.set_font("Helvetica", "", 7)
        pdf.cell(146, 5, _s(f" {action}"), fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    _pdf_section(pdf, "POST-MAINTENANCE VERIFICATION")
    _pdf_kv(pdf, "Vibration DE:", "4.1 mm/s — NORMAL (was 7.4 mm/s)", _GREEN)
    _pdf_kv(pdf, "Vibration NDE:", "3.8 mm/s — NORMAL (was 5.8 mm/s)", _GREEN)
    _pdf_kv(pdf, "Bearing Temp DE:", "52 deg C — NORMAL (was 78 deg C)", _GREEN)
    _pdf_kv(pdf, "Functional Test:", "PASS — Flow 252 m3/hr, Pressure 8.6 bar")
    _pdf_kv(pdf, "Return to Service:", f"{_TODAY}  09:45 AM IST")
    _pdf_kv(pdf, "Technician Signature:", "Rajesh Kumar  ___________________")
    _pdf_kv(pdf, "Supervisor Sign-off:", "Ahmed Khan    ___________________")
    _pdf_kv(pdf, "Safety Sign-off:", "Priya Nair    ___________________")

    _pdf_section(pdf, "STANDARDS & REFERENCES")
    refs = [
        ("OISD-117", "Section 8.3 — Vibration monitoring response requirements for rotating equipment"),
        ("ISO 10816-7", "Zone C: 7.1 mm/s — immediate corrective action required"),
        ("API 610", "Centrifugal pump design, maintenance and inspection standard"),
        ("SOP-P101-BEARING", "P-101 Lubrication and Bearing Maintenance Procedure (180-day interval)"),
        ("INC-2022-034", "Historical bearing failure — same signature — 12h downtime"),
    ]
    _pdf_table_header(pdf, [("Reference", 40), ("Description", 146)])
    for i, (ref, desc) in enumerate(refs):
        _pdf_table_row(pdf, [(ref, 40), (desc, 146)], alt=(i % 2 == 0))

    _pdf_footer(pdf, "CONFIDENTIAL  |  Apex Refinery  |  WO-2026-0042")

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# DOC 2 — PDF: K-401 Compressor Incident Investigation Report
# ─────────────────────────────────────────────────────────────────────────────

def _gen_pdf_incident_report() -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.set_margins(12, 22, 12)
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    _pdf_header(pdf, "INCIDENT INVESTIGATION REPORT  -  INC-2026-0031  -  K-401")
    _pdf_title_block(pdf, "K-401 PROCESS AIR COMPRESSOR",
                     f"Incident Report INC-2026-0031  |  Property Damage P4  |  VDU Unit 5  |  {_d(14)}")

    _pdf_section(pdf, "INCIDENT SUMMARY")
    _pdf_kv(pdf, "Incident Number:", "INC-2026-0031")
    _pdf_kv(pdf, "Classification:", "Property Damage — Severity P4")
    _pdf_kv(pdf, "Status:", "Corrective-action stage — actions in progress")
    _pdf_kv(pdf, "Equipment:", "K-401 Process Air Compressor (Atlas Copco ZH350)")
    _pdf_kv(pdf, "Location:", "VDU Unit 5 — South Block, Apex Refinery")
    _pdf_kv(pdf, "Occurred:", _d(14))
    _pdf_kv(pdf, "Reported By:", "Ahmed Khan (EMP-005) — Maintenance Supervisor")
    _pdf_kv(pdf, "Investigation Lead:", "Dr. Anand Sharma (EMP-004) — QA Inspector")

    _pdf_section(pdf, "DESCRIPTION OF EVENT")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_BLACK)
    pdf.multi_cell(0, 5, _s(
        "On " + _d(14) + " at 14:30 hrs, routine DCS monitoring revealed K-401 discharge pressure had dropped to "
        "10.8 bar (rated 12.5 bar), representing a 14% capacity reduction. The drop was gradual over 48 hours. "
        "No process upsets were observed — suction conditions, ambient temperature and motor current were all normal. "
        "Technician Ahmed Khan was dispatched for physical inspection. The inlet filter housing was found to have "
        "significantly elevated differential pressure (0.82 bar, normal < 0.30 bar), indicating severe filter choking.\n\n"
        "Investigation confirmed the inlet filter element (Part No. AC-ZH350-FE) was completely blocked with iron-oxide "
        "particulate and dust. The filter was 84 days into its 60-day replacement interval (replacement was overdue by "
        "24 days). No automated CMMS alert had triggered because the filter interval had not been updated in the system "
        "following the 2024 interval reduction (INC-2024-015 corrective action CA-K401-2 — STATUS: STILL OPEN)."
    ))

    _pdf_section(pdf, "IMMEDIATE ACTIONS TAKEN")
    imm = [
        ("1", "14:45", "COMPLETE", "K-401 load reduced to 70% to prevent motor trip while isolating filter"),
        ("2", "15:00", "COMPLETE", "Inlet filter replaced with new element AC-ZH350-FE (from Warehouse B — Row 6, Qty 4 in stock)"),
        ("3", "15:15", "COMPLETE", "Discharge pressure restored to 12.4 bar within 8 minutes of restart"),
        ("4", "16:00", "COMPLETE", "DCS historian reviewed — 48hr pressure trend confirms gradual filter fouling"),
        ("5", "16:30", "COMPLETE", "Incident report INC-2026-0031 opened and investigation team convened"),
    ]
    _pdf_table_header(pdf, [("Step", 12), ("Time", 18), ("Status", 26), ("Action", 130)])
    for i, row in enumerate(imm):
        _pdf_table_row(pdf, list(zip(row, [12, 18, 26, 130])), alt=(i % 2 == 0))

    _pdf_section(pdf, "ROOT CAUSE ANALYSIS (5-Why)")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_BLACK)
    five_why = [
        ("Why 1", "Discharge pressure dropped?", "Compressor capacity reduced by choked inlet filter"),
        ("Why 2", "Filter became choked?", "Filter reached end-of-life — particulate loading exceeded design capacity"),
        ("Why 3", "Filter was not changed on time?", "Filter change interval in CMMS still set to 90 days (old interval)"),
        ("Why 4", "CMMS not updated?", "CA-K401-2 (from INC-2024-015) to reduce interval to 60 days was never closed"),
        ("Why 5", "Corrective action was not closed?", "No owner assigned to corrective-action tracking. No automated overdue reminder in place"),
    ]
    _pdf_table_header(pdf, [("Level", 16), ("Question", 75), ("Answer", 95)])
    for i, (lv, q, a) in enumerate(five_why):
        _pdf_table_row(pdf, [(lv, 16), (q, 75), (a, 95)], alt=(i % 2 == 0))

    _pdf_section(pdf, "CONTRIBUTING FACTORS")
    factors = [
        "Open corrective action CA-K401-2 not tracked — no automated overdue reminder in CMMS",
        "Filter change intervals updated manually in CMMS without enforcement workflow",
        "No differential pressure transmitter on K-401 inlet filter (would have given advance warning)",
    ]
    for f in factors:
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_BLACK)
        pdf.set_x(16)
        pdf.multi_cell(180, 5, _s(f"- {f}"))

    _pdf_section(pdf, "CORRECTIVE ACTIONS")
    capa = [
        ("CA-K401-1", "Corrective", "Replace K-401 inlet filter — immediate", "Ahmed Khan", "CLOSED", _GREEN),
        ("CA-K401-2", "Preventive", "Update CMMS: filter interval to 60 days. Raise WO-2026-K401-PM", "Ahmed Khan", "OPEN", _AMBER),
        ("CA-K401-3", "Preventive", "Install dP transmitter on K-401 inlet — raise CAPEX request", "Deepa Menon", "OPEN", _AMBER),
        ("CA-K401-4", "Improvement", "Implement corrective-action tracking review in monthly safety meeting agenda", "Priya Nair", "OPEN", _BLUE),
    ]
    _pdf_table_header(pdf, [("ID", 28), ("Type", 22), ("Description", 90),
                             ("Owner", 30), ("Status", 16)])
    for i, (cid, ctype, desc, owner, status, col) in enumerate(capa):
        pdf.set_fill_color(*(_LIGHT if i % 2 == 0 else _WHITE))
        pdf.set_text_color(*_BLACK)
        pdf.set_font("Helvetica", "", 7)
        pdf.cell(28, 5, _s(f" {cid}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(22, 5, _s(f" {ctype}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(90, 5, _s(f" {desc[:60]}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(30, 5, _s(f" {owner}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_text_color(*col)
        pdf.set_font("Helvetica", "B", 7)
        pdf.cell(16, 5, _s(f" {status}"), fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    _pdf_kv(pdf, "Downtime Hours:", "4.0 h (load reduction only — no full shutdown required)")
    _pdf_kv(pdf, "Cost Impact:", "USD 2 200 (filter element + 4h technician labour)")
    _pdf_kv(pdf, "Report Approved:", f"Dr. Anand Sharma  |  {_today_str()}")

    _pdf_footer(pdf, "CONFIDENTIAL  |  Apex Refinery VDU Unit 5  |  INC-2026-0031")

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()


def _today_str() -> str:
    return datetime.date.today().strftime("%d %b %Y")


# ─────────────────────────────────────────────────────────────────────────────
# DOC 3 — DOCX: SOP-P101 Bearing Replacement Procedure
# ─────────────────────────────────────────────────────────────────────────────

def _gen_docx_sop() -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    import docx.oxml

    doc = Document()

    # Narrow margins
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    def add_heading(text: str, level: int = 1, color: tuple = (20, 20, 30)):
        h = doc.add_heading(text, level=level)
        h.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in h.runs:
            run.font.color.rgb = RGBColor(*color)
        return h

    def add_para(text: str, bold: bool = False, italic: bool = False):
        p = doc.add_paragraph(text)
        for run in p.runs:
            run.bold = bold
            run.italic = italic
        return p

    def add_table_row(table, cells: list[str], header: bool = False):
        row = table.add_row()
        for i, text in enumerate(cells):
            cell = row.cells[i]
            cell.text = text
            if header:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.bold = True
                        run.font.color.rgb = RGBColor(255, 255, 255)
                cell._tc.get_or_add_tcPr().append(
                    docx.oxml.parse_xml(f'<w:shd {qn("w:xmlns:w")}="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="14141E" w:color="14141E" w:val="clear"/>') # noqa: E501
                )

    # ── Cover ──────────────────────────────────────────────────
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_para.add_run("APEX REFINERY — STANDARD OPERATING PROCEDURE")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(20, 20, 30)

    sub_para = doc.add_paragraph()
    sub_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub_para.add_run("SOP-P101-BEARING-REV3")
    run.bold = True
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor(245, 158, 11)

    sub2 = doc.add_paragraph()
    sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub2.add_run("P-101 Bearing Inspection, Lubrication & Replacement Procedure")
    run.font.size = Pt(12)

    doc.add_paragraph()

    # ── Metadata table ─────────────────────────────────────────
    meta_table = doc.add_table(rows=1, cols=4)
    meta_table.style = "Table Grid"
    hdr = meta_table.rows[0].cells
    for cell, text in zip(hdr, ["Field", "Value", "Field", "Value"]):
        cell.text = text
        for para in cell.paragraphs:
            for run in para.runs:
                run.bold = True

    meta_rows = [
        ("Document No.", "SOP-P101-BEARING-REV3", "Equipment:", "P-101 Crude Oil Feed Pump"),
        ("Rev.", "3", "Date:", _TODAY),
        ("Author:", "Rajesh Kumar (EMP-001)", "Approved:", "Ahmed Khan — Supervisor"),
        ("Category:", "Mechanical / Rotating Equipment", "Standard:", "OISD-117, API 610, API 686"),
        ("Scope:", "CDU Unit 4 — Pump House A", "Next Review:", _d(-365)),
    ]
    for f1, v1, f2, v2 in meta_rows:
        row = meta_table.add_row().cells
        row[0].text = f1
        row[1].text = v1
        row[2].text = f2
        row[3].text = v2

    doc.add_paragraph()

    # ── 1. Purpose ─────────────────────────────────────────────
    add_heading("1. Purpose & Scope", level=1, color=(245, 158, 11))
    add_para(
        "This SOP defines the safe procedure for routine lubrication, inspection, and replacement of drive-end (DE) "
        "and non-drive-end (NDE) bearings on P-101 Crude Oil Feed Pump in CDU Unit 4. This procedure applies to "
        "scheduled preventive maintenance (180-day lubrication interval) and corrective maintenance triggered by "
        "vibration alarm (>7.1 mm/s per ISO 10816-7)."
    )

    # ── 2. Hazards ─────────────────────────────────────────────
    add_heading("2. Hazards & Risk Controls", level=1, color=(239, 68, 68))
    hazards = [
        ("Rotating Equipment", "High", "Full LOTO (Lock-Out/Tag-Out) before any contact. Verify zero energy."),
        ("Hydrocarbon Release", "High", "Drain suction/discharge lines. Test combustible gas detector before entry."),
        ("Hot Surfaces", "Medium", "Allow minimum 30 min cool-down after shutdown. Use thermal gloves."),
        ("Manual Handling", "Medium", "Bearing assembly weighs 4.2 kg. Two-person lift required."),
        ("Chemical — Grease", "Low", "LGMT-2 grease — nitrile gloves and eye protection. See MSDS-LGMT2."),
    ]
    hz_table = doc.add_table(rows=1, cols=3)
    hz_table.style = "Table Grid"
    for cell, hdr_text in zip(hz_table.rows[0].cells, ["Hazard", "Risk Level", "Control Measure"]):
        cell.text = hdr_text
        for para in cell.paragraphs:
            for run in para.runs:
                run.bold = True
    for hazard, risk, control in hazards:
        row = hz_table.add_row().cells
        row[0].text = hazard
        row[1].text = risk
        row[2].text = control

    doc.add_paragraph()

    # ── 3. Tools & Materials ───────────────────────────────────
    add_heading("3. Tools & Materials Required", level=1, color=(245, 158, 11))
    tools = [
        "SKF bearing puller set (hydraulic, 5 tonne capacity) — Warehouse A, Tool Room T3",
        "Torque wrench 20–200 Nm — Tool Room T3",
        "Dial indicator gauge (0.001 mm resolution) — Tool Room T3",
        "SKF 6311-2RS/C3 bearing (x2 DE + x1 NDE) — Part No. SKF-6311-2RS — Warehouse A, Rack 4",
        "Shell LGMT-2 grease (2 cartridges, 400 g each) — Warehouse A, Rack 7",
        "Emerson laser alignment kit (Model CSI 2140) — Tool Room T4",
        "Thermal imaging camera — Safety Officer Priya Nair (EMP-002)",
        "Combustible gas detector (BW Clip4) — Safety Office",
        "Work permit form (Cold Work) — Safety Management System",
        "Torque values sheet SOP-P101-TORQUE-REV2 — Document Management System",
    ]
    for tool in tools:
        doc.add_paragraph(f"• {tool}")

    doc.add_paragraph()

    # ── 4. Procedure ───────────────────────────────────────────
    add_heading("4. Procedure Steps", level=1, color=(245, 158, 11))

    steps = [
        ("PREPARATION", [
            ("4.1", "Obtain approved work permit (Cold Work) from Area Authority. Confirm permit is displayed at pump.",
             "Responsible: Lead Technician. Verify: Area Authority signature present."),
            ("4.2", "Notify DCS operator to reduce pump load to minimum before shutdown.",
             "Record in handover log: Equipment tag P-101, planned downtime start, estimated duration 4h."),
            ("4.3", "Close suction MOV-101A and discharge MOV-101B. Verify closed via DCS and physical inspection.",
             "Use LOTO locks: Red (Rajesh Kumar), Blue (Ahmed Khan — Supervisor). MINIMUM 2 LOCKS required."),
            ("4.4", "De-energise MCC-101 (Motor Control Centre). Apply LOTO padlock and tag.",
             "Verify zero voltage with approved test meter. Do NOT proceed without zero-energy verification."),
            ("4.5", "Drain seal flush Plan 11 piping. Collect hydrocarbon in designated drip pan.",
             "Test combustible gas at pump base and bearing housing access area. Reading must be < 10% LEL."),
        ]),
        ("BEARING REMOVAL", [
            ("4.6", "Remove bearing housing end cover (8x M12 bolts, torque 85 Nm). Note bolt condition for reuse.",
             "If bolts corroded, replace with new (Part: SS-M12-85-DIN) — check Warehouse A."),
            ("4.7", "Photograph bearing in situ before removal. Record grease colour and condition.",
             "Reference photo: SOP-P101-BEARING-FIG-01. Grease should be amber/brown. Black = contaminated."),
            ("4.8", "Heat bearing housing to 80 deg C using heat gun. Never exceed 110 deg C.",
             "Use thermal camera to confirm temperature. Apply hydraulic puller to extract bearing — do not strike shaft."),
            ("4.9", "Measure shaft journal diameter with micrometer. Record actual vs spec (nominal 55 mm, tolerance h6).",
             "Enter on work order data sheet. If outside tolerance: STOP and call Supervisor immediately."),
        ]),
        ("BEARING INSTALLATION", [
            ("4.10", "Clean shaft journal and housing bore with acetone. Inspect for scoring or burrs.",
             "Polish minor scores with 600-grit wet/dry paper along shaft axis only. Major damage: refer to workshop."),
            ("4.11", "Heat new bearing (SKF 6311-2RS/C3) to 100 deg C in oil bath or induction heater.",
             "DO NOT use open flame. Verify temperature with contact thermometer. Install within 60 sec of heating."),
            ("4.12", "Slide bearing onto shaft (inner ring drive fit). Apply force to INNER RING ONLY.",
             "Bearing should seat with audible click. Verify no gap between ring and shoulder."),
            ("4.13", "Apply fresh LGMT-2 grease — fill bearing cavity 30-40% (approx 18 g for SKF 6311).",
             "Over-greasing causes heat buildup. Use calibrated grease gun (1 stroke = 1.8 g)."),
            ("4.14", "Refit bearing housing cover with new gasket (GS-P101-COVER). Torque to 85 Nm in star pattern.",
             "Apply anti-seize compound (Molykote 1000) to bolt threads to prevent future seizure."),
        ]),
        ("COMMISSIONING", [
            ("4.15", "With LOTO removed (reverse order — supervisor removes last), perform 30-sec jog test.",
             "Observe bearing housing for heat, unusual noise, or vibration. Abort if any anomaly detected."),
            ("4.16", "Remove isolation from MOV-101A and MOV-101B. Notify DCS operator to restart pump.",
             "Monitor vibration trend for minimum 30 minutes at normal operating speed (2960 RPM)."),
            ("4.17", "Verify vibration DE < 4.5 mm/s and bearing temp DE < 65 deg C within 30 min of startup.",
             "Record readings on work order data sheet. Sign off if readings are within acceptable range."),
            ("4.18", "Close the work permit. Return all tools to Tool Room. Dispose of spent bearing and grease per waste SOP.",
             "Update CMMS: next lubrication date = today + 150 days (buffer before 180-day limit)."),
        ]),
    ]

    for phase, phase_steps in steps:
        add_heading(f"  Phase: {phase}", level=2, color=(20, 20, 30))
        step_table = doc.add_table(rows=1, cols=3)
        step_table.style = "Table Grid"
        for cell, hdr_text in zip(step_table.rows[0].cells, ["Step", "Action", "Verification"]):
            cell.text = hdr_text
            for para in cell.paragraphs:
                for run in para.runs:
                    run.bold = True
        for step_no, action, verify in phase_steps:
            row = step_table.add_row().cells
            row[0].text = step_no
            row[1].text = action
            row[2].text = verify
        doc.add_paragraph()

    # ── 5. Sign-off ────────────────────────────────────────────
    add_heading("5. Work Completion Sign-off", level=1, color=(16, 185, 129))
    signoff_table = doc.add_table(rows=1, cols=3)
    signoff_table.style = "Table Grid"
    for cell, text in zip(signoff_table.rows[0].cells, ["Role", "Name", "Signature / Date"]):
        cell.text = text
        for para in cell.paragraphs:
            for run in para.runs:
                run.bold = True
    for role, name in [
        ("Lead Technician", "Rajesh Kumar"),
        ("Supervisor", "Ahmed Khan"),
        ("Safety Officer", "Priya Nair"),
    ]:
        row = signoff_table.add_row().cells
        row[0].text = role
        row[1].text = name
        row[2].text = "___________________  Date: ______"

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# DOC 4 — DOCX: Shift Handover Log — CDU Night Shift
# ─────────────────────────────────────────────────────────────────────────────

def _gen_docx_handover() -> bytes:
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    # Title
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("APEX REFINERY  |  CDU UNIT 4 — SHIFT HANDOVER LOG")
    r.bold = True
    r.font.size = Pt(14)

    t2 = doc.add_paragraph()
    t2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = t2.add_run(f"Night Shift  |  22 Jul 2026  |  02:00 – 06:00 hrs  |  Suresh Nair (Supervisor)")
    r2.font.size = Pt(10)

    doc.add_paragraph()

    def heading(text):
        p = doc.add_paragraph()
        r = p.add_run(text)
        r.bold = True
        r.font.size = Pt(12)
        r.font.color.rgb = RGBColor(245, 158, 11)
        return p

    def para(text, indent=False):
        p = doc.add_paragraph(("    " if indent else "") + text)
        p.paragraph_format.space_after = Pt(2)
        return p

    # Plant status
    heading("1. UNIT STATUS AT HANDOVER")
    status_table = doc.add_table(rows=1, cols=4)
    status_table.style = "Table Grid"
    for cell, text in zip(status_table.rows[0].cells, ["Equipment", "Status", "Key Reading", "Action Required"]):
        cell.text = text
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True

    statuses = [
        ("P-101", "ALARM — Bearing", "Vibration 7.4 mm/s (alarm 7.1)", "WO-2026-0042 raised — bearing replacement"),
        ("P-202", "Running", "Vibration 3.1 mm/s — Normal", "Routine monitoring"),
        ("HX-201", "Running", "Tube-side dP 1.8 bar — Normal", "None"),
        ("V-301", "Running", "Level 65%, Pressure 3.2 barg — Normal", "None"),
        ("K-401", "Running", "Discharge 10.8 bar (low)", "CA-K401-2 filter interval to be updated"),
        ("G-101", "Running", "Vibration 2.8 mm/s — Normal", "Fan blade inspection due in 14 days"),
    ]
    for eq, status, reading, action in statuses:
        row = status_table.add_row().cells
        row[0].text = eq
        row[1].text = status
        row[2].text = reading
        row[3].text = action

    doc.add_paragraph()

    heading("2. EVENTS THIS SHIFT")
    events = [
        ("02:15", "P-101 vibration alarm fired — VT-101A = 7.4 mm/s. Threshold monitor auto-raised WO-2026-0042."),
        ("02:18", "AI query initiated by Suresh Nair. Risk HIGH — 75% bearing failure probability."),
        ("02:31", "Incident report INC-2026-0042 (Near Miss P2) opened by Suresh Nair."),
        ("02:35", "WP-2026-018 (Cold Work — P-101 bearing replacement) created."),
        ("02:41", "Work permit issued after Area Authority and Safety review. Rajesh Kumar briefed."),
        ("02:44", "WO-2026-0042 formally created and approved by Ahmed Khan."),
        ("03:55", "Rajesh Kumar commenced bearing replacement. Pump isolated, LOTO applied."),
        ("04:30", "DE bearing replaced (SKF 6311). NDE grease replenished."),
        ("05:15", "Alignment verified 0.3 mrad. Functional test commenced."),
        ("05:45", "P-101 returned to service. Vibration 4.1 mm/s (Normal). Work permit closed."),
        ("06:00", "WO-2026-0042 closed and verified. Handover to Day Shift."),
    ]
    evt_table = doc.add_table(rows=1, cols=2)
    evt_table.style = "Table Grid"
    for cell, text in zip(evt_table.rows[0].cells, ["Time (IST)", "Event"]):
        cell.text = text
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True
    for time, event in events:
        row = evt_table.add_row().cells
        row[0].text = time
        row[1].text = event

    doc.add_paragraph()

    heading("3. PENDING ACTIONS FOR DAY SHIFT")
    pending = [
        "Close compliance issue CI-P101-3 (lubrication overdue) after CMMS update confirmed.",
        "Update CMMS: set P-101 next lubrication date to today + 150 days.",
        "Follow up CA-K401-2 (K-401 filter interval change to 60 days) — assign owner.",
        "Book fan blade erosion inspection for G-101 (due in 14 days).",
        "Review INC-2026-0042 investigation with Priya Nair — root cause due in 48 hours.",
    ]
    for item in pending:
        para(f"• {item}")

    doc.add_paragraph()

    heading("4. HANDOVER SIGNATURES")
    sig_table = doc.add_table(rows=3, cols=3)
    sig_table.style = "Table Grid"
    for cell, text in zip(sig_table.rows[0].cells, ["Role", "Name", "Signature"]):
        cell.text = text
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True
    sig_table.rows[1].cells[0].text = "Night Shift Supervisor (Handover)"
    sig_table.rows[1].cells[1].text = "Suresh Nair"
    sig_table.rows[1].cells[2].text = "___________________"
    sig_table.rows[2].cells[0].text = "Day Shift Supervisor (Received)"
    sig_table.rows[2].cells[1].text = "Ahmed Khan"
    sig_table.rows[2].cells[2].text = "___________________"

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# DOC 5 — XLSX: Equipment Maintenance Schedule 2026
# ─────────────────────────────────────────────────────────────────────────────

def _gen_xlsx_maintenance_schedule() -> bytes:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()

    AMBER_FILL = PatternFill("solid", fgColor="F59E0B")
    DARK_FILL = PatternFill("solid", fgColor="14141E")
    RED_FILL = PatternFill("solid", fgColor="EF4444")
    GREEN_FILL = PatternFill("solid", fgColor="10B981")
    LIGHT_FILL = PatternFill("solid", fgColor="F0F0F0")
    WHITE_FONT = Font(color="FFFFFF", bold=True)
    DARK_FONT = Font(color="14141E", bold=True)
    AMBER_FONT = Font(color="F59E0B", bold=True)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    def set_header(ws, row_idx: int, values: list[str], col_widths: list[int]):
        for i, (val, width) in enumerate(zip(values, col_widths), start=1):
            cell = ws.cell(row=row_idx, column=i, value=val)
            cell.font = WHITE_FONT
            cell.fill = DARK_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border
            ws.column_dimensions[get_column_letter(i)].width = width

    def set_cell(ws, row, col, value, fill=None, font=None, align="left"):
        cell = ws.cell(row=row, column=col, value=value)
        if fill:
            cell.fill = fill
        if font:
            cell.font = font
        cell.alignment = Alignment(horizontal=align, vertical="center")
        cell.border = thin_border
        return cell

    # ── Sheet 1: Master Schedule ───────────────────────────────
    ws1 = wb.active
    ws1.title = "Master Schedule"
    ws1.row_dimensions[1].height = 20

    # Title row
    ws1.merge_cells("A1:K1")
    title_cell = ws1["A1"]
    title_cell.value = "APEX REFINERY — CDU/VDU EQUIPMENT MAINTENANCE SCHEDULE 2026"
    title_cell.font = Font(color="F59E0B", bold=True, size=12)
    title_cell.fill = DARK_FILL
    title_cell.alignment = Alignment(horizontal="center", vertical="center")

    ws1.merge_cells("A2:K2")
    sub_cell = ws1["A2"]
    sub_cell.value = f"Generated: {_TODAY}  |  Project: PRJ-DEMO-001 — Apex Refinery CDU Upgrade 2026"
    sub_cell.font = Font(italic=True)
    sub_cell.alignment = Alignment(horizontal="center")

    headers = ["Eq Tag", "Equipment Name", "Type", "Criticality",
               "Last PM Date", "PM Interval (days)", "Next PM Due",
               "Days Until Due", "PM Type", "Technician", "Status"]
    col_widths = [10, 25, 18, 12, 14, 18, 14, 14, 20, 18, 14]
    set_header(ws1, 3, headers, col_widths)

    from datetime import timedelta
    today = datetime.date.today()
    schedule = [
        ("P-101", "Crude Oil Feed Pump",   "Centrifugal Pump",   "Critical", _d(45),  30, 0,  -15, "Lubrication + Bearing Check", "Rajesh Kumar",    "OVERDUE"),
        ("P-202", "Reflux Pump",           "Centrifugal Pump",   "High",     _d(30),  30, 0,    0, "Lubrication",                 "Rajesh Kumar",    "DUE TODAY"),
        ("HX-201","Crude Feed Pre-heater", "Heat Exchanger",     "High",     _d(90), 365, 0,  275, "Annual Tube Inspection",      "Dr. Anand Sharma","SCHEDULED"),
        ("V-301", "Crude Feed Surge Drum", "Pressure Vessel",    "Critical", _d(30), 730, 0,  700, "Biennial Inspection (IBR)",   "Dr. Anand Sharma","SCHEDULED"),
        ("K-401", "Process Air Compressor","Compressor",         "High",     _d(5),   60, 0,   55, "Filter Replacement",          "Ahmed Khan",      "SCHEDULED"),
        ("K-401", "Process Air Compressor","Compressor",         "High",     _d(90), 180, 0,   90, "Half-Yearly Overhaul",        "Ahmed Khan",      "SCHEDULED"),
        ("G-101", "Cooling Tower Fan",     "Fan",                "Medium",   _d(14),  30, 0,   16, "Fan Blade Inspection",        "Ahmed Khan",      "SCHEDULED"),
    ]
    for i, (tag, name, eq_type, crit, last_pm, interval, _, days_remaining, pm_type, tech, status) in enumerate(schedule):
        last = datetime.datetime.strptime(last_pm, "%Y-%m-%d").date()
        next_due = last + timedelta(days=interval)
        days_left = (next_due - today).days
        row = i + 4
        alt_fill = LIGHT_FILL if i % 2 == 0 else None
        set_cell(ws1, row, 1, tag, fill=alt_fill)
        set_cell(ws1, row, 2, name, fill=alt_fill)
        set_cell(ws1, row, 3, eq_type, fill=alt_fill)
        crit_fill = RED_FILL if crit == "Critical" else AMBER_FILL if crit == "High" else None
        set_cell(ws1, row, 4, crit,
                 fill=crit_fill,
                 font=WHITE_FONT if crit in ("Critical", "High") else None,
                 align="center")
        set_cell(ws1, row, 5, str(last_pm), fill=alt_fill, align="center")
        set_cell(ws1, row, 6, interval, fill=alt_fill, align="center")
        set_cell(ws1, row, 7, str(next_due), fill=alt_fill, align="center")
        days_fill = RED_FILL if days_left < 0 else AMBER_FILL if days_left <= 7 else alt_fill
        set_cell(ws1, row, 8, days_left, fill=days_fill,
                 font=WHITE_FONT if days_fill in (RED_FILL, AMBER_FILL) else None,
                 align="center")
        set_cell(ws1, row, 9, pm_type, fill=alt_fill)
        set_cell(ws1, row, 10, tech, fill=alt_fill)
        status_fill = RED_FILL if status == "OVERDUE" else AMBER_FILL if status == "DUE TODAY" else GREEN_FILL
        set_cell(ws1, row, 11, status, fill=status_fill, font=WHITE_FONT, align="center")

    # ── Sheet 2: Monthly Calendar View ────────────────────────
    ws2 = wb.create_sheet("Monthly Calendar")
    ws2.merge_cells("A1:N1")
    ws2["A1"].value = "MAINTENANCE CALENDAR — Q3 2026 (Jul–Sep)"
    ws2["A1"].font = Font(color="F59E0B", bold=True, size=11)
    ws2["A1"].fill = DARK_FILL
    ws2["A1"].alignment = Alignment(horizontal="center")

    months = ["Equipment", "01 Jul", "08 Jul", "15 Jul", "22 Jul", "29 Jul",
              "05 Aug", "12 Aug", "19 Aug", "26 Aug", "02 Sep", "09 Sep", "16 Sep", "23 Sep"]
    for col, month in enumerate(months, 1):
        c = ws2.cell(row=2, column=col, value=month)
        c.font = WHITE_FONT
        c.fill = DARK_FILL
        c.alignment = Alignment(horizontal="center")
        c.border = thin_border
        ws2.column_dimensions[get_column_letter(col)].width = 12

    cal_data = [
        ("P-101",  ["", "", "", "BEARING REPLACE", "", "", "", "LUB CHECK", "", "", "", "", "", ""]),
        ("P-202",  ["", "", "", "", "PM DUE", "", "", "", "", "PM", "", "", "", ""]),
        ("HX-201", ["", "", "", "", "", "", "", "", "", "", "", "", "", "INSPECTION"]),
        ("K-401",  ["", "", "", "", "FILTER CHG", "", "", "", "", "", "FILTER CHG", "", "", ""]),
        ("G-101",  ["", "", "", "", "", "FAN INSP", "", "", "", "", "", "FAN INSP", "", ""]),
    ]
    for row_idx, (eq, months_data) in enumerate(cal_data, 3):
        ws2.cell(row=row_idx, column=1, value=eq).border = thin_border
        for col_idx, entry in enumerate(months_data, 2):
            c = ws2.cell(row=row_idx, column=col_idx, value=entry)
            c.border = thin_border
            if entry:
                c.fill = AMBER_FILL
                c.font = Font(bold=True, size=8, color="14141E")
                c.alignment = Alignment(horizontal="center")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# DOC 6 — XLSX: Spare Parts Inventory Register
# ─────────────────────────────────────────────────────────────────────────────

def _gen_xlsx_spare_parts() -> bytes:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Spare Parts Register"

    DARK_FILL = PatternFill("solid", fgColor="14141E")
    AMBER_FILL = PatternFill("solid", fgColor="F59E0B")
    RED_FILL = PatternFill("solid", fgColor="EF4444")
    GREEN_FILL = PatternFill("solid", fgColor="10B981")
    LIGHT_FILL = PatternFill("solid", fgColor="F5F5F5")
    WHITE_FONT = Font(color="FFFFFF", bold=True)
    thin = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    # Title
    ws.merge_cells("A1:J1")
    c = ws["A1"]
    c.value = "APEX REFINERY — SPARE PARTS INVENTORY REGISTER"
    c.font = Font(color="F59E0B", bold=True, size=13)
    c.fill = DARK_FILL
    c.alignment = Alignment(horizontal="center")

    ws.merge_cells("A2:J2")
    ws["A2"].value = f"CDU/VDU Units  |  Last Updated: {_TODAY}  |  Warehouse: A & B  |  Total SKUs: 12"
    ws["A2"].alignment = Alignment(horizontal="center")
    ws["A2"].font = Font(italic=True)

    headers = ["Part No.", "Description", "Equipment", "Qty in Stock",
               "Reorder Point", "Lead Time (days)", "Location",
               "Unit Cost (USD)", "Total Value (USD)", "Status"]
    col_widths = [18, 35, 20, 14, 14, 18, 20, 16, 16, 14]

    for col_idx, (header, width) in enumerate(zip(headers, col_widths), 1):
        c = ws.cell(row=3, column=col_idx, value=header)
        c.font = WHITE_FONT
        c.fill = DARK_FILL
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    parts = [
        ("SKF-6311-2RS",   "SKF Bearing 6311 Deep Groove Ball Bearing",  "P-101, P-202",  3, 2, 7,  "Whs A Rack 4", 280,  840,  "Available"),
        ("JC-8B1-T2",      "John Crane Mechanical Seal 8B-1 Type-2",     "P-101, P-202",  1, 2, 14, "Whs A Rack 5", 3200, 3200, "Low Stock"),
        ("GEA-HX450-GS",   "HX-201 Tube Bundle Gasket Set",              "HX-201",        2, 1, 21, "Whs B Row 2",  1850, 3700, "Available"),
        ("AC-ZH350-FE",    "K-401 Inlet Filter Element",                 "K-401",         4, 3, 5,  "Whs B Row 6",  450,  1800, "Available"),
        ("SKF-NJ311-E",    "SKF NJ311E Cylindrical Roller Bearing",      "K-401",         1, 2, 10, "Whs A Rack 4", 420,  420,  "Low Stock"),
        ("LGMT2-400G",     "Shell LGMT-2 Grease Cartridge 400g",         "All Pumps",     12, 8, 3, "Whs A Rack 7", 18,   216,  "Available"),
        ("MOLYK-1000-1KG", "Molykote 1000 Anti-Seize Compound 1kg",      "All",           3, 2, 7,  "Whs A Row 1",  85,   255,  "Available"),
        ("SEAL-CAR-V8",    "V301 Manway Gasket Set (Spiral Wound)",      "V-301",         1, 1, 30, "Whs B Row 3",  2200, 2200, "Low Stock"),
        ("ORP-P101-SHAFT", "P-101 Shaft (Spare — OEM Flowserve)",        "P-101",         0, 1, 60, "On Order",     8500, 0,    "Out of Stock"),
        ("CABL-MOV101-MCB","MCC-101 Motor Circuit Breaker 75A",          "P-101",         1, 1, 21, "Elect Store",  650,  650,  "Available"),
        ("RTDPT100-3W",    "RTD Pt100 Temperature Sensor 3-wire",        "P-101, K-401",  4, 3, 5,  "Inst Store",   95,   380,  "Available"),
        ("PROX-3300XL",    "Bently Nevada 3300XL Proximity Probe",       "P-101",         2, 2, 14, "Inst Store",   1200, 2400, "Available"),
    ]

    status_fills = {
        "Available": GREEN_FILL,
        "Low Stock": AMBER_FILL,
        "Out of Stock": RED_FILL,
    }

    for row_idx, part in enumerate(parts, 4):
        alt = LIGHT_FILL if row_idx % 2 == 0 else None
        for col_idx, value in enumerate(part, 1):
            c = ws.cell(row=row_idx, column=col_idx, value=value)
            c.border = thin
            c.alignment = Alignment(horizontal="center" if col_idx not in (2, 3, 4, 7) else "left",
                                    vertical="center")
            if col_idx == 10:  # Status column
                c.fill = status_fills.get(str(value), LIGHT_FILL)
                c.font = WHITE_FONT
            else:
                c.fill = alt or PatternFill("solid", fgColor="FFFFFF")

    # Summary row
    total_row = len(parts) + 4
    ws.cell(row=total_row, column=1, value="TOTAL VALUE").font = Font(bold=True)
    total_val = ws.cell(row=total_row, column=9, value=sum(p[8] for p in parts))
    total_val.font = Font(bold=True, color="F59E0B")
    total_val.fill = DARK_FILL
    for col_idx in range(1, 11):
        ws.cell(row=total_row, column=col_idx).border = thin

    # Summary sheet
    ws2 = wb.create_sheet("Summary")
    ws2.merge_cells("A1:C1")
    ws2["A1"].value = "SPARE PARTS — STOCK STATUS SUMMARY"
    ws2["A1"].font = Font(color="F59E0B", bold=True, size=12)
    ws2["A1"].fill = DARK_FILL
    ws2["A1"].alignment = Alignment(horizontal="center")

    for cell_ref, label, value in [
        ("A3", "Total SKUs:", 12),
        ("A4", "Available:", sum(1 for p in parts if p[9] == "Available")),
        ("A5", "Low Stock:", sum(1 for p in parts if p[9] == "Low Stock")),
        ("A6", "Out of Stock:", sum(1 for p in parts if p[9] == "Out of Stock")),
        ("A8", "Total Inventory Value:", f"USD {sum(p[8] for p in parts):,}"),
        ("A9", "Items Below Reorder Point:", sum(1 for p in parts if p[3] <= p[4])),
        ("A11", "Critical Equipment (P-101) Spares:", "Bearing 3x, Seal 1x (LOW STOCK), Shaft 0x (ORDER)"),
    ]:
        ws2[cell_ref].value = label
        ws2[cell_ref].font = Font(bold=True)
        row = cell_ref[1:]
        ws2[f"B{row}"].value = value

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# DOC 7 — PPTX: Safety Toolbox Talk — Rotating Equipment
# ─────────────────────────────────────────────────────────────────────────────

def _gen_pptx_toolbox_talk() -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    DARK = RGBColor(20, 20, 30)
    AMBER = RGBColor(245, 158, 11)
    GREEN = RGBColor(16, 185, 129)
    RED = RGBColor(239, 68, 68)
    WHITE = RGBColor(255, 255, 255)
    LGREY = RGBColor(240, 240, 240)

    blank_layout = prs.slide_layouts[6]  # Blank

    def add_slide(title_text: str, subtitle_text: str = "") -> object:
        slide = prs.slides.add_slide(blank_layout)
        # Dark background
        from pptx.util import Emu
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = DARK

        # Title bar
        title_box = slide.shapes.add_textbox(Inches(0), Inches(0), prs.slide_width, Inches(1.2))
        tf = title_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title_text
        run.font.bold = True
        run.font.size = Pt(28)
        run.font.color.rgb = AMBER
        title_box.left = Inches(0.5)
        title_box.top = Inches(0.2)

        if subtitle_text:
            sub_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.2), prs.slide_width - Inches(1), Inches(0.5))
            tf2 = sub_box.text_frame
            p2 = tf2.paragraphs[0]
            p2.alignment = PP_ALIGN.LEFT
            run2 = p2.add_run()
            run2.text = subtitle_text
            run2.font.size = Pt(14)
            run2.font.color.rgb = RGBColor(180, 180, 180)

        return slide

    def add_bullet_box(slide, left, top, width, height, title: str, bullets: list[tuple[str, RGBColor]]):
        box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = box.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = title
        run.font.bold = True
        run.font.size = Pt(16)
        run.font.color.rgb = AMBER

        for bullet_text, color in bullets:
            para = tf.add_paragraph()
            para.space_before = Pt(4)
            run = para.add_run()
            run.text = f"  {bullet_text}"
            run.font.size = Pt(13)
            run.font.color.rgb = color

    # ── Slide 1: Title ─────────────────────────────────────────
    slide1 = prs.slides.add_slide(blank_layout)
    fill = slide1.background.fill
    fill.solid()
    fill.fore_color.rgb = DARK

    title_box = slide1.shapes.add_textbox(Inches(1), Inches(1.5), Inches(11), Inches(1.5))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = "ROTATING EQUIPMENT SAFETY"
    run.font.bold = True
    run.font.size = Pt(40)
    run.font.color.rgb = AMBER

    sub_box = slide1.shapes.add_textbox(Inches(1), Inches(3.2), Inches(11), Inches(1))
    tf2 = sub_box.text_frame
    p2 = tf2.paragraphs[0]
    p2.alignment = PP_ALIGN.CENTER
    run2 = p2.add_run()
    run2.text = "Monthly Toolbox Talk — CDU Unit 4  |  22 Jul 2026  |  Priya Nair (Safety Officer)"
    run2.font.size = Pt(16)
    run2.font.color.rgb = RGBColor(180, 180, 180)

    lesson_box = slide1.shapes.add_textbox(Inches(2), Inches(4.5), Inches(9), Inches(1.5))
    tf3 = lesson_box.text_frame
    tf3.word_wrap = True
    p3 = tf3.paragraphs[0]
    p3.alignment = PP_ALIGN.CENTER
    run3 = p3.add_run()
    run3.text = "Key Lesson This Month: P-101 vibration alarm at 02:15 — caught before failure by EPIC AI."
    run3.font.size = Pt(15)
    run3.font.color.rgb = GREEN
    run3.font.bold = True

    # ── Slide 2: Vibration Alarm Response ─────────────────────
    slide2 = add_slide("LESSON 1: VIBRATION ALARM RESPONSE",
                       "What happened on P-101 this month — and what to do when you see a vibration alarm")

    add_bullet_box(slide2, 0.5, 1.8, 5.8, 5.2, "THE INCIDENT (02:15 AM):", [
        ("P-101 vibration alarm fired: 7.4 mm/s (alarm 7.1)", RED),
        ("Bearing temp also rising: 78 deg C (normal 55)", RED),
        ("Vibration trending up for 6 days — not caught earlier", RED),
        ("EPIC AI flagged 75% bearing failure risk", AMBER),
        ("WO raised, work permit issued, bearing replaced by 05:45", GREEN),
        ("Equipment back in service before day shift", GREEN),
    ])
    add_bullet_box(slide2, 6.5, 1.8, 6.3, 5.2, "YOUR RESPONSE CHECKLIST:", [
        ("Do NOT silence alarm without investigation", RED),
        ("Tell your supervisor IMMEDIATELY", AMBER),
        ("Check trend: is it rising or stable?", WHITE),
        ("Check bearing temp — co-movement confirms bearing", WHITE),
        ("Do NOT operate above 9.0 mm/s (Zone D — shutdown)", RED),
        ("Raise incident report even if caught in time", AMBER),
    ])

    # ── Slide 3: ISO Vibration Zones ──────────────────────────
    slide3 = add_slide("ISO 10816-7 VIBRATION ZONES",
                       "Know the zones — P-101 reached Zone C. Zone D = emergency shutdown.")

    zones = [
        ("ZONE A", "< 2.3 mm/s",  "New equipment — excellent condition",       GREEN),
        ("ZONE B", "2.3–4.5 mm/s","Normal operation — acceptable for long-term", RGBColor(100, 200, 100)),
        ("ZONE C", "4.5–7.1 mm/s","Alert — investigate cause. Do not ignore",   AMBER),
        ("ZONE D", "> 7.1 mm/s",  "IMMEDIATE ACTION — risk of bearing damage",  RED),
        ("ALARM",  "7.1 mm/s",    "P-101 alarm setpoint (OISD-117 requirement)", AMBER),
        ("TRIP",   "11.2 mm/s",   "Automatic shutdown — API 670 requirement",    RED),
    ]

    zone_box = slide3.shapes.add_textbox(Inches(0.5), Inches(1.8), Inches(12), Inches(5))
    tf_z = zone_box.text_frame
    tf_z.word_wrap = True
    first = True
    for zone, value, desc, color in zones:
        p_z = tf_z.paragraphs[0] if first else tf_z.add_paragraph()
        first = False
        p_z.space_before = Pt(6)
        run = p_z.add_run()
        run.text = f"  {zone:8s}  {value:15s}  {desc}"
        run.font.size = Pt(16)
        run.font.color.rgb = color
        run.font.bold = (color == RED)

    # ── Slide 4: LOTO Rule ─────────────────────────────────────
    slide4 = add_slide("LESSON 2: LOCK-OUT / TAG-OUT (LOTO)",
                       "LOTO saved Rajesh from a 75 kW motor restart during bearing work this morning")

    add_bullet_box(slide4, 0.5, 1.8, 5.8, 5.2, "LOTO RULES — NO EXCEPTIONS:", [
        ("MINIMUM 2 LOTO locks on every isolation", RED),
        ("Your lock, your key — nobody else removes it", RED),
        ("VERIFY zero energy before ANY contact", RED),
        ("Test with approved test meter — not by feeling", AMBER),
        ("Supervisor adds 2nd lock — cannot start until both removed", AMBER),
        ("Drain, vent, purge ALL energy sources", WHITE),
    ])
    add_bullet_box(slide4, 6.5, 1.8, 6.3, 5.2, "ENERGY SOURCES TO ISOLATE (P-101):", [
        ("Electrical: MCC-101 motor (75 kW, 415 V)", RED),
        ("Process: Suction MOV-101A (crude oil 8.5 bar)", AMBER),
        ("Process: Discharge MOV-101B (crude oil 8.5 bar)", AMBER),
        ("Hydraulic: Seal flush Plan 11 (drain first)", AMBER),
        ("Thermal: Allow 30 min cool-down after shutdown", WHITE),
        ("Verify: Zero voltage, zero pressure, zero flow", GREEN),
    ])

    # ── Slide 5: Key Contacts ──────────────────────────────────
    slide5 = add_slide("EMERGENCY CONTACTS & KEY INFORMATION",
                       "If you see a problem — speak up. EPIC is a tool, not a replacement for your eyes")

    add_bullet_box(slide5, 0.5, 1.8, 6.0, 5.0, "KEY CONTACTS:", [
        ("Shift Supervisor: Suresh Nair — EXT 2210", WHITE),
        ("Safety Officer: Priya Nair — EXT 2301", AMBER),
        ("Maintenance Lead: Rajesh Kumar — EXT 2415", WHITE),
        ("Control Room DCS: EXT 2100 (24/7)", WHITE),
        ("Plant Emergency: DIAL 0 — Fire/Ambulance", RED),
        ("Plant Manager: Deepa Menon — EXT 2001", WHITE),
    ])
    add_bullet_box(slide5, 7.0, 1.8, 6.0, 5.0, "THIS MONTH'S SAFETY STATS:", [
        ("Near Misses Reported: 1 (P-101 vibration — GOOD)", GREEN),
        ("Lost Time Incidents: 0", GREEN),
        ("Open work permits today: 1 (P-101 bearing — CLOSED)", GREEN),
        ("Open Work Orders: 4 (1 critical — P-101 closed)", AMBER),
        ("Compliance Score: 78% (P-101 driving)", AMBER),
        ("Corrective actions overdue: 1 (CA-K401-2 — assign owner!)", RED),
    ])

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# DOC 8 — TXT: Night Shift Handover Notes
# ─────────────────────────────────────────────────────────────────────────────

def _gen_txt_handover() -> str:
    return f"""APEX REFINERY — CDU UNIT 4
NIGHT SHIFT HANDOVER NOTES
Date: {_TODAY}  |  Shift: 22:00 – 06:00  |  Supervisor: Suresh Nair
============================================================

UNIT STATUS SUMMARY
-------------------
P-101  Crude Oil Feed Pump   : ALARM at 02:15. Bearing replaced. BACK IN SERVICE 05:45.
P-202  Reflux Pump           : Running normally. Vibration 3.1 mm/s.
HX-201 Crude Feed Pre-heater : Running normally. Tube-side dP 1.8 bar.
V-301  Surge Drum            : Running normally. Level 65%, Pressure 3.2 barg.
K-401  Process Air Compressor: Running. Discharge 10.8 bar (low — corrective action pending).
G-101  Cooling Tower Fan     : Running. Vibration 2.8 mm/s. Blade inspection due 14 days.

EVENTS THIS SHIFT (chronological)
-----------------------------------
02:15  P-101 vibration alarm VT-101A = 7.4 mm/s (alarm 7.1, trip 11.2).
       Threshold monitor auto-raised WO-2026-0042. Rajesh Kumar notified.
02:18  AI query initiated. Risk: HIGH. 75% bearing failure probability.
       Recommendation: Controlled shutdown within 2 hours.
02:31  Incident report INC-2026-0042 opened (Near Miss P2 — Rajesh Kumar).
02:35  WP-2026-018 (Cold Work) created: bearing inspection + lube oil change.
02:38  Area Authority review: Suresh Patel approved.
02:39  Safety review: Priya Nair approved.
02:41  WP-2026-018 ISSUED. Rajesh Kumar briefed on scope and isolations.
02:44  WO-2026-0042 formally submitted by Rajesh Kumar.
02:46  WO approved by Ahmed Khan (Supervisor). Status: In Progress.
03:00  P-101 isolated. MCC-101 LOTO applied (2 locks: Rajesh Kumar, Ahmed Khan).
03:10  Suction MOV-101A and discharge MOV-101B closed. Zero pressure verified.
03:55  Bearing removal commenced. DE bearing: play 0.15 mm (limit 0.08 mm). FAILED.
04:30  SKF 6311-2RS/C3 DE bearing replaced. NDE grease replenished (2x LGMT-2).
05:00  Alignment check: angular 0.3 mrad (limit 0.5 mrad). PASS.
05:15  LOTO removed. 30-sec jog test: no anomaly.
05:30  P-101 restarted by DCS operator. Vibration 4.1 mm/s. Temp 52 deg C. NORMAL.
05:45  Functional test complete. P-101 flow 252 m3/hr, pressure 8.6 bar. PASS.
05:50  WO-2026-0042 marked complete by Rajesh Kumar.
05:52  WO verified by Ahmed Khan. Status: CLOSED. (Two-person rule confirmed.)
05:55  WP-2026-018 CLOSED.
06:00  Handover to Day Shift.

ACTIONS REQUIRED — DAY SHIFT
------------------------------
1. [Ahmed Khan] Close compliance issue CI-P101-3 after CMMS update confirmed.
2. [Ahmed Khan] Update CMMS: set P-101 next lubrication = today + 150 days.
3. [Ahmed Khan] CA-K401-2 (K-401 filter interval 60 days) — assign owner and close.
4. [Dr. Anand Sharma] Book G-101 fan blade erosion inspection (due in 14 days).
5. [Priya Nair] INC-2026-0042 investigation — root cause due within 48 hours.
6. [All] OEM maintenance PDF for P-101 bearing job to be uploaded to EPIC.

COST AVOIDANCE NOTE
--------------------
Estimated 18h unplanned CDU shutdown avoided = USD 240,000 lost production.
Actual maintenance cost: USD 14,200 (bearing + labour).
Net benefit of early detection: USD 225,800.

Suresh Nair — Night Shift Supervisor
{_TODAY}  06:00 IST
"""


# ─────────────────────────────────────────────────────────────────────────────
# DOC 9 — CSV: P-101 Sensor Data Export (30-day)
# ─────────────────────────────────────────────────────────────────────────────

def _gen_csv_sensor_export() -> str:
    import random
    import math

    random.seed(42)  # Reproducible
    rows = ["timestamp,equipment_id,sensor_key,value,unit,alarm_threshold,trip_threshold,status"]

    today = datetime.datetime.utcnow()
    for day in range(30, -1, -1):
        dt = today - datetime.timedelta(days=day)
        # vibration_de: 4.5 base, trending up from day 6
        vib_base = 4.5 if day > 6 else 4.5 + (6 - day) * 0.48
        vib = round(vib_base + random.uniform(-0.15, 0.15), 2)
        vib_status = "ALARM" if vib > 7.1 else ("ELEVATED" if vib > 5.5 else "NORMAL")
        rows.append(f"{dt.strftime('%Y-%m-%d %H:%M')},P-101,vibration_de,{vib},mm/s,7.1,11.2,{vib_status}")

        # bearing_temp_de: 55 base, rising with vibration
        temp_base = 55 + (vib - 4.5) * 7
        temp = round(temp_base + random.uniform(-1, 1), 1)
        temp_status = "ALARM" if temp > 75 else "NORMAL"
        rows.append(f"{dt.strftime('%Y-%m-%d %H:%M')},P-101,bearing_temp_de,{temp},deg_C,75.0,90.0,{temp_status}")

        # discharge_pressure: stable 8.2–8.5 bar
        pres = round(8.2 + random.uniform(0, 0.3), 2)
        rows.append(f"{dt.strftime('%Y-%m-%d %H:%M')},P-101,discharge_pressure,{pres},bar,9.5,10.5,NORMAL")

        # flow_rate: 240–255 m3/hr
        flow = round(245 + random.uniform(-7, 7), 1)
        rows.append(f"{dt.strftime('%Y-%m-%d %H:%M')},P-101,flow_rate,{flow},m3/hr,200.0,180.0,NORMAL")

    return "\n".join(rows)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — called by admin.py
# ─────────────────────────────────────────────────────────────────────────────

def generate_demo_documents() -> list[dict]:
    """
    Generate all demo documents, save them to UPLOADS_DIR, and return a list of
    DocumentRecord dicts ready for pg_insert into the DB.
    Safe to call multiple times — files are overwritten but DB uses on_conflict_do_nothing.
    """
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    def _save(name: str, content: bytes | str) -> str:
        path = os.path.join(UPLOADS_DIR, name)
        mode = "wb" if isinstance(content, bytes) else "w"
        encoding = None if isinstance(content, bytes) else "utf-8"
        with open(path, mode, encoding=encoding) as f:
            f.write(content)
        return path

    records: list[dict] = []

    # ── 1. PDF: Maintenance inspection report ───────────────────
    try:
        content = _gen_pdf_maintenance_report()
        path = _save("P101_Maintenance_Inspection_Report_2026.pdf", content)
        records.append({
            "id": "DOC-DEMO-PDF-01",
            "name": "P101_Maintenance_Inspection_Report_2026.pdf",
            "type": "manual",
            "equipment_ids": ["P-101"],
            "date": _TODAY_ISO,
            "file_path": path,
            "status": "processed",
            "char_count": 3200,
            "pipeline_steps": _PIPELINE_DONE,
            "sections": {
                "summary": "P-101 bearing inspection following vibration alarm VT-101A = 7.4 mm/s. DE bearing replaced (SKF 6311). Root cause: lubrication interval 214 days (max 180). Post-maintenance vibration 4.1 mm/s NORMAL.",
                "findings": "DE bearing radial play 0.15 mm (limit 0.08 mm). Grease contaminated with iron-oxide. NDE bearing within limits — regreased. Shaft coupling alignment 0.3 mrad — acceptable.",
                "actions": "DE bearing replaced. NDE grease replenished. CMMS alert set to 150 days. Compliance issue CI-P101-3 flagged.",
                "references": "OISD-117 Sec 8.3, ISO 10816-7 Zone C, API 610, SOP-P101-BEARING-REV3, INC-2022-034",
            },
            "entities": {
                "equipment_ids": ["P-101"],
                "parts": ["SKF 6311-2RS", "LGMT-2 grease"],
                "people": ["Rajesh Kumar", "Ahmed Khan", "Priya Nair"],
                "regulations": ["OISD-117", "ISO 10816-7", "API 610", "API 686"],
                "work_orders": ["WO-2026-0042"],
                "permits": ["WP-2026-018"],
                "incidents": ["INC-2026-0042", "INC-2022-034"],
            },
        })
    except Exception as e:
        records.append(_fallback_record("DOC-DEMO-PDF-01", "P101_Maintenance_Inspection_Report_2026.pdf",
                                        ".pdf", ["P-101"], str(e)))

    # ── 2. PDF: K-401 Incident investigation report ─────────────
    try:
        content = _gen_pdf_incident_report()
        path = _save("K401_Incident_Investigation_Report_INC2026-0031.pdf", content)
        records.append({
            "id": "DOC-DEMO-PDF-02",
            "name": "K401_Incident_Investigation_Report_INC2026-0031.pdf",
            "type": "incident_report",
            "equipment_ids": ["K-401"],
            "date": _d(14),
            "file_path": path,
            "status": "processed",
            "char_count": 2800,
            "pipeline_steps": _PIPELINE_DONE,
            "sections": {
                "summary": "K-401 compressor discharge pressure dropped to 10.8 bar (rated 12.5 bar) due to choked inlet filter. CA-K401-2 overdue. 4h downtime, USD 2,200 cost.",
                "root_cause": "Inlet filter element completely choked. Filter change interval in CMMS set to 90 days (not updated to 60 days per CA-K401-2 from INC-2024-015).",
                "corrective_actions": "CA-K401-1: Filter replaced (CLOSED). CA-K401-2: CMMS interval update (OPEN). CA-K401-3: Install dP transmitter (OPEN).",
            },
            "entities": {
                "equipment_ids": ["K-401"],
                "parts": ["AC-ZH350-FE"],
                "people": ["Ahmed Khan", "Dr. Anand Sharma"],
                "regulations": ["ASME B19.3", "ISO 10816"],
                "incidents": ["INC-2026-0031", "INC-2024-015"],
                "corrective_action_items": ["CA-K401-1", "CA-K401-2", "CA-K401-3"],
            },
        })
    except Exception as e:
        records.append(_fallback_record("DOC-DEMO-PDF-02", "K401_Incident_Investigation_Report_INC2026-0031.pdf",
                                        ".pdf", ["K-401"], str(e)))

    # ── 3. DOCX: SOP — P-101 Bearing Replacement ────────────────
    try:
        content = _gen_docx_sop()
        path = _save("SOP-P101-BEARING-REV3_Bearing_Replacement_Procedure.docx", content)
        records.append({
            "id": "DOC-DEMO-DOCX-01",
            "name": "SOP-P101-BEARING-REV3_Bearing_Replacement_Procedure.docx",
            "type": "sop",
            "equipment_ids": ["P-101"],
            "date": _TODAY_ISO,
            "file_path": path,
            "status": "processed",
            "char_count": 4100,
            "pipeline_steps": _PIPELINE_DONE,
            "sections": {
                "scope": "Lubrication, inspection, and replacement of DE and NDE bearings on P-101. Applies to scheduled PM (180-day interval) and corrective maintenance triggered by vibration alarm.",
                "hazards": "Rotating equipment (LOTO required), hydrocarbon release, hot surfaces (30 min cooldown), manual handling (4.2 kg bearing — two-person lift).",
                "procedure": "4 phases: Preparation (LOTO, gas test), Bearing Removal (hydraulic puller, journal measurement), Bearing Installation (heat to 100 deg C, 30-40% grease fill), Commissioning (jog test, vibration check).",
                "standards": "OISD-117, API 610, API 686, SOP-P101-BEARING-REV3, MSDS-LGMT2",
            },
            "entities": {
                "equipment_ids": ["P-101"],
                "parts": ["SKF 6311-2RS/C3", "Shell LGMT-2 grease", "Molykote 1000"],
                "people": ["Rajesh Kumar", "Ahmed Khan", "Priya Nair"],
                "regulations": ["OISD-117", "API 610", "API 686"],
                "doc_type": "SOP",
                "revision": "REV3",
            },
        })
    except Exception as e:
        records.append(_fallback_record("DOC-DEMO-DOCX-01", "SOP-P101-BEARING-REV3_Bearing_Replacement_Procedure.docx",
                                        ".docx", ["P-101"], str(e)))

    # ── 4. DOCX: Shift Handover Log ──────────────────────────────
    try:
        content = _gen_docx_handover()
        path = _save("Shift_Handover_Log_CDU_NightShift_22Jul2026.docx", content)
        records.append({
            "id": "DOC-DEMO-DOCX-02",
            "name": "Shift_Handover_Log_CDU_NightShift_22Jul2026.docx",
            "type": "other",
            "equipment_ids": ["P-101", "P-202", "HX-201", "V-301", "K-401", "G-101"],
            "date": _TODAY_ISO,
            "file_path": path,
            "status": "processed",
            "char_count": 2200,
            "pipeline_steps": _PIPELINE_DONE,
            "sections": {
                "summary": "Night shift handover 22 Jul 2026. P-101 vibration alarm at 02:15 — bearing replaced, back in service 05:45. K-401 discharge pressure low — corrective action pending. All other equipment running normally.",
                "events": "02:15 alarm, 02:18 AI query, 02:41 work permit issued, 03:55 bearing removal, 05:45 P-101 back in service, 06:00 handover.",
                "actions": "Close CI-P101-3, update CMMS lube interval, assign CA-K401-2 owner, book G-101 blade inspection.",
            },
            "entities": {
                "equipment_ids": ["P-101", "P-202", "HX-201", "V-301", "K-401", "G-101"],
                "people": ["Suresh Nair", "Rajesh Kumar", "Ahmed Khan", "Priya Nair"],
                "work_orders": ["WO-2026-0042"],
                "permits": ["WP-2026-018"],
                "incidents": ["INC-2026-0042"],
            },
        })
    except Exception as e:
        records.append(_fallback_record("DOC-DEMO-DOCX-02", "Shift_Handover_Log_CDU_NightShift_22Jul2026.docx",
                                        ".docx", ["P-101", "K-401"], str(e)))

    # ── 5. XLSX: Maintenance Schedule 2026 ──────────────────────
    try:
        content = _gen_xlsx_maintenance_schedule()
        path = _save("CDU_Equipment_Maintenance_Schedule_2026.xlsx", content)
        records.append({
            "id": "DOC-DEMO-XLSX-01",
            "name": "CDU_Equipment_Maintenance_Schedule_2026.xlsx",
            "type": "other",
            "equipment_ids": ["P-101", "P-202", "HX-201", "V-301", "K-401", "G-101"],
            "date": _TODAY_ISO,
            "file_path": path,
            "status": "processed",
            "char_count": 1800,
            "pipeline_steps": _PIPELINE_DONE,
            "sections": {
                "summary": "2026 preventive maintenance schedule for CDU/VDU equipment. P-101 lubrication overdue (-15 days). P-202 PM due today. K-401 filter change due in 55 days. HX-201 annual inspection in 275 days.",
                "overdue": "P-101 lubrication and bearing check: 15 days overdue. Immediate action required.",
            },
            "entities": {
                "equipment_ids": ["P-101", "P-202", "HX-201", "V-301", "K-401", "G-101"],
                "people": ["Rajesh Kumar", "Dr. Anand Sharma", "Ahmed Khan"],
                "standards": ["OISD-117", "API 610", "API 660"],
                "document_type": "Maintenance Schedule",
            },
        })
    except Exception as e:
        records.append(_fallback_record("DOC-DEMO-XLSX-01", "CDU_Equipment_Maintenance_Schedule_2026.xlsx",
                                        ".xlsx", ["P-101", "P-202", "HX-201", "V-301", "K-401", "G-101"], str(e)))

    # ── 6. XLSX: Spare Parts Inventory ──────────────────────────
    try:
        content = _gen_xlsx_spare_parts()
        path = _save("Spare_Parts_Inventory_Register_CDU_VDU.xlsx", content)
        records.append({
            "id": "DOC-DEMO-XLSX-02",
            "name": "Spare_Parts_Inventory_Register_CDU_VDU.xlsx",
            "type": "other",
            "equipment_ids": ["P-101", "P-202", "HX-201", "V-301", "K-401"],
            "date": _TODAY_ISO,
            "file_path": path,
            "status": "processed",
            "char_count": 1400,
            "pipeline_steps": _PIPELINE_DONE,
            "sections": {
                "summary": "12 spare part SKUs across CDU/VDU. 3 items low stock or out of stock: JC-8B1-T2 (mechanical seal — LOW), SKF-NJ311-E (LOW), ORP-P101-SHAFT (OUT OF STOCK — on order). Total inventory USD 15,421.",
                "critical": "P-101 critical spares: Bearing SKF-6311 (3 available), Seal JC-8B1-T2 (1 — LOW STOCK), Shaft (OUT OF STOCK — 60-day lead time).",
            },
            "entities": {
                "equipment_ids": ["P-101", "P-202", "HX-201", "V-301", "K-401"],
                "parts": ["SKF-6311-2RS", "JC-8B1-T2", "GEA-HX450-GS", "AC-ZH350-FE", "LGMT2-400G"],
                "locations": ["Warehouse A", "Warehouse B"],
                "document_type": "Inventory Register",
            },
        })
    except Exception as e:
        records.append(_fallback_record("DOC-DEMO-XLSX-02", "Spare_Parts_Inventory_Register_CDU_VDU.xlsx",
                                        ".xlsx", ["P-101", "K-401"], str(e)))

    # ── 7. PPTX: Safety Toolbox Talk ────────────────────────────
    try:
        content = _gen_pptx_toolbox_talk()
        path = _save("Toolbox_Talk_Rotating_Equipment_Safety_Jul2026.pptx", content)
        records.append({
            "id": "DOC-DEMO-PPTX-01",
            "name": "Toolbox_Talk_Rotating_Equipment_Safety_Jul2026.pptx",
            "type": "other",
            "equipment_ids": ["P-101", "P-202"],
            "date": _TODAY_ISO,
            "file_path": path,
            "status": "processed",
            "char_count": 2600,
            "pipeline_steps": _PIPELINE_DONE,
            "sections": {
                "summary": "Monthly safety toolbox talk: rotating equipment vibration awareness and LOTO procedure. Key lesson: P-101 vibration alarm this month — caught before failure by EPIC AI. ISO 10816-7 vibration zones explained.",
                "key_points": "ISO 10816-7 Zones A/B/C/D. LOTO 2-lock rule. P-101 alarm response checklist. Emergency contacts.",
            },
            "entities": {
                "equipment_ids": ["P-101", "P-202"],
                "people": ["Priya Nair", "Suresh Nair", "Rajesh Kumar"],
                "regulations": ["OISD-117", "ISO 10816-7", "API 670"],
                "document_type": "Safety Presentation",
            },
        })
    except Exception as e:
        records.append(_fallback_record("DOC-DEMO-PPTX-01", "Toolbox_Talk_Rotating_Equipment_Safety_Jul2026.pptx",
                                        ".pptx", ["P-101", "P-202"], str(e)))

    # ── 8. TXT: Shift Handover Notes ────────────────────────────
    try:
        content = _gen_txt_handover()
        path = _save("Night_Shift_Handover_Notes_CDU_22Jul2026.txt", content)
        records.append({
            "id": "DOC-DEMO-TXT-01",
            "name": "Night_Shift_Handover_Notes_CDU_22Jul2026.txt",
            "type": "other",
            "equipment_ids": ["P-101", "P-202", "HX-201", "V-301", "K-401", "G-101"],
            "date": _TODAY_ISO,
            "file_path": path,
            "status": "processed",
            "char_count": len(content),
            "pipeline_steps": _PIPELINE_DONE,
            "sections": {
                "summary": content[:500],
                "full_text": content,
            },
            "entities": {
                "equipment_ids": ["P-101", "P-202", "HX-201", "V-301", "K-401", "G-101"],
                "people": ["Suresh Nair", "Rajesh Kumar", "Ahmed Khan", "Priya Nair"],
                "work_orders": ["WO-2026-0042"],
                "permits": ["WP-2026-018"],
                "incidents": ["INC-2026-0042"],
                "cost_avoidance_usd": 225800,
            },
        })
    except Exception as e:
        records.append(_fallback_record("DOC-DEMO-TXT-01", "Night_Shift_Handover_Notes_CDU_22Jul2026.txt",
                                        ".txt", ["P-101", "K-401"], str(e)))

    # ── 9. CSV: P-101 Sensor Data Export ────────────────────────
    try:
        content = _gen_csv_sensor_export()
        path = _save("P101_Sensor_Data_Export_30Day_Jul2026.csv", content)
        lines = content.count("\n")
        records.append({
            "id": "DOC-DEMO-CSV-01",
            "name": "P101_Sensor_Data_Export_30Day_Jul2026.csv",
            "type": "other",
            "equipment_ids": ["P-101"],
            "date": _TODAY_ISO,
            "file_path": path,
            "status": "processed",
            "char_count": len(content),
            "pipeline_steps": _PIPELINE_DONE,
            "sections": {
                "summary": f"P-101 sensor data export: 30-day history for vibration_de, bearing_temp_de, discharge_pressure, flow_rate. {lines} data rows. Vibration trend: 4.5 to 7.4 mm/s over final 6 days — bearing failure signature.",
                "schema": "timestamp,equipment_id,sensor_key,value,unit,alarm_threshold,trip_threshold,status",
            },
            "entities": {
                "equipment_ids": ["P-101"],
                "sensors": ["vibration_de", "bearing_temp_de", "discharge_pressure", "flow_rate"],
                "standards": ["OISD-117", "ISO 10816-7"],
                "alarm_events": ["vibration_de ALARM"],
            },
        })
    except Exception as e:
        records.append(_fallback_record("DOC-DEMO-CSV-01", "P101_Sensor_Data_Export_30Day_Jul2026.csv",
                                        ".csv", ["P-101"], str(e)))

    return records


def _fallback_record(doc_id: str, name: str, ext: str, equipment_ids: list[str], error: str) -> dict:
    """Return a minimal stub record when file generation fails (e.g. fpdf2 not installed)."""
    path = os.path.join(UPLOADS_DIR, name)
    # Write a minimal placeholder so the file exists
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"[Demo document placeholder — generation error: {error}]\nDocument: {name}\n")
    except Exception:
        path = ""
    return {
        "id": doc_id,
        "name": name,
        "type": "other",
        "equipment_ids": equipment_ids,
        "date": _TODAY_ISO,
        "file_path": path,
        "status": "processed",
        "char_count": 0,
        "pipeline_steps": _PIPELINE_DONE,
        "sections": {"summary": f"Demo document (generation skipped: {error})"},
        "entities": {"equipment_ids": equipment_ids},
    }
