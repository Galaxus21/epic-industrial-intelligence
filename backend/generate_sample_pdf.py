"""
Generate a sample industrial maintenance report PDF for Pump P-101.
Run: python generate_sample_pdf.py
Output: sample_docs/P101_Maintenance_Inspection_Report_2026.pdf
"""
import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_docs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

AMBER  = (245, 158, 11)
GREEN  = (16, 185, 129)
RED    = (239, 68, 68)
DARK   = (31, 31, 31)
GREY   = (100, 100, 100)
LIGHT  = (240, 240, 240)
WHITE  = (255, 255, 255)
BLACK  = (10, 10, 10)

_REPLACE = str.maketrans({
    "\u2014": " - ",   # em dash
    "\u2013": " - ",   # en dash
    "\u2018": "'",     # left single quote
    "\u2019": "'",     # right single quote
    "\u201c": '"',     # left double quote
    "\u201d": '"',     # right double quote
    "\u2026": "...",   # ellipsis
    "\u2022": "*",     # bullet
    "\u00b0": "deg",   # degree sign (outside fpdf safe range when bold)
})

def s(text: str) -> str:
    """Sanitize text to Latin-1 safe characters."""
    return text.translate(_REPLACE).encode("latin-1", errors="replace").decode("latin-1")


class IndustrialReport(FPDF):
    def header(self):
        self.set_fill_color(*DARK)
        self.rect(0, 0, 210, 18, "F")
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*AMBER)
        self.set_xy(8, 4)
        self.cell(0, 10, "AI OPERATIONS BRAIN  |  MAINTENANCE INSPECTION REPORT", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def footer(self):
        self.set_y(-14)
        self.set_fill_color(*DARK)
        self.rect(0, self.get_y(), 210, 14, "F")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*AMBER)
        self.cell(0, 10, f"CONFIDENTIAL  |  CDU Unit 4  |  Page {self.page_no()}", align="C")

    def section_header(self, title: str):
        self.ln(4)
        self.set_fill_color(*DARK)
        self.set_text_color(*AMBER)
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 8, f"  {title}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.ln(2)

    def kv_row(self, key: str, value: str, value_color=None, bold_value=False):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*GREY)
        self.cell(60, 6, s(key), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "B" if bold_value else "", 9)
        self.set_text_color(*(value_color or BLACK))
        self.cell(0, 6, s(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def table_header(self, cols: list[tuple[str, int]]):
        self.set_fill_color(*DARK)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 8)
        for label, width in cols:
            self.cell(width, 7, s(f" {label}"), border=0, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.ln()

    def table_row(self, values: list[tuple[str, int]], fill=False, color=None):
        self.set_fill_color(*(LIGHT if fill else WHITE))
        self.set_text_color(*(color or BLACK))
        self.set_font("Helvetica", "", 8)
        for val, width in values:
            self.cell(width, 6, s(f" {val}"), border=0, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.ln()

    def alert_box(self, text: str, level="warning"):
        color_map = {"warning": AMBER, "danger": RED, "ok": GREEN}
        color = color_map.get(level, AMBER)
        self.set_fill_color(*color)
        self.rect(self.get_x(), self.get_y(), 4, 8, "F")
        self.set_x(self.get_x() + 6)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*BLACK)
        self.cell(0, 8, s(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)


def build_pdf(output_path: str):
    pdf = IndustrialReport(orientation="P", unit="mm", format="A4")
    pdf.set_margins(12, 22, 12)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # -- Title block ----------------------------------------------------------
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 10, "MAINTENANCE INSPECTION REPORT", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 6, "Pump P-101  |  Crude Oil Feed Pump  |  CDU Unit 4", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(2)
    pdf.set_draw_color(*AMBER)
    pdf.set_line_width(0.8)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.ln(4)

    # -- ALERT -----------------------------------------------------------------
    pdf.alert_box("[!]  VIBRATION ALARM ACTIVE: DE Bearing at 7.2 mm/s  -  Exceeds alarm setpoint 7.1 mm/s", level="warning")
    pdf.alert_box("[!]  MAINTENANCE OVERDUE: Lubrication schedule exceeded by 12 days", level="warning")

    # -- Equipment Details -----------------------------------------------------
    pdf.section_header("1. EQUIPMENT DETAILS")
    rows = [
        ("Equipment ID",      "P-101"),
        ("Equipment Name",    "Crude Oil Feed Pump"),
        ("Type",              "Centrifugal Pump  -  API 610 Type BB1"),
        ("Location",          "Unit 4  -  CDU (Crude Distillation Unit), Pump House A"),
        ("Manufacturer",      "Flowserve Corporation"),
        ("Model / Serial",    "PVXM-100  |  S/N: FS-2018-4412"),
        ("Installed Date",    "12 March 2018"),
        ("Criticality",       "HIGH"),
        ("P&ID Reference",    "PID-CDU-001-Rev4"),
        ("Inspection Date",   "20 July 2026"),
        ("Inspector",         "Rajesh Kumar  -  Senior Maintenance Technician"),
        ("Supervisor",        "S. Venkataraman  -  Operations Supervisor"),
    ]
    for k, v in rows:
        pdf.kv_row(k, v)

    # -- Specifications --------------------------------------------------------
    pdf.section_header("2. EQUIPMENT SPECIFICATIONS")
    pdf.table_header([("Parameter", 65), ("Design Value", 55), ("Unit", 40), ("Notes", 28)])
    specs = [
        ("Rated Flow",                "250",   "m³/hr",  "At BEP"),
        ("Rated Head",                "85",    "m",      ""),
        ("Motor Power",               "75",    "kW",     ""),
        ("Rated Speed",               "2960",  "RPM",    "50 Hz"),
        ("Design Pressure",           "8.5",   "bar",    ""),
        ("Operating Temperature",     "-20 to 120", " deg C", ""),
        ("NPSHR",                     "3.2",   "m",      ""),
        ("Pump Efficiency",           "82",    "%",      "At BEP"),
        ("Process Fluid",             "Crude Oil", "API 35 deg , 65 deg C", ""),
        ("Seal Type",                 "Mech. Seal Type-2", "Plan 11", "John Crane 8B-1"),
        ("Bearing Type (DE/NDE)",     "SKF 6311", " - ",   "Relubricate 14-day interval"),
    ]
    for i, (p, v, u, n) in enumerate(specs):
        pdf.table_row([(p, 65), (v, 55), (u, 40), (n, 28)], fill=(i % 2 == 0))

    # -- Current Sensor Readings -----------------------------------------------
    pdf.section_header("3. CURRENT SENSOR READINGS (as at 20 July 2026)")
    pdf.table_header([("Sensor", 60), ("Reading", 30), ("Normal", 28), ("Alarm", 28), ("Trip", 28), ("Status", 18)])
    readings = [
        ("Vibration  -  DE Bearing",   "7.2 mm/s",  "4.5",  "7.1",  "11.2", "ALARM",   RED),
        ("Vibration  -  NDE Bearing",  "5.8 mm/s",  "4.5",  "7.1",  "11.2", "OK",      GREEN),
        ("Bearing Temp  -  DE",        "68  deg C",     "55",   "75",   "90",   "OK",      GREEN),
        ("Bearing Temp  -  NDE",       "62  deg C",     "55",   "75",   "90",   "OK",      GREEN),
        ("Discharge Pressure",       "7.8 bar",   "8.5",  " - ",    " - ",    "LOW",     AMBER),
        ("Flow Rate",                "238 m³/hr", "250",  " - ",    " - ",    "OK",      GREEN),
        ("Motor Current",            "42.3 A",    "45",   " - ",    " - ",    "OK",      GREEN),
    ]
    for i, (sensor, reading, normal, alarm, trip, status, scolor) in enumerate(readings):
        pdf.set_fill_color(*(LIGHT if i % 2 == 0 else WHITE))
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*BLACK)
        for val, width in [(sensor, 60), (reading, 30), (normal, 28), (alarm, 28), (trip, 28)]:
            pdf.cell(width, 6, f" {val}", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_text_color(*scolor)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(18, 6, f" {status}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # -- Vibration Trend Table -------------------------------------------------
    pdf.section_header("4. VIBRATION TREND  -  DE BEARING (Last 10 Readings)")
    pdf.table_header([("Timestamp", 65), ("Vibration DE (mm/s)", 55), ("Status", 32), ("Logged By", 36)])
    trend = [
        ("16 Jul 2026  08:00",  "3.5",  "Normal"),
        ("16 Jul 2026  12:00",  "3.6",  "Normal"),
        ("16 Jul 2026  16:00",  "3.7",  "Normal"),
        ("16 Jul 2026  20:00",  "3.9",  "Normal"),
        ("17 Jul 2026  00:00",  "4.1",  "Normal"),
        ("17 Jul 2026  04:00",  "4.5",  "Normal"),
        ("17 Jul 2026  08:00",  "5.2",  "Monitor"),
        ("17 Jul 2026  12:00",  "5.9",  "Monitor"),
        ("17 Jul 2026  16:00",  "6.7",  "Warning"),
        ("20 Jul 2026  10:00",  "7.2",  "ALARM [!]"),
    ]
    operators = ["Auto", "Auto", "Auto", "Auto", "Auto", "Auto",
                 "R. Kumar", "R. Kumar", "A. Shah", "R. Kumar"]
    for i, ((ts, vib, st), op) in enumerate(zip(trend, operators)):
        color = RED if "ALARM" in st else (AMBER if st in ("Warning", "Monitor") else BLACK)
        pdf.set_fill_color(*(LIGHT if i % 2 == 0 else WHITE))
        pdf.set_font("Helvetica", "" if "ALARM" not in st else "B", 8)
        pdf.set_text_color(*BLACK)
        pdf.cell(65, 6, f" {ts}", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_text_color(*color)
        pdf.cell(55, 6, f" {vib}", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(32, 6, f" {st}", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_text_color(*BLACK)
        pdf.cell(36, 6, f" {op}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # -- Maintenance History ---------------------------------------------------
    pdf.add_page()
    pdf.section_header("5. MAINTENANCE HISTORY")
    pdf.table_header([("Work Order", 30), ("Date", 28), ("Type", 28), ("Description", 68), ("Technician", 34)])
    history = [
        ("MR-2026-012", "10 May 2026",  "Preventive",  "Biweekly lubrication + vibration check. Vib: 4.1 mm/s",   "R. Kumar"),
        ("MR-2026-008", "26 Apr 2026",  "Preventive",  "Biweekly lubrication. Vib: 3.8 mm/s. Slight upward trend", "A. Shah"),
        ("MR-2026-003", "22 Mar 2026",  "Preventive",  "Annual bearing inspect + alignment check. Clearance OK",   "A. Shah"),
        ("MR-2025-044", "15 Nov 2025",  "Preventive",  "Biweekly lubrication. All readings normal.",               "R. Kumar"),
        ("MR-2025-031", "02 Aug 2025",  "Preventive",  "Half-yearly inspection. No anomalies found.",              "P. Nair"),
        ("MR-OVERDUE",  "DUE 08 Jul",   "OVERDUE [!]",   "Biweekly lubrication  -  NOT PERFORMED. 12 days overdue",   "Unassigned"),
    ]
    for i, (wo, dt, typ, desc, tech) in enumerate(history):
        is_overdue = "OVERDUE" in typ
        color = RED if is_overdue else BLACK
        pdf.set_fill_color(*(LIGHT if i % 2 == 0 else WHITE))
        pdf.set_font("Helvetica", "B" if is_overdue else "", 8)
        pdf.set_text_color(*color)
        for val, width in [(wo, 30), (dt, 28), (typ, 28), (desc, 68), (tech, 34)]:
            pdf.cell(width, 6, f" {val}", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln()

    # -- Related Incidents -----------------------------------------------------
    pdf.section_header("6. INCIDENT HISTORY")
    pdf.table_header([("Incident ID", 30), ("Date", 24), ("Severity", 20), ("Description", 90), ("Downtime", 24)])
    incidents = [
        ("INC-2022-034", "14 Aug 2022", "HIGH",   "Bearing failure  -  vibration reached 8.7mm/s after lubrication overdue 15 days. DE bearing replaced.",  "12 hrs"),
        ("INC-2021-011", "22 Mar 2021", "MEDIUM", "Mechanical seal leakage detected during inspection. Replaced with John Crane Type-2 seal.",             "8 hrs"),
        ("INC-2020-005", "09 Jan 2020", "MEDIUM", "Discharge pressure drop due to impeller erosion. Replaced with Stellite-coated impeller.",             "20 hrs"),
    ]
    for i, (iid, dt, sev, desc, down) in enumerate(incidents):
        scolor = RED if sev == "HIGH" else AMBER
        pdf.set_fill_color(*(LIGHT if i % 2 == 0 else WHITE))
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*BLACK)
        pdf.cell(30, 6, f" {iid}", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(24, 6, f" {dt}", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_text_color(*scolor)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(20, 6, f" {sev}", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*BLACK)
        pdf.cell(90, 6, f" {desc}", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(24, 6, f" {down}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # -- OEM Key Warnings (what an OCR system would extract) -------------------
    pdf.section_header("7. OEM MANUAL EXCERPTS  (Flowserve PVXM-100, Rev 3.1)")
    excerpts = [
        ("Section 4.2  -  Vibration Analysis",
         "Alarm setpoint: 7.1 mm/s. Trip setpoint: 11.2 mm/s. If vibration exceeds alarm for more than\n"
         "2 continuous hours, initiate controlled shutdown. Sustained vibration above alarm without\n"
         "intervention typically results in bearing failure within 12 to 24 hours."),
        ("Section 4.3  -  Bearing Lubrication",
         "Relubricate drive-end and non-drive-end bearings every 14 days using SKF LGMT 2 grease,\n"
         "150 ml per bearing. Intervals exceeding 21 days risk lubricant hardening and inadequate\n"
         "film thickness, leading to premature bearing wear."),
        ("Section 6.1  -  High Vibration Troubleshooting",
         "Most common cause: bearing wear due to inadequate lubrication. Check lubrication date\n"
         "first. Secondary causes: shaft misalignment (check if >0.05 mm), coupling wear, cavitation\n"
         "(check NPSH margin and inlet strainer differential pressure), or unbalance."),
    ]
    for title, body in excerpts:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*DARK)
        pdf.cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 5, body)
        pdf.ln(2)

    # -- Compliance ------------------------------------------------------------
    pdf.section_header("8. COMPLIANCE STATUS")
    pdf.table_header([("Regulation", 60), ("Requirement", 90), ("Status", 38)])
    compliance = [
        ("OISD-117 Section 8.3",  "Vibration monitoring every 4 hrs for High Criticality equip.",      "VIOLATION [X]"),
        ("OISD-117 Section 8.3",  "Shutdown if vibration >alarm for >2 hours (or risk assessment)",    "ACTION REQUIRED"),
        ("SOP-P-001 Section 3.1", "Lubrication per 14-day schedule",                                    "OVERDUE [X]"),
        ("OISD-117 Section 9.1",  "Annual inspection completed",                                        "COMPLIANT [OK]"),
        ("Factory Act 1948",      "PTW system active for all maintenance work",                         "COMPLIANT [OK]"),
        ("ISO 10816-3",           "Vibration Zone D (>7.1 mm/s)  -  risk of damage if continued",        "ZONE D [!]"),
    ]
    for i, (reg, req, st) in enumerate(compliance):
        scolor = RED if "[X]" in st or "REQUIRED" in st else (AMBER if "[!]" in st or "OVERDUE" in st else GREEN)
        pdf.set_fill_color(*(LIGHT if i % 2 == 0 else WHITE))
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*BLACK)
        pdf.cell(60, 6, f" {reg}", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(90, 6, f" {req}", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_text_color(*scolor)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(38, 6, f" {st}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # -- Recommendations -------------------------------------------------------
    pdf.section_header("9. INSPECTOR RECOMMENDATIONS")
    recs = [
        ("IMMEDIATE",   "Initiate planned shutdown within 4 hours per OISD-117 Section 8.3 compliance window"),
        ("IMMEDIATE",   "Increase vibration monitoring to every 30 minutes until shutdown"),
        ("WITHIN 2 HRS","Issue PTW Class C (Mechanical/Rotating Equipment) and PTW LOTO"),
        ("WITHIN 2 HRS","Notify downstream equipment operators (HX-201, V-301) of planned shutdown"),
        ("MAINTENANCE", "Inspect and replace DE bearing assembly (SKF 6311  -  3 units in stock, Warehouse A)"),
        ("MAINTENANCE", "Perform overdue lubrication using SKF LGMT 2 grease, 150 ml per bearing"),
        ("MAINTENANCE", "Check coupling alignment after bearing replacement  -  limit 0.05 mm"),
        ("MONITORING",  "Install continuous vibration transmitter (current setup is manual rounds only)"),
    ]
    for i, (priority, rec) in enumerate(recs):
        pcolor = RED if priority == "IMMEDIATE" else (AMBER if "WITHIN" in priority else DARK)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*pcolor)
        pdf.cell(30, 6, f"  [{priority}]", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*BLACK)
        pdf.cell(0, 6, rec, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # -- Sign-off --------------------------------------------------------------
    pdf.ln(6)
    pdf.set_draw_color(*DARK)
    pdf.set_line_width(0.3)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*GREY)
    pdf.cell(90, 5, "Inspector: Rajesh Kumar  -  Senior Maintenance Technician", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(0, 5,  "Date: 20 July 2026  |  Report Ref: INS-P101-2026-07-20", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(90, 5, "Signature: ______________________________", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(0, 5,  "Next Inspection: 20 October 2026", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(output_path)
    print(f"PDF created: {output_path}")
    print(f"Size: {os.path.getsize(output_path):,} bytes")


if __name__ == "__main__":
    out = os.path.join(OUTPUT_DIR, "P101_Maintenance_Inspection_Report_2026.pdf")
    build_pdf(out)
