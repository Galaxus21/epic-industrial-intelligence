"""
EPIC — Sample document: the K-401 incident investigation report for the choked inlet filter.

The incident, its work order and its corrective actions are the same records the demo seeds (demoHistory,
demoWorkOrders). The report is approved two days after the filter change, before the pressure began to fall again,
so it says nothing about the intercooler.
"""
from __future__ import annotations

from datetime import datetime

from app.services import demoPdfLayout as layout
from app.services import demoTimeline as timeline
from app.services.demoPeople import AHMED_KHAN, ANAND_SHARMA, DEEPA_MENON, PRIYA_NAIR

APPROVED_DAYS_AFTER_INCIDENT = 2
STATUS_COLOURS = {"CLOSED": layout.GREEN, "OPEN": layout.AMBER, "DONE": layout.GREEN}


def buildK401IncidentReport(now: datetime) -> bytes:
    incident = timeline.k401IncidentId(now)
    occurred = timeline.documentDate(now, timeline.K401_FILTER_CHANGE_DAYS_AGO)
    pdf = layout.startReport(f"INCIDENT INVESTIGATION REPORT  -  {incident}  -  K-401",
                             f"CONFIDENTIAL  |  Apex Refinery VDU Unit 5  |  {incident}")
    layout.titleBlock(pdf, "K-401 PROCESS AIR COMPRESSOR", f"Incident Investigation Report  |  {incident}  |  {occurred}")
    _summarySection(pdf, incident, occurred)
    _descriptionSection(pdf, occurred)
    _immediateActionsSection(pdf, now)
    _whySection(pdf)
    _correctiveActionsSection(pdf, now)
    _impactSection(pdf, now)
    return layout.pdfBytes(pdf)


def _summarySection(pdf, incident: str, occurred: str) -> None:
    layout.section(pdf, "INCIDENT SUMMARY")
    layout.keyValues(pdf, [
        ("Incident number:", incident),
        ("Severity:", "Medium - performance loss; no injury, no release"),
        ("Status:", "Corrective actions in progress (2 of 4 closed)"),
        ("Equipment:", "K-401 Process Air Compressor (Atlas Copco ZH350), Unit 5 - VDU"),
        ("Occurred:", f"{occurred}, 14:30"),
        ("Reported by:", f"{AHMED_KHAN} (EMP-005), Maintenance Supervisor"),
        ("Investigation lead:", f"{ANAND_SHARMA} (EMP-004), Inspection Engineer"),
    ])


def _descriptionSection(pdf, occurred: str) -> None:
    layout.section(pdf, "WHAT HAPPENED")
    layout.paragraph(pdf, (
        f"At 14:30 on {occurred} the DCS showed K-401 discharge pressure at 10.6 bar against the rated 12.5 bar, "
        "down from 12.1 bar two weeks earlier. Suction conditions, ambient temperature and motor current were "
        f"normal. {AHMED_KHAN} found the inlet filter differential pressure at 0.82 bar (change at 0.30 bar).\n\n"
        "The element was 84 days old. The CMMS still scheduled it every 90 days, although INC-2024-015 had found "
        "that site dust chokes it in about 60 days and had raised corrective action CA-K401-2 to change the "
        "interval. CA-K401-2 had never been closed, and nothing reminded anyone that it was open."
    ))


def _immediateActionsSection(pdf, now: datetime) -> None:
    workOrder = timeline.k401FilterWorkOrderId(now)
    layout.section(pdf, "IMMEDIATE ACTIONS")
    layout.table(pdf, ("Time", "Action", "Status"), [
        ("14:45", f"Load reduced to 70% to protect the motor while the filter was isolated ({workOrder}).", "DONE"),
        ("15:00", "Filter housing isolated under LOTO; zero pressure confirmed at the housing drain.", "DONE"),
        ("15:30", "New element AC-ZH350-FE fitted from Warehouse B, Row 6.", "DONE"),
        ("15:50", "Restarted; discharge pressure back to 12.4 bar within 8 minutes.", "DONE"),
        ("16:30", "CMMS filter interval set to 60 days; work order closed.", "DONE"),
    ], (14, 140, 16), STATUS_COLOURS)


def _whySection(pdf) -> None:
    layout.section(pdf, "ROOT CAUSE (5 WHYS)")
    layout.table(pdf, ("Why", "Question", "Answer"), [
        ("1", "Why did discharge pressure drop?", "A choked inlet filter cut the compressor's air intake."),
        ("2", "Why was the filter choked?", "It was 84 days old; site dust chokes it in about 60 days."),
        ("3", "Why was it not changed at 60 days?", "The CMMS still scheduled it every 90 days."),
        ("4", "Why was the CMMS not updated?", "CA-K401-2 from INC-2024-015 was never carried out."),
        ("5", "Why was CA-K401-2 left open?", "It had no owner and no due-date reminder."),
    ], (10, 60, 100))


def _correctiveActionsSection(pdf, now: datetime) -> None:
    layout.section(pdf, "CORRECTIVE ACTIONS")
    layout.table(pdf, ("ID", "Type", "Action", "Owner", "Status"), [
        ("CA-K401-1", "Corrective", f"Replace the inlet filter element ({timeline.k401FilterWorkOrderId(now)}).",
         AHMED_KHAN, "CLOSED"),
        ("CA-K401-2", "Preventive", "Set the CMMS filter interval to 60 days.", AHMED_KHAN, "CLOSED"),
        ("CA-K401-3", "Preventive", "Install an inlet-filter differential-pressure transmitter with a DCS alarm at "
                                    "0.30 bar (capital request).", DEEPA_MENON, "OPEN"),
        ("CA-K401-4", "Improvement", "Review every open corrective action at the monthly safety meeting.",
         PRIYA_NAIR, "OPEN"),
    ], (20, 20, 90, 26, 14), STATUS_COLOURS)


def _impactSection(pdf, now: datetime) -> None:
    approved = timeline.documentDate(now, timeline.K401_FILTER_CHANGE_DAYS_AGO - APPROVED_DAYS_AFTER_INCIDENT)
    layout.section(pdf, "IMPACT AND APPROVAL")
    layout.keyValues(pdf, [
        ("Downtime:", "About 4 hours at 70% load; no full stop"),
        ("Cost:", "USD 2,400 (filter element and labour)"),
        ("Lesson:", "A corrective action that changes a maintenance interval is closed only when the CMMS task "
                    "shows the new interval."),
        ("Approved:", f"{ANAND_SHARMA}  |  {approved}"),
    ])
