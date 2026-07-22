"""
Generate three sample industrial documents for the AI Operations Brain demo:
  1. CDU_Unit4_PID_Rev5.pdf       - P&ID Engineering Drawing (CDU Unit 4)
  2. P103_Commissioning_2026.pdf  - New equipment: Pump P-103 commissioning datasheet
  3. SOP_P003_Emergency_Shutdown.pdf - Safety SOP for rotating equipment ESD

Run: python generate_sample_docs.py
Output: sample_docs/
"""
import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_docs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Colour palette ──────────────────────────────────────────────────────────
AMBER = (245, 158, 11)
GREEN = (16, 185, 129)
RED   = (239, 68, 68)
BLUE  = (59, 130, 246)
DARK  = (20, 20, 30)
GREY  = (110, 110, 110)
LGREY = (200, 200, 200)
LIGHT = (240, 240, 240)
WHITE = (255, 255, 255)
BLACK = (15, 15, 15)

def s(text: str) -> str:
    """Sanitise to Latin-1 so fpdf core fonts never raise."""
    return (text
        .replace("\u2014", " - ").replace("\u2013", " - ")
        .replace("\u2018", "'").replace("\u2019", "'")
        .replace("\u201c", '"').replace("\u201d", '"')
        .replace("\u00b0", " deg ").replace("\u2022", "*")
        .encode("latin-1", errors="replace").decode("latin-1"))


# ════════════════════════════════════════════════════════════════════════════
# BASE CLASS
# ════════════════════════════════════════════════════════════════════════════

