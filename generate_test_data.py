"""
@file generate_test_data.py
@module root

SUMMARY
-------
Generate a realistic 110-document construction dataset for the OpsBrain demo.
The script parses the manifest table from plan.md, then materializes DOCX, PDF,
XLSX, PPTX, DXF, SVG, PNG, TXT, and EML files with cross-linked entities.

EXPORTS
-------
- DocumentSpec: Dataclass for one manifest item.
- parse_manifest_from_plan: Parse file specs from plan.md table rows.
- generate_documents: Generate all documents into category directories.
- main: CLI entrypoint.

DEPENDENCIES (non-obvious)
--------------------------
- reportlab: PDF assembly with paragraph/table layouts.
- ezdxf: CAD-like DXF geometry and layer definitions.
- python-pptx: Slide generation for kickoff/QBR/safety/board decks.

USAGE EXAMPLE
-------------
python generate_test_data.py --output test_data --plan plan.md

@author  AI-generated
@created 2026-07-22
"""

from __future__ import annotations

import argparse
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

import ezdxf
import svgwrite
from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.util import Inches, Pt as PptPt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


CATEGORY_DIRS: dict[str, str] = {
    "project_management": "01_project_management",
    "engineering_drawings": "02_engineering_drawings",
    "safety_compliance": "03_safety_compliance",
    "maintenance_equipment": "04_maintenance_equipment",
    "quality_management": "05_quality_management",
    "procurement_contracts": "06_procurement_contracts",
    "emails": "07_emails",
    "reports_presentations": "08_reports_presentations",
}

CATEGORY_RANGES: list[tuple[int, int, str]] = [
    (1, 15, "project_management"),
    (16, 30, "engineering_drawings"),
    (31, 45, "safety_compliance"),
    (46, 60, "maintenance_equipment"),
    (61, 75, "quality_management"),
    (76, 85, "procurement_contracts"),
    (86, 100, "emails"),
    (101, 110, "reports_presentations"),
]

DEFAULT_PLAN = Path(__file__).resolve().parent / "plan.md"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "test_data"


COMPANY = {
    "name": "Apex Infrastructure Pvt. Ltd.",
    "cin": "U45200MH2015PTC271842",
    "gstin": "27AADCA6841K1ZS",
    "pan": "AADCA6841K",
    "license": "FL/MH/Pune/2024/001234",
    "regd_office": "Plot 14B, Hinjewadi Phase II, Pune - 411057",
    "site_office": "NH47 Bypass Site, Ch. Km 34+200, Navi Mumbai-Pune Expressway",
}

DEFAULT_PROJECT = "NH47-BPB-24"
DEFAULT_CONTACTS = [
    "anil.mehta@apexinfra.in",
    "rajesh.kumar@apexinfra.in",
    "priya.sharma@apexinfra.in",
    "vikram.singh@apexinfra.in",
]

DEMO_DATA = {
    "crane001_breakdown": {
        "date": "2024-04-17",
        "time": "08:42",
        "fault_code": "H-E03",
        "fault_desc": "Main boom lift cylinder servo pressure underrange (Actual: 17 bar, Setpoint: 35 bar)",
        "cause": "Internal leakage with worn slipper pads in servo pump assembly",
        "part_no": "LH-ER-6840-022",
        "technician": "Amol Kulkarni (Liebherr India Service)",
        "downtime_days": 3,
        "cost_parts_inr": 312000,
        "cost_labour_inr": 74000,
        "cost_standby_inr": 100000,
        "cost_total_inr": 486000,
        "last_service_date": "2024-02-28",
        "tpi_cert": "LR-IN-24-0047",
        "tpi_valid_until": "2025-04-01",
    },
    "incident001": {
        "id": "INCIDENT-001",
        "date": "2024-03-08",
        "time": "09:45",
        "location": "Pier P3, Soffit Formwork Bay 3B, +14 m elevation",
        "equipment": "SCAFFOLD-SYS-01",
        "injured": [
            "Suresh Babu (Prop. 2204) - right radius fracture - 18 LTI days",
            "Mohammed Iqbal (Prop. 1876) - soft tissue injuries - 3 LTI days",
        ],
        "total_lti_days": 21,
        "ltifr_after": 5.71,
        "root_cause": "Base plate on inclined ground surface, base jack not installed per MS-SCF-001",
        "regulation_violated": "BOCW Act 1996, Schedule 7, Rule 14",
        "prior_near_miss": "NM-001",
    },
    "concrete_c002": {
        "batch": "C002",
        "pour_date": "2024-03-14",
        "location": "Pile Cap PC-03",
        "pour_volume_m3": 38.4,
        "slump_mm": 110,
        "strength_7d_mpa": 18.6,
        "strength_28d_mpa": 29.4,
        "min_acceptable_individual_mpa": 32.0,
        "min_acceptable_mean_mpa": 39.0,
        "status": "FAIL",
        "ncr": "NCR-001",
        "disposition": "Remove and re-cast",
        "recast_completed": "2024-04-28",
        "ncr_status": "CLOSED",
    },
}


DXF_LAYERS: dict[str, dict[str, int]] = {
    "GRIDLINES": {"color": 8},
    "PILES": {"color": 2},
    "PILE_CAPS": {"color": 3},
    "REBAR": {"color": 30},
    "DIMENSIONS": {"color": 1},
    "ANNOTATIONS": {"color": 7},
    "TITLEBLOCK": {"color": 5},
    "STRUCTURAL": {"color": 4},
}


MANIFEST_ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*([A-Za-z0-9]+)\s*\|\s*(.+?)\s*\|\s*$"
)


@dataclass(frozen=True)
class DocumentSpec:
    """One document item parsed from plan.md."""

    doc_id: int
    filename: str
    fmt: str
    summary: str
    category: str


def category_for_doc_id(doc_id: int) -> str:
    """Return category key for the manifest numeric range."""
    for start, end, category in CATEGORY_RANGES:
        if start <= doc_id <= end:
            return category
    raise ValueError(f"Unknown doc id range: {doc_id}")


def parse_manifest_from_plan(plan_path: Path) -> list[DocumentSpec]:
    """Parse all document rows from Section 4 tables in plan.md."""
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan file not found: {plan_path}")

    specs: list[DocumentSpec] = []
    for line in plan_path.read_text(encoding="utf-8").splitlines():
        match = MANIFEST_ROW_RE.match(line.strip())
        if not match:
            continue
        doc_id = int(match.group(1))
        filename = match.group(2).strip()
        fmt = match.group(3).strip().lower()
        summary = match.group(4).strip()
        specs.append(
            DocumentSpec(
                doc_id=doc_id,
                filename=filename,
                fmt=fmt,
                summary=summary,
                category=category_for_doc_id(doc_id),
            )
        )

    specs = sorted(specs, key=lambda s: s.doc_id)
    if len(specs) != 110:
        raise ValueError(f"Expected 110 documents in plan manifest, found {len(specs)}")
    return specs


def clean_title(filename: str) -> str:
    """Create a human-readable title from file name."""
    stem = Path(filename).stem
    title = stem.replace("_", " ").replace("-", " ")
    title = re.sub(r"\s+", " ", title).strip()
    return title.title()


