"""
AI Operations Brain — Knowledge Graph Service
The graph lives in PostgreSQL (graph_nodes / graph_links). This service is the
single read interface the API and the ReAct tools use over it.
"""
from typing import Any

from app.services import db_service as db


class GraphService:
    """Unified interface for knowledge graph operations."""

    async def get_equipment_brain(self, equipment_id: str) -> dict[str, Any]:
        """Return all connected knowledge for one equipment."""
        return await db.get_equipment_brain(equipment_id)

    async def get_full_graph(self) -> dict[str, Any]:
        """Return all graph nodes and links."""
        return await db.get_full_graph()

    async def get_equipment_subgraph(self, equipment_id: str) -> dict[str, Any]:
        """Return neighbourhood subgraph for one equipment."""
        return await db.get_equipment_subgraph(equipment_id)

    async def traverse_neighbours(
        self,
        equipment_id: str,
        max_depth: int = 2,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Multi-hop traversal from an equipment node: everything within max_depth hops, at most limit nodes."""
        graph = await db.get_equipment_neighbourhood(equipment_id, max_depth=max_depth, limit=limit)
        graph["items"] = graph["nodes"]
        graph["source"] = "postgres_graph"
        graph["degraded"] = False
        return graph


# Shared singleton used by the orchestrator, the ReAct tools and the API router.
graph_service = GraphService()