class DocBase(FPDF):
    _doc_title = "DOCUMENT"

    def header(self):
        self.set_fill_color(*DARK)
        self.rect(0, 0, 210, 18, "F")
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*AMBER)
        self.set_xy(8, 4)
        self.cell(0, 10, s(f"AI OPERATIONS BRAIN  |  {self._doc_title}"))

    def footer(self):
        self.set_y(-14)
        self.set_fill_color(*DARK)
        self.rect(0, self.get_y(), 210, 14, "F")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*AMBER)
        self.cell(0, 10, s(f"CONFIDENTIAL  -  CDU Unit 4  -  Page {self.page_no()}"), align="C")

    def section(self, title: str):
        self.ln(4)
        self.set_fill_color(*DARK)
        self.set_text_color(*AMBER)
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 7, s(f"  {title}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.ln(2)

    def kv(self, key: str, val: str, vcol=None):
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(58, 5, s(key), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*(vcol or BLACK))
        self.cell(0, 5, s(val), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def th(self, cols):
        self.set_fill_color(*DARK)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 7)
        for lbl, w in cols:
            self.cell(w, 6, s(f" {lbl}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.ln()

    def tr(self, cells, alt=False, tcol=None):
        self.set_fill_color(*(LIGHT if alt else WHITE))
        self.set_text_color(*(tcol or BLACK))
        self.set_font("Helvetica", "", 7)
        for val, w in cells:
            self.cell(w, 5, s(f" {val}"), fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.ln()

    def flag(self, text: str, color=AMBER):
        self.set_fill_color(*color)
        self.rect(self.l_margin, self.get_y(), 3, 7, "F")
        self.set_x(self.l_margin + 5)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*BLACK)
        self.cell(0, 7, s(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def title_block(self, title: str, subtitle: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*DARK)
        self.cell(0, 9, s(title), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*GREY)
        self.cell(0, 5, s(subtitle), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)
        self.set_draw_color(*AMBER)
        self.set_line_width(0.7)
        self.line(12, self.get_y(), 198, self.get_y())
        self.ln(4)


# ════════════════════════════════════════════════════════════════════════════
# DOC 1 — P&ID Engineering Drawing: CDU Unit 4
# ════════════════════════════════════════════════════════════════════════════

class PIDDoc(DocBase):
    _doc_title = "P&ID ENGINEERING DRAWING  -  CDU UNIT 4  -  PID-CDU-001-Rev5"


def build_pid(out: str):
    pdf = PIDDoc("L", "mm", "A4")  # Landscape for drawing
    pdf.set_margins(12, 22, 12)
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    pdf.title_block(
        "PIPING & INSTRUMENTATION DIAGRAM",
        "CDU Unit 4 - Crude Distillation Unit Feed Section  |  Drawing No: PID-CDU-001  |  Rev 5  |  Date: 20 Jul 2026",
    )

    # ── Revision history table ──────────────────────────────────────────────
    pdf.section("REVISION HISTORY")
    pdf.th([("Rev", 12), ("Date", 28), ("Description", 120), ("Prepared", 28), ("Approved", 29)])
    revs = [
        ("1", "12 Mar 2018", "Initial issue - plant construction", "J. Mehta",    "S. Venkataraman"),
        ("2", "09 Jan 2020", "Added Y-strainer ST-101 on P-101 suction after impeller erosion INC-2020-005", "R. Kumar", "S. Venkataraman"),
        ("3", "22 Mar 2021", "Updated seal flush piping Plan 11 - upgraded to John Crane 8B-1 after INC-2021-011", "A. Shah", "P. Nair"),
        ("4", "15 Aug 2022", "Added vibration transmitters VT-101A/B after bearing failure INC-2022-034", "R. Kumar", "S. Venkataraman"),
        ("5", "20 Jul 2026", "Added Pump P-103 (spare/standby for P-101) and updated instrument loop", "R. Kumar", "S. Venkataraman"),
    ]
    for i, row in enumerate(revs):
        pdf.tr(list(zip(row, [12, 28, 120, 28, 29])), alt=(i % 2 == 0), tcol=AMBER if row[0] == "5" else None)

    pdf.ln(4)

    # ── Process Flow Description ────────────────────────────────────────────
    pdf.section("PROCESS FLOW DESCRIPTION")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*BLACK)
    pdf.multi_cell(0, 5, s(
        "Crude oil from storage tank T-001 is pumped by centrifugal pump P-101 (duty) or P-103 (standby) "
        "through the feed pre-heater HX-201 (shell and tube, crude on tube side) then into the feed surge drum V-301. "
        "The surge drum provides 15 minutes of liquid inventory and feeds the crude distillation column. "
        "All rotating equipment is monitored per OISD-117 requirements with vibration transmitters, "
        "pressure transmitters, and flow transmitters feeding the DCS (Honeywell Experion PKS)."
    ))
    pdf.ln(4)

    # ── Equipment List ──────────────────────────────────────────────────────
    pdf.section("EQUIPMENT LIST")
    pdf.th([("Tag", 18), ("Description", 60), ("Type", 40), ("Design P (bar)", 25),
            ("Design T (degC)", 28), ("Capacity", 30), ("MOC", 22), ("Status", 14)])
    equip = [
        ("T-001",  "Crude Oil Storage Tank",       "Fixed Roof Tank",         "Atm",   "60",    "5000 m3",   "CS",  "Normal"),
        ("P-101",  "Crude Oil Feed Pump (Duty)",   "Centrifugal API 610 BB1", "8.5",   "120",   "250 m3/hr", "CS",  "ALARM"),
        ("P-103",  "Crude Oil Feed Pump (Standby)","Centrifugal API 610 BB1", "8.5",   "120",   "250 m3/hr", "CS",  "Standby"),
        ("ST-101", "Suction Strainer P-101/103",   "Y-Strainer, 100 mesh",    "8.5",   "120",   "350 m3/hr", "SS",  "Normal"),
        ("HX-201", "Crude Feed Pre-heater",        "Shell & Tube, 1-2 pass",  "12.0",  "200",   "250 m3/hr", "CS",  "Normal"),
        ("V-301",  "Crude Feed Surge Drum",        "Horiz. Drum with demist", "6.0",   "180",   "15 min",    "CS",  "Normal"),
        ("PSV-101","P-101 Discharge PSV",          "Spring loaded, API 526",  "10.2",  "130",   "300 m3/hr", "SS",  "Normal"),
        ("MOV-101A","P-101 Suction Block Valve",   "Motor-operated gate",     "8.5",   "120",   "10\" 300#", "CS",  "Open"),
        ("MOV-101B","P-101 Discharge Block Valve", "Motor-operated gate",     "8.5",   "120",   "8\" 300#",  "CS",  "Open"),
        ("MOV-103A","P-103 Suction Block Valve",   "Motor-operated gate",     "8.5",   "120",   "10\" 300#", "CS",  "Closed"),
        ("MOV-103B","P-103 Discharge Block Valve", "Motor-operated gate",     "8.5",   "120",   "8\" 300#",  "CS",  "Closed"),
    ]
    for i, row in enumerate(equip):
        tcol = RED if row[7] == "ALARM" else (AMBER if row[7] == "Standby" else BLACK)
        cells = list(zip(row, [18, 60, 40, 25, 28, 30, 22, 14]))
        pdf.tr(cells, alt=(i % 2 == 0), tcol=tcol)

    # ── Instrument List ─────────────────────────────────────────────────────
    pdf.section("INSTRUMENT & CONTROL LIST")
    pdf.th([("Tag", 18), ("Description", 68), ("Type", 40), ("Range", 28), ("Alarm Lo", 22),
            ("Alarm Hi", 22), ("Trip Hi", 22), ("Location", 17)])
    instruments = [
        ("FT-101",  "P-101 Suction Flow Transmitter",    "Coriolis, 4-20 mA",  "0-400 m3/hr", "-",     "350",  "380",  "Field"),
        ("PT-101",  "P-101 Discharge Pressure",          "Piezo, 4-20 mA",     "0-16 bar",    "5.0",   "9.5",  "10.5", "Field"),
        ("PT-102",  "P-101 Suction Pressure",            "Piezo, 4-20 mA",     "0-6 bar",     "0.5",   "-",    "-",    "Field"),
        ("TT-101",  "P-101 DE Bearing Temperature",      "RTD Pt100",          "0-150 degC",  "-",     "75",   "90",   "Field"),
        ("TT-102",  "P-101 NDE Bearing Temperature",     "RTD Pt100",          "0-150 degC",  "-",     "75",   "90",   "Field"),
        ("VT-101A", "P-101 DE Bearing Vibration",        "Proximity probe",    "0-25 mm/s",   "-",     "7.1",  "11.2", "Field"),
        ("VT-101B", "P-101 NDE Bearing Vibration",       "Proximity probe",    "0-25 mm/s",   "-",     "7.1",  "11.2", "Field"),
        ("TT-103",  "P-103 DE Bearing Temperature",      "RTD Pt100",          "0-150 degC",  "-",     "75",   "90",   "Field"),
        ("VT-103A", "P-103 DE Bearing Vibration",        "Proximity probe",    "0-25 mm/s",   "-",     "7.1",  "11.2", "Field"),
        ("LT-301",  "V-301 Level Transmitter",           "DP type, 4-20 mA",   "0-3000 mm",   "300",   "2500", "-",    "Field"),
        ("TT-301",  "V-301 Outlet Temperature",          "RTD Pt100",          "0-250 degC",  "50",    "175",  "195",  "Field"),
        ("DPDP-101","ST-101 Strainer Differential Press","DP Cell, 4-20 mA",   "0-2 bar",     "-",     "0.8",  "1.2",  "Field"),
    ]
    for i, row in enumerate(instruments):
        pdf.tr(list(zip(row, [18, 68, 40, 28, 22, 22, 22, 17])), alt=(i % 2 == 0))

    pdf.add_page()

    # ── Process Flow Diagram (ASCII-art style box drawing) ───────────────────
    pdf.section("PROCESS FLOW SCHEMATIC (Simplified)")

    # Draw a simplified PFD using fpdf2 rectangles and lines
    Y0 = pdf.get_y() + 2
    LM = 12

    def box(x, y, w, h, label, tag, color=DARK, tcolor=WHITE):
        pdf.set_fill_color(*color)
        pdf.set_draw_color(*AMBER)
        pdf.set_line_width(0.4)
        pdf.rect(x, y, w, h, "FD")
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*tcolor)
        pdf.set_xy(x, y + h/2 - 4)
        pdf.cell(w, 4, s(tag), align="C")
        pdf.set_font("Helvetica", "", 6)
        pdf.set_xy(x, y + h/2)
        pdf.cell(w, 4, s(label), align="C")

    def arrow(x1, y, x2):
        pdf.set_draw_color(*AMBER)
        pdf.set_line_width(0.5)
        pdf.line(x1, y, x2, y)
        # arrowhead
        pdf.line(x2, y, x2-2, y-1)
        pdf.line(x2, y, x2-2, y+1)

    def label_pipe(x, y, txt, color=GREY):
        pdf.set_font("Helvetica", "", 5)
        pdf.set_text_color(*color)
        pdf.set_xy(x, y-4)
        pdf.cell(20, 4, s(txt))

    # Equipment boxes
    bh, bw = 16, 28
    row1y = Y0 + 10

    box(LM + 0,   row1y, bw, bh, "Crude Oil",     "T-001",   DARK)
    arrow(LM + 28, row1y + bh/2, LM + 40)
    box(LM + 40,  row1y, 12, bh, "ST-101",        "Strainer", (40,40,60))
    arrow(LM + 52, row1y + bh/2, LM + 60)

    # P-101 (duty) - highlighted in amber due to ALARM
    box(LM + 60,  row1y - 14, bw, bh, "P-101 [ALARM]", "Duty Pump", AMBER, BLACK)
    # P-103 (standby)
    box(LM + 60,  row1y + 6,  bw, bh, "P-103 [Standby]", "Standby Pump", (40,40,60))

    # Connect both pumps to discharge header
    pdf.set_draw_color(*AMBER)
    pdf.line(LM + 88, row1y - 6,   LM + 96, row1y - 6)   # P-101 outlet
    pdf.line(LM + 88, row1y + 14,  LM + 96, row1y + 14)  # P-103 outlet
    pdf.line(LM + 96, row1y - 6,   LM + 96, row1y + 14)  # vertical combine
    arrow(LM + 96, row1y + 4, LM + 106)

    box(LM + 106, row1y - 4, bw, bh, "Feed Pre-heater", "HX-201")
    arrow(LM + 134, row1y + bh/2 - 4, LM + 148)
    box(LM + 148, row1y - 4, bw, bh, "Surge Drum",   "V-301")
    arrow(LM + 176, row1y + bh/2 - 4, LM + 190)
    box(LM + 190, row1y - 4, 25, bh, "CDU Column",   "T-201")

    # Pipe labels
    label_pipe(LM + 30, row1y + bh/2 - 2, '10"-CS-1001')
    label_pipe(LM + 63, row1y - 14, '8"-CS-1002')
    label_pipe(LM + 98, row1y + 3,  '8"-CS-1003')
    label_pipe(LM + 136,row1y + bh/2 - 4, '8"-CS-1004')

    # Instrument tags
    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(*GREEN)
    tags = [
        (LM + 66, row1y - 26, "VT-101A"),
        (LM + 72, row1y - 26, "VT-101B"),
        (LM + 78, row1y - 26, "TT-101"),
        (LM + 105, row1y - 18, "PT-101"),
        (LM + 45,  row1y - 12, "FT-101"),
    ]
    for tx, ty, tag in tags:
        pdf.set_xy(tx - 2, ty)
        pdf.cell(14, 4, s(tag))
        pdf.set_draw_color(*GREEN)
        pdf.set_line_width(0.2)
        pdf.line(tx + 4, ty + 4, tx + 4, row1y - 2)

    # Legend
    ly = row1y + bh + 24
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(*DARK)
    pdf.set_xy(LM, ly)
    pdf.cell(0, 5, "LEGEND:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    legend_items = [
        (AMBER,    "Equipment in ALARM / at-risk state"),
        (DARK,     "Normal operating equipment"),
        ((40,40,60), "Standby equipment"),
        (GREEN,    "Instrumentation signal to DCS"),
    ]
    for color, label in legend_items:
        pdf.set_fill_color(*color)
        pdf.rect(pdf.l_margin, pdf.get_y() + 1, 8, 4, "F")
        pdf.set_xy(pdf.l_margin + 10, pdf.get_y())
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*BLACK)
        pdf.cell(60, 5, s(label), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ── Safety Notes ────────────────────────────────────────────────────────
    pdf.ln(4)
    pdf.section("SAFETY NOTES AND HAZARD IDENTIFICATION")
    notes = [
        ("HIGH", "P-101 vibration currently in ALARM (7.2 mm/s > 7.1 alarm). OISD-117 Sec 8.3 requires shutdown within 2 hours."),
        ("HIGH", "Crude oil service: Class IIA flammable liquid. Hot work requires PTW Class B. All ignition sources to be eliminated within 15m."),
        ("MED",  "PSV-101 set at 10.2 bar. Do not dead-head P-101 or P-103. Minimum flow bypass MOV-101C to be open at all times."),
        ("MED",  "V-301 operates at 4.5 bar, 160 degC. Vessel inspection certificate valid until Jan 2028. Insulated."),
        ("LOW",  "ST-101 strainer differential pressure > 0.8 bar triggers maintenance alarm. Strainer to be cleaned during next pump switch."),
    ]
    for sev, note in notes:
        scolor = RED if sev == "HIGH" else (AMBER if sev == "MED" else GREY)
        pdf.flag(f"[{sev}]  {note}", color=scolor)

    # ── Title block (engineering drawing standard) ──────────────────────────
    pdf.ln(4)
    pdf.set_draw_color(*DARK)
    pdf.set_line_width(0.3)
    tb_y = pdf.get_y()
    pdf.rect(12, tb_y, 263, 28, "D")
    pdf.line(12, tb_y + 9, 275, tb_y + 9)
    pdf.line(120, tb_y, 120, tb_y + 28)
    pdf.line(190, tb_y, 190, tb_y + 28)

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*DARK)
    for x, y, t in [
        (13, tb_y + 1, "PROJECT:"),
        (13, tb_y + 10, "DRAWING TITLE:"),
        (121, tb_y + 1, "PLANT:"),
        (121, tb_y + 10, "AREA:"),
        (191, tb_y + 1, "DRG NO:"),
        (191, tb_y + 10, "REV:"),
    ]:
        pdf.set_xy(x, y)
        pdf.cell(40, 4, t)

    pdf.set_font("Helvetica", "", 8)
    for x, y, t in [
        (13,  tb_y + 5,  "Crude Distillation Unit Expansion"),
        (13,  tb_y + 14, "Crude Feed Section - P-101/P-103/HX-201/V-301"),
        (121, tb_y + 5,  "Refinery Complex - Site A"),
        (121, tb_y + 14, "CDU Unit 4, Pump House A"),
        (191, tb_y + 5,  "PID-CDU-001"),
        (191, tb_y + 14, "Rev 5 - 20 Jul 2026"),
        (191, tb_y + 19, "Approved: S. Venkataraman"),
    ]:
        pdf.set_xy(x, y)
        pdf.cell(70, 4, s(t))

    pdf.output(out)
    print(f"[1] P&ID: {out}  ({os.path.getsize(out):,} bytes)")


# ════════════════════════════════════════════════════════════════════════════
# DOC 2 — New Equipment: Pump P-103 Commissioning Datasheet
# ════════════════════════════════════════════════════════════════════════════

class CommissionDoc(DocBase):
    _doc_title = "EQUIPMENT COMMISSIONING DATASHEET  -  PUMP P-103  -  NEW INSTALLATION"


def build_commissioning(out: str):
    pdf = CommissionDoc()
    pdf.set_margins(12, 22, 12)
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    pdf.title_block(
        "EQUIPMENT COMMISSIONING DATASHEET",
        "Pump P-103  -  Crude Oil Feed Pump (Standby)  -  CDU Unit 4  |  Commissioned: 18 July 2026",
    )

    pdf.flag("[NEW EQUIPMENT]  P-103 installed as standby for P-101. Knowledge graph update required.", color=GREEN)
    pdf.flag("[BASELINE]  Vibration and temperature baselines recorded during first run. All within normal.", color=GREEN)

    # ── Equipment Identity ────────────────────────────────────────────────
    pdf.section("1. EQUIPMENT IDENTITY")
    identity = [
        ("New Equipment Tag",    "P-103"),
        ("Equipment Name",       "Crude Oil Feed Pump - Standby"),
        ("P&ID Drawing",         "PID-CDU-001 Rev 5"),
        ("Equipment Class",      "Centrifugal Pump - API 610 Type BB1"),
        ("Service",              "Crude oil transfer T-001 to HX-201 (standby for P-101)"),
        ("Location",             "CDU Unit 4, Pump House A, Bay 3 (adjacent to P-101)"),
        ("Manufacturer",         "Flowserve Corporation"),
        ("Model",                "PVXM-100 (identical to P-101 for interchangeability)"),
        ("Serial Number",        "FS-2026-8851"),
        ("Purchase Order",       "PO-2025-0342  -  Ordered 14 Nov 2025"),
        ("Arrival at Site",      "02 June 2026"),
        ("Mechanical Completion","10 July 2026"),
        ("Pre-commissioning",    "14 July 2026  -  Completed by R. Kumar, A. Shah"),
        ("First Run / Wet Commissioning", "18 July 2026  -  Witnessed by S. Venkataraman"),
        ("Handed Over to Ops",   "20 July 2026  -  Asset registered in CMMS"),
        ("Criticality Rating",   "HIGH  -  Standby for critical duty pump P-101"),
        ("Insurance Spare",      "YES  -  P-101 has no other standby; P-103 is critical safety spare"),
    ]
    for k, v in identity:
        pdf.kv(k, v, vcol=GREEN if k == "New Equipment Tag" else None)

    # ── Design Specifications ─────────────────────────────────────────────
    pdf.section("2. DESIGN SPECIFICATIONS")
    pdf.th([("Parameter", 65), ("Design Value", 45), ("Unit", 30), ("Test Value", 40), ("Pass/Fail", 18)])
    specs = [
        ("Rated Flow at BEP",             "250",      "m3/hr",       "252",       "PASS"),
        ("Rated Differential Head",       "85",       "m",           "86.2",      "PASS"),
        ("Motor Power (installed)",       "75",       "kW",          "71.3",      "PASS"),
        ("Rated Speed",                   "2960",     "RPM",         "2958",      "PASS"),
        ("Design Pressure",               "8.5",      "bar",         "Tested 12.8","PASS"),
        ("Hydraulic Test Pressure",       "12.8",     "bar",         "Held 30min","PASS"),
        ("Min. Continuous Stable Flow",   "85",       "m3/hr",       "87",        "PASS"),
        ("NPSHR at rated flow",           "3.2",      "m",           "3.0",       "PASS"),
        ("Pump Efficiency at BEP",        "82",       "%",           "82.5",      "PASS"),
        ("Max Allowable Working Pressure","10.5",     "bar",         "-",         "Design"),
        ("Operating Temperature Range",   "-20 to 120","degC",       "-",         "Design"),
        ("Mechanical Seal Type",          "Type 2 Plan 11","John Crane 8B-1", "-","Design"),
        ("Bearing Type DE/NDE",           "SKF 6311", "-",           "-",         "Design"),
        ("Bearing Lubrication Interval",  "14",       "days",        "-",         "Design"),
        ("Coupling Type",                 "Flexible disc","RWB-100", "-",         "Design"),
        ("Material of Construction",      "Carbon Steel","ASTM A216 WCB","-",     "Design"),
        ("Impeller Material",             "Stellite coated","316 SS substrate","-","Design"),
    ]
    for i, row in enumerate(specs):
        tcol = GREEN if row[4] == "PASS" else (AMBER if row[4] == "Design" else RED)
        pdf.tr(list(zip(row, [65, 45, 30, 40, 18])), alt=(i % 2 == 0), tcol=tcol)

    # ── Commissioning Baseline Readings ──────────────────────────────────
    pdf.section("3. COMMISSIONING BASELINE READINGS (18 July 2026 - First Run)")
    pdf.th([("Parameter", 72), ("Value", 28), ("Unit", 22), ("Normal Range", 30),
            ("Alarm Setpoint", 28), ("Status", 18)])
    baseline = [
        ("Vibration - DE Bearing (radial)",  "2.1",  "mm/s",  "< 4.5",  "7.1",    "NORMAL"),
        ("Vibration - NDE Bearing (radial)", "1.9",  "mm/s",  "< 4.5",  "7.1",    "NORMAL"),
        ("Bearing Temperature - DE",         "43",   "degC",  "< 55",   "75",     "NORMAL"),
        ("Bearing Temperature - NDE",        "41",   "degC",  "< 55",   "75",     "NORMAL"),
        ("Discharge Pressure",               "8.6",  "bar",   "8.5+/-0.3","9.5",  "NORMAL"),
        ("Suction Pressure",                 "1.2",  "bar",   "0.8-1.5","0.5 lo", "NORMAL"),
        ("Flow Rate",                        "249",  "m3/hr", "235-265","350 hi",  "NORMAL"),
        ("Motor Current",                    "44.1", "A",     "40-48",  "-",      "NORMAL"),
        ("Seal Chamber Pressure (Plan 11)",  "2.1",  "bar",   "> 1.5",  "< 1.0",  "NORMAL"),
        ("Noise Level at 1m",                "78",   "dB(A)", "< 85",   "90",     "NORMAL"),
    ]
    for i, row in enumerate(baseline):
        pdf.tr(list(zip(row, [72, 28, 22, 30, 28, 18])), alt=(i % 2 == 0), tcol=GREEN)

    pdf.add_page()

    # ── Pre-commissioning Checklist ───────────────────────────────────────
    pdf.section("4. PRE-COMMISSIONING CHECKLIST")
    pdf.th([("No.", 10), ("Check Item", 120), ("Method", 40), ("By", 22), ("Date", 22), ("Result", 14)])
    checks = [
        ("1",  "Pump aligned to motor (cold alignment) - laser method", "Laser align",  "A. Shah",  "14 Jul", "PASS"),
        ("2",  "Coupling guard installed and secure",                   "Visual",        "A. Shah",  "14 Jul", "PASS"),
        ("3",  "All instrument connections made and tagged",            "Visual + loop", "R. Kumar", "14 Jul", "PASS"),
        ("4",  "MOV-103A/B functional test - full open/close cycle",   "Operate/DCS",   "R. Kumar", "15 Jul", "PASS"),
        ("5",  "Motor rotation check (jog test - correct direction)",  "Jog test",      "A. Shah",  "15 Jul", "PASS"),
        ("6",  "Suction strainer ST-101 cleaned before first run",     "Physical",      "A. Shah",  "15 Jul", "PASS"),
        ("7",  "Seal flush Plan 11 lines open and flow confirmed",     "Visual flow",   "R. Kumar", "16 Jul", "PASS"),
        ("8",  "Pump casing and suction line vented and primed",       "Physical",      "R. Kumar", "16 Jul", "PASS"),
        ("9",  "Initial bearing lubrication - 150ml SKF LGMT2 each",  "Grease gun",    "A. Shah",  "16 Jul", "PASS"),
        ("10", "DCS alarms configured and tested (VT/TT/PT setpoints)","DCS test",      "DCS Eng",  "17 Jul", "PASS"),
        ("11", "Witness run - 4 hours continuous operation",           "Witnessed",     "S.Venkat", "18 Jul", "PASS"),
        ("12", "Post-run vibration and temperature readings recorded", "Instruments",   "R. Kumar", "18 Jul", "PASS"),
        ("13", "CMMS asset card created and maintenance schedule set", "CMMS (SAP)",    "Maint Eng","20 Jul", "PASS"),
        ("14", "Spare parts (2x bearings, 1x seal) confirmed in WH",  "Stock check",   "Stores",   "20 Jul", "PASS"),
        ("15", "Knowledge graph / AI Operations Brain update required","AI System",     "PENDING",  "PENDING","OPEN"),
    ]
    for i, row in enumerate(checks):
        tcol = GREEN if row[5] == "PASS" else (AMBER if row[5] == "OPEN" else RED)
        pdf.tr(list(zip(row, [10, 120, 40, 22, 22, 14])), alt=(i % 2 == 0), tcol=tcol)

    # ── Spare Parts Registered ────────────────────────────────────────────
    pdf.section("5. SPARE PARTS REGISTERED IN WAREHOUSE")
    pdf.th([("Part Number", 35), ("Description", 80), ("Qty", 12), ("Location", 40), ("Lead Time", 28)])
    parts = [
        ("SKF-6311-2RS",  "Drive-end and Non-drive-end Bearing (identical to P-101)",  "2", "WH-A Rack 4 Bin 12", "7 days"),
        ("JC-8B1-55MM",   "John Crane 8B-1 Mechanical Seal (identical to P-101)",      "1", "WH-A Rack 6 Bin 3",  "14 days"),
        ("RWB-100",       "Flexible Disc Coupling Insert (identical to P-101)",         "2", "WH-A Rack 5 Bin 7",  "5 days"),
        ("SKF-LGMT2-0.4", "Grease Cartridge 400g (shared with P-101, K-401)",          "12","WH-A Rack 2 Bin 1",  "3 days"),
        ("IMP-PVXM-ST",   "Stellite-coated Impeller (P-101/P-103 identical)",          "1", "WH-A Rack 8 Bin 2",  "21 days"),
    ]
    for i, row in enumerate(parts):
        pdf.tr(list(zip(row, [35, 80, 12, 40, 28])), alt=(i % 2 == 0))

    # ── Maintenance Schedule ──────────────────────────────────────────────
    pdf.section("6. PREVENTIVE MAINTENANCE SCHEDULE (NEW)")
    pdf.th([("Task", 85), ("Frequency", 25), ("Next Due", 28), ("Est. Time", 22),
            ("Assigned To", 28), ("WO Type", 18)])
    schedule = [
        ("Bearing lubrication (150 ml SKF LGMT2 per bearing)",     "14 days",   "01 Aug 2026",  "1 hr",  "R. Kumar",  "PM"),
        ("Vibration check and trend log (during standby run)",      "14 days",   "01 Aug 2026",  "30 min","A. Shah",   "PM"),
        ("Seal chamber pressure check",                             "Monthly",   "18 Aug 2026",  "30 min","R. Kumar",  "PM"),
        ("Motor insulation resistance test",                        "6 months",  "18 Jan 2027",  "2 hrs", "Electrical","PM"),
        ("Full mechanical overhaul (bearing/seal replacement)",     "3 years",   "18 Jul 2029",  "24 hrs","R. Kumar",  "Overhaul"),
        ("Coupling alignment check",                                "6 months",  "18 Jan 2027",  "2 hrs", "A. Shah",   "PM"),
        ("ST-101 strainer cleaning",                                "6 months",  "18 Jan 2027",  "4 hrs", "A. Shah",   "PM"),
        ("Standby run (30 min on-load test to verify readiness)",   "Monthly",   "18 Aug 2026",  "1 hr",  "R. Kumar",  "PM"),
    ]
    for i, row in enumerate(schedule):
        pdf.tr(list(zip(row, [85, 25, 28, 22, 28, 18])), alt=(i % 2 == 0))

    # ── Sign-off ──────────────────────────────────────────────────────────
    pdf.ln(6)
    pdf.set_draw_color(*DARK)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*GREY)
    pdf.cell(95, 5, "Commissioned by: Rajesh Kumar  -  Sr. Maintenance Technician")
    pdf.cell(0,  5, "Date: 18 July 2026  |  Doc Ref: COMM-P103-2026-07-18",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(95, 5, "Witnessed by: S. Venkataraman  -  Operations Supervisor")
    pdf.cell(0,  5, "CMMS Asset Tag: P-103  |  SAP PM Order: 4500001234",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(out)
    print(f"[2] Commissioning: {out}  ({os.path.getsize(out):,} bytes)")


# ════════════════════════════════════════════════════════════════════════════
# DOC 3 — SOP: Emergency Shutdown Procedure for Rotating Equipment
# ════════════════════════════════════════════════════════════════════════════

class SOPDoc(DocBase):
    _doc_title = "SOP-P003 REV 3  -  EMERGENCY SHUTDOWN - ROTATING EQUIPMENT"


def build_sop(out: str):
    pdf = SOPDoc()
    pdf.set_margins(12, 22, 12)
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()

    pdf.title_block(
        "STANDARD OPERATING PROCEDURE",
        "SOP-P003 Rev 3  -  Emergency Shutdown of Rotating Equipment (Pumps & Compressors)  |  CDU Unit 4",
    )

    pdf.flag("[SAFETY CRITICAL]  This SOP is MANDATORY for all vibration/temperature alarm conditions. Failure to follow = OISD-117 violation.", color=RED)
    pdf.flag("Applies to: P-101, P-103, P-202, K-401 and all API 610 pumps in CDU Unit 4", color=AMBER)

    # ── Document Control ──────────────────────────────────────────────────
    pdf.section("DOCUMENT CONTROL")
    control = [
        ("SOP Number",        "SOP-P003"),
        ("Title",             "Emergency Shutdown - Rotating Equipment"),
        ("Revision",          "3  (supersedes Rev 2 dated 15 Jan 2025)"),
        ("Effective Date",    "20 July 2026"),
        ("Review Date",       "20 July 2027"),
        ("Prepared By",       "Rajesh Kumar - Sr. Maintenance Technician"),
        ("Reviewed By",       "Priya Nair - Inspection Engineer"),
        ("Approved By",       "S. Venkataraman - Operations Supervisor"),
        ("Applicability",     "CDU Unit 4 - all rotating equipment"),
        ("Reason for Rev 3",  "Updated P-103 commissioning details and added standby pump switchover procedure"),
    ]
    for k, v in control:
        pdf.kv(k, v)

    # ── Trigger Conditions ────────────────────────────────────────────────
    pdf.section("1. TRIGGER CONDITIONS FOR EMERGENCY SHUTDOWN")
    pdf.th([("Condition", 80), ("Setpoint", 32), ("Equipment", 35), ("Response Time", 28), ("Authority", 23)])
    triggers = [
        ("Vibration exceeds ALARM setpoint",          "> 7.1 mm/s",   "P-101, P-103, P-202", "Within 4 hrs",   "Supervisor"),
        ("Vibration exceeds ALARM for > 2 hours",     "> 7.1 mm/s",   "All pumps",           "IMMEDIATE",      "Operator"),
        ("Vibration exceeds TRIP setpoint",           "> 11.2 mm/s",  "All pumps",           "AUTO / IMMEDIATE","DCS/Operator"),
        ("Bearing temperature exceeds ALARM",         "> 75 degC",    "All pumps",           "Within 1 hr",    "Supervisor"),
        ("Bearing temperature exceeds TRIP",          "> 90 degC",    "All pumps",           "AUTO / IMMEDIATE","DCS/Operator"),
        ("Mechanical seal leakage detected",          "Visible leak", "P-101, P-103",        "Within 30 min",  "Operator"),
        ("Unusual noise or smoke",                    "Audible",      "All equipment",        "IMMEDIATE",      "Operator"),
        ("Process fluid leak at pump flange",         "Any leak",     "All pumps",           "IMMEDIATE",      "Operator"),
        ("Fire/gas alarm in pump house area",         "Any alarm",    "All equipment",        "IMMEDIATE",      "Control Room"),
        ("Operator observation - unsafe condition",   "Judgment",     "All equipment",        "IMMEDIATE",      "Operator"),
    ]
    for i, row in enumerate(triggers):
        tcol = RED if "IMMEDIATE" in row[3] or "AUTO" in row[3] else (AMBER if "1 hr" in row[3] or "30 min" in row[3] else BLACK)
        pdf.tr(list(zip(row, [80, 32, 35, 28, 23])), alt=(i % 2 == 0), tcol=tcol)

    # ── Step-by-step ESD for Vibration Alarm ─────────────────────────────
    pdf.section("2. EMERGENCY SHUTDOWN PROCEDURE - VIBRATION ALARM (Step by Step)")
    pdf.flag("[P-101 CURRENT STATUS]  Vibration 7.2 mm/s > ALARM 7.1 mm/s. This procedure is ACTIVE.", color=RED)

    steps = [
        ("STEP 1", "NOTIFY SUPERVISOR",
         "Immediately notify Shift Supervisor S. Venkataraman (ext. 4500) and Maintenance Lead "
         "Rajesh Kumar (ext. 4512). State equipment tag, current vibration reading, and duration above alarm. "
         "Do NOT wait. Notification within 5 minutes of alarm is required by OISD-117 Sec 10.2."),
        ("STEP 2", "INCREASE MONITORING FREQUENCY",
         "Increase vibration monitoring rounds from every 4 hours to every 30 minutes. "
         "Log all readings in CMMS with timestamp. If vibration trend is still increasing, "
         "escalate immediately to Step 4 (shutdown) regardless of time remaining."),
        ("STEP 3", "PREPARE STANDBY PUMP P-103",
         "Verify P-103 is ready for service: check MOV-103A/B in CLOSED position, "
         "verify seal flush pressure on P-103 (Plan 11 > 1.5 bar), confirm bearing lubrication "
         "date is within 14 days, verify DCS alarms for P-103 are active. "
         "Estimated preparation time: 15 minutes."),
        ("STEP 4", "INITIATE CONTROLLED PUMP SWITCHOVER",
         "a) Slowly open P-103 suction MOV-103A from DCS  "
         "b) Start P-103 motor from DCS  "
         "c) Confirm P-103 discharge pressure and flow establish (allow 60 seconds)  "
         "d) Slowly close P-101 discharge MOV-101B (throttle over 2 minutes to avoid hammer)  "
         "e) Once P-103 carries full flow, close P-101 suction MOV-101A  "
         "f) Allow P-101 to coast to stop naturally - DO NOT brake."),
        ("STEP 5", "ISSUE PERMIT TO WORK",
         "Issue PTW Class C (Mechanical/Rotating Equipment) for P-101 maintenance work. "
         "Obtain LOTO (Lockout/Tagout) on P-101 motor isolator and on MOV-101A, MOV-101B. "
         "Verify zero energy state before any mechanical work begins. "
         "Hot work (welding, grinding) requires additional PTW Class B."),
        ("STEP 6", "CONFIRM SAFE STATE",
         "Verify: P-101 at rest (zero rotation), MOV-101A closed, MOV-101B closed, "
         "LOTO applied, permit signed. Allow 30 minutes cool-down before opening bearing housing. "
         "Check for residual hydrocarbon vapour with portable gas detector before opening any flanges."),
        ("STEP 7", "INITIATE MAINTENANCE",
         "Call Rajesh Kumar (ext. 4512) to begin bearing inspection. "
         "Required spare parts: SKF 6311 bearing (Warehouse A, Rack 4, Bin 12 - 3 in stock), "
         "SKF LGMT 2 grease (2 cartridges). Estimated repair time: 12 hours."),
        ("STEP 8", "DOCUMENT AND REPORT",
         "Within 4 hours of alarm: submit incident report to Plant Safety Officer per OISD-117 Sec 10.2. "
         "Log all actions in CMMS with timestamps. Raise RCA (Root Cause Analysis) work order. "
         "Update vibration baseline after repair and recommissioning."),
    ]
    for step, title, body in steps:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*AMBER)
        pdf.cell(0, 6, s(f"{step}  -  {title}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*BLACK)
        pdf.multi_cell(0, 5, s(body))
        pdf.ln(2)

    pdf.add_page()

    # ── Standby Pump Switchover Criteria ─────────────────────────────────
    pdf.section("3. P-103 STANDBY PUMP SWITCHOVER READINESS CHECKLIST")
    pdf.th([("Check", 105), ("Expected Value", 40), ("Actual", 28), ("OK?", 12), ("By", 13)])
    readiness = [
        ("P-103 lubrication date within 14 days",            "< 14 days ago",  "2 days",  "[OK]", "R.K"),
        ("P-103 seal flush pressure (Plan 11)",               "> 1.5 bar",      "2.1 bar", "[OK]", "R.K"),
        ("MOV-103A suction valve CLOSED and functional",      "Closed",         "Closed",  "[OK]", "R.K"),
        ("MOV-103B discharge valve CLOSED and functional",    "Closed",         "Closed",  "[OK]", "R.K"),
        ("P-103 motor ready in DCS (no trips)",               "Healthy",        "Healthy", "[OK]", "R.K"),
        ("P-103 VT-103A vibration baseline < 3 mm/s",         "< 3.0 mm/s",     "2.1 mm/s","[OK]", "R.K"),
        ("P-103 last standby run within 30 days",             "< 30 days",      "2 days",  "[OK]", "R.K"),
        ("Downstream HX-201 operator notified of switchover", "Notified",       "PENDING", "[ ]",  "-"),
        ("Control Room advised of switchover",                "Advised",        "PENDING", "[ ]",  "-"),
    ]
    for i, row in enumerate(readiness):
        tcol = GREEN if row[3] == "[OK]" else (AMBER if row[3] == "[ ]" else RED)
        pdf.tr(list(zip(row, [105, 40, 28, 12, 13])), alt=(i % 2 == 0), tcol=tcol)

    # ── Emergency Contacts ────────────────────────────────────────────────
    pdf.section("4. EMERGENCY CONTACTS")
    pdf.th([("Role", 65), ("Name", 48), ("Extension", 25), ("Mobile", 38), ("Available", 22)])
    contacts = [
        ("Shift Supervisor (24/7)",       "S. Venkataraman",   "4500",  "+91-98xx-xxxx01", "24/7"),
        ("Maintenance Lead - Pumps",      "Rajesh Kumar",      "4512",  "+91-98xx-xxxx02", "Day shift"),
        ("Maintenance Technician",        "Amit Shah",         "4514",  "+91-98xx-xxxx03", "Day shift"),
        ("Inspection Engineer",           "Priya Nair",        "4521",  "+91-98xx-xxxx04", "Day shift"),
        ("DCS Control Room",              "On-duty operator",  "4100",  "-",               "24/7"),
        ("Safety Officer",                "D. Patel",          "4600",  "+91-98xx-xxxx05", "Day shift + oncall"),
        ("Plant Fire Brigade",            "Fire Station",      "4999",  "Emergency: 4999", "24/7"),
        ("OEM Technical Support (Flowserve)","Global Helpdesk","0-800-FLOW","+1-800-356-9371","24/7"),
    ]
    for i, row in enumerate(contacts):
        pdf.tr(list(zip(row, [65, 48, 25, 38, 22])), alt=(i % 2 == 0))

    # ── Related Documents ─────────────────────────────────────────────────
    pdf.section("5. RELATED DOCUMENTS AND REFERENCES")
    refs = [
        ("OISD-117",           "Oil Industry Safety Directorate Standard 117 - Inspection of Rotary Equipment"),
        ("ISO 10816-3",        "Mechanical vibration - Evaluation of machine vibration - Part 3: Industrial machines"),
        ("SOP-P001 Rev 2.3",   "Centrifugal Pump Normal Operations and Routine Maintenance"),
        ("SOP-P002 Rev 1.1",   "Permit to Work (PTW) Procedure - Mechanical and Rotating Equipment"),
        ("PID-CDU-001 Rev 5",  "P&ID Engineering Drawing - CDU Unit 4 Feed Section"),
        ("INC-2022-034",       "Incident Investigation Report - P-101 Bearing Failure August 2022"),
        ("COMM-P103-2026",     "P-103 Commissioning Datasheet (this incident - cross-reference)"),
        ("Flowserve PVXM-100", "OEM Maintenance Manual Rev 3.1 - Sections 4.2, 6.1, 7.1"),
        ("API 610",            "American Petroleum Institute Standard 610 - Centrifugal Pumps for Petroleum"),
        ("API 686",            "API Recommended Practice 686 - Machinery Installation and Installation Design"),
    ]
    pdf.th([("Document Reference", 45), ("Description", 153)])
    for i, (ref, desc) in enumerate(refs):
        pdf.tr([(ref, 45), (desc, 153)], alt=(i % 2 == 0))

    # ── Sign-off ──────────────────────────────────────────────────────────
    pdf.ln(6)
    pdf.set_draw_color(*DARK)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*GREY)
    pdf.cell(95, 5, "Prepared by: Rajesh Kumar  -  Sr. Maintenance Technician")
    pdf.cell(0,  5, "Approved by: S. Venkataraman  -  Operations Supervisor",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(95, 5, "Effective: 20 July 2026  |  Review Date: 20 July 2027")
    pdf.cell(0,  5, "Document Control: SOP-P003-Rev3  |  OISD-117 Compliant",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(out)
    print(f"[3] SOP: {out}  ({os.path.getsize(out):,} bytes)")


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    build_pid(os.path.join(OUTPUT_DIR, "CDU_Unit4_PID_Rev5.pdf"))
    build_commissioning(os.path.join(OUTPUT_DIR, "P103_Commissioning_2026.pdf"))
    build_sop(os.path.join(OUTPUT_DIR, "SOP_P003_Emergency_Shutdown.pdf"))
    print("\nAll 3 documents generated in:", OUTPUT_DIR)
    print("Upload to http://localhost:3000/documents to test document intelligence.")