def extract_refs(text: str) -> list[str]:
    """Extract known entity tokens from summary text."""
    tokens: set[str] = set()
    patterns = [
        r"CRANE-\d{3}",
        r"EXCAVATOR-\d{3}",
        r"CONCRETE-PUMP-\d{2}",
        r"GENSET-[A-Z]\d",
        r"SCAFFOLD-SYS-\d{2}",
        r"WO-\d{4}-\d{3}",
        r"NCR-\d{3}",
        r"NM-\d{3}",
        r"INCIDENT-\d{3}",
        r"BR-\d{3}",
        r"DWG-[A-Z]\d{3}",
        r"C\d{3}",
        r"NH47-BPB-24",
        r"SKY-PUN-23",
    ]
    for pattern in patterns:
        for found in re.findall(pattern, text):
            tokens.add(found)
    return sorted(tokens)


def default_refs_for_category(category: str) -> list[str]:
    """Provide baseline cross-link refs by category."""
    if category == "project_management":
        return ["NH47-BPB-24", "Anil Mehta", "WO-2024-001"]
    if category == "engineering_drawings":
        return ["NH47-BPB-24", "CRANE-001", "DWG-A002"]
    if category == "safety_compliance":
        return ["INCIDENT-001", "Vikram Singh", "SCAFFOLD-SYS-01"]
    if category == "maintenance_equipment":
        return ["CRANE-001", "WO-2024-001", "BR-001"]
    if category == "quality_management":
        return ["NCR-001", "NCR-002", "C002"]
    if category == "procurement_contracts":
        return ["FastCrete Pvt. Ltd.", "PO-2024-001", "NH47-BPB-24"]
    if category == "emails":
        return ["anil.mehta@apexinfra.in", "NH47-BPB-24", "CRANE-001"]
    return ["NH47-BPB-24", "Priya Sharma", "INCIDENT-001"]


def refs_for_spec(spec: DocumentSpec) -> list[str]:
    """Build a reference list ensuring at least two linked entities."""
    refs = default_refs_for_category(spec.category) + extract_refs(spec.summary)
    dedup: list[str] = []
    for ref in refs:
        if ref not in dedup:
            dedup.append(ref)
    if len(dedup) < 2:
        dedup.extend(["NH47-BPB-24", "Anil Mehta"])
    return dedup[:8]


def details_for_spec(spec: DocumentSpec) -> list[str]:
    """Construct detailed points for each document body."""
    details = [spec.summary]

    if "BR-001" in spec.filename or "breakdown_report" in spec.filename:
        bd = DEMO_DATA["crane001_breakdown"]
        details.extend(
            [
                f"Failure timestamp: {bd['date']} {bd['time']}; fault code {bd['fault_code']}.",
                f"Technical cause: {bd['cause']}; failed part: {bd['part_no']}.",
                f"Downtime impact: {bd['downtime_days']} days; total cost INR {bd['cost_total_inr']:,}.",
                f"Last PM service date {bd['last_service_date']} confirms PM was not overdue.",
            ]
        )

    if "INCIDENT-001" in spec.summary or "incident_report_INCIDENT-001" in spec.filename:
        inc = DEMO_DATA["incident001"]
        details.extend(
            [
                f"Incident recorded at {inc['location']} on {inc['date']} {inc['time']}.",
                f"Regulation violation: {inc['regulation_violated']}.",
                f"Root cause analysis: {inc['root_cause']}.",
                f"LTI impact: {inc['total_lti_days']} days; LTIFR changed to {inc['ltifr_after']}.",
            ]
        )

    if "C002" in spec.summary or "NCR-001" in spec.summary:
        c002 = DEMO_DATA["concrete_c002"]
        details.extend(
            [
                f"Batch {c002['batch']} 28-day cube strength {c002['strength_28d_mpa']} MPa.",
                f"Acceptance threshold per IS 456 Cl.16.3.1: {c002['min_acceptable_individual_mpa']} MPa individual.",
                f"Disposition: {c002['disposition']}; re-cast completed {c002['recast_completed']}.",
                f"NCR status: {c002['ncr_status']}.",
            ]
        )

    category_defaults = {
        "project_management": [
            "Baseline schedule uses WBS codes W1.1 through W7.4 with monthly review gates.",
            "All progress and risk records reference project code NH47-BPB-24.",
        ],
        "engineering_drawings": [
            "All geometric dimensions use metric units and are tagged with revision status.",
            "Drawing title block includes project code, drawing number, revision, and checker fields.",
        ],
        "safety_compliance": [
            "Safety controls align to Factory Act 1948 and BOCW Act 1996 requirements.",
            "Permit workflows require sign-off by site safety officer before work start.",
        ],
        "maintenance_equipment": [
            "Service records capture equipment tag, hour meter, task, parts, and responsible technician.",
            "Work order links ensure traceability from inspection findings to corrective completion.",
        ],
        "quality_management": [
            "Concrete and rebar quality checks cite IS clauses and include pass/fail evidence.",
            "NCR lifecycle is tracked with owner, due date, and closure verification notes.",
        ],
        "procurement_contracts": [
            "Procurement records include vendor qualification status and inspection references.",
            "Cost controls map to BOQ and monthly variance reports for management review.",
        ],
        "emails": [
            "Email threads include sender, recipient, subject, and action-required timeline.",
            "Messages cross-reference IDs such as BR-001, NCR-001, and drawing revisions.",
        ],
        "reports_presentations": [
            "Management reports consolidate schedule, cost, safety, and quality indicators.",
            "Presentations include explicit decisions and next actions for the next review cycle.",
        ],
    }

    details.extend(category_defaults.get(spec.category, []))

    # Keep the final body concise but meaningful.
    compact: list[str] = []
    for item in details:
        item = item.strip()
        if item and item not in compact:
            compact.append(item)
    return compact[:8]


def metadata_for_spec(spec: DocumentSpec) -> list[tuple[str, str]]:
    """Metadata rows reused by most document formats."""
    now = datetime.now().strftime("%Y-%m-%d")
    rows = [
        ("Document ID", f"DOC-{spec.doc_id:03d}"),
        ("Document Title", clean_title(spec.filename)),
        ("Project", DEFAULT_PROJECT),
        ("Company", COMPANY["name"]),
        ("Generated On", now),
    ]
    return rows


