"""
EPIC — Search by keyword in PostgreSQL, for when semantic search cannot run or finds nothing.

It is not semantic: an incident or a document section matches only when it contains a word of the query. The search
result carries `degraded` as the caller says, because only the caller knows whether semantic search ran at all.
"""
from __future__ import annotations

from typing import Any

from app.services import db_service as db
from app.services.db_service import maxSearchKeywords

KEYWORD_SOURCE = "keyword_fallback"
# A word of three letters or fewer (the, and, for) carries no meaning to match on.
MIN_KEYWORD_CHARS = 4
SECTION_TEXT_CHARS = 600


class SearchResult(dict):
    """Degradation-aware search result payload that also behaves like a sequence of items.

    Serializes to JSON as: {"items": [...], "source": "...", "degraded": bool}
    Allows dict key lookups: res["degraded"], res["source"], res["items"]
    Allows list operations: len(res), res[0], for item in res
    """
    def __init__(self, items: list[dict[str, Any]], source: str, degraded: bool):
        super().__init__(items=items, source=source, degraded=degraded)

    def __iter__(self):
        return iter(self["items"])

    def __len__(self):
        return len(self["items"])

    def __getitem__(self, k):
        if isinstance(k, (int, slice)):
            return self["items"][k]
        return super().__getitem__(k)


def extract_fallback_keywords(query: str, max_keywords: int = maxSearchKeywords) -> list[str]:
    """Extract, deduplicate, and cap fallback keywords from query while preserving order."""
    seen: set[str] = set()
    keywords: list[str] = []
    for word in query.lower().split():
        if len(word) >= MIN_KEYWORD_CHARS and word not in seen:
            seen.add(word)
            keywords.append(word)
            if len(keywords) >= max_keywords:
                break
    return keywords


async def keywordIncidents(query: str, limit: int, degraded: bool) -> SearchResult:
    """Incidents sharing a keyword with the query, plant-wide."""
    results = await db.find_similar_incidents(extract_fallback_keywords(query), exclude_equipment_id=None)
    for result in results:
        result["_source"] = KEYWORD_SOURCE
    return SearchResult(items=results[:limit], source=KEYWORD_SOURCE, degraded=degraded)


async def keywordSections(query: str, equipmentId: str | None, limit: int, degraded: bool) -> SearchResult:
    """Sections containing a keyword of the query, from the equipment's documents or, plant-wide, every document;
    that also reaches documents the app writes itself, which are never vector-indexed."""
    documents = await db.get_equipment_documents(equipmentId) if equipmentId else await db.list_all_documents()
    keywords = extract_fallback_keywords(query)
    sections = [
        {
            "doc_id": document["id"],
            "document": document["name"],
            "section": sectionId,
            "text": text[:SECTION_TEXT_CHARS],
            "type": document.get("type", ""),
            "origin": document.get("origin"),
            "_source": KEYWORD_SOURCE,
        }
        for document in documents
        for sectionId, text in (document.get("sections") or {}).items()
        if any(keyword in text.lower() for keyword in keywords)
    ]
    return SearchResult(items=sections[:limit], source=KEYWORD_SOURCE, degraded=degraded)
