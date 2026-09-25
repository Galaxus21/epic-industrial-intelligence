"""
EPIC — Shapes retrieved evidence into the text a chat model reads.

Every evidence token costs time on a local model and money on OpenAI, and a local model whose context window is
too small drops what does not fit without saying so (Ollama logged "truncating input prompt", 6,774 tokens cut to
2,050, for the P-101 demo question on 2026-09-24). So each fact goes into the prompt once, compactly:
- compact JSON that keeps characters such as "°" and "—" as they are, instead of multi-token "\\u00b0" escapes;
- no empty values, no internal markers (keys starting with "_"), no row bookkeeping (timestamps, search keywords,
  registry flags), and no flags that only the UI reads at the top of a retriever's result;
- each sensor series summarized to its range and last readings instead of every point;
- the equipment profile without the parts that have their own prompt section, each technician reduced to who they
  are and what they know, and each downstream asset reduced to what it is and how it is running;
- the maintenance section without the readings, scores, records and incidents the profile already carries.
The UI still receives the full data through the stream events; this only shapes what the model reads.
"""
from __future__ import annotations

import json
from typing import Any

UI_ONLY_TOP_LEVEL_KEYS = frozenset({"highlights", "vector_search_used", "degraded", "source"})
ROW_BOOKKEEPING_KEYS = frozenset({"created_at", "keywords", "discovered", "manually_registered", "source_documents"})
INTERNAL_KEY_PREFIX = "_"
RECENT_READINGS_KEPT = 7
DATE_LENGTH = len("2026-09-24")
# The compliance record has its own prompt section, so the profile's copy is left out.
PROFILE_KEYS_WITH_OWN_SECTION = frozenset({"compliance"})
TECHNICIAN_KEYS_KEPT = ("name", "role", "expertise", "certifications")
DOWNSTREAM_KEYS_KEPT = ("id", "name", "type", "status", "criticality")
# The maintenance section repeats readings and scores the profile already carries, and a subset of its records.
MAINTENANCE_KEYS_IN_PROFILE = frozenset({"recent_maintenance", "current_readings", "health_score", "failure_probability"})
SIMILAR_INCIDENTS_KEY = "similar_incidents"


def promptJson(value: Any) -> str:
    """Compact JSON of `value` without empty values, internal markers, row bookkeeping or UI-only flags."""
    if isinstance(value, dict):
        value = {key: item for key, item in value.items() if key not in UI_ONLY_TOP_LEVEL_KEYS}
    return json.dumps(_pruned(value), ensure_ascii=False, separators=(",", ":"), default=str)


def equipmentProfileForPrompt(equipmentContext: dict[str, Any]) -> dict[str, Any]:
    """The equipment profile minus sections the prompt carries elsewhere, with every sensor series summarized."""
    profile = {key: value for key, value in equipmentContext.items() if key not in PROFILE_KEYS_WITH_OWN_SECTION}
    sensorHistory = profile.get("sensor_history")
    if isinstance(sensorHistory, dict):
        profile["sensor_history"] = {name: summarizeSeries(points) for name, points in sensorHistory.items()}
    for key, keptKeys in (("technicians", TECHNICIAN_KEYS_KEPT), ("downstream_equipment", DOWNSTREAM_KEYS_KEPT)):
        if isinstance(profile.get(key), list):
            profile[key] = [_picked(entry, keptKeys) for entry in profile[key]]
    return profile


def maintenanceForPrompt(maintenanceContext: dict[str, Any], equipmentContext: dict[str, Any] | None = None) -> dict[str, Any]:
    """The maintenance retriever's result minus what the equipment profile already carries."""
    maintenance = {key: value for key, value in maintenanceContext.items() if key not in MAINTENANCE_KEYS_IN_PROFILE}
    profileIncidentIds = {incident.get("id") for incident in (equipmentContext or {}).get("incidents") or []
                          if isinstance(incident, dict)}
    similar = maintenance.get(SIMILAR_INCIDENTS_KEY)
    if isinstance(similar, list) and profileIncidentIds:
        maintenance[SIMILAR_INCIDENTS_KEY] = [
            incident for incident in similar
            if not (isinstance(incident, dict) and _incidentId(incident) in profileIncidentIds)
        ]
    return maintenance


def summarizeSeries(points: Any) -> Any:
    """First and last reading, range, and the most recent readings of one sensor series."""
    if not isinstance(points, list):
        return points
    readings = [point for point in points if isinstance(point, dict) and isinstance(point.get("value"), (int, float))]
    if not readings:
        return {"readings": 0}
    values = [reading["value"] for reading in readings]
    return {
        "unit": readings[-1].get("unit"),
        "readings": len(readings),
        "first": _datedValue(readings[0]),
        "last": _datedValue(readings[-1]),
        "min": min(values),
        "max": max(values),
        "recent": [_datedValue(reading) for reading in readings[-RECENT_READINGS_KEPT:]],
    }


def _picked(entry: Any, keptKeys: tuple[str, ...]) -> Any:
    if not isinstance(entry, dict):
        return entry
    return {key: entry[key] for key in keptKeys if key in entry}


def _incidentId(incident: dict[str, Any]) -> Any:
    # A semantic hit names its incident as incident_id; a keyword hit is the incident row itself.
    return incident.get("id") or incident.get("incident_id")


def _datedValue(reading: dict[str, Any]) -> list[Any]:
    return [str(reading.get("ts", ""))[:DATE_LENGTH], reading["value"]]


def _pruned(value: Any) -> Any:
    if isinstance(value, dict):
        kept = {
            key: _pruned(item) for key, item in value.items()
            if not str(key).startswith(INTERNAL_KEY_PREFIX) and key not in ROW_BOOKKEEPING_KEYS
        }
        return {key: item for key, item in kept.items() if not _isEmpty(item)}
    if isinstance(value, list):
        return [_pruned(item) for item in value]
    return value


def _isEmpty(value: Any) -> bool:
    # 0 and False are evidence ("0 overdue tasks"), so only None and empty containers or strings are dropped.
    return value is None or (isinstance(value, (str, list, dict)) and len(value) == 0)
