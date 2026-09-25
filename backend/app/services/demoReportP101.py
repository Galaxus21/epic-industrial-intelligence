"""
EPIC — Sample document: the P-101 vibration analysis report written on the spectrum-check day (MR-P101-033).

It is the evidence behind the demo question "Can I continue operating?": it finds DE bearing damage, estimates when
the alarm will be reached, and names the stop rule from INC-2022-034. Its readings are the ones the maintenance
records and the sensor series carry for the same days.
"""
from __future__ import annotations

from datetime import datetime

from app.services import demoPdfLayout as layout
from app.services import demoTimeline as timeline
from app.services.demoPeople import AHMED_KHAN, AMIT_SHAH, RAJESH_KUMAR

CHECK_RECORD_ID = "MR-P101-033"
STATUS_COLOURS = {"ABOVE ALERT": layout.AMBER, "ELEVATED": layout.AMBER, "NORMAL": layout.GREEN,
                  "OPEN": layout.AMBER, "DONE": layout.GREEN, "PRESENT": layout.RED}


def buildP101VibrationReport(now: datetime) -> bytes:
    checkDate = timeline.documentDate(now, timeline.P101_SPECTRUM_CHECK_DAYS_AGO)
    pdf = layout.startReport("VIBRATION ANALYSIS REPORT  -  P-101",
                             f"CONFIDENTIAL  |  Apex Refinery CDU Unit 4  |  {CHECK_RECORD_ID}")
    layout.titleBlock(pdf, "P-101 CRUDE OIL FEED PUMP",
                      f"Vibration Analysis Report  |  {CHECK_RECORD_ID}  |  {checkDate}")
    _equipmentSection(pdf)
    _triggerSection(pdf, now)
    _readingsSection(pdf)
    _historySection(pdf, now)
    _spectrumSection(pdf)
    _assessmentSection(pdf, now)
    _recommendationsSection(pdf)
    _signOffSection(pdf, checkDate)
    return layout.pdfBytes(pdf)


def _equipmentSection(pdf) -> None:
    layout.section(pdf, "EQUIPMENT")
    layout.keyValues(pdf, [
        ("Tag / description:", "P-101 Crude Oil Feed Pump (Unit 4 - CDU, Pump House A)"),
        ("Type:", "Centrifugal pump, overhung, single stage; Flowserve PVXM-100, installed 15 Apr 2018"),
        ("Rating:", "250 m³/h at 70 m head; 75 kW motor at 2,960 rpm"),
        ("Bearings:", "SKF 6311/C3 at DE and NDE, grease-lubricated; regrease every 30 days (SOP-P101-BEARING)"),
        ("Criticality:", "CRITICAL - no installed spare; stopping P-101 stops crude feed to the CDU"),
    ], {"Criticality:": layout.RED})


def _triggerSection(pdf, now: datetime) -> None:
    layout.section(pdf, "WHY THIS CHECK")
    layout.paragraph(pdf, (
        "The DCS trend alert flagged P-101 drive-end (DE) vibration: 4.4 mm/s on the last monthly route "
        f"(MR-P101-032, {timeline.documentDate(now, timeline.P101_LAST_ROUTE_DAYS_AGO)}) and 6.1 mm/s on "
        f"{timeline.documentDate(now, timeline.P101_SPECTRUM_CHECK_DAYS_AGO)}. The readings and spectra below were "
        "taken at full rate on that day."
    ))


def _readingsSection(pdf) -> None:
    layout.section(pdf, "READINGS AT FULL RATE")
    layout.table(pdf, ("Parameter", "Reading", "Alert", "Alarm", "Trip", "Status"), [
        ("DE vibration (VT-101A)", "6.1 mm/s", "4.5", "7.1", "11.2", "ABOVE ALERT"),
        ("NDE vibration (VT-101B)", "3.9 mm/s", "4.5", "7.1", "11.2", "NORMAL"),
        ("DE bearing temperature (TT-101)", "66 °C", "55", "75", "90", "ELEVATED"),
        ("NDE bearing temperature (TT-102)", "54 °C", "55", "75", "90", "NORMAL"),
        ("Suction pressure (PT-100)", "2.4 bar", "-", "1.2 low", "-", "NORMAL"),
        ("Discharge pressure (PT-101)", "8.3 bar", "-", "6.0 low", "-", "NORMAL"),
        ("Flow (FT-101)", "246 m³/h", "-", "200 low", "-", "NORMAL"),
        ("Motor current", "87 A", "-", "-", "-", "NORMAL"),
    ], (50, 22, 16, 18, 14, 22), STATUS_COLOURS)


