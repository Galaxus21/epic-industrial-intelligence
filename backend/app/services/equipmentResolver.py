"""
EPIC Deterministic Equipment Resolver (WP-2 / GAP-02 part).
Resolves free-text operator queries and optional equipment_id parameters
to plant asset tags without LLM invocation.

Resolution Order:
1. Explicit sentinel: if equipment_id == "__all_equipment__", treat as explicit plant-wide request.
2. Tag pattern: extract candidate tags using prefixes from db_service._TYPE_MAP. A tag that is not in the
   equipment register resolves to UNKNOWN, never to a target: analysing it would dress up empty context as findings
   about equipment that does not exist.
3. Exact ID match (case-insensitive) against db.get_all_equipment_list(); an explicit equipment_id that is not
   registered is UNKNOWN for the same reason.
4. Name match: substring match against the equipment name field.
5. No match: fallback to unresolved (plant-wide path).
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.services import db_service as db
from app.services.db_service import _TYPE_MAP

SENTINEL_ALL_EQUIPMENT = "__all_equipment__"


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"
    UNKNOWN = "unknown"


@dataclass
class ResolutionResult:
    status: ResolutionStatus
    equipment_id: str | None = None
    equipment_name: str | None = None
    candidates: list[str] = field(default_factory=list)
    is_plant_wide: bool = False
    equipment: dict[str, Any] | None = None

    @property
    def is_resolved(self) -> bool:
        return self.status == ResolutionStatus.RESOLVED

    @property
    def is_ambiguous(self) -> bool:
        return self.status == ResolutionStatus.AMBIGUOUS

    @property
    def is_unresolved(self) -> bool:
        return self.status == ResolutionStatus.UNRESOLVED

    @property
    def is_unknown(self) -> bool:
        return self.status == ResolutionStatus.UNKNOWN


def get_valid_prefixes() -> list[str]:
    """Dynamically extract all equipment prefixes from db_service._TYPE_MAP."""
    prefixes: set[str] = set()
    for prefix_tuple, _ in _TYPE_MAP:
        for p in prefix_tuple:
            prefixes.add(p.strip().upper())
    # Sort descending by length so multi-letter prefixes match before single letters
    return sorted(prefixes, key=lambda x: (-len(x), x))


def build_tag_pattern() -> re.Pattern:
    """
    Build regex pattern matching plant tag conventions:
    prefix letters, hyphen, digits, optional trailing letter (e.g. P-101, K-401, HX-201A).
    """
    prefixes = get_valid_prefixes()
    escaped = [re.escape(p) for p in prefixes]
    prefix_group = "|".join(escaped)
    pattern = rf"\b(?:{prefix_group})-\d+[a-zA-Z]?\b"
    return re.compile(pattern, re.IGNORECASE)


async def resolve_equipment(
    query: str = "",
    equipment_id: str | None = None,
    equipment_list: list[dict[str, Any]] | None = None,
) -> ResolutionResult:
    """
    Pure deterministic asset resolver.
    Never calls an LLM.

    Parameters can be passed in either order or as keywords:
    - query: operator query string
    - equipment_id: optional explicit equipment ID or sentinel "__all_equipment__"
    - equipment_list: optional pre-fetched equipment list (for test isolation)
    """
    # Guard against None
    if query is None:
        query = ""
    if equipment_id is None:
        equipment_id = ""

    query_str = query.strip()
    eq_id_str = equipment_id.strip()

    # 1. Explicit sentinel: __all_equipment__
    if query_str == SENTINEL_ALL_EQUIPMENT or eq_id_str == SENTINEL_ALL_EQUIPMENT:
        return ResolutionResult(
            status=ResolutionStatus.UNRESOLVED,
            equipment_id=None,
            equipment_name="Plant-wide",
            candidates=[],
            is_plant_wide=True,
        )

    # Detect swapped positional arguments
    if query_str and eq_id_str:
        if " " in eq_id_str and " " not in query_str:
            query_str, eq_id_str = eq_id_str, query_str

    # Fetch equipment list if not supplied
    if equipment_list is None:
        equipment_list = await db.get_all_equipment_list()

    # Index equipment by uppercase ID and canonical mapping
    id_to_eq: dict[str, dict[str, Any]] = {}
    for eq in equipment_list:
        eid = str(eq.get("id", "")).strip()
        if eid:
            id_to_eq[eid.upper()] = eq

    # 2. Tag pattern extraction from query text
    tag_pattern = build_tag_pattern()
    found_tags = tag_pattern.findall(query_str)

    if found_tags:
        tags = list(dict.fromkeys(t.upper() for t in found_tags))
        unknown = [tag for tag in tags if tag not in id_to_eq]
        if unknown:
            return ResolutionResult(status=ResolutionStatus.UNKNOWN, candidates=unknown)
        candidates = [id_to_eq[tag]["id"] for tag in tags]
        if len(candidates) == 1:
            cid = candidates[0]
            eq = id_to_eq.get(cid.upper())
            return ResolutionResult(
                status=ResolutionStatus.RESOLVED,
                equipment_id=cid,
                equipment_name=eq.get("name") if eq else None,
                candidates=[cid],
                equipment=eq,
            )
        elif len(candidates) > 1:
            return ResolutionResult(
                status=ResolutionStatus.AMBIGUOUS,
                equipment_id=None,
                candidates=candidates,
            )

    # 3. Exact ID match (case-insensitive) against equipment list
    matched_ids: list[str] = []

    # Check if any known equipment ID appears as an exact whole word in query
    for eid_upper, eq in id_to_eq.items():
        pattern = rf"\b{re.escape(eid_upper)}\b"
        if re.search(pattern, query_str, re.IGNORECASE):
            matched_ids.append(eq["id"])

    # If still no match from query, but explicit equipment_id was provided, check it
    if not matched_ids and eq_id_str:
        canonical_eq = id_to_eq.get(eq_id_str.upper())
        if not canonical_eq:
            return ResolutionResult(status=ResolutionStatus.UNKNOWN, candidates=[eq_id_str.upper()])
        matched_ids.append(canonical_eq["id"])

    unique_matches = list(dict.fromkeys(matched_ids))

    if len(unique_matches) == 1:
        resolved_id = unique_matches[0]
        eq = id_to_eq.get(resolved_id.upper())
        return ResolutionResult(
            status=ResolutionStatus.RESOLVED,
            equipment_id=resolved_id,
            equipment_name=eq.get("name") if eq else None,
            candidates=[resolved_id],
            equipment=eq,
        )
    elif len(unique_matches) > 1:
        return ResolutionResult(
            status=ResolutionStatus.AMBIGUOUS,
            equipment_id=None,
            candidates=unique_matches,
        )

    # 4. Name match: Substring match against equipment name field
    name_matches: list[str] = []
    q_lower = query_str.lower()

    stop_words = frozenset({
        "what", "is", "going", "on", "in", "the", "plant", "a", "an", "and", "or",
        "to", "for", "of", "with", "at", "by", "from", "how", "why", "where", "when",
        "who", "all", "equipment", "status", "overview", "report", "issue", "alarm",
        "running", "operating", "vibrating", "today", "now"
    })

    if q_lower:
        # Check if full equipment name is contained in query
        for eid_upper, eq in id_to_eq.items():
            name = (eq.get("name") or "").strip()
            if len(name) >= 3 and name.lower() in q_lower:
                name_matches.append(eq["id"])

        # If no full name matches, check if query words (non-stop) match name
        if not name_matches:
            words = [w for w in re.findall(r"[a-zA-Z0-9]+", q_lower) if w not in stop_words and len(w) >= 3]
            if words:
                for eid_upper, eq in id_to_eq.items():
                    name_lower = (eq.get("name") or "").lower()
                    if all(w in name_lower for w in words):
                        name_matches.append(eq["id"])

    unique_name_matches = list(dict.fromkeys(name_matches))
    if len(unique_name_matches) == 1:
        resolved_id = unique_name_matches[0]
        eq = id_to_eq.get(resolved_id.upper())
        return ResolutionResult(
            status=ResolutionStatus.RESOLVED,
            equipment_id=resolved_id,
            equipment_name=eq.get("name") if eq else None,
            candidates=[resolved_id],
            equipment=eq,
        )
    elif len(unique_name_matches) > 1:
        return ResolutionResult(
            status=ResolutionStatus.AMBIGUOUS,
            equipment_id=None,
            candidates=unique_name_matches,
        )

    # 5. Unresolved fallback -> plant-wide path
    return ResolutionResult(
        status=ResolutionStatus.UNRESOLVED,
        equipment_id=None,
        equipment_name=None,
        candidates=[],
        is_plant_wide=True,
    )
