"""
AI Operations Brain — Knowledge Graph API
Returns graph data (nodes + links) for visualization.
The graph is stored in PostgreSQL; traversal is a breadth-first walk over graph_links.
"""
from fastapi import APIRouter
from app.services.knowledge_graph import graph_service as _graph
from app.services import vector_service as vs

router = APIRouter()


@router.get("")
async def get_full_graph():
    """Return all nodes and links for the full plant knowledge graph."""
    return await _graph.get_full_graph()


@router.get("/status")
async def get_backend_status():
    """Return honest backend health — connectivity AND whether the semantic
    index actually contains data (a reachable Qdrant with no points is not a
    working semantic search)."""
    vector_health = await vs.get_health()
    qdrant_active = vector_health["qdrant_reachable"]
    return {
        "qdrant_active": qdrant_active,
        "vector_health": vector_health,
        "degraded": not qdrant_active,
    }


@router.get("/{equipment_id}/traverse")
async def traverse_equipment_graph(equipment_id: str, depth: int = 2):
    """Multi-hop graph traversal: every node within `depth` hops of the equipment."""
    return await _graph.traverse_neighbours(equipment_id, max_depth=depth)


@router.get("/{equipment_id}")
async def get_equipment_subgraph(equipment_id: str):
    """Return a subgraph centred on one piece of equipment."""
    return await _graph.get_equipment_subgraph(equipment_id)
