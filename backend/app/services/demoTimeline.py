"""
EPIC — The demo plant's calendar: every date and dated ID the demo dataset and its sample documents share.

The demo tells one story, dated backwards from the moment it is seeded, so the database rows, the sensor series and
the sample documents agree on every day they mention. Each module reads its days from here instead of counting its
own. All names, procedures (SOP-*), limits and events in the demo are fictional site values; none cites an external
standard.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

DATE_FORMAT = "%Y-%m-%d"
DOCUMENT_DATE_FORMAT = "%d %b %Y"
FILE_DATE_FORMAT = "%d%b%Y"

# P-101: monthly regrease routes, the spectrum check that found DE bearing damage, and the missed route.
P101_ROUTE_BEFORE_LAST_DAYS_AGO = 63
P101_LAST_ROUTE_DAYS_AGO = 33
P101_SPECTRUM_CHECK_DAYS_AGO = 8
P101_REGREASE_INTERVAL_DAYS = 30
P101_ROUTE_OVERDUE_DAYS = P101_LAST_ROUTE_DAYS_AGO - P101_REGREASE_INTERVAL_DAYS
# The night shift before the seed saw DE vibration cross the alarm at this clock time.
P101_ALARM_CLOCK_TIME = "02:15"

# P-202: annual seal inspection and the latest monthly route.
P202_SEAL_INSPECTION_DAYS_AGO = 60
P202_LAST_ROUTE_DAYS_AGO = 8
P202_ROUTE_INTERVAL_DAYS = 30

# K-401: the choked-filter incident, the filter change that fixed it, and the check that ruled the filter out.
K401_FILTER_CHANGE_DAYS_AGO = 14
K401_FILTER_INTERVAL_DAYS = 60
K401_DECLINE_CHECK_DAYS_AGO = 2
K401_INTERCOOLER_WORK_ORDER_DAYS_AGO = 2
K401_INTERCOOLER_PLANNED_IN_DAYS = 5

# HX-201, V-301 and G-101 inspections.
HX201_TUBE_INSPECTION_DAYS_AGO = 90
HX201_PERFORMANCE_CHECK_DAYS_AGO = 45
HX201_PERFORMANCE_INTERVAL_DAYS = 90
V301_EXTERNAL_INSPECTION_DAYS_AGO = 30
V301_INSPECTION_INTERVAL_DAYS = 90
G101_BLADE_INSPECTION_DAYS_AGO = 168
G101_BLADE_INSPECTION_INTERVAL_DAYS = 182
G101_WORK_ORDER_DAYS_AGO = 5

# Sequence numbers of the dated records; the year comes from the day each record falls on.
K401_INCIDENT_NUMBER = 31
K401_FILTER_WORK_ORDER_NUMBER = 47
G101_WORK_ORDER_NUMBER = 49
K401_INTERCOOLER_WORK_ORDER_NUMBER = 52


def seedMoment() -> datetime:
    """The instant the demo is dated from: now, in UTC, without the offset (the stored format)."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def daysAgo(now: datetime, days: int) -> datetime:
    return now - timedelta(days=days)


def dateString(now: datetime, days: int) -> str:
    """The day `days` before `now` as YYYY-MM-DD; a negative count is a day ahead."""
    return daysAgo(now, days).strftime(DATE_FORMAT)


def documentDate(now: datetime, days: int) -> str:
    return daysAgo(now, days).strftime(DOCUMENT_DATE_FORMAT)


def datedId(prefix: str, now: datetime, days: int, number: int) -> str:
    """An ID such as INC-2026-0031, numbered within the year of the day it belongs to."""
    return f"{prefix}-{daysAgo(now, days).year}-{number:04d}"


def k401IncidentId(now: datetime) -> str:
    return datedId("INC", now, K401_FILTER_CHANGE_DAYS_AGO, K401_INCIDENT_NUMBER)


def k401FilterWorkOrderId(now: datetime) -> str:
    return datedId("WO", now, K401_FILTER_CHANGE_DAYS_AGO, K401_FILTER_WORK_ORDER_NUMBER)


def k401IntercoolerWorkOrderId(now: datetime) -> str:
    return datedId("WO", now, K401_INTERCOOLER_WORK_ORDER_DAYS_AGO, K401_INTERCOOLER_WORK_ORDER_NUMBER)


def g101WorkOrderId(now: datetime) -> str:
    return datedId("WO", now, G101_WORK_ORDER_DAYS_AGO, G101_WORK_ORDER_NUMBER)
