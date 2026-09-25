"""
AI Operations Brain — Vector Search Service
Wraps Qdrant for semantic similarity search: every document section and incident description is embedded and indexed
so the agent pipeline finds relevant knowledge by *meaning*, not just keyword overlap.

- Collections are named by vector size, so switching embedding model never mixes sizes: "op_documents_<dim>" holds
  document sections (chunks of at most 600 characters), "op_incidents_<dim>" incident and defect descriptions.
- Embeddings come from modelRegistry's EmbeddingModel: OpenAI text-embedding-3-small (1536 dims) with an
  OPENAI_API_KEY, otherwise Ollama nomic-embed-text (768 dims). Without a working one nothing is written to Qdrant and
  search falls back to PostgreSQL keyword matching (keywordSearch.py), which is NOT semantic.
- This module keeps the one Qdrant connection and its health state; what it runs on the connected client is in
  qdrantOperations.py.
- Health honesty: is_active() only says Qdrant is reachable. get_health() says whether a semantic index exists
  (embeddings work AND points are indexed); a reachable Qdrant with empty collections is NOT a working search.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from app.core.config import settings
from app.services import qdrantOperations as qdrant
from app.services.keywordSearch import SearchResult, extract_fallback_keywords, keywordIncidents, keywordSections
from app.services.providers import modelRegistry

# Names this module exported before the keyword search moved out; callers still import them here.
__all__ = [
    "SearchResult", "extract_fallback_keywords", "clear_document_index", "clear_incident_index",
    "delete_document_points", "delete_incident_points", "embeddings_available", "get_document_collection",
    "get_health", "get_incident_collection", "get_vector_dim", "index_document_section", "index_incident",
    "is_active", "reset_client_state", "search_relevant_docs", "search_similar_incidents", "set_probe_interval",
]

logger = logging.getLogger(__name__)

POINT_ID_SCHEME = "epic"
QDRANT_TIMEOUT_SECONDS = 5
INCIDENT_PAYLOAD_DESCRIPTION_CHARS = 300
DOCUMENT_PAYLOAD_TEXT_CHARS = 600
HEALTH_PROBE_TEXT = "health probe"


def get_vector_dim() -> int:
    """Obtain active vector dimension dynamically from the embedding model."""
    return modelRegistry.getEmbeddingModel().dimension


def get_incident_collection() -> str:
    """Namespace incident collection by vector dimension."""
    return f"op_incidents_{get_vector_dim()}"


def get_document_collection() -> str:
    """Namespace document collection by vector dimension."""
    return f"op_documents_{get_vector_dim()}"


_qdrant_client: Any = None
_qdrant_ok: bool = False
_last_qdrant_probe: float = 0.0
_PROBE_INTERVAL_SECONDS: float = 30.0


def set_probe_interval(seconds: float) -> None:
    """Configurable re-probe interval for testing and runtime tuning."""
    global _PROBE_INTERVAL_SECONDS
    _PROBE_INTERVAL_SECONDS = seconds


def reset_client_state() -> None:
    """Reset cached client and probe state (useful in tests)."""
    global _qdrant_client, _qdrant_ok, _last_qdrant_probe
    _qdrant_client = None
    _qdrant_ok = False
    _last_qdrant_probe = 0.0


async def _get_client():
    """The connected client, or None while Qdrant is unreachable; after a failure it is probed again only once the
    probe interval has passed. A collection of another vector size raises ValueError."""
    global _qdrant_client, _qdrant_ok, _last_qdrant_probe
    now = time.monotonic()
    if _qdrant_client is not None and _qdrant_ok:
        return _qdrant_client
    if not _qdrant_ok and _last_qdrant_probe > 0 and (now - _last_qdrant_probe < _PROBE_INTERVAL_SECONDS):
        return None

    _last_qdrant_probe = now
    try:
        from qdrant_client import AsyncQdrantClient

        client = AsyncQdrantClient(url=settings.qdrant_url, timeout=QDRANT_TIMEOUT_SECONDS)
        await client.get_collections()
        await qdrant.ensureCollections(client, (get_incident_collection(), get_document_collection()),
                                       get_vector_dim())
        _qdrant_client = client
        _qdrant_ok = True
        logger.info("Qdrant connected at %s — semantic search active", settings.qdrant_url)
    except ValueError:
        raise
    except Exception as exc:
        logger.warning("Qdrant unavailable (%s) — falling back to PostgreSQL keyword search", exc, exc_info=True)
        _qdrant_ok = False
        _qdrant_client = None
    return _qdrant_client if _qdrant_ok else None


async def _embed(text: str) -> list[float] | None:
    """Generate an embedding vector via the active EmbeddingModel. Returns None if unavailable."""
    embeddingModel = modelRegistry.getEmbeddingModel()
    try:
        return await embeddingModel.embed(text)
    except Exception as exc:
        logger.warning("Embedding failed via %s: %s", type(embeddingModel).__name__, exc, exc_info=True)
        return None


def _stable_id(prefix: str, text: str) -> str:
    """Deterministic point ID, so indexing the same item again overwrites it instead of duplicating it.

    Qdrant accepts only unsigned integers and UUIDs as point IDs (its 400 reply to any other string: "valid values
    are either an unsigned integer or a UUID", Qdrant v1.9.2, seen 2026-09-24), hence a name-based UUID.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{POINT_ID_SCHEME}:{prefix}:{text}"))


