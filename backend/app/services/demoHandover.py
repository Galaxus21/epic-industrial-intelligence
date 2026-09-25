"""
EPIC — Sample document: the night-shift handover that ends at the seed moment.

It is where the demo question comes from: P-101 went into alarm overnight and the day shift must decide whether to
keep it running. Its closing readings are the live readings the demo seeds.
"""
from __future__ import annotations

from datetime import datetime

from app.services import demoTimeline as timeline
from app.services.demoPeople import AHMED_KHAN, AMIT_SHAH, RAJESH_KUMAR, SURESH_NAIR

SHIFT_START_DAYS_AGO = 1


def buildNightShiftHandover(now: datetime) -> str:
    shiftStart = timeline.documentDate(now, SHIFT_START_DAYS_AGO)
    shiftEnd = timeline.documentDate(now, 0)
    intercoolerWorkOrder = timeline.k401IntercoolerWorkOrderId(now)
    bladeWorkOrder = timeline.g101WorkOrderId(now)
    bladeDueInDays = timeline.G101_BLADE_INSPECTION_INTERVAL_DAYS - timeline.G101_BLADE_INSPECTION_DAYS_AGO
    spectrumDate = timeline.dateString(now, timeline.P101_SPECTRUM_CHECK_DAYS_AGO)
    alarmAt = timeline.P101_ALARM_CLOCK_TIME
    return f"""APEX REFINERY — CDU UNIT 4 AND VDU UNIT 5
NIGHT SHIFT HANDOVER
Shift: {shiftStart} 22:00 to {shiftEnd} 06:00  |  Supervisor: {SURESH_NAIR}
============================================================

UNIT STATUS AT 06:00
--------------------
P-101  Crude Oil Feed Pump    : RUNNING IN ALARM. DE vibration 7.4 mm/s (alarm 7.1), DE bearing 78 °C (alarm 75).
P-202  Reflux Pump            : Normal. DE vibration 3.1 mm/s, DE bearing 51 °C.
HX-201 Crude Feed Pre-heater  : Normal. Tube-side dP 1.8 bar.
V-301  Crude Feed Surge Drum  : Normal. Level 65%, pressure 3.2 barg.
K-401  Process Air Compressor : Running, degraded. Discharge 11.2 bar (rated 12.5), discharge temp 186 °C.
G-101  Cooling Tower Fan      : Normal. Vibration 2.8 mm/s, current 145 A.

EVENTS
------
22:00  Shift start. P-101 DE vibration 7.0 mm/s and DE bearing 74 °C, both rising.
       DE bearing change pending since the spectrum check MR-P101-033 ({spectrumDate}).
{alarmAt}  P-101 DE vibration alarm: 7.2 mm/s (alarm 7.1). DE bearing 76 °C (alarm 75).
       The EPIC threshold monitor raised an automatic work order for P-101.
02:30  {RAJESH_KUMAR} (on call) checked P-101 in the field: no leak, rough bearing noise at the
       DE end, suction pressure 2.4 bar (normal).
02:45  Run-or-stop decision (SOP-ROT-VIB, due within 4 hours of the alarm): keep running under
       watch until the day shift decides. P-101 has no installed spare and a stop cuts CDU feed.
       Agreed with {AHMED_KHAN} by phone. Readings every 30 minutes; stop at once if DE vibration
       reaches 9.0 mm/s or the DE bearing reaches 85 °C.
       Note: MR-P101-033 recommends a stop once DE vibration has been above 7.1 mm/s for
       2 hours. Night shift could not arrange the CDU feed cut; the day shift has to decide.
03:10  K-401 discharge pressure 11.2 bar, discharge temp 186 °C. The slow decline continues;
       {intercoolerWorkOrder} (intercooler cleaning) is open.
04:00  P-101 DE vibration 7.3 mm/s, DE bearing 77 °C.
05:30  P-101 DE vibration 7.4 mm/s, DE bearing 78 °C. Above the alarm for 3 h 15 min.
06:00  Handover to the day shift.

FOR THE DAY SHIFT
-----------------
1. [{AHMED_KHAN}] Decide on P-101 this morning: change the DE bearing now or run to the planned
   stop. DE vibration has been above the 7.1 mm/s alarm since {alarmAt}. INC-2022-034: above
   7.1 mm/s for more than 2 hours was followed by bearing seizure within 18 hours.
2. [{AHMED_KHAN}] If stopping: one SKF 6311/C3 is reserved in Warehouse A, Rack 4. Plan the
   feed cut with the CDU panel.
3. [{RAJESH_KUMAR}] Keep taking P-101 readings every 30 minutes until the decision.
4. [{AHMED_KHAN}] Book the K-401 stop window for {intercoolerWorkOrder}.
5. [{AMIT_SHAH}] Book scaffold for the G-101 blade inspection ({bladeWorkOrder}, due in {bladeDueInDays} days).

{SURESH_NAIR}, Night Shift Supervisor
{shiftEnd} 06:00
"""
