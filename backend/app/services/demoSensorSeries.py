"""
EPIC — Thirty days of readings for every demo sensor.

Each series has one reading a day (at 18:00) for the 29 days before the seed and ends with the live reading at the seed moment,
so the history and equipment.current_readings never disagree. Between anchor days it moves in straight lines with a
little repeatable noise; on an anchor day it takes the anchor's exact value, because a maintenance record quotes that
reading (P-101 DE vibration 6.1 mm/s on the spectrum-check day, for one).
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Any

from app.services import demoTimeline as timeline
from app.services.sensorReadings import historyPoint

HISTORY_DAYS = 29
# Past daily readings sit at a fixed clock time, so a day's reading never depends on when the seed ran.
DAILY_READING_HOUR = 18

# equipment -> sensor -> (anchors as (days ago, value), noise amplitude, decimals). Anchors run oldest first and the
# oldest sits at HISTORY_DAYS; the live reading closes each series.
SERIES_SHAPES: dict[str, dict[str, tuple[list[tuple[int, float]], float, int]]] = {
    "P-101": {
        "vibration_de": ([(HISTORY_DAYS, 4.3), (16, 4.4), (timeline.P101_SPECTRUM_CHECK_DAYS_AGO, 6.1), (1, 7.0)], 0.08, 2),
        "bearing_temp_de": ([(HISTORY_DAYS, 57), (16, 58), (timeline.P101_SPECTRUM_CHECK_DAYS_AGO, 66), (1, 74)], 0.6, 1),
        "discharge_pressure": ([(HISTORY_DAYS, 8.4), (1, 8.3)], 0.06, 2),
        "flow_rate": ([(HISTORY_DAYS, 247), (1, 245)], 3.0, 0),
    },
    "P-202": {
        "vibration_de": ([(HISTORY_DAYS, 3.0), (timeline.P202_LAST_ROUTE_DAYS_AGO, 3.1), (1, 3.1)], 0.08, 2),
        "bearing_temp_de": ([(HISTORY_DAYS, 50), (timeline.P202_LAST_ROUTE_DAYS_AGO, 51), (1, 51)], 0.6, 1),
    },
    "HX-201": {
        "tube_side_dp": ([(HISTORY_DAYS, 1.7), (1, 1.8)], 0.03, 2),
        "shell_side_temp_out": ([(HISTORY_DAYS, 143), (1, 142)], 0.8, 1),
    },
    "V-301": {
        "level": ([(HISTORY_DAYS, 63), (1, 65)], 1.5, 0),
        "pressure": ([(HISTORY_DAYS, 3.2), (1, 3.2)], 0.05, 2),
    },
    "K-401": {
        # The filter chokes until the change, jumps back to 12.4 bar, then falls again as the intercooler fouls.
        "discharge_pressure": ([(HISTORY_DAYS, 12.1), (timeline.K401_FILTER_CHANGE_DAYS_AGO + 1, 10.6),
                                (timeline.K401_FILTER_CHANGE_DAYS_AGO, 12.4), (7, 11.9), (1, 11.3)], 0.05, 2),
        "discharge_temp": ([(HISTORY_DAYS, 176), (timeline.K401_FILTER_CHANGE_DAYS_AGO + 1, 177),
                            (timeline.K401_FILTER_CHANGE_DAYS_AGO, 176), (7, 180), (1, 185)], 0.5, 1),
        "vibration": ([(HISTORY_DAYS, 3.3), (1, 3.4)], 0.07, 2),
    },
    "G-101": {
        "vibration": ([(HISTORY_DAYS, 2.7), (1, 2.8)], 0.07, 2),
        "current": ([(HISTORY_DAYS, 146), (1, 145)], 2.0, 0),
    },
}


def demoSensorSeries(now: datetime, equipment: list[dict[str, Any]]) -> list[tuple[str, str, list[dict[str, Any]]]]:
    """(equipment ID, sensor key, readings) for every live reading of every demo asset."""
    series = []
    for asset in equipment:
        shapes = SERIES_SHAPES[asset["id"]]
        for sensorKey, reading in asset["current_readings"].items():
            anchors, noise, decimals = shapes[sensorKey]
            series.append((asset["id"], sensorKey, _readings(now, asset["id"], sensorKey, reading, anchors, noise,
                                                             decimals)))
    return series


def _readings(now: datetime, equipmentId: str, sensorKey: str, reading: dict[str, Any],
              anchors: list[tuple[int, float]], noise: float, decimals: int) -> list[dict[str, Any]]:
    # Seeded by the sensor's name so a re-seed on the same day writes the same values.
    generator = random.Random(f"{equipmentId}:{sensorKey}")
    anchorDays = dict(anchors)
    points = []
    for days in range(HISTORY_DAYS, 0, -1):
        value = anchorDays.get(days)
        if value is None:
            value = _interpolated(anchors, days) + generator.uniform(-noise, noise)
        readingTime = timeline.daysAgo(now, days).replace(hour=DAILY_READING_HOUR, minute=0, second=0)
        points.append(historyPoint(readingTime, _rounded(value, decimals), reading["unit"]))
    points.append(historyPoint(now, reading["value"], reading["unit"]))
    return points


def _interpolated(anchors: list[tuple[int, float]], days: int) -> float:
    for (olderDays, olderValue), (newerDays, newerValue) in zip(anchors, anchors[1:]):
        if newerDays <= days <= olderDays:
            share = (olderDays - days) / (olderDays - newerDays)
            return olderValue + share * (newerValue - olderValue)
    raise ValueError(f"day {days} lies outside the anchors {anchors}")


def _rounded(value: float, decimals: int) -> float | int:
    return round(value, decimals) if decimals else round(value)