def _historySection(pdf, now: datetime) -> None:
    layout.section(pdf, "ROUTE HISTORY")
    layout.table(pdf, ("Date", "Record", "DE vibration", "DE bearing temp.", "Note"), [
        (timeline.dateString(now, timeline.P101_ROUTE_BEFORE_LAST_DAYS_AGO), "MR-P101-031", "4.1 mm/s", "56 °C",
         "Monthly route; regreased"),
        (timeline.dateString(now, timeline.P101_LAST_ROUTE_DAYS_AGO), "MR-P101-032", "4.4 mm/s", "58 °C",
         "Monthly route; regreased"),
        (timeline.dateString(now, timeline.P101_SPECTRUM_CHECK_DAYS_AGO), CHECK_RECORD_ID, "6.1 mm/s", "66 °C",
         "This check; regreasing did not lower the level"),
    ], (22, 26, 22, 24, 50))


def _spectrumSection(pdf) -> None:
    layout.section(pdf, "SPECTRUM FINDINGS")
    layout.table(pdf, ("Feature", "Finding", "Meaning"), [
        ("Outer-race defect frequency (BPFO) with 2x and 3x harmonics", "PRESENT", "DE bearing outer-race damage"),
        ("1x running speed (49.3 Hz)", "Normal amplitude", "No imbalance"),
        ("2x running speed", "Low", "No misalignment"),
        ("High-frequency envelope", "Raised", "Surface damage in the rolling contact"),
    ], (70, 30, 60), STATUS_COLOURS)


def _assessmentSection(pdf, now: datetime) -> None:
    daysSinceRoute = timeline.P101_LAST_ROUTE_DAYS_AGO - timeline.P101_SPECTRUM_CHECK_DAYS_AGO
    layout.section(pdf, "ASSESSMENT")
    layout.paragraph(pdf, (
        f"The DE bearing (SKF 6311/C3) has outer-race damage. DE vibration rose 1.7 mm/s in the {daysSinceRoute} "
        "days since the last route and is still rising; at this rate it reaches the 7.1 mm/s alarm in about a "
        "week. Regreasing did not lower the level, so this is not a lubrication shortfall alone.\n\n"
        "P-101 has no installed spare: stopping it stops crude feed to the CDU. On this pump, in INC-2022-034, DE "
        "vibration above 7.1 mm/s for more than 2 hours was followed by bearing seizure within 18 hours.\n\n"
        "P-202 showed a similar rise in INC-2023-067, caused by cavitation. P-101 suction pressure is normal "
        "(2.4 bar), so cavitation is not indicated here."
    ))


def _recommendationsSection(pdf) -> None:
    layout.section(pdf, "RECOMMENDATIONS")
    layout.table(pdf, ("No.", "Action", "Owner", "Status"), [
        ("1", "Replace the DE bearing at the next planned stop, within 3 weeks; plan the CDU feed cut with "
              "Operations.", AHMED_KHAN, "OPEN"),
        ("2", "Reserve one SKF 6311/C3 (Warehouse A, Rack 4; 3 in stock).", AMIT_SHAH, "DONE"),
        ("3", "Take DE vibration and temperature twice a week until the change.", RAJESH_KUMAR, "OPEN"),
        ("4", "If DE vibration passes the 7.1 mm/s alarm, make the run-or-stop decision within 4 hours "
              "(SOP-ROT-VIB). Stop the pump if it stays above 7.1 mm/s for 2 hours or the DE bearing reaches the "
              "90 °C trip.", "Shift supervisor", "OPEN"),
        ("5", "Check the NDE bearing during the same stop.", RAJESH_KUMAR, "OPEN"),
    ], (8, 118, 28, 16), STATUS_COLOURS)


def _signOffSection(pdf, checkDate: str) -> None:
    layout.section(pdf, "REFERENCES AND SIGN-OFF")
    layout.keyValues(pdf, [
        ("Site procedures:", "SOP-ROT-VIB (rotating equipment vibration limits and alarm response); "
                             "SOP-P101-BEARING (P-101 lubrication and bearings)"),
        ("Related records:", "INC-2022-034, INC-2023-067, MR-P101-031, MR-P101-032"),
        ("Analyst:", f"{AMIT_SHAH}, Reliability Engineer (EMP-002)  |  {checkDate}"),
        ("Reviewed by:", f"{AHMED_KHAN}, Maintenance Supervisor (EMP-005)"),
    ])
