"""
EPIC — An extracted entity is one the document states.

A model asked for a document's entities can return values the document does not contain: a copy of an example it was
shown, or a guess. Every identifier and figure it returns is checked against the document text before the pipeline
stores or links anything (documentEntities.extractEntities):
- a list entry (equipment tag, incident id, person, regulation, symptom, measurement, date) is kept only when the text
  contains it;
- an equipment object is kept only when the text names its tag; a name, type, location, manufacturer or model the text
  does not contain is dropped, and so is a status that is not one of EQUIPMENT_STATUSES;
- an incident is dropped when it carries a reference the text does not contain, and keeps only the tags the text names;
- a defect is dropped unless the text names its equipment, and a sensor reading unless the text names its equipment
  and contains its value;
- a document type that is not one of DOCUMENT_TYPES becomes DEFAULT_DOCUMENT_TYPE.
The summary, titles, descriptions and severities are the model's own words about the text and are not checked. A value
is checked for being in the text, not for belonging to the entity it is attached to. A reading's timestamp and an
incident's date are not checked either: a model may rightly rewrite "14 August 2022" as 2022-08-14, which is not in
the text as written.
"""
from __future__ import annotations

import re
from typing import Any

LIST_FIELDS = ("equipment_ids", "incident_ids", "people", "regulations", "symptoms", "measurements", "dates")
EQUIPMENT_TEXT_FIELDS = ("name", "type", "location", "manufacturer", "model")
EQUIPMENT_STATUSES = frozenset({"Operating", "Shutdown", "Standby", "Fault"})
DOCUMENT_TYPES = frozenset({"manual", "sop", "inspection_report", "incident_report", "commissioning", "drawing",
                            "work_order", "other"})
DEFAULT_DOCUMENT_TYPE = "other"
INCIDENT_REFERENCE_KEYS = ("ref", "incident_number")
# A value matches only as a whole: B-201 is not found inside SOP-B-201, B-2019 or B-201_OLD, 7.2 not inside 17.25,
# and 0.4 not inside -0.4.
BEFORE_VALUE = r"(?<![A-Za-z0-9._-])"
AFTER_VALUE = r"(?![A-Za-z0-9_]|\.\d|-[A-Za-z0-9])"


def groundEntities(entities: Any, text: str) -> dict[str, Any]:
    """The entities in `entities` that `text` states, with every unstated value removed (see the module rules)."""
    if not isinstance(entities, dict):
        return {}
    grounded = dict(entities)
    if "document_type" in entities and not _oneOf(entities["document_type"], DOCUMENT_TYPES):
        grounded["document_type"] = DEFAULT_DOCUMENT_TYPE
    for field in LIST_FIELDS:
        if field in entities:
            grounded[field] = list(dict.fromkeys(value for value in _texts(entities[field]) if appearsIn(value, text)))
    if "equipment" in entities:
        grounded["equipment"] = [_groundEquipment(equipment, text) for equipment in _objects(entities["equipment"])
                                 if appearsIn(equipment.get("id"), text)]
    if "incidents" in entities:
        grounded["incidents"] = [_groundIncident(incident, text) for incident in _objects(entities["incidents"])
                                 if _referenceStated(incident, text)]
    if "defects" in entities:
        grounded["defects"] = [defect for defect in _objects(entities["defects"])
                               if appearsIn(defect.get("equipment_id"), text)]
    if "sensors" in entities:
        grounded["sensors"] = [sensor for sensor in _objects(entities["sensors"])
                               if appearsIn(sensor.get("equipment_id"), text)
                               and appearsIn(_leadingFigure(sensor.get("value")), text)]
    return grounded


def appearsIn(value: Any, text: str) -> bool:
    """Whether `text` contains `value` as a whole, ignoring case and the spacing between its words."""
    words = str(value).split() if isinstance(value, (str, int, float)) else []
    if not words:
        return False
    pattern = r"\s*".join(re.escape(word) for word in words)
    return re.search(f"{BEFORE_VALUE}{pattern}{AFTER_VALUE}", text, re.IGNORECASE) is not None


def _groundEquipment(equipment: dict[str, Any], text: str) -> dict[str, Any]:
    kept = {key: value for key, value in equipment.items()
            if key not in EQUIPMENT_TEXT_FIELDS or appearsIn(value, text)}
    if not _oneOf(kept.get("status"), EQUIPMENT_STATUSES):
        kept.pop("status", None)
    return kept


def _groundIncident(incident: dict[str, Any], text: str) -> dict[str, Any]:
    return {**incident, "equipment_ids": [tag for tag in _texts(incident.get("equipment_ids")) if appearsIn(tag, text)]}


def _referenceStated(incident: dict[str, Any], text: str) -> bool:
    references = [incident[key] for key in INCIDENT_REFERENCE_KEYS if incident.get(key)]
    return all(appearsIn(reference, text) for reference in references)


def _leadingFigure(value: Any) -> str:
    # A reading may arrive as "7.2 mm/s"; the pipeline stores its first word as the number (doc_entity_mapper).
    words = str(value).split() if value is not None else []
    return words[0] if words else ""


def _oneOf(value: Any, allowed: frozenset[str]) -> bool:
    # Model output: a list or an object where a string belongs cannot even be looked up in a set.
    return isinstance(value, str) and value in allowed


def _texts(values: Any) -> list[str]:
    return [str(value) for value in values if isinstance(value, (str, int, float))] if isinstance(values, list) else []


def _objects(values: Any) -> list[dict[str, Any]]:
    return [value for value in values if isinstance(value, dict)] if isinstance(values, list) else []
