"""
EPIC — The demo plant's saved work orders: one completed with outcome feedback, and two open.

P-101 gets no seeded work order on purpose: its vibration is above the alarm, so the threshold monitor raises one on
its next pass, and the demo shows that happening.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.services import demoTimeline as timeline
from app.services.demoPeople import AHMED_KHAN

FILTER_JOB_START_HOUR = 14
FILTER_JOB_START_MINUTE = 45
FILTER_JOB_HOURS = 1.75
MINUTES_PER_HOUR = 60
# A re-seed reopens an open demo work order, so any outcome a user recorded on it is cleared.
NO_OUTCOME = {"solution_worked": None, "is_partial": False, "extra_steps_taken": None, "outcome_notes": None,
              "completed_by": None, "actual_duration_hours": None, "completed_at": None}


def demoWorkOrders(now: datetime) -> list[dict[str, Any]]:
    workOrders = [_k401FilterWorkOrder(now), _k401IntercoolerWorkOrder(now), _g101BladeWorkOrder(now)]
    return [{**workOrder, "estimated_duration_hours": _plannedHours(workOrder["steps"])} for workOrder in workOrders]


def _k401FilterWorkOrder(now: datetime) -> dict[str, Any]:
    incident = timeline.k401IncidentId(now)
    started = timeline.daysAgo(now, timeline.K401_FILTER_CHANGE_DAYS_AGO).replace(
        hour=FILTER_JOB_START_HOUR, minute=FILTER_JOB_START_MINUTE, second=0)
    return {
        "id": timeline.k401FilterWorkOrderId(now), "equipment_id": "K-401",
        "query_text": f"Discharge pressure 10.6 bar and falling; filter dP 0.82 bar ({incident}).",
        "risk_level": "Medium", "wo_type": "Corrective",
        "description": f"Replace the choked K-401 inlet filter element ({incident}).",
        "required_technicians": 2, "status": "completed",
        "steps": [
            _step(1, "Preparation", "Reduce load", "Reduce K-401 to 70% load with the VDU panel.", None, 10, True,
                  f"Load at 70% at {started:%H:%M}."),
            _step(2, "Isolation", "Isolate the filter housing", "Close the inlet isolation and apply LOTO.",
                  "Confirm zero pressure at the housing drain before opening.", 15, True, "Two locks applied."),
            _step(3, "Execution", "Change the element", "Remove the choked element and fit a new AC-ZH350-FE.",
                  None, 30, True, "Old element 84 days old, dP 0.82 bar, iron-oxide dust."),
            _step(4, "Restart", "Restart and verify", "Remove LOTO, restore load, watch discharge pressure.",
                  None, 20, True, "12.4 bar within 8 minutes of restart."),
            _step(5, "Verification", "Fix the CMMS interval", "Set the filter task to 60 days and close CA-K401-2.",
                  None, 15, True, "CMMS task now 60 days."),
        ],
        "spare_parts": ["K-401 inlet filter element AC-ZH350-FE × 1"],
        "safety_precautions": ["Reduce load before isolating the filter housing", "LOTO on the filter housing"],
        "required_permits": ["Cold work permit"],
        "solution_worked": True, "is_partial": False,
        "outcome_notes": "Discharge pressure back to 12.4 bar within 8 minutes of restart. The old element was "
                         "84 days old with 0.82 bar differential pressure.",
        "extra_steps_taken": "Changed the CMMS filter interval from 90 to 60 days and closed CA-K401-2.",
        "completed_by": AHMED_KHAN, "actual_duration_hours": FILTER_JOB_HOURS,
        "created_at": started, "completed_at": started + timedelta(hours=FILTER_JOB_HOURS),
    }


def _k401IntercoolerWorkOrder(now: datetime) -> dict[str, Any]:
    return {
        "id": timeline.k401IntercoolerWorkOrderId(now), "equipment_id": "K-401",
        "query_text": "Discharge pressure falling again with a new filter; intercooler approach 14 °C.",
        "risk_level": "Medium", "wo_type": "Corrective",
        "description": "Clean the K-401 stage-2 intercooler on the water side: an approach temperature of 14 °C "
                       "against 8 °C design is cutting discharge pressure (MR-K401-041).",
        "required_technicians": 2, "status": "open",
        "steps": [
            _step(1, "Preparation", "Agree the stop window", "Agree a K-401 stop with the VDU panel; standby air "
                  "from the plant air header.", None, 30),
            _step(2, "Isolation", "Isolate and drain", "Stop K-401, apply LOTO on the main motor, isolate and drain "
                  "the cooling water side, vent the air side.", "Vent the air side to zero before opening.", 45),
            _step(3, "Execution", "Open and inspect", "Remove the intercooler end covers and photograph the fouling.",
                  None, 60),
            _step(4, "Execution", "Clean the tubes", "Hydro-jet the tubes; record how many are blocked.",
                  "Hydro-jetting: barrier and trained operator only.", 150),
            _step(5, "Restart", "Reassemble and restart", "Fit new gaskets, refill cooling water, remove LOTO and "
                  "restart.", None, 45),
            _step(6, "Verification", "Verify performance", "Approach temperature at or below 9 °C and discharge "
                  "pressure at or above 12.2 bar after one hour at full load.", None, 30),
        ],
        "spare_parts": ["K-401 stage-2 intercooler gasket set AC-ZH350-ICG × 1"],
        "safety_precautions": ["Vent the air side to zero pressure before opening",
                               "LOTO on the compressor main motor", "Isolate and drain the cooling water side"],
        "required_permits": ["Cold work permit"],
        "created_at": timeline.daysAgo(now, timeline.K401_INTERCOOLER_WORK_ORDER_DAYS_AGO), **NO_OUTCOME,
    }


def _g101BladeWorkOrder(now: datetime) -> dict[str, Any]:
    return {
        "id": timeline.g101WorkOrderId(now), "equipment_id": "G-101",
        "query_text": "Six-monthly fan blade erosion-coating inspection due.",
        "risk_level": "Low", "wo_type": "Inspection",
        "description": "Six-monthly fan blade erosion-coating inspection on G-101; book scaffold access.",
        "required_technicians": 2, "status": "open",
        "steps": [
            _step(1, "Preparation", "Book scaffold", "Book scaffold access to the fan deck.", None, 30),
            _step(2, "Isolation", "Stop and lock the fan", "Stop G-101, apply LOTO and lock the fan against "
                  "windmilling.", "A windmilling fan can turn with the motor isolated.", 20),
            _step(3, "Execution", "Inspect each blade", "Check the leading-edge coating on all 8 blades and "
                  "photograph any wear.", "Work at height: harness and scaffold tag checked.", 120),
            _step(4, "Verification", "Record and restart", "Record coating wear per blade, remove LOTO, restart and "
                  "check vibration.", None, 30),
        ],
        "spare_parts": [],
        "safety_precautions": ["LOTO on the fan motor and lock against windmilling", "Work at height: harness on"],
        "required_permits": ["Work-at-height permit"],
        "created_at": timeline.daysAgo(now, timeline.G101_WORK_ORDER_DAYS_AGO), **NO_OUTCOME,
    }


def _plannedHours(steps: list[dict[str, Any]]) -> float:
    return round(sum(step["expected_duration_minutes"] for step in steps) / MINUTES_PER_HOUR, 2)


def _step(number: int, phase: str, title: str, description: str, safetyNote: str | None, minutes: int,
          checked: bool = False, actualNotes: str = "") -> dict[str, Any]:
    return {
        "step": number, "phase": phase, "title": title, "description": description, "safety_note": safetyNote,
        "expected_duration_minutes": minutes, "checked": checked, "actual_notes": actualNotes,
    }