def xlsx_table_for_spec(spec: DocumentSpec) -> tuple[list[str], list[list[str]]]:
    """Return headers and rows for spreadsheet-like documents."""
    file_key = spec.filename.lower()

    if "risk_register" in file_key:
        headers = ["Risk ID", "Description", "Likelihood", "Impact", "Owner", "Mitigation"]
        rows = [
            [f"R-{i:02d}", desc, lik, imp, owner, mit]
            for i, (desc, lik, imp, owner, mit) in enumerate(
                [
                    ("Monsoon delay on piling", "High", "High", "Anil Mehta", "Shift critical pours before 15 Jun"),
                    ("Rebar supply volatility", "Medium", "High", "Ravi Narayan", "Lock two alternate suppliers"),
                    ("Crane breakdown recurrence", "Medium", "High", "Rajesh Kumar", "Weekly hydraulic trend checks"),
                    ("Scaffold compliance lapse", "Low", "High", "Vikram Singh", "Daily WAH pre-start checklist"),
                    ("Concrete batch variability", "Medium", "Medium", "Priya Sharma", "On-site slump and cube witness checks"),
                ],
                start=1,
            )
        ]
        return headers, rows

    if "project_schedule_gantt" in file_key:
        headers = ["WBS", "Activity", "Start", "Finish", "Duration Days", "Owner", "Status"]
        rows = [
            ["W1.1", "Mobilisation", "2024-01-08", "2024-01-20", "13", "Anil Mehta", "Complete"],
            ["W2.1", "Piling P1-P2", "2024-01-22", "2024-03-05", "44", "Rajesh Kumar", "Complete"],
            ["W2.2", "Piling P3-P5", "2024-03-06", "2024-06-30", "117", "Rajesh Kumar", "In Progress"],
            ["W3.1", "Pile Caps", "2024-02-10", "2024-07-20", "162", "Rajesh Kumar", "In Progress"],
            ["W4.1", "Pier Shaft", "2024-03-15", "2024-09-10", "180", "Anil Mehta", "Planned"],
            ["W5.1", "Superstructure", "2024-08-20", "2025-02-10", "175", "Anil Mehta", "Planned"],
        ]
        return headers, rows

    if "resource_allocation_matrix" in file_key:
        headers = ["Person", "Role", "Piling", "Pile Caps", "Piers", "QA/QC", "Safety"]
        rows = [
            ["Rajesh Kumar", "Site Engineer", "100%", "80%", "60%", "20%", "10%"],
            ["Priya Sharma", "QA Manager", "30%", "40%", "40%", "100%", "20%"],
            ["Vikram Singh", "Safety Officer", "40%", "50%", "50%", "20%", "100%"],
            ["Anil Mehta", "Project Manager", "20%", "20%", "20%", "20%", "20%"],
        ]
        return headers, rows

    if "safety_inspection_checklist" in file_key:
        headers = ["Week", "Area", "Checklist Item", "Status", "Action Owner", "Due"]
        rows = [
            ["W1", "P1 Access", "Guardrails installed", "PASS", "Vikram Singh", "-"],
            ["W2", "P3 Scaffold", "Base jacks installed", "FAIL", "Rajesh Kumar", "2024-03-09"],
            ["W3", "P3 Scaffold", "Working platform fully decked", "FAIL", "Rajesh Kumar", "2024-03-10"],
            ["W3", "P3 Scaffold", "Double lanyard harness checks", "FAIL", "Vikram Singh", "2024-03-10"],
            ["W4", "P3 Scaffold", "Post-incident re-inspection", "PASS", "Vikram Singh", "2024-03-21"],
            ["W5", "Hot Work Zone", "Fire watch present", "PASS", "Sunil Rao", "-"],
        ]
        return headers, rows

    if "maintenance_log_crane-001" in file_key:
        headers = ["Date", "Equipment", "Hour Meter", "Task", "Parts", "Technician", "Status"]
        rows = [
            ["2024-01-20", "CRANE-001", "2240", "6-month statutory check", "NA", "Deepak Verma", "PASS"],
            ["2024-02-28", "CRANE-001", "2510", "250h PM service", "Hyd filter H-442", "Deepak Verma", "PASS"],
            ["2024-04-17", "CRANE-001", "2870", "Breakdown event H-E03", "LH-ER-6840-022", "Amol Kulkarni", "FAIL"],
            ["2024-04-20", "CRANE-001", "2876", "Post-repair verification", "Servo pump assy", "Amol Kulkarni", "PASS"],
        ]
        return headers, rows

    if "maintenance_log_crane-002" in file_key:
        headers = ["Date", "Equipment", "Task", "Observations", "Technician", "Status"]
        rows = [
            ["2024-01-18", "CRANE-002", "Monthly PM", "Normal", "Karan Yadav", "PASS"],
            ["2024-02-22", "CRANE-002", "Hook block check (post NM-001)", "Tag line update", "Karan Yadav", "PASS"],
            ["2024-03-18", "CRANE-002", "Wire rope inspection", "No broken strands", "Karan Yadav", "PASS"],
        ]
        return headers, rows

    if "equipment_inventory_register" in file_key:
        headers = ["Tag", "Model", "Serial/Reg", "Owner/Hire", "Insurance", "Cert Expiry", "Next PM"]
        rows = [
            ["CRANE-001", "Liebherr LTM 1080-1", "MH-14-AE-9924", "Owned", "New India Assurance", "2025-04-01", "2024-06-15"],
            ["CRANE-002", "XCMG QY50K", "HR-YC-2241", "SkyLift Hire", "SkyLift Policy", "2024-12-31", "2024-06-01"],
            ["EXCAVATOR-003", "CAT 320 GC", "CAT0320DPJLT09562", "Owned", "New India Assurance", "2025-01-15", "2025-01-15"],
            ["CONCRETE-PUMP-01", "Schwing SP 1800", "SS-SP1800-2021-4481", "Owned", "New India Assurance", "2025-03-01", "2024-08-01"],
            ["GENSET-A1", "Kirloskar K-1250", "KL-K1250-2020-0341", "Owned", "New India Assurance", "2025-01-31", "2024-06-30"],
            ["GENSET-A2", "Kirloskar K-1250", "KL-K1250-2020-0342", "Owned", "New India Assurance", "2025-01-31", "2024-05-15"],
            ["SCAFFOLD-SYS-01", "Layher Ringlock", "NA", "Owned", "New India Assurance", "2025-02-28", "2024-07-01"],
        ]
        return headers, rows

    if "concrete_pour_register" in file_key:
        headers = ["Pour ID", "Date", "Location", "Batch", "Volume m3", "Slump mm", "Cube IDs", "Weather"]
        rows = [
            ["P-001", "2024-02-12", "PC-01", "C001", "36.0", "80", "C001-1..3", "31C / 64%"],
            ["P-009", "2024-03-14", "PC-03", "C002", "38.4", "110", "C002-1..3", "33C / 68%"],
            ["P-010", "2024-04-28", "PC-03 Recast", "C010", "40.1", "82", "C010-1..3", "30C / 61%"],
            ["P-018", "2024-05-10", "Pier P5", "C018", "31.2", "76", "C018-1..3", "32C / 59%"],
        ]
        return headers, rows

    if "inspection_test_plan_pile_foundation" in file_key:
        headers = ["ITP Point", "Description", "Type", "Responsibility", "Record", "Status"]
        rows = [
            ["ITP-01", "Bore depth verification", "H", "Rajesh Kumar", "Bore Log", "PASS"],
            ["ITP-02", "Base cleaning confirmation", "W", "Priya Sharma", "Checklist", "PASS"],
            ["ITP-03", "Rebar cage insertion", "W", "Priya Sharma", "Photo Log", "PASS"],
            ["ITP-04", "Concrete start approval", "H", "Priya Sharma", "Pour Permit", "PASS"],
            ["ITP-05", "28-day cube acceptance", "R", "Priya Sharma", "Lab Report", "NCR-001"],
        ]
        return headers, rows

    if "is_code_compliance_checklist" in file_key:
        headers = ["Code", "Clause", "Activity", "Requirement", "Status", "Reference"]
        rows = [
            ["IS 456:2000", "Cl.16.3.1", "Concrete acceptance", "Cube >= 32 MPa", "NON-CONFORMING", "NCR-001"],
            ["IS 1786:2008", "Cl.4", "Rebar strength", "Fe500D UTS check", "PASS", "R001 report"],
            ["IS 13920:2016", "Cl.5", "Ductile detailing", "Confinement spacing", "PASS", "DWG-S001"],
            ["IRC 112:2020", "Cl.14", "Bridge durability", "Cover and exposure class", "PASS", "A003 section"],
        ]
        return headers, rows

    if "quality_dashboard" in file_key:
        headers = ["KPI", "Target", "Actual", "Status", "Notes"]
        rows = [
            ["Concrete pass rate", ">=95%", "91.7%", "AMBER", "C002 fail closed via recast"],
            ["Open NCR count", "0", "1", "RED", "NCR-002 open"],
            ["ITP completion", ">=90%", "83%", "AMBER", "Late witness sign-offs"],
            ["Cube test compliance", "100%", "100%", "GREEN", "All cube sets logged"],
        ]
        return headers, rows

    if "vendor_list" in file_key:
        headers = ["Vendor", "Category", "Contact", "Approval", "Last PO", "Rating"]
        rows = [
            ["RCC Materials Ltd", "Aggregate", "procurement@rccmaterials.in", "Approved", "PO-2024-009", "78/100"],
            ["Steel Forge India", "Rebar", "sales@steelforge.co.in", "Approved", "PO-2024-001", "82/100"],
            ["FastCrete Pvt. Ltd.", "Concrete", "ops@fastcrete.in", "Approved", "PO-2024-002", "76/100"],
            ["SkyLift Equipment", "Equipment Hire", "fleet@skylift.in", "Approved", "PO-2024-003", "80/100"],
        ]
        return headers, rows

    if "delivery_challan_register" in file_key:
        headers = ["Date", "Supplier", "Material", "Quantity", "Challan", "MRI Ref", "Status"]
        rows = [
            ["2024-02-27", "Steel Forge India", "Fe500D 25mm", "48 MT", "CH-4418", "MRI-001", "Part Reject"],
            ["2024-03-14", "FastCrete Pvt. Ltd.", "M35 Concrete", "38.4 m3", "CH-9077", "MRI-002", "Accepted"],
            ["2024-04-28", "FastCrete Pvt. Ltd.", "M35 Concrete", "40.1 m3", "CH-9312", "MRI-005", "Accepted"],
        ]
        return headers, rows

    if "cost_report_apr2024" in file_key or "cost_report_may2024" in file_key:
        headers = ["Cost Code", "Description", "Budget INR", "Actual INR", "Variance INR", "Variance %"]
        rows = [
            ["EQ-001", "Equipment", "40000000", "44200000", "4200000", "10.5%"],
            ["MAT-001", "Materials", "82000000", "80100000", "-1900000", "-2.3%"],
            ["LAB-001", "Labour", "36000000", "35250000", "-750000", "-2.1%"],
            ["SUB-001", "Subcontracts", "51000000", "52800000", "1800000", "3.5%"],
        ]
        return headers, rows

    if "productivity_analysis" in file_key:
        headers = ["Activity", "Target", "Actual", "Unit", "Variance", "Remarks"]
        rows = [
            ["Piling", "2.0", "1.6", "piles/day", "-0.4", "Impact from BR-001"],
            ["Formwork", "150", "132", "m2/day", "-18", "Manpower shortage"],
            ["Concreting", "60", "67", "m3/day", "+7", "Improved batching"],
        ]
        return headers, rows

    # Generic fallback table
    headers = ["Field", "Value", "Reference"]
    rows = [
        ["Summary", spec.summary[:120], "plan.md"],
        ["Project", DEFAULT_PROJECT, "Project Charter"],
        ["Document", f"DOC-{spec.doc_id:03d}", "Manifest"],
    ]
    return headers, rows


