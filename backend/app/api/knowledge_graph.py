"""
AI Operations Brain — Knowledge Graph API
Returns graph data (nodes + links) for visualization.
Neo4j is used when available for multi-hop Cypher traversal;
falls back to PostgreSQL otherwise.
"""
from fastapi import APIRouter
from app.services.knowledge_graph import GraphService
from app.services import vector_service as vs

router = APIRouter()
_graph = GraphService()


@router.get("")
async def get_full_graph():
    """Return all nodes and links for the full plant knowledge graph."""
    return await _graph.get_full_graph()


@router.get("/status")
async def get_backend_status():
    """Return which graph/vector backends are currently active."""
    return {
        "neo4j_active":  await _graph.is_neo4j_active(),
        "qdrant_active": await vs.is_active(),
    }


@router.get("/{equipment_id}/traverse")
async def traverse_equipment_graph(equipment_id: str, depth: int = 2):
    """Multi-hop graph traversal — uses Neo4j Cypher when available."""
    return await _graph.traverse_neighbours(equipment_id, max_depth=depth)


@router.get("/{equipment_id}/similar")
async def similar_equipment(equipment_id: str):
    """Find equipment with similar failure patterns via graph edges."""
    return await _graph.find_similar_equipment(equipment_id)


@router.get("/{equipment_id}")
async def get_equipment_subgraph(equipment_id: str):
    """Return a subgraph centred on one piece of equipment."""
    return await _graph.get_equipment_subgraph(equipment_id)