async def index_incident(incident_id: str, title: str, description: str, equipment_id: str, severity: str = "",
                         date: str = "") -> None:
    """Index an incident for semantic similarity search."""
    payload = {
        "incident_id": incident_id, "title": title, "description": description[:INCIDENT_PAYLOAD_DESCRIPTION_CHARS],
        "equipment_id": equipment_id, "severity": severity, "date": date,
    }
    await _upsert(get_incident_collection, _stable_id("inc", incident_id), f"{title}. {description}".strip(),
                  payload, f"Incident {incident_id}")


async def index_document_section(doc_id: str, doc_name: str, section_id: str, text: str,
                                 equipment_ids: list[str] | None = None, doc_type: str = "") -> None:
    """Index a document text chunk for retrieval during agent queries."""
    payload = {
        "doc_id": doc_id, "doc_name": doc_name, "section": section_id, "text": text[:DOCUMENT_PAYLOAD_TEXT_CHARS],
        "equipment_ids": equipment_ids or [], "doc_type": doc_type,
    }
    await _upsert(get_document_collection, _stable_id("doc", f"{doc_id}-{section_id}"), text, payload,
                  f"Document {doc_id} section {section_id}")


async def _upsert(collection: Callable[[], str], pointId: str, text: str, payload: dict[str, Any], label: str) -> None:
    client = await _get_client()
    if client is None:
        return
    vector = await _embed(text)
    if vector is None:
        logger.warning("%s NOT semantically indexed — embeddings unavailable (keyword fallback only)", label)
        return
    try:
        from qdrant_client.models import PointStruct

        await client.upsert(collection_name=collection(),
                            points=[PointStruct(id=pointId, vector=vector, payload=payload)])
    except Exception as exc:
        logger.warning("Qdrant upsert of %s failed: %s", label, exc, exc_info=True)


async def search_similar_incidents(query: str, equipment_id: str | None = None, limit: int = 4) -> SearchResult:
    """Semantic search for incidents similar to the query.

    Returns SearchResult dictionary payload:
      {"items": [...], "source": "qdrant_semantic"|"keyword_fallback", "degraded": bool}
    A semantic hit comes back as the full incident row (root cause, lessons learned), because the Qdrant payload
    only carries what the index needs. Falls back to PostgreSQL keyword search when semantic search finds nothing;
    `degraded` is true only when semantic search could not run at all.
    """
    hits = await _semanticHits(query, lambda client, vector: qdrant.incidentHits(
        client, vector, get_incident_collection(), equipment_id, limit))
    if hits:
        return SearchResult(items=hits, source=qdrant.SEMANTIC_SOURCE, degraded=False)
    return await keywordIncidents(query, limit, degraded=hits is None)


