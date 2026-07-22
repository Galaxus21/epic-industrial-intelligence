"""
AI Operations Brain — Knowledge Graph Service
Wraps Neo4j with a PostgreSQL fallback so the demo always works.
When Neo4j is reachable, real Cypher queries provide multi-hop traversal
and relationship-aware reasoning that PostgreSQL cannot match.
"""
import logging
from typing import Any

from app.core.config import settings
from app.services import db_service as db

logger = logging.getLogger(__name__)

# Try to import Neo4j; fall back to PostgreSQL if unavailable
try:
    from neo4j import AsyncGraphDatabase, AsyncDriver
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False


class GraphService:
    """Unified interface for knowledge graph operations."""

    def __init__(self) -> None:
        self._driver: Any = None
        self._use_neo4j = False

    async def _get_driver(self) -> Any:
        if not _NEO4J_AVAILABLE:
            return None
        if self._driver is None:
            try:
                self._driver = AsyncGraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_username, settings.neo4j_password),
                )
                await self._driver.verify_connectivity()
                self._use_neo4j = True
                logger.info("Connected to Neo4j at %s", settings.neo4j_uri)
            except Exception as exc:
                logger.warning("Neo4j unavailable (%s) — using PostgreSQL graph", exc)
                self._driver = None
                self._use_neo4j = False
        return self._driver

    # ── Core reads (always work via PostgreSQL) ───────────────────────────────

    async def get_equipment_brain(self, equipment_id: str) -> dict[str, Any]:
        """Return all connected knowledge for one equipment."""
        return await db.get_equipment_brain(equipment_id)

    async def get_full_graph(self) -> dict[str, Any]:
        """Return all graph nodes and links."""
        return await db.get_full_graph()

    async def get_equipment_subgraph(self, equipment_id: str) -> dict[str, Any]:
        """Return neighbourhood subgraph for one equipment."""
        return await db.get_equipment_subgraph(equipment_id)

    # ── Neo4j Cypher traversal (rich multi-hop reasoning) ────────────────────

    async def traverse_neighbours(
        self,
        equipment_id: str,
        max_depth: int = 2,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        Multi-hop traversal from an equipment node.
        Uses Neo4j Cypher when available for true graph path reasoning;
        falls back to PostgreSQL subgraph otherwise.

        Returns: {nodes: [...], links: [...], neo4j_used: bool}
        """
        driver = await self._get_driver()
        if driver and self._use_neo4j:
            try:
                async with driver.session() as session:
                    result = await session.run(
                        """
                        MATCH (start {id: $eq_id})
                        CALL apoc.path.subgraphAll(start, {
                            maxLevel: $depth,
                            limit: $limit
                        })
                        YIELD nodes, relationships
                        RETURN
                          [n IN nodes | {
                            id: n.id,
                            name: coalesce(n.name, n.id),
                            type: head(labels(n)),
                            val: coalesce(n.val, 10)
                          }] AS nodes,
                          [r IN relationships | {
                            source: startNode(r).id,
                            target: endNode(r).id,
                            label: type(r)
                          }] AS links
                        """,
                        {"eq_id": equipment_id, "depth": max_depth, "limit": limit},
                    )
                    record = await result.single()
                    if record:
                        return {
                            "nodes": record["nodes"],
                            "links": record["links"],
                            "neo4j_used": True,
                        }
            except Exception as exc:
                # APOC may not be installed; try simpler Cypher
                try:
                    async with driver.session() as session:
                        result = await session.run(
                            """
                            MATCH path = (start {id: $eq_id})-[*1..$depth]-(related)
                            WITH collect(distinct start) + collect(distinct related) AS all_nodes,
                                 collect(distinct relationships(path)) AS all_rels
                            UNWIND all_nodes AS n
                            WITH collect(distinct {
                                id: n.id,
                                name: coalesce(n.name, n.id),
                                type: head(labels(n)),
                                val: coalesce(n.val, 10)
                            }) AS nodes, all_rels
                            UNWIND all_rels AS rel_list
                            UNWIND rel_list AS r
                            RETURN nodes,
                                   collect(distinct {
                                     source: startNode(r).id,
                                     target: endNode(r).id,
                                     label: type(r)
                                   }) AS links
                            LIMIT 1
                            """,
                            {"eq_id": equipment_id, "depth": max_depth},
                        )
                        record = await result.single()
                        if record and record["nodes"]:
                            return {
                                "nodes": record["nodes"],
                                "links": record["links"],
                                "neo4j_used": True,
                            }
                except Exception as exc2:
                    logger.debug("Neo4j traversal failed: %s / %s", exc, exc2)

        # PostgreSQL fallback
        pg_graph = await db.get_equipment_subgraph(equipment_id)
        pg_graph["neo4j_used"] = False
        return pg_graph

    async def find_similar_equipment(self, equipment_id: str) -> list[dict[str, Any]]:
        """
        Find equipment that experienced similar failures (SIMILAR_PATTERN edges).
        Uses Neo4j Cypher when available.
        """
        driver = await self._get_driver()
        if driver and self._use_neo4j:
            try:
                async with driver.session() as session:
                    result = await session.run(
                        """
                        MATCH (e {id: $eq_id})-[:EXPERIENCED]->(i:Incident)-[:SIMILAR_PATTERN]-(i2:Incident)<-[:EXPERIENCED]-(e2)
                        WHERE e2.id <> $eq_id
                        RETURN e2.id AS equipment_id,
                               e2.name AS name,
                               count(i2) AS shared_incidents
                        ORDER BY shared_incidents DESC
                        LIMIT 5
                        """,
                        {"eq_id": equipment_id},
                    )
                    records = await result.data()
                    if records:
                        return records
            except Exception as exc:
                logger.debug("Neo4j similar equipment query failed: %s", exc)

        # PostgreSQL fallback: return downstream equipment
        eq = await db.get_equipment(equipment_id) or {}
        downstream = eq.get("downstream_equipment") or []
        return [{"equipment_id": eid, "name": eid, "shared_incidents": 0} for eid in downstream[:5]]

    async def is_neo4j_active(self) -> bool:
        driver = await self._get_driver()
        return driver is not None and self._use_neo4j