def write_docx(spec: DocumentSpec, target: Path) -> None:
    """Generate a DOCX document with metadata, details, and reference list."""
    doc = Document()
    heading = doc.add_heading(clean_title(spec.filename), level=0)
    heading.alignment = 1

    sub = doc.add_paragraph(f"{COMPANY['name']} | Project {DEFAULT_PROJECT} | DOC-{spec.doc_id:03d}")
    sub.runs[0].font.size = Pt(10)

    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for key, value in metadata_for_spec(spec):
        row = table.add_row().cells
        row[0].text = key
        row[1].text = value

    doc.add_heading("Executive Summary", level=1)
    doc.add_paragraph(spec.summary)

    doc.add_heading("Key Details", level=1)
    for detail in details_for_spec(spec):
        doc.add_paragraph(detail, style="List Bullet")

    doc.add_heading("Linked Entities", level=1)
    for ref in refs_for_spec(spec):
        doc.add_paragraph(ref, style="List Bullet")

    doc.add_paragraph("Approved by: Anil Mehta (Project Manager)")
    doc.add_paragraph("Reviewed by: Priya Sharma (QA Manager)")

    target.parent.mkdir(parents=True, exist_ok=True)
    doc.save(target)


def write_pdf(spec: DocumentSpec, target: Path) -> None:
    """Generate a PDF with title, metadata table, summary, and detail bullets."""
    target.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title_custom",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=12,
    )
    normal = ParagraphStyle(
        "normal_custom",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        spaceAfter=8,
    )

    doc = SimpleDocTemplate(str(target), pagesize=A4, topMargin=36, bottomMargin=36)
    flow: list = []

    flow.append(Paragraph(clean_title(spec.filename), title_style))
    flow.append(Paragraph(f"{COMPANY['name']} | Project {DEFAULT_PROJECT} | DOC-{spec.doc_id:03d}", normal))
    flow.append(Spacer(1, 6))

    meta_rows = [["Field", "Value"]] + [[k, v] for k, v in metadata_for_spec(spec)]
    meta_table = Table(meta_rows, colWidths=[130, 360])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    flow.append(meta_table)
    flow.append(Spacer(1, 10))

    flow.append(Paragraph("Executive Summary", styles["Heading3"]))
    flow.append(Paragraph(spec.summary, normal))

    flow.append(Paragraph("Key Details", styles["Heading3"]))
    for detail in details_for_spec(spec):
        flow.append(Paragraph(f"- {detail}", normal))

    flow.append(Paragraph("Linked Entities", styles["Heading3"]))
    refs = ", ".join(refs_for_spec(spec))
    flow.append(Paragraph(refs, normal))

    doc.build(flow)


def write_xlsx(spec: DocumentSpec, target: Path) -> None:
    """Generate a spreadsheet with a metadata sheet and a data sheet."""
    target.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws_meta = wb.active
    ws_meta.title = "Metadata"

    header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)

    ws_meta.append(["Field", "Value"])
    for cell in ws_meta[1]:
        cell.fill = header_fill
        cell.font = header_font

    for key, value in metadata_for_spec(spec):
        ws_meta.append([key, value])

    ws_meta.column_dimensions["A"].width = 28
    ws_meta.column_dimensions["B"].width = 70

    ws_data = wb.create_sheet("Data")
    headers, rows = xlsx_table_for_spec(spec)
    ws_data.append(headers)

    for idx, cell in enumerate(ws_data[1], start=1):
        cell.fill = header_fill
        cell.font = header_font
        ws_data.column_dimensions[chr(64 + idx)].width = 24

    for row in rows:
        ws_data.append(row)

    for row in ws_data.iter_rows(min_row=2, max_row=ws_data.max_row):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    wb.save(target)


def add_bullet_slide(prs: Presentation, title: str, bullets: list[str]) -> None:
    """Add one bullet slide to a deck."""
    layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(layout)
    slide.shapes.title.text = title
    slide.shapes.title.text_frame.paragraphs[0].font.size = PptPt(28)

    body = slide.shapes.placeholders[1].text_frame
    body.clear()
    for i, bullet in enumerate(bullets):
        p = body.paragraphs[0] if i == 0 else body.add_paragraph()
        p.text = bullet
        p.font.size = PptPt(18)


