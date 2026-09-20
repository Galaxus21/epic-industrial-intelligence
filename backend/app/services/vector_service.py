"""
AI Operations Brain — Vector Search Service
==========================================
Wraps Qdrant for semantic similarity search.  Every document section and
incident description is embedded and indexed so the agent pipeline finds
relevant knowledge by *meaning*, not just keyword overlap.

Collections
-----------
  "op_documents"  — document sections (text chunks, ≤600 chars each)
  "op_incidents"  — incident/defect descriptions

Embedding backend
-----------------
  Primary  : OpenAI text-embedding-3-small (1536 dims)
  Fallback : PostgreSQL keyword search (NOT semantic). There is no sparse/BM25
             index — without a working embedding client nothing is written to
             Qdrant, and search quality degrades to keyword matching.

Health honesty: is_active() only says Qdrant is reachable. Use get_health()
to know whether a semantic index actually exists (embeddings configured AND
points indexed) — a reachable Qdrant with empty collections is NOT a working
semantic search.
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from app.core.config import settings
from app.services.providers import EmbeddingProvider, get_embedding_provider

logger = logging.getLogger(__name__)


def get_vector_dim() -> int:
    """Obtain active vector dimension dynamically from the embedding provider."""
    return get_embedding_provider().dimension


def get_incident_collection() -> str:
    """Namespace incident collection by vector dimension."""
    return f"op_incidents_{get_vector_dim()}"


def get_document_collection() -> str:
    """Namespace document collection by vector dimension."""
    return f"op_documents_{get_vector_dim()}"


# Dynamic module-level resolution for backwards compatibility
def __getattr__(name: str) -> Any:
    if name == "VECTOR_DIM":
        return get_vector_dim()
    if name == "_INCIDENT_COLLECTION":
        return get_incident_collection()
    if name == "_DOCUMENT_COLLECTION":
        return get_document_collection()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")



MAX_FALLBACK_KEYWORDS = 32


def extract_fallback_keywords(query: str, max_keywords: int = MAX_FALLBACK_KEYWORDS) -> list[str]:
    """Extract, deduplicate, and cap fallback keywords from query while preserving order."""
    seen: set[str] = set()
    keywords: list[str] = []
    for w in query.lower().split():
        if len(w) > 3 and w not in seen:
            seen.add(w)
            keywords.append(w)
            if len(keywords) >= max_keywords:
                break
    return keywords


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


# ─── Qdrant client (lazy singleton with periodic re-probing) ────────────────

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
    global _qdrant_client, _qdrant_ok, _last_qdrant_probe
    now = time.monotonic()
    if _qdrant_client is not None and _qdrant_ok:
        return _qdrant_client

    # If previously failed, only re-probe after probe interval has elapsed
    if not _qdrant_ok and _last_qdrant_probe > 0 and (now - _last_qdrant_probe < _PROBE_INTERVAL_SECONDS):
        return None

    _last_qdrant_probe = now
    try:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import Distance, VectorParams

        client = AsyncQdrantClient(url=settings.qdrant_url, timeout=5)
        # Ping by listing collections
        await client.get_collections()

        expected_dim = get_vector_dim()
        incident_col = get_incident_collection()
        document_col = get_document_collection()

        # Ensure both dimension-namespaced collections exist, and fail loudly on dimension mismatch
        for col in (incident_col, document_col):
            try:
                info = await client.get_collection(col)
                existing_dim = None
                try:
                    vectors_cfg = info.config.params.vectors
                    if hasattr(vectors_cfg, "size"):
                        existing_dim = int(vectors_cfg.size)
                    elif isinstance(vectors_cfg, dict):
                        for v in vectors_cfg.values():
                            if hasattr(v, "size"):
                                existing_dim = int(v.size)
                                break
                            elif isinstance(v, dict) and "size" in v:
                                existing_dim = int(v["size"])
                                break
                except Exception:
                    pass

                if existing_dim is not None and existing_dim != expected_dim:
                    raise ValueError(
                        f"Qdrant collection '{col}' exists with dimension {existing_dim}, "
                        f"but active embedding provider reports dimension {expected_dim}. "
                        f"Aborting startup to prevent silent vector write failures."
                    )
            except ValueError:
                raise
            except Exception as exc:
                logger.info("Collection %s missing (%s), creating collection", col, exc)
                try:
                    await client.create_collection(
                        collection_name=col,
                        vectors_config=VectorParams(size=expected_dim, distance=Distance.COSINE),
                    )
                except Exception as c_exc:
                    logger.warning("Could not create collection %s: %s", col, c_exc, exc_info=True)

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


# ─── Embedding helper ─────────────────────────────────────────────────────────

async def _embed(text: str) -> list[float] | None:
    """Generate an embedding vector via active EmbeddingProvider. Returns None if unavailable."""
    provider = get_embedding_provider()
    try:
        return await provider.embed_text(text)
    except Exception as exc:
        logger.warning("Embedding failed via %s: %s", type(provider).__name__, exc, exc_info=True)
        return None



def _stable_id(prefix: str, text: str) -> str:
    """Deterministic point ID from a stable hash so we can upsert idempotently."""
    h = hashlib.sha1(text.encode()).hexdigest()[:16]
    return f"{prefix}-{h}"


# ─── Public write API ─────────────────────────────────────────────────────────

async def index_incident(
    incident_id: str,
    title: str,
    description: str,
    equipment_id: str,
    severity: str = "",
    date: str = "",
) -> None:
    """Index an incident for semantic similarity search."""
    client = await _get_client()
    if client is None:
        return
    text = f"{title}. {description}".strip()
    vector = await _embed(text)
    if vector is None:
        logger.warning("Incident %s NOT semantically indexed — embeddings unavailable "
                       "(keyword fallback only)", incident_id)
        return
    try:
        from qdrant_client.models import PointStruct
        await client.upsert(
            collection_name=get_incident_collection(),
            points=[PointStruct(
                id=_stable_id("inc", incident_id),
                vector=vector,
                payload={
                    "incident_id": incident_id,
                    "title": title,
                    "description": description[:300],
                    "equipment_id": equipment_id,
                    "severity": severity,
                    "date": date,
                },
            )],
        )
    except Exception as exc:
        logger.warning("Qdrant index_incident failed: %s", exc, exc_info=True)


async def index_document_section(
    doc_id: str,
    doc_name: str,
    section_id: str,
    text: str,
    equipment_ids: list[str] | None = None,
    doc_type: str = "",
) -> None:
    """Index a document text chunk for retrieval during agent queries."""
    client = await _get_client()
    if client is None:
        return
    vector = await _embed(text)
    if vector is None:
        logger.warning("Document %s section %s NOT semantically indexed — embeddings "
                       "unavailable (keyword fallback only)", doc_id, section_id)
        return
    try:
        from qdrant_client.models import PointStruct
        await client.upsert(
            collection_name=get_document_collection(),
            points=[PointStruct(
                id=_stable_id("doc", f"{doc_id}-{section_id}"),
                vector=vector,
                payload={
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "section": section_id,
                    "text": text[:600],
                    "equipment_ids": equipment_ids or [],
                    "doc_type": doc_type,
                },
            )],
        )
    except Exception as exc:
        logger.warning("Qdrant index_document_section failed: %s", exc, exc_info=True)


# ─── Public read API ──────────────────────────────────────────────────────────

async def search_similar_incidents(
    query: str,
    equipment_id: str | None = None,
    limit: int = 4,
) -> SearchResult:
    """Semantic search for incidents similar to the query.

    Returns SearchResult dictionary payload:
      {"items": [...], "source": "qdrant_semantic"|"keyword_fallback", "degraded": bool}
    Falls back to PostgreSQL keyword search when Qdrant/embeddings are unavailable.
    """
    client = await _get_client()

    # ── Qdrant semantic path ──────────────────────────────────────────────────
    if client is not None:
        vector = await _embed(query)
        if vector is not None:
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                q_filter = None
                if equipment_id:
                    q_filter = Filter(
                        should=[
                            FieldCondition(key="equipment_id", match=MatchValue(value=equipment_id)),
                            FieldCondition(key="equipment_id", match=MatchValue(value="")),
                        ]
                    )
                hits = await client.search(
                    collection_name=get_incident_collection(),
                    query_vector=vector,
                    query_filter=q_filter,
                    limit=limit,
                    with_payload=True,
                )
                if hits:
                    items = [
                        {
                            **h.payload,
                            "_score": round(h.score, 3),
                            "_source": "qdrant_semantic",
                        }
                        for h in hits
                    ]
                    return SearchResult(items=items, source="qdrant_semantic", degraded=False)
            except Exception as exc:
                logger.warning("Qdrant search failed, falling back to PostgreSQL: %s", exc, exc_info=True)
                global _qdrant_ok
                _qdrant_ok = False

    # ── PostgreSQL keyword fallback ───────────────────────────────────────────
    from app.services import db_service as db
    keywords = extract_fallback_keywords(query)
    results = await db.find_similar_incidents(keywords, exclude_equipment_id=None)
    for r in results:
        r["_source"] = "keyword_fallback"
    return SearchResult(items=results[:limit], source="keyword_fallback", degraded=True)


async def search_relevant_docs(
    query: str,
    equipment_id: str | None = None,
    limit: int = 6,
) -> SearchResult:
    """Semantic search for document sections relevant to the query.

    Returns SearchResult dictionary payload:
      {"items": [...], "source": "qdrant_semantic"|"keyword_fallback", "degraded": bool}
    Falls back to equipment-scoped PostgreSQL document lookup.
    """
    client = await _get_client()

    # ── Qdrant semantic path ──────────────────────────────────────────────────
    if client is not None:
        vector = await _embed(query)
        if vector is not None:
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                q_filter = None
                if equipment_id:
                    q_filter = Filter(
                        should=[
                            FieldCondition(key="equipment_ids", match=MatchValue(value=equipment_id)),
                        ]
                    )
                hits = await client.search(
                    collection_name=get_document_collection(),
                    query_vector=vector,
                    query_filter=q_filter,
                    limit=limit,
                    with_payload=True,
                )
                if hits:
                    items = [
                        {
                            "doc_id":    h.payload.get("doc_id", ""),
                            "document":  h.payload.get("doc_name", ""),
                            "section":   h.payload.get("section", ""),
                            "text":      h.payload.get("text", ""),
                            "type":      h.payload.get("doc_type", ""),
                            "_score":    round(h.score, 3),
                            "_source":   "qdrant_semantic",
                        }
                        for h in hits
                    ]
                    return SearchResult(items=items, source="qdrant_semantic", degraded=False)
            except Exception as exc:
                logger.warning("Qdrant doc search failed, falling back to PostgreSQL: %s", exc, exc_info=True)
                _qdrant_ok = False

    # ── PostgreSQL fallback ───────────────────────────────────────────────────
    sections: list[dict[str, Any]] = []
    if equipment_id:
        from app.services import db_service as db
        docs = await db.get_equipment_documents(equipment_id)
        fallback_kws = extract_fallback_keywords(query)
        for doc in docs:
            if doc.get("ai_generated") is False or "generation unavailable" in (doc.get("name") or "").lower():
                continue
            for sid, text in (doc.get("sections") or {}).items():
                if any(w in text.lower() for w in fallback_kws):
                    sections.append({
                        "doc_id": doc["id"],
                        "document": doc["name"],
                        "section": sid,
                        "text": text[:600],
                        "type": doc.get("type", ""),
                        "_source": "keyword_fallback",
                    })
    return SearchResult(items=sections[:limit], source="keyword_fallback", degraded=True)


async def delete_document_points(doc_id: str) -> int:
    """Remove every indexed vector for a document (called on document deletion).

    Deleting a source document must also delete its retrieval copies —
    otherwise search keeps surfacing content the user believes is gone.
    Returns the number of points deleted (0 when Qdrant is unavailable).
    """
    client = await _get_client()
    if client is None:
        return 0
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        flt = Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])
        # Count first so we can report what was removed
        count = 0
        try:
            res = await client.count(collection_name=get_document_collection(), count_filter=flt, exact=True)
            count = res.count
        except Exception as exc:
            logger.warning("Could not count points before deletion for %s: %s", doc_id, exc)
        await client.delete(collection_name=get_document_collection(), points_selector=flt)
        logger.info("Deleted %d Qdrant point(s) for document %s", count, doc_id)
        return count
    except Exception as exc:
        logger.warning("Qdrant delete_document_points failed for %s: %s", doc_id, exc, exc_info=True)
        return 0


async def is_active() -> bool:
    """Return True if Qdrant is reachable and collections are ready.

    NOTE: reachability is not the same as a working semantic index — use
    get_health() for the honest picture.
    """
    return (await _get_client()) is not None


async def embeddings_available() -> bool:
    """Return True only if an embedding call actually succeeds."""
    return (await _embed("health probe")) is not None


async def get_health() -> dict[str, Any]:
    """Honest health report for the semantic search stack.

    semantic_search_ready is True only when Qdrant is reachable, embeddings
    work, AND at least one point is indexed — collection existence alone is
    not evidence of a functioning semantic index.
    """
    client = await _get_client()
    qdrant_ok = client is not None
    embed_ok = await embeddings_available() if qdrant_ok else False
    doc_points = inc_points = 0
    if qdrant_ok:
        try:
            doc_points = (await client.count(collection_name=get_document_collection(), exact=True)).count
            inc_points = (await client.count(collection_name=get_incident_collection(), exact=True)).count
        except Exception as exc:
            logger.warning("Failed to count collection points in get_health: %s", exc)
    return {
        "qdrant_reachable": qdrant_ok,
        "embeddings_available": embed_ok,
        "document_points": doc_points,
        "incident_points": inc_points,
        "semantic_search_ready": qdrant_ok and embed_ok and (doc_points + inc_points) > 0,
        "fallback_mode": "postgresql_keyword" if not (qdrant_ok and embed_ok) else None,
    }
