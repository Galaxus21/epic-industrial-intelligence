"""
EPIC — What vector_service asks of a connected Qdrant client: make sure the collections fit the embedding size, find
the incidents and document sections nearest a query vector, and delete points.

Every function takes the client it works with, so vector_service keeps the one connection and its health state, and
decides what a failure means (a query error raises here; vector_service falls back to keyword search).
"""
from __future__ import annotations

import logging
from typing import Any

from app.services import db_service as db

logger = logging.getLogger(__name__)

SEMANTIC_SOURCE = "qdrant_semantic"
SCORE_DECIMALS = 3


async def ensureCollections(client: Any, collections: tuple[str, ...], expectedDimension: int) -> None:
    """Create each missing collection with `expectedDimension`; raise ValueError when one exists with another size,
    because every later write to it would fail without a word."""
    from qdrant_client.models import Distance, VectorParams

    for collection in collections:
        try:
            info = await client.get_collection(collection)
        except Exception as exc:
            logger.info("Collection %s missing (%s), creating collection", collection, exc)
            try:
                await client.create_collection(
                    collection_name=collection,
                    vectors_config=VectorParams(size=expectedDimension, distance=Distance.COSINE),
                )
            except Exception as createExc:
                logger.warning("Could not create collection %s: %s", collection, createExc, exc_info=True)
            continue
        existing = _vectorSize(info)
        if existing is not None and existing != expectedDimension:
            raise ValueError(
                f"Qdrant collection '{collection}' exists with dimension {existing}, "
                f"but active embedding provider reports dimension {expectedDimension}. "
                f"Aborting startup to prevent silent vector write failures."
            )


async def incidentHits(client: Any, vector: list[float], collection: str, equipmentId: str | None,
                       limit: int) -> list[dict[str, Any]]:
    """The incidents nearest `vector`, each as its full incident row plus score. With an equipment id, incidents of
    that equipment and incidents indexed without one."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    queryFilter = Filter(should=[
        FieldCondition(key="equipment_id", match=MatchValue(value=equipmentId)),
        FieldCondition(key="equipment_id", match=MatchValue(value="")),
    ]) if equipmentId else None
    hits = await client.search(collection_name=collection, query_vector=vector, query_filter=queryFilter,
                               limit=limit, with_payload=True)
    return await _incidentRecords(hits) if hits else []


async def documentHits(client: Any, vector: list[float], collection: str, equipmentId: str | None,
                       limit: int) -> list[dict[str, Any]]:
    """The document sections nearest `vector`; with an equipment id, only sections indexed under it."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    queryFilter = Filter(should=[
        FieldCondition(key="equipment_ids", match=MatchValue(value=equipmentId)),
    ]) if equipmentId else None
    hits = await client.search(collection_name=collection, query_vector=vector, query_filter=queryFilter,
                               limit=limit, with_payload=True)
    return [
        {
            "doc_id": hit.payload.get("doc_id", ""),
            "document": hit.payload.get("doc_name", ""),
            "section": hit.payload.get("section", ""),
            "text": hit.payload.get("text", ""),
            "type": hit.payload.get("doc_type", ""),
            "_score": round(hit.score, SCORE_DECIMALS),
            "_source": SEMANTIC_SOURCE,
        }
        for hit in hits
    ]


async def deleteDocumentPoints(client: Any, collection: str, docId: str) -> int:
    """Delete every point of the document; return how many there were (0 when the count or the delete fails)."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    try:
        documentFilter = Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=docId))])
        count = 0
        try:
            count = (await client.count(collection_name=collection, count_filter=documentFilter, exact=True)).count
        except Exception as exc:
            logger.warning("Could not count points before deletion for %s: %s", docId, exc)
        await client.delete(collection_name=collection, points_selector=documentFilter)
        logger.info("Deleted %d Qdrant point(s) for document %s", count, docId)
        return count
    except Exception as exc:
        logger.warning("Qdrant delete_document_points failed for %s: %s", docId, exc, exc_info=True)
        return 0


async def deletePoints(client: Any, collection: str, pointIds: list[str]) -> int:
    """Delete the points with these ids; return how many were sent for deletion (0 when the delete fails)."""
    from qdrant_client.models import PointIdsList

    try:
        await client.delete(collection_name=collection, points_selector=PointIdsList(points=pointIds))
        return len(pointIds)
    except Exception as exc:
        logger.warning("Qdrant delete of %d point(s) from %s failed: %s", len(pointIds), collection, exc,
                       exc_info=True)
        return 0


async def clearCollection(client: Any, collection: str) -> int:
    """Delete all points and keep the collection. An empty filter matches every point: on Qdrant v1.9.2 a delete
    with it took a 3-point collection to 0 (measured 2026-09-25). Returns the number removed, 0 when it fails."""
    from qdrant_client.models import Filter

    try:
        count = (await client.count(collection_name=collection, exact=True)).count
        await client.delete(collection_name=collection, points_selector=Filter())
        logger.info("Cleared %d Qdrant point(s) from %s", count, collection)
        return count
    except Exception as exc:
        logger.warning("Qdrant clear of %s failed: %s", collection, exc, exc_info=True)
        return 0


async def pointCounts(client: Any, collections: tuple[str, ...]) -> tuple[int, ...]:
    """How many points each collection holds; all zero when there is no client or a count fails."""
    if client is None:
        return tuple(0 for _ in collections)
    try:
        return tuple([(await client.count(collection_name=collection, exact=True)).count for collection in collections])
    except Exception as exc:
        logger.warning("Failed to count collection points: %s", exc)
        return tuple(0 for _ in collections)


async def _incidentRecords(hits: list[Any]) -> list[dict[str, Any]]:
    """Each hit as its full incident row plus score; a hit whose row was deleted keeps its index payload."""
    rows = await db.get_incidents_by_ids([hit.payload.get("incident_id", "") for hit in hits])
    records = []
    for hit in hits:
        row = rows.get(hit.payload.get("incident_id", ""), {})
        records.append({**hit.payload, **row, "_score": round(hit.score, SCORE_DECIMALS), "_source": SEMANTIC_SOURCE})
    return records


def _vectorSize(info: Any) -> int | None:
    """The vector size a collection was created with, whether it has one unnamed vector or named ones."""
    try:
        vectors = info.config.params.vectors
        if hasattr(vectors, "size"):
            return int(vectors.size)
        if isinstance(vectors, dict):
            for vector in vectors.values():
                if hasattr(vector, "size"):
                    return int(vector.size)
                if isinstance(vector, dict) and "size" in vector:
                    return int(vector["size"])
    except Exception:
        return None
    return None
