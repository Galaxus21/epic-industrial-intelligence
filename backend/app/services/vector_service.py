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
  Fallback : qdrant-client built-in sparse BM25 text payload search
             (works with no OpenAI key — just less semantic)

The public API is identical regardless of which backend is active;
callers never need to check.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

VECTOR_DIM = 1536              # text-embedding-3-small output dimension
_INCIDENT_COLLECTION = "op_incidents"
_DOCUMENT_COLLECTION = "op_documents"


# ─── Qdrant client (lazy singleton) ──────────────────────────────────────────

_qdrant_client: Any = None
_qdrant_ok: bool = False


async def _get_client():
    global _qdrant_client, _qdrant_ok
    if _qdrant_client is not None:
        return _qdrant_client if _qdrant_ok else None
    try:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import Distance, VectorParams

        client = AsyncQdrantClient(url=settings.qdrant_url, timeout=5)
        # Ping by listing collections
        await client.get_collections()

        # Ensure both collections exist
        for col in (_INCIDENT_COLLECTION, _DOCUMENT_COLLECTION):
            try:
                await client.get_collection(col)
            except Exception:
                await client.create_collection(
                    collection_name=col,
                    vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
                )

        _qdrant_client = client
        _qdrant_ok = True
        logger.info("Qdrant connected at %s — semantic search active", settings.qdrant_url)
    except Exception as exc:
        logger.warning("Qdrant unavailable (%s) — falling back to PostgreSQL keyword search", exc)
        _qdrant_ok = False
    return _qdrant_client if _qdrant_ok else None


# ─── Embedding helper ─────────────────────────────────────────────────────────

async def _embed(text: str) -> list[float] | None:
    """Generate an embedding vector via OpenAI.  Returns None if unavailable."""
    from app.services.llm_service import _get_client as _llm_client
    client = _llm_client()
    if not client:
        return None
    try:
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000],
        )
        return resp.data[0].embedding
    except Exception as exc:
        logger.debug("Embedding failed: %s", exc)
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
        return
    try:
        from qdrant_client.models import PointStruct
        await client.upsert(
            collection_name=_INCIDENT_COLLECTION,
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
        logger.debug("Qdrant index_incident failed: %s", exc)


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
        return
    try:
        from qdrant_client.models import PointStruct
        await client.upsert(
            collection_name=_DOCUMENT_COLLECTION,
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
        logger.debug("Qdrant index_document_section failed: %s", exc)


# ─── Public read API ──────────────────────────────────────────────────────────

async def search_similar_incidents(
    query: str,
    equipment_id: str | None = None,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """
    Semantic search for incidents similar to the query.
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
                    collection_name=_INCIDENT_COLLECTION,
                    query_vector=vector,
                    query_filter=q_filter,
                    limit=limit,
                    with_payload=True,
                )
                if hits:
                    return [
                        {
                            **h.payload,
                            "_score": round(h.score, 3),
                            "_source": "qdrant_semantic",
                        }
                        for h in hits
                    ]
            except Exception as exc:
                logger.debug("Qdrant search failed, falling back: %s", exc)

    # ── PostgreSQL keyword fallback ───────────────────────────────────────────
    from app.services import db_service as db
    keywords = [w for w in query.lower().split() if len(w) > 3]
    results = await db.find_similar_incidents(keywords, exclude_equipment_id=None)
    for r in results:
        r["_source"] = "pg_keyword"
    return results[:limit]


async def search_relevant_docs(
    query: str,
    equipment_id: str | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    """
    Semantic search for document sections relevant to the query.
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
                    collection_name=_DOCUMENT_COLLECTION,
                    query_vector=vector,
                    query_filter=q_filter,
                    limit=limit,
                    with_payload=True,
                )
                if hits:
                    return [
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
            except Exception as exc:
                logger.debug("Qdrant doc search failed, falling back: %s", exc)

    # ── PostgreSQL fallback ───────────────────────────────────────────────────
    if equipment_id:
        from app.services import db_service as db
        docs = await db.get_equipment_documents(equipment_id)
        sections: list[dict[str, Any]] = []
        query_lower = query.lower()
        for doc in docs:
            for sid, text in (doc.get("sections") or {}).items():
                if any(w in text.lower() for w in query_lower.split() if len(w) > 3):
                    sections.append({
                        "doc_id": doc["id"],
                        "document": doc["name"],
                        "section": sid,
                        "text": text[:600],
                        "type": doc.get("type", ""),
                        "_source": "pg_keyword",
                    })
        return sections[:limit]
    return []


async def is_active() -> bool:
    """Return True if Qdrant is reachable and collections are ready."""
    return (await _get_client()) is not None
