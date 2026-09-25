"""
EPIC — An answer names only what was retrieved.

A model can name an incident, a regulation or a record id that no retriever returned: a copy of an example it was
shown, or a memory from training. The prompts ask it not to; this module enforces it, once, for the fan-out synthesis
(llm_service._verify_citations), the conversational reply (llm_service.synthesize_conversational_query) and the ReAct
investigation (reactLoop.verify_react_citations):
- a source whose doc_id is not a retrieved record is downgraded to ai_inference;
- a similar incident whose incident_id is not a retrieved record is dropped;
- a compliance issue whose regulation names no retrieved open compliance issue (its id or its standard) is dropped;
- a record id anywhere else in the answer that neither was retrieved nor appears in the retrieved data is replaced by
  UNVERIFIED_ID_MARK.
Record ids are upper case by construction and matched as written: a lower-case "doc-999" is not caught, because
matching without case would also replace ordinary words such as "Gen-2".
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterable

# The record id prefixes promptSafety.SOURCE_ID_RULES names (testAnswerGrounding pins the two together).
RECORD_ID_PREFIXES = ("UPLOAD", "FEEDBACK", "DOC", "GEN", "INC", "LESSON", "DEF", "MR", "CI")
RECORD_ID_PATTERN = re.compile(r"\b(?:" + "|".join(RECORD_ID_PREFIXES) + r")(?:-[A-Z0-9]+)+\b")
UNVERIFIED_ID_MARK = "[unverified reference]"
AI_INFERENCE = "ai_inference"
EMPTY_DOC_IDS = (None, "", "null")
COMPLIANCE_TERM_KEYS = ("id", "standard")
# Written by the pipeline from what it retrieved, or by this module, never by the model: not checked.
PIPELINE_FIELDS = frozenset({"source_verification", "investigation_trace", "tools_used", "verification_note"})


def groundAnswer(
    result: dict[str, Any],
    *,
    evidenceIds: set[str],
    complianceRecords: Iterable[Any],
    retrieved: Any,
) -> dict[str, Any]:
    """`result` with every unretrieved citation, incident, compliance issue and record id removed or downgraded.

    `evidenceIds` are the ids of the records retrieved, `complianceRecords` the compliance records retrieved, and
    `retrieved` everything the model was shown, so an id a retrieved document mentions may be repeated."""
    if not isinstance(result, dict):
        return result
    verified, downgraded = _groundSources(result.get("sources"), evidenceIds)
    droppedIncidents = _keepOnly(result, "similar_incidents", lambda incident: _incidentId(incident) in evidenceIds)
    terms = complianceTerms(complianceRecords)
    droppedIssues = _keepOnly(result, "compliance_issues", lambda issue: _namesAny(issue.get("regulation"), terms))
    mentionedIds = evidenceIds | set(RECORD_ID_PATTERN.findall(json.dumps(retrieved, default=str)))
    unverifiedIds: set[str] = set()
    for key in [key for key in result if key not in PIPELINE_FIELDS]:
        result[key] = _scrubIds(result[key], mentionedIds, unverifiedIds)
    result["source_verification"] = {
        "known_evidence_ids": sorted(evidenceIds),
        "verified_citations": verified,
        "downgraded_citations": downgraded,
        "dropped_incidents": droppedIncidents,
        "dropped_compliance_issues": droppedIssues,
        "unverified_ids": sorted(unverifiedIds),
    }
    return result


def complianceTerms(records: Iterable[Any]) -> set[str]:
    """The id and the standard of every open issue in the compliance records."""
    terms: set[str] = set()
    for record in records:
        issues = record.get("issues") if isinstance(record, dict) else None
        for issue in issues or []:
            if isinstance(issue, dict):
                terms.update(str(issue[key]) for key in COMPLIANCE_TERM_KEYS if issue.get(key))
    return terms


def _groundSources(sources: Any, evidenceIds: set[str]) -> tuple[int, int]:
    verified, downgraded = 0, 0
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        docId = source.get("doc_id")
        if source.get("source_type") == AI_INFERENCE or docId in EMPTY_DOC_IDS:
            source.update(doc_id=None, source_type=AI_INFERENCE, verified=False)
        elif str(docId) in evidenceIds:
            source["verified"] = True
            verified += 1
        else:
            source.update(doc_id=None, source_type=AI_INFERENCE, verified=False,
                          verification_note=f"Cited id '{docId}' was not in the retrieved evidence")
            downgraded += 1
    return verified, downgraded


def _keepOnly(result: dict[str, Any], key: str, isRetrieved: Callable[[dict[str, Any]], bool]) -> int:
    """Keep the entries of result[key] that isRetrieved accepts, marked verified; return how many were dropped."""
    if key not in result:
        return 0
    entries = [entry for entry in result[key] or [] if isinstance(entry, dict)]
    kept = [{**entry, "verified": True} for entry in entries if isRetrieved(entry)]
    result[key] = kept
    return len(entries) - len(kept)


def _incidentId(incident: dict[str, Any]) -> str:
    return str(incident.get("incident_id") or incident.get("id") or "")


def _namesAny(text: Any, terms: set[str]) -> bool:
    """Whether text names one of the terms as a whole word, ignoring case."""
    if not isinstance(text, str):
        return False
    return any(re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", text, re.IGNORECASE) for term in terms)


def _scrubIds(value: Any, mentionedIds: set[str], unverifiedIds: set[str]) -> Any:
    if isinstance(value, str):
        return RECORD_ID_PATTERN.sub(lambda match: _checkedId(match.group(0), mentionedIds, unverifiedIds), value)
    if isinstance(value, list):
        return [_scrubIds(item, mentionedIds, unverifiedIds) for item in value]
    if isinstance(value, dict):
        return {key: item if key in PIPELINE_FIELDS else _scrubIds(item, mentionedIds, unverifiedIds)
                for key, item in value.items()}
    return value


def _checkedId(token: str, mentionedIds: set[str], unverifiedIds: set[str]) -> str:
    # Every record id carries a digit; a word such as GEN-SET does not, and is left alone.
    if token in mentionedIds or not any(character.isdigit() for character in token):
        return token
    unverifiedIds.add(token)
    return UNVERIFIED_ID_MARK