def write_pptx(spec: DocumentSpec, target: Path) -> None:
    """Generate presentation decks with realistic business and technical bullets."""
    target.parent.mkdir(parents=True, exist_ok=True)

    prs = Presentation()
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = clean_title(spec.filename)
    title_slide.placeholders[1].text = (
        f"{COMPANY['name']}\nProject {DEFAULT_PROJECT}\nDocument DOC-{spec.doc_id:03d}"
    )

    if "project_kickoff" in spec.filename.lower():
        slides = [
            ("Project Vision", ["Construct NH47 bypass elevated bridge with 24-month target.", "Safety-first execution under BOCW and Factory Act compliance."]),
            ("Scope and Deliverables", ["120 m elevated structure with 5 primary piers.", "Associated drainage, access roads, and traffic diversion works."]),
            ("Team and Governance", ["PM: Anil Mehta", "Site Engineering: Rajesh Kumar", "QA: Priya Sharma", "Safety: Vikram Singh"]),
            ("Equipment Plan", ["CRANE-001 Liebherr LTM 1080-1 (80T)", "CRANE-002 XCMG QY50K (50T)", "EXCAVATOR-003 CAT 320", "CONCRETE-PUMP-01 Schwing SP 1800"]),
            ("Milestone Baseline", ["Piling complete by 30 Jun 2024", "Substructure complete by Sep 2024", "Superstructure complete by Feb 2025"]),
            ("Top Risks", ["Monsoon delays", "Equipment breakdown recurrence", "Rebar supply volatility"]),
            ("Controls and KPIs", ["Weekly status reviews", "NCR turnaround <= 14 days", "LTIFR target < 1.0"]),
        ]
    elif "qbr_q1_2024" in spec.filename.lower():
        slides = [
            ("Quarter Snapshot", ["Progress 21.8% vs planned 28.0%", "Cost variance +INR 4.2 Cr", "Two project portfolio: NH47 + SKY-PUN-23"]),
            ("Schedule Position", ["Delay primarily from CRANE-001 breakdown BR-001", "Recovery measures in place from Apr W4 onward"]),
            ("Safety Performance", ["LTIFR: 5.71", "INCIDENT-001 and 2 near misses logged", "WAH controls upgraded"]),
            ("Quality Performance", ["NCR-001 closed after PC-03 recast", "NCR-002 remains open at Pier P5"]),
            ("Cost Position", ["Equipment line exceeded by INR 42.0 lakh", "Materials and labour within tolerance"]),
            ("Q2 Focus", ["Close NCR-002", "Protect schedule before monsoon", "Stabilize crane uptime"]),
        ]
    elif "annual_safety_performance" in spec.filename.lower():
        slides = [
            ("Safety Overview", ["YTD LTIFR 5.71 (target < 1.0)", "2 LTIs, 2 near misses"]),
            ("Major Incident", ["INCIDENT-001: scaffold collapse at Pier P3", "21 total LTI days"]),
            ("Near Miss Learnings", ["NM-001: unsecured load on CRANE-002", "NM-002: slip on wet rebar cage"]),
            ("Training and Competency", ["35 workers trained across induction, WAH, CSE, hot work", "Competency scores tracked per individual"]),
            ("Corrective Actions", ["WAH permit controls tightened", "Scaffold base jack checks mandated", "Daily safety checklist enforcement"]),
            ("Next-year Targets", ["LTIFR < 1.0", "Zero repeat scaffold non-compliances", "100% permit adherence"]),
        ]
    elif "board_update_nh47" in spec.filename.lower():
        slides = [
            ("Executive Summary", ["Progress 31.4% as of May 2024", "Two open red risks: NCR-002 and monsoon exposure"]),
            ("Schedule", ["Critical path protected after CRANE-001 recovery", "Piling completion milestone: 30 Jun 2024"]),
            ("Cost", ["Actual INR 62.6 Cr vs budget INR 60.0 Cr", "Variance driven by BR-001 impact"]),
            ("Safety and Quality", ["INCIDENT-001 fully investigated", "NCR-001 closed, NCR-002 in progress"]),
            ("Decisions Required", ["Approve additional weekend shifts", "Approve contingency pump hire", "Approve supplier dual-sourcing strategy"]),
        ]
    else:
        slides = [
            ("Overview", [spec.summary]),
            ("Key Details", details_for_spec(spec)[:4]),
            ("Linked Entities", refs_for_spec(spec)[:5]),
        ]

    for title, bullets in slides:
        add_bullet_slide(prs, title, bullets)

    prs.save(target)


def write_txt(spec: DocumentSpec, target: Path) -> None:
    """Generate plain text technical or contractual summary docs."""
    target.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        clean_title(spec.filename),
        "=" * max(20, len(clean_title(spec.filename))),
        f"Document: DOC-{spec.doc_id:03d}",
        f"Project: {DEFAULT_PROJECT}",
        f"Company: {COMPANY['name']}",
        "",
        "Summary:",
        textwrap.fill(spec.summary, width=100),
        "",
        "Key Details:",
    ]
    lines.extend([f"- {d}" for d in details_for_spec(spec)])
    lines.append("")
    lines.append("Linked Entities:")
    lines.append(", ".join(refs_for_spec(spec)))

    target.write_text("\n".join(lines), encoding="utf-8")


def parse_email_summary(summary: str) -> tuple[str, str, str, str]:
    """Parse from/to/subject/body from summary text."""
    from_email = "anil.mehta@apexinfra.in"
    to_email = "rajesh.kumar@apexinfra.in"
    subject = "Project Update"
    body = summary

    from_match = re.search(r"From:\s*([^\s;]+)", summary)
    to_match = re.search(r"To:\s*([^;]+)", summary)
    subject_match = re.search(r"Subject:\s*([^;]+)", summary)

    if from_match:
        from_email = from_match.group(1).strip()
    if to_match:
        to_email = to_match.group(1).strip()
    if subject_match:
        subject = subject_match.group(1).strip()
        body_part = summary.split(";", maxsplit=3)
        if len(body_part) == 4:
            body = body_part[3].strip()

    return from_email, to_email, subject, body


def write_txt_email(spec: DocumentSpec, target: Path) -> None:
    """Write email content as a plain-text file with readable headers and body."""
    target.parent.mkdir(parents=True, exist_ok=True)

    from_email, to_email, subject, body = parse_email_summary(spec.summary)

    ist = timezone(timedelta(hours=5, minutes=30))
    dt = datetime(2024, 1, 8, 9, 0, tzinfo=ist) + timedelta(days=spec.doc_id - 86)
    date_str = dt.strftime("%a, %d %b %Y %H:%M:%S %z")

    cc: str | None = None
    if "incident" in spec.filename.lower():
        cc = "pd.nh47@nhai.gov.in"
    elif "quality" in spec.filename.lower() or "ncr" in body.lower():
        cc = "priya.sharma@apexinfra.in"

    refs = ", ".join(refs_for_spec(spec))
    body_full = (
        f"{body}\n\n"
        f"Document Reference: DOC-{spec.doc_id:03d}\n"
        f"Project: {DEFAULT_PROJECT}\n"
        f"Linked Entities: {refs}\n\n"
        "Please acknowledge and action as applicable.\n"
        "Regards,\n"
        f"{from_email.split('@')[0].replace('.', ' ').title()}"
    )

    separator = "-" * 72
    lines = [
        f"From:    {from_email}",
        f"To:      {to_email}",
    ]
    if cc:
        lines.append(f"Cc:      {cc}")
    lines += [
        f"Subject: {subject}",
        f"Date:    {date_str}",
        f"Ref:     DOC-{spec.doc_id:03d} | Project {DEFAULT_PROJECT}",
        separator,
        "",
        body_full,
        "",
        separator,
    ]

    target.write_text("\n".join(lines), encoding="utf-8")