async def search_relevant_docs(query: str, equipment_id: str | None = None, limit: int = 6) -> SearchResult:
    """Semantic search for document sections relevant to the query.

    Returns SearchResult dictionary payload:
      {"items": [...], "source": "qdrant_semantic"|"keyword_fallback", "degraded": bool}
    Falls back to a PostgreSQL keyword lookup when semantic search finds nothing, over the equipment's documents or,
    plant-wide, over every document; that also reaches documents the app writes itself, which are never
    vector-indexed. A section matches only when it contains a query keyword. `degraded` is true only when semantic
    search could not run at all.
    """
    hits = await _semanticHits(query, lambda client, vector: qdrant.documentHits(
        client, vector, get_document_collection(), equipment_id, limit))
    if hits:
        return SearchResult(items=hits, source=qdrant.SEMANTIC_SOURCE, degraded=False)
    return await keywordSections(query, equipment_id, limit, degraded=hits is None)


async def _semanticHits(
    query: str, search: Callable[[Any, list[float]], Awaitable[list[dict[str, Any]]]],
) -> list[dict[str, Any]] | None:
    """What `search` finds for the query's vector: [] when it finds nothing, None when semantic search could not run.
    A failed search marks Qdrant unhealthy, so the next searches skip it until the re-probe."""
    global _qdrant_ok
    client = await _get_client()
    vector = await _embed(query) if client is not None else None
    if vector is None:
        return None
    try:
        return await search(client, vector)
    except Exception as exc:
        logger.warning("Qdrant search failed, falling back to PostgreSQL: %s", exc, exc_info=True)
        _qdrant_ok = False
        return None


async def delete_document_points(doc_id: str) -> int:
    """Remove every indexed vector for a document (called on document deletion).

    Deleting a source document must also delete its retrieval copies —
    otherwise search keeps surfacing content the user believes is gone.
    Returns the number of points deleted (0 when Qdrant is unavailable).
    """
    client = await _get_client()
    return 0 if client is None else await qdrant.deleteDocumentPoints(client, get_document_collection(), doc_id)


async def delete_incident_points(incident_ids: list[str]) -> int:
    """Remove the indexed vectors of these incidents (called when the document that created them is deleted).

    Point ids are derived from incident ids (_stable_id), so no search is needed. Returns how many were sent for
    deletion, 0 when Qdrant is unavailable or there is nothing to delete.
    """
    client = await _get_client()
    if client is None or not incident_ids:
        return 0
    points = [_stable_id("inc", incident_id) for incident_id in incident_ids]
    return await qdrant.deletePoints(client, get_incident_collection(), points)


async def clear_incident_index() -> int:
    """Remove every incident point (called when the admin purge deletes incident rows)."""
    return await _clear_collection(get_incident_collection())


async def clear_document_index() -> int:
    """Remove every document point (called when the admin purge deletes document rows)."""
    return await _clear_collection(get_document_collection())


async def _clear_collection(collection: str) -> int:
    client = await _get_client()
    if client is None:
        logger.warning("Qdrant unreachable: %s keeps its points after the purge", collection)
        return 0
    return await qdrant.clearCollection(client, collection)


async def is_active() -> bool:
    """Return True if Qdrant is reachable and collections are ready.

    NOTE: reachability is not the same as a working semantic index — use
    get_health() for the honest picture.
    """
    return (await _get_client()) is not None


async def embeddings_available() -> bool:
    """Return True only if an embedding call actually succeeds."""
    return (await _embed(HEALTH_PROBE_TEXT)) is not None


async def get_health() -> dict[str, Any]:
    """Honest health report for the semantic search stack.

    semantic_search_ready is True only when Qdrant is reachable, embeddings
    work, AND at least one point is indexed — collection existence alone is
    not evidence of a functioning semantic index.
    """
    client = await _get_client()
    qdrant_ok = client is not None
    embed_ok = await embeddings_available() if qdrant_ok else False
    doc_points, inc_points = await qdrant.pointCounts(client, (get_document_collection(), get_incident_collection()))
    return {
        "qdrant_reachable": qdrant_ok,
        "embeddings_available": embed_ok,
        "document_points": doc_points,
        "incident_points": inc_points,
        "semantic_search_ready": qdrant_ok and embed_ok and (doc_points + inc_points) > 0,
        "fallback_mode": "postgresql_keyword" if not (qdrant_ok and embed_ok) else None,
    }
