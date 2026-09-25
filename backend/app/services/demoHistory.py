"""
EPIC — The demo plant's history: past incidents and the maintenance records that lead up to today.

Older incidents keep their fixed dates; everything in the last few months is dated from demoTimeline, so the records
agree with the sensor series and the sample documents. Each record's findings carry the readings that the series
show on that day.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services import demoTimeline as timeline
from app.services.demoPeople import AHMED_KHAN, AMIT_SHAH, ANAND_SHARMA, RAJESH_KUMAR

P101_ROUTE = "Monthly regrease and vibration route per SOP-P101-BEARING."
P101_OVERDUE_ROUTE_ID = "MR-P101-034"


def demoIncidents(now: datetime) -> list[dict[str, Any]]:
    k401Incident = timeline.k401IncidentId(now)
    filterWorkOrder = timeline.k401FilterWorkOrderId(now)
    return [
        {"id": "INC-2021-011", "equipment_id": "P-101", "date": "2021-03-22",
         "title": "Mechanical seal leak found on routine inspection", "severity": "Medium",
         "root_cause_category": "Wear",
         "symptom": "Leak at the seal flush line; seal chamber pressure 0.3 bar below normal.",
         "root_cause": "Seal O-rings hardened after 30 months in crude service. Normal wear.",
         "action_taken": "Replaced the cartridge seal from stock and added a 36-month seal inspection to "
                         "SOP-P101-SEAL.",
         "lessons_learned": "Inspect the P-101 and P-202 seals at the 36-month mark: O-rings start hardening at "
                            "about 30 months in crude service.",
         "downtime_hours": 8, "cost_usd": 8500, "technician": AMIT_SHAH,
         "keywords": ["seal", "leak", "mechanical seal", "O-ring", "flush"]},
        {"id": "INC-2022-034", "equipment_id": "P-101", "date": "2022-08-14",
         "title": "Drive-end bearing failure after vibration alarm", "severity": "High",
         "root_cause_category": "Maintenance",
         "symptom": "DE vibration rose from 4.2 to 8.7 mm/s over 6 hours with a high-pitched noise from the DE "
                    "bearing; DE bearing temperature reached 84 °C.",
         "root_cause": "DE bearing wear from lubrication starvation: the regrease was 15 days late on what was then "
                       "a 60-day interval.",
         "action_taken": "Emergency stop at 9.1 mm/s. Replaced the DE bearing (SKF 6311/C3). SOP-P101-BEARING "
                         "changed to a 30-day regrease with a monthly vibration route.",
         "lessons_learned": "On P-101, DE vibration above 7.1 mm/s for more than 2 hours was followed by bearing "
                            "seizure within 18 hours. Plan the bearing change at the first alarm instead of running "
                            "to the trip.",
         "downtime_hours": 12, "cost_usd": 14200, "technician": RAJESH_KUMAR,
         "keywords": ["vibration", "bearing", "lubrication", "wear", "centrifugal pump", "alarm"]},
        {"id": "INC-2023-067", "equipment_id": "P-202", "date": "2023-11-08",
         "title": "Vibration rise and DE bearing failure caused by cavitation", "severity": "High",
         "root_cause_category": "Process",
         "symptom": "DE vibration rose to 7.8 mm/s with a crackling noise at the suction; the DE bearing failed "
                    "14 hours later.",
         "root_cause": "Cavitation: suction pressure fell below what the pump needs when the reflux drum level ran "
                       "low at high throughput.",
         "action_taken": "Replaced the DE bearing. Raised the reflux drum minimum level from 30% to 45% and kept the "
                         "pump inside its efficient flow range.",
         "lessons_learned": "P-202 showed the same vibration rise as P-101 in INC-2022-034, but the cause was "
                            "cavitation, not lubrication. Check suction pressure and drum level before concluding "
                            "that a bearing is failing.",
         "downtime_hours": 36, "cost_usd": 31000, "technician": RAJESH_KUMAR,
         "keywords": ["vibration", "bearing", "cavitation", "suction", "P-202"]},
        {"id": "INC-2024-015", "equipment_id": "K-401", "date": "2024-03-05",
         "title": "Discharge pressure drop from a choked inlet filter", "severity": "Medium",
         "root_cause_category": "Maintenance",
         "symptom": "Discharge pressure fell from 12.5 to 10.2 bar over 48 hours.",
         "root_cause": "Inlet filter element choked with dust; the change was 3 weeks late on a 90-day interval.",
         "action_taken": "Replaced the filter element (AC-ZH350-FE); pressure back to 12.4 bar. Corrective action "
                         "CA-K401-2 raised to cut the CMMS filter interval from 90 to 60 days.",
         "lessons_learned": "Site dust chokes the K-401 inlet filter in about 60 days, not the 90 days the OEM "
                            "manual suggests.",
         "downtime_hours": 4, "cost_usd": 2200, "technician": AHMED_KHAN,
         "keywords": ["compressor", "pressure drop", "filter", "K-401"]},
        {"id": k401Incident, "equipment_id": "K-401",
         "date": timeline.dateString(now, timeline.K401_FILTER_CHANGE_DAYS_AGO),
         "title": "Inlet filter choked again: the 2024 interval change never reached the CMMS", "severity": "Medium",
         "root_cause_category": "Maintenance",
         "symptom": "Discharge pressure fell from 12.1 to 10.6 bar over two weeks; filter differential pressure "
                    "0.82 bar (change at 0.30 bar).",
         "root_cause": "CA-K401-2 from INC-2024-015 was never closed, so the CMMS still scheduled the filter every "
                       "90 days; the element was 84 days old.",
         "action_taken": f"Replaced the filter element under {filterWorkOrder}; pressure back to 12.4 bar. CMMS "
                         "interval set to 60 days and CA-K401-2 closed. CA-K401-3 raised for an inlet-filter "
                         "differential-pressure transmitter.",
         "lessons_learned": "A corrective action that changes a maintenance interval is closed only when the CMMS "
                            "task shows the new interval.",
         "downtime_hours": 4, "cost_usd": 2400, "technician": AHMED_KHAN,
         "keywords": ["compressor", "pressure drop", "filter", "CMMS", "corrective action", "K-401"]},
    ]


def demoMaintenanceRecords(now: datetime) -> list[dict[str, Any]]:
    return _p101Records(now) + _p202Records(now) + _staticEquipmentRecords(now) + _k401Records(now) + _g101Records(now)


def _p101Records(now: datetime) -> list[dict[str, Any]]:
    overdueDate = timeline.dateString(now, timeline.P101_ROUTE_OVERDUE_DAYS)
    return [
        _record("MR-P101-031", "P-101", now, timeline.P101_ROUTE_BEFORE_LAST_DAYS_AGO, "Preventive", P101_ROUTE,
                "DE 4.1 mm/s, NDE 3.6 mm/s, DE bearing 56 °C. Regreased DE and NDE with one LGMT 2 cartridge each.",
                RAJESH_KUMAR),
        _record("MR-P101-032", "P-101", now, timeline.P101_LAST_ROUTE_DAYS_AGO, "Preventive", P101_ROUTE,
                "DE 4.4 mm/s, NDE 3.7 mm/s, DE bearing 58 °C. Regreased DE and NDE. No abnormal noise.",
                RAJESH_KUMAR),
        _record("MR-P101-033", "P-101", now, timeline.P101_SPECTRUM_CHECK_DAYS_AGO, "Predictive",
                "Vibration spectrum check after the DCS trend alert on DE vibration.",
                "DE 6.1 mm/s, DE bearing 66 °C. Spectrum shows the DE bearing outer-race defect frequency with "
                "harmonics; no misalignment or imbalance signature. Regreasing did not lower the level. Replace the "
                "DE bearing at the next planned stop, within 3 weeks; one SKF 6311/C3 reserved in Warehouse A. "
                "Suction pressure 2.4 bar (normal), so cavitation is not indicated.",
                AMIT_SHAH),
        {"id": P101_OVERDUE_ROUTE_ID, "equipment_id": "P-101", "date": overdueDate, "scheduled_date": overdueDate,
         "type": "Preventive", "description": P101_ROUTE, "status": "Overdue",
         "overdue_days": timeline.P101_ROUTE_OVERDUE_DAYS, "technician": RAJESH_KUMAR,
         "findings": "Deferred by the planner while the DE bearing change is decided (see MR-P101-033)."},
    ]


def _p202Records(now: datetime) -> list[dict[str, Any]]:
    return [
        _record("MR-P202-020", "P-202", now, timeline.P202_SEAL_INSPECTION_DAYS_AGO, "Preventive",
                "Annual mechanical seal inspection per SOP-P202-SEAL.",
                "Seal flush normal; O-rings acceptable. Seal at 28 of 36 months.", AMIT_SHAH),
        _record("MR-P202-021", "P-202", now, timeline.P202_LAST_ROUTE_DAYS_AGO, "Preventive",
                "Monthly regrease and vibration route.",
                "DE 3.1 mm/s, DE bearing 51 °C. Regreased. Seal flush line insulation damaged near the gland; "
                "repair requested.", RAJESH_KUMAR),
    ]


def _staticEquipmentRecords(now: datetime) -> list[dict[str, Any]]:
    return [
        _record("MR-HX201-011", "HX-201", now, timeline.HX201_TUBE_INSPECTION_DAYS_AGO, "Inspection",
                "Annual tube-bundle inspection and cleaning per SOP-HX-INSP.",
                "2 of 450 tubes plugged (limit 5%). Shell side cleaned. Fouling within the design allowance.",
                ANAND_SHARMA),
        _record("MR-HX201-012", "HX-201", now, timeline.HX201_PERFORMANCE_CHECK_DAYS_AGO, "Inspection",
                "Quarterly thermal performance check.",
                "Duty 12.3 MW against 12.5 MW design; tube-side dP 1.7 bar. Next check in 90 days.", ANAND_SHARMA),
        _record("MR-V301-007", "V-301", now, timeline.V301_EXTERNAL_INSPECTION_DAYS_AGO, "Inspection",
                "Quarterly external visual inspection.",
                "No leaks and no corrosion under insulation. PSV-301 seal wire intact. Level 64%, pressure 3.2 barg.",
                ANAND_SHARMA),
    ]


def _k401Records(now: datetime) -> list[dict[str, Any]]:
    k401Incident = timeline.k401IncidentId(now)
    intercoolerWorkOrder = timeline.k401IntercoolerWorkOrderId(now)
    plannedDate = timeline.dateString(now, -timeline.K401_INTERCOOLER_PLANNED_IN_DAYS)
    filterAgeDays = timeline.K401_FILTER_CHANGE_DAYS_AGO - timeline.K401_DECLINE_CHECK_DAYS_AGO
    return [
        _record("MR-K401-040", "K-401", now, timeline.K401_FILTER_CHANGE_DAYS_AGO, "Corrective",
                f"Inlet filter element replaced under {timeline.k401FilterWorkOrderId(now)} ({k401Incident}).",
                "Filter dP 0.82 bar before the change (change at 0.30 bar); element loaded with iron-oxide dust. "
                "Discharge pressure 12.4 bar after restart. CMMS filter interval set to 60 days.", AHMED_KHAN),
        _record("MR-K401-041", "K-401", now, timeline.K401_DECLINE_CHECK_DAYS_AGO, "Inspection",
                "Check of the renewed discharge pressure decline.",
                f"Inlet filter dP 0.12 bar, so the {filterAgeDays}-day-old filter is not the cause. Stage-2 "
                "intercooler approach "
                "14 °C against 8 °C design with cooling water supply at 31 °C (normal for the season): points to "
                f"water-side fouling. Raised {intercoolerWorkOrder} to clean the intercooler.", AHMED_KHAN),
        {"id": f"MR-{intercoolerWorkOrder}", "equipment_id": "K-401", "date": plannedDate,
         "scheduled_date": plannedDate, "type": "Corrective", "status": "Scheduled", "technician": AHMED_KHAN,
         "description": f"Work order {intercoolerWorkOrder}: clean the stage-2 intercooler on the water side.",
         "findings": "Planned for the next compressor stop window."},
    ]


def _g101Records(now: datetime) -> list[dict[str, Any]]:
    workOrder = timeline.g101WorkOrderId(now)
    dueIn = timeline.G101_BLADE_INSPECTION_INTERVAL_DAYS - timeline.G101_BLADE_INSPECTION_DAYS_AGO
    dueDate = timeline.dateString(now, -dueIn)
    return [
        _record("MR-G101-015", "G-101", now, timeline.G101_BLADE_INSPECTION_DAYS_AGO, "Inspection",
                "Six-monthly fan blade erosion-coating inspection.",
                "Leading-edge coating worn on 2 of 8 blades, within limits. Next inspection in 6 months.",
                AHMED_KHAN),
        {"id": f"MR-{workOrder}", "equipment_id": "G-101", "date": dueDate, "scheduled_date": dueDate,
         "type": "Inspection", "status": "Scheduled", "technician": AHMED_KHAN,
         "description": f"Work order {workOrder}: six-monthly fan blade erosion-coating inspection.",
         "findings": "Scaffold access to be booked."},
    ]


def _record(recordId: str, equipmentId: str, now: datetime, days: int, recordType: str, description: str,
            findings: str, technician: str) -> dict[str, Any]:
    return {
        "id": recordId, "equipment_id": equipmentId, "date": timeline.dateString(now, days), "type": recordType,
        "description": description, "status": "Completed", "findings": findings, "technician": technician,
    }