def draw_svg_common_title(dwg: svgwrite.Drawing, title: str) -> None:
    """Draw a title box and title for SVG engineering outputs."""
    dwg.add(dwg.rect(insert=(20, 20), size=(1160, 60), fill="#0f172a", stroke="#f59e0b", stroke_width=2))
    dwg.add(dwg.text(title, insert=(40, 58), fill="#f8fafc", font_size="28px", font_family="Arial"))
    dwg.add(dwg.text(f"Project: {DEFAULT_PROJECT}", insert=(900, 58), fill="#f8fafc", font_size="16px"))


def write_svg(spec: DocumentSpec, target: Path) -> None:
    """Generate authentic-looking SVG schematics for drawing files."""
    target.parent.mkdir(parents=True, exist_ok=True)

    dwg = svgwrite.Drawing(str(target), size=(1200, 800))
    dwg.add(dwg.rect(insert=(0, 0), size=(1200, 800), fill="#f8fafc"))
    draw_svg_common_title(dwg, clean_title(spec.filename))

    fname = spec.filename.lower()

    if "structural_section_detail" in fname:
        # Pile cap section with bars.
        dwg.add(dwg.rect(insert=(180, 220), size=(840, 320), fill="none", stroke="#0f172a", stroke_width=3))
        for x in range(220, 980, 60):
            dwg.add(dwg.circle(center=(x, 300), r=8, fill="#dc2626"))
            dwg.add(dwg.circle(center=(x, 460), r=8, fill="#dc2626"))
        dwg.add(dwg.text("12 x T25 longitudinal bars", insert=(190, 200), fill="#111827", font_size="18px"))
        dwg.add(dwg.text("T10 @ 150 mm helical links", insert=(190, 570), fill="#111827", font_size="18px"))
        dwg.add(dwg.text("Cover = 75 mm (XS2)", insert=(780, 570), fill="#111827", font_size="18px"))

    elif "pile_layout_plan" in fname:
        start_x, start_y = 350, 230
        spacing = 180
        for row in range(2):
            for col in range(3):
                cx = start_x + col * spacing
                cy = start_y + row * spacing
                dwg.add(dwg.circle(center=(cx, cy), r=48, fill="none", stroke="#2563eb", stroke_width=3))
                dwg.add(dwg.text(f"P{row+1}{col+1}", insert=(cx - 14, cy + 6), fill="#111827", font_size="16px"))
        dwg.add(dwg.text("Pile dia: 800 mm | Spacing: 2.4 m c/c | Design load: 2500 kN", insert=(250, 640), fill="#111827", font_size="20px"))

    elif "electrical_single_line" in fname:
        # GENSET -> MDB -> SP feeders.
        dwg.add(dwg.rect(insert=(120, 220), size=(180, 120), fill="#dbeafe", stroke="#1d4ed8", stroke_width=3))
        dwg.add(dwg.text("GENSET-A1", insert=(145, 285), fill="#0f172a", font_size="22px"))
        dwg.add(dwg.rect(insert=(120, 420), size=(180, 120), fill="#e0e7ff", stroke="#4338ca", stroke_width=3))
        dwg.add(dwg.text("GENSET-A2", insert=(145, 485), fill="#0f172a", font_size="22px"))
        dwg.add(dwg.rect(insert=(500, 300), size=(220, 170), fill="#dcfce7", stroke="#15803d", stroke_width=3))
        dwg.add(dwg.text("MLDB", insert=(585, 390), fill="#0f172a", font_size="28px"))
        for idx in range(4):
            x = 860
            y = 180 + idx * 140
            dwg.add(dwg.rect(insert=(x, y), size=(180, 90), fill="#fef3c7", stroke="#b45309", stroke_width=2))
            dwg.add(dwg.text(f"SP-0{idx+1}", insert=(920, y + 52), fill="#0f172a", font_size="20px"))
            dwg.add(dwg.line(start=(720, 350), end=(860, y + 45), stroke="#111827", stroke_width=2))
        dwg.add(dwg.line(start=(300, 280), end=(500, 340), stroke="#111827", stroke_width=3))
        dwg.add(dwg.line(start=(300, 480), end=(500, 420), stroke="#111827", stroke_width=3))
        dwg.add(dwg.text("4C x 240 sqmm Al cables", insert=(480, 520), fill="#111827", font_size="18px"))

    elif "site_access_road" in fname:
        dwg.add(dwg.polyline(points=[(120, 650), (340, 520), (620, 500), (980, 320)], fill="none", stroke="#374151", stroke_width=28))
        dwg.add(dwg.text("Haul Road (6.0 m)", insert=(420, 460), fill="#111827", font_size="22px"))
        dwg.add(dwg.circle(center=(720, 450), r=150, fill="none", stroke="#ef4444", stroke_dasharray="10,8", stroke_width=3))
        dwg.add(dwg.text("Turning radius 15 m", insert=(650, 620), fill="#ef4444", font_size="20px"))

    elif "drainage_layout" in fname:
        for y in [220, 320, 420, 520, 620]:
            dwg.add(dwg.line(start=(120, y), end=(1080, y), stroke="#0284c7", stroke_width=8))
        for x in [280, 520, 760, 980]:
            dwg.add(dwg.line(start=(x, 200), end=(x, 660), stroke="#0284c7", stroke_width=8))
        for x, y in [(280, 320), (760, 520), (980, 420)]:
            dwg.add(dwg.rect(insert=(x - 20, y - 20), size=(40, 40), fill="#fef9c3", stroke="#a16207", stroke_width=2))
            dwg.add(dwg.text("ST", insert=(x - 10, y + 8), fill="#111827", font_size="16px"))
        dwg.add(dwg.text("Surface channels 300x300 mm with silt traps", insert=(250, 730), fill="#111827", font_size="20px"))

    elif "skyline_tower_structural_plan" in fname:
        # Column grid A1-E5.
        for i in range(5):
            x = 250 + i * 170
            dwg.add(dwg.line(start=(x, 180), end=(x, 680), stroke="#111827", stroke_width=2))
            dwg.add(dwg.text(chr(65 + i), insert=(x - 8, 160), fill="#111827", font_size="18px"))
        for j in range(5):
            y = 220 + j * 110
            dwg.add(dwg.line(start=(210, y), end=(980, y), stroke="#111827", stroke_width=2))
            dwg.add(dwg.text(str(j + 1), insert=(180, y + 6), fill="#111827", font_size="18px"))
        for i in range(5):
            for j in range(5):
                x = 250 + i * 170
                y = 220 + j * 110
                dwg.add(dwg.rect(insert=(x - 14, y - 14), size=(28, 28), fill="#93c5fd", stroke="#1d4ed8", stroke_width=2))
        dwg.add(dwg.text("Column grid A1-E5, slab panels S-01 to S-24", insert=(280, 740), fill="#111827", font_size="20px"))

    else:
        dwg.add(dwg.text(spec.summary, insert=(40, 120), fill="#111827", font_size="18px"))

    # Linked refs block
    refs = ", ".join(refs_for_spec(spec))
    dwg.add(dwg.rect(insert=(20, 750), size=(1160, 35), fill="#111827"))
    dwg.add(dwg.text(f"Linked entities: {refs}", insert=(35, 773), fill="#f8fafc", font_size="14px"))
    dwg.save()


def draw_png_canvas(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Create common canvas for PNG engineering layouts."""
    image = Image.new("RGB", (1600, 1200), (250, 252, 255))
    draw = ImageDraw.Draw(image)

    draw.rectangle((20, 20, 1580, 120), fill=(17, 24, 39), outline=(245, 158, 11), width=3)
    draw.text((40, 55), title, fill=(248, 250, 252))
    draw.text((1320, 55), f"Project {DEFAULT_PROJECT}", fill=(248, 250, 252))
    return image, draw


def write_png(spec: DocumentSpec, target: Path) -> None:
    """Generate realistic PNG diagrams with labeled geometry and notes."""
    target.parent.mkdir(parents=True, exist_ok=True)

    image, draw = draw_png_canvas(clean_title(spec.filename))
    fname = spec.filename.lower()

    if "site_layout_plan" in fname:
        draw.rectangle((110, 180, 1490, 1020), outline=(31, 41, 55), width=4)
        draw.text((120, 190), "Site Boundary", fill=(17, 24, 39))
        # Zones and roads
        draw.rectangle((150, 240, 620, 560), outline=(34, 197, 94), width=3)
        draw.rectangle((680, 240, 1120, 560), outline=(59, 130, 246), width=3)
        draw.rectangle((150, 620, 620, 980), outline=(245, 158, 11), width=3)
        draw.rectangle((680, 620, 1120, 980), outline=(168, 85, 247), width=3)
        draw.text((330, 400), "Zone-1", fill=(17, 24, 39))
        draw.text((860, 400), "Zone-2", fill=(17, 24, 39))
        draw.text((330, 790), "Zone-3", fill=(17, 24, 39))
        draw.text((860, 790), "Zone-4", fill=(17, 24, 39))
        draw.rectangle((1150, 240, 1450, 980), fill=(229, 231, 235), outline=(55, 65, 81), width=2)
        draw.text((1170, 270), "Access Road", fill=(17, 24, 39))
        # Equipment icons.
        draw.ellipse((370, 690, 470, 790), fill=(220, 38, 38), outline=(127, 29, 29), width=3)
        draw.text((330, 810), "CRANE-001", fill=(17, 24, 39))
        draw.ellipse((860, 690, 960, 790), fill=(245, 158, 11), outline=(146, 64, 14), width=3)
        draw.text((825, 810), "CRANE-002", fill=(17, 24, 39))
        draw.rectangle((720, 310, 880, 390), fill=(16, 185, 129), outline=(6, 95, 70), width=3)
        draw.text((710, 400), "CONCRETE-PUMP-01", fill=(17, 24, 39))

    elif "formwork_detail" in fname:
        draw.rectangle((180, 260, 1420, 930), outline=(31, 41, 55), width=3)
        for x in range(220, 1400, 120):
            draw.line((x, 320, x, 880), fill=(120, 113, 108), width=4)
        for y in range(320, 920, 120):
            draw.line((220, y, 1380, y), fill=(120, 113, 108), width=4)
        draw.text((230, 940), "MS props @ 1.2 m grid", fill=(17, 24, 39))
        draw.rectangle((250, 360, 1350, 430), fill=(191, 219, 254), outline=(30, 64, 175), width=2)
        draw.text((260, 370), "Soffit form panel", fill=(17, 24, 39))
        draw.text((260, 460), "Double waling 200x75", fill=(17, 24, 39))

    elif "rebar_arrangement" in fname:
        draw.rectangle((220, 260, 1380, 980), outline=(31, 41, 55), width=3)
        for x in range(260, 1360, 70):
            draw.line((x, 300, x, 940), fill=(220, 38, 38), width=3)
        for y in range(300, 940, 70):
            draw.line((260, y, 1360, y), fill=(220, 38, 38), width=3)
        draw.text((250, 1010), "Deck slab rebar T12 @ 150 BW/TW, lap 600 mm, cover 40 mm", fill=(17, 24, 39))

    elif "skyline_tower_floor_plan_l1" in fname:
        draw.rectangle((180, 220, 1420, 980), outline=(31, 41, 55), width=3)
        for i in range(5):
            x = 300 + i * 230
            draw.line((x, 260, x, 940), fill=(107, 114, 128), width=2)
        for j in range(5):
            y = 300 + j * 150
            draw.line((240, y, 1360, y), fill=(107, 114, 128), width=2)
        for i in range(5):
            for j in range(5):
                x = 300 + i * 230
                y = 300 + j * 150
                draw.rectangle((x - 20, y - 20, x + 20, y + 20), fill=(147, 197, 253), outline=(30, 64, 175), width=2)
        draw.rectangle((640, 500, 880, 760), outline=(55, 65, 81), width=3)
        draw.text((685, 620), "Lift Core", fill=(17, 24, 39))

    elif "equipment_placement" in fname:
        draw.rectangle((120, 190, 1480, 1040), outline=(31, 41, 55), width=3)
        draw.text((130, 200), "NH47 Site Equipment Placement", fill=(17, 24, 39))
        draw.rectangle((300, 350, 620, 520), fill=(20, 184, 166), outline=(15, 118, 110), width=3)
        draw.text((320, 430), "CONCRETE-PUMP-01", fill=(255, 255, 255))
        draw.rectangle((800, 330, 1250, 760), fill=(167, 139, 250), outline=(91, 33, 182), width=3)
        draw.text((830, 530), "SCAFFOLD-SYS-01\n(1400 m2)", fill=(255, 255, 255))
        draw.rectangle((700, 260, 1360, 820), outline=(220, 38, 38), width=3)
        draw.text((740, 830), "Safety exclusion zone", fill=(220, 38, 38))

    elif "traffic_management" in fname:
        draw.rectangle((120, 180, 1480, 1020), outline=(31, 41, 55), width=3)
        draw.line((180, 980, 780, 500), fill=(75, 85, 99), width=40)
        draw.line((840, 460, 1420, 220), fill=(75, 85, 99), width=40)
        draw.text((420, 560), "Diversion Route A", fill=(17, 24, 39))
        draw.text((1010, 320), "Diversion Route B", fill=(17, 24, 39))
        for x, y in [(430, 640), (590, 540), (980, 400), (1180, 320)]:
            draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill=(251, 191, 36), outline=(146, 64, 14), width=2)
        draw.text((300, 1040), "Flagman points and barricade positions", fill=(17, 24, 39))

    else:
        draw.text((80, 170), spec.summary, fill=(17, 24, 39))

    refs = ", ".join(refs_for_spec(spec))
    draw.rectangle((20, 1110, 1580, 1180), fill=(17, 24, 39), outline=(245, 158, 11), width=2)
    draw.text((40, 1140), f"Linked entities: {refs}", fill=(248, 250, 252))

    image.save(target)


def prepare_dxf_doc() -> ezdxf.document.Drawing:
    """Create a DXF document with standard layers and metric units."""
    doc = ezdxf.new(dxfversion="R2018")
    for name, cfg in DXF_LAYERS.items():
        if name not in doc.layers:
            doc.layers.new(name=name, dxfattribs=cfg)
    doc.header["$INSUNITS"] = 4
    doc.header["$MEASUREMENT"] = 1
    return doc


def write_dxf(spec: DocumentSpec, target: Path) -> None:
    """Generate DXF files with realistic bridge geometry."""
    target.parent.mkdir(parents=True, exist_ok=True)

    doc = prepare_dxf_doc()
    msp = doc.modelspace()
    fname = spec.filename.lower()

    # Title frame
    msp.add_lwpolyline([(0, 0), (120, 0), (120, 80), (0, 80), (0, 0)], dxfattribs={"layer": "TITLEBLOCK"})
    msp.add_text(clean_title(spec.filename), dxfattribs={"height": 2.5, "layer": "ANNOTATIONS"}).set_placement((2, 76))
    msp.add_text(f"Project {DEFAULT_PROJECT}", dxfattribs={"height": 2.0, "layer": "ANNOTATIONS"}).set_placement((85, 76))

    if "foundation_plan" in fname:
        # Grid lines P1-P5 and abutments.
        x_grids = [10, 25, 40, 55, 70, 85]
        for x in x_grids:
            msp.add_line((x, 10), (x, 70), dxfattribs={"layer": "GRIDLINES"})
        for i, x in enumerate(x_grids, start=1):
            label = f"P{i}" if i <= 5 else "A2"
            if i == 1:
                label = "A1"
            msp.add_text(label, dxfattribs={"height": 1.6, "layer": "ANNOTATIONS"}).set_placement((x - 1.2, 72))

        # Pile caps and pile circles.
        for idx, x in enumerate(x_grids[1:6], start=1):
            cx, cy = x, 40
            msp.add_lwpolyline(
                [(cx - 2.4, cy - 2.4), (cx + 2.4, cy - 2.4), (cx + 2.4, cy + 2.4), (cx - 2.4, cy + 2.4), (cx - 2.4, cy - 2.4)],
                dxfattribs={"layer": "PILE_CAPS"},
            )
            offsets = [(-1.2, -1.2), (0, -1.2), (1.2, -1.2), (-1.2, 1.2), (0, 1.2), (1.2, 1.2)]
            for ox, oy in offsets:
                msp.add_circle((cx + ox, cy + oy), radius=0.4, dxfattribs={"layer": "PILES"})
            msp.add_text(f"Pier P{idx}", dxfattribs={"height": 1.2, "layer": "ANNOTATIONS"}).set_placement((cx - 1.8, cy + 4.0))

        msp.add_text("Scale 1:100 | 36 piles, dia 800 mm", dxfattribs={"height": 1.6, "layer": "ANNOTATIONS"}).set_placement((2, 4))

    elif "bridge_elevation" in fname:
        # Deck profile and piers.
        deck_y = 55
        msp.add_line((8, deck_y), (112, deck_y), dxfattribs={"layer": "STRUCTURAL"})
        pier_x = [22, 42, 62, 82]
        pier_heights = [36, 42, 45, 40]
        for x, height in zip(pier_x, pier_heights):
            msp.add_lwpolyline(
                [(x - 1.0, 10), (x + 1.0, 10), (x + 1.0, height), (x - 1.0, height), (x - 1.0, 10)],
                dxfattribs={"layer": "STRUCTURAL"},
            )
            msp.add_text(f"H={height-10} m", dxfattribs={"height": 1.1, "layer": "DIMENSIONS"}).set_placement((x - 2.4, height + 1.4))
        msp.add_text("4 spans x 30 m = 120 m", dxfattribs={"height": 1.6, "layer": "DIMENSIONS"}).set_placement((45, 60))

    elif "bridge_cross_section" in fname:
        # Section: deck + girders + pier.
        msp.add_lwpolyline(
            [(20, 58), (100, 58), (100, 62), (20, 62), (20, 58)],
            dxfattribs={"layer": "STRUCTURAL"},
        )
        for x in [30, 45, 60, 75]:
            msp.add_lwpolyline(
                [(x, 50), (x + 6, 50), (x + 6, 58), (x, 58), (x, 50)],
                dxfattribs={"layer": "STRUCTURAL"},
            )
        msp.add_lwpolyline(
            [(55, 10), (65, 10), (65, 50), (55, 50), (55, 10)],
            dxfattribs={"layer": "STRUCTURAL"},
        )
        msp.add_text("Deck width 9.6 m", dxfattribs={"height": 1.4, "layer": "DIMENSIONS"}).set_placement((52, 64))
        msp.add_text("Pier shaft 800 mm", dxfattribs={"height": 1.2, "layer": "DIMENSIONS"}).set_placement((52, 8))

    else:
        msp.add_text(spec.summary, dxfattribs={"height": 1.5, "layer": "ANNOTATIONS"}).set_placement((5, 10))

    doc.saveas(target)


def write_document(spec: DocumentSpec, output_root: Path) -> Path:
    """Generate one document to its category directory."""
    category_dir = output_root / CATEGORY_DIRS[spec.category]
    category_dir.mkdir(parents=True, exist_ok=True)
    target = category_dir / spec.filename

    if spec.fmt == "docx":
        write_docx(spec, target)
    elif spec.fmt == "pdf":
        write_pdf(spec, target)
    elif spec.fmt == "xlsx":
        write_xlsx(spec, target)
    elif spec.fmt == "pptx":
        write_pptx(spec, target)
    elif spec.fmt == "txt":
        write_txt(spec, target)
    elif spec.fmt == "eml":
        # Override filename to .txt for plain-text email output.
        target = target.with_suffix(".txt")
        write_txt_email(spec, target)
    elif spec.fmt == "svg":
        write_svg(spec, target)
    elif spec.fmt == "png":
        write_png(spec, target)
    elif spec.fmt == "dxf":
        write_dxf(spec, target)
    else:
        raise ValueError(f"Unsupported format {spec.fmt} for {spec.filename}")

    return target


def generate_documents(
    output_root: Path,
    specs: Sequence[DocumentSpec] | None = None,
    plan_path: Path = DEFAULT_PLAN,
) -> list[Path]:
    """Generate all or selected documents into the output directory."""
    if specs is None:
        specs = parse_manifest_from_plan(plan_path)

    generated: list[Path] = []
    for spec in specs:
        generated.append(write_document(spec, output_root))
    return generated


def parse_doc_id_filter(value: str) -> set[int]:
    """Parse comma-separated ids or ranges like 1-10,45,88."""
    selected: set[int] = set()
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_str, end_str = token.split("-", maxsplit=1)
            start, end = int(start_str), int(end_str)
            for i in range(start, end + 1):
                selected.add(i)
        else:
            selected.add(int(token))
    return selected


def main() -> None:
    """CLI entrypoint for dataset generation."""
    parser = argparse.ArgumentParser(description="Generate 110 construction demo documents from plan manifest")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN, help="Path to plan.md with manifest tables")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output root directory")
    parser.add_argument(
        "--only",
        type=str,
        default="",
        help="Optional id filter, e.g. 1-20 or 1,2,3,88",
    )

    args = parser.parse_args()

    specs = parse_manifest_from_plan(args.plan)
    if args.only:
        chosen = parse_doc_id_filter(args.only)
        specs = [spec for spec in specs if spec.doc_id in chosen]

    generated = generate_documents(args.output, specs=specs, plan_path=args.plan)

    by_category: dict[str, int] = {}
    for spec in specs:
        by_category[spec.category] = by_category.get(spec.category, 0) + 1

    print(f"Generated {len(generated)} documents at: {args.output}")
    for category, count in sorted(by_category.items()):
        print(f"  - {CATEGORY_DIRS[category]}: {count}")

    print("Sample outputs:")
    for path in generated[:8]:
        print(f"  - {path}")


if __name__ == "__main__":
    main()
