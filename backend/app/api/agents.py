"""
AI Operations Brain — Agents API
SSE streaming query endpoint — the heart of the demo.
POST /api/v1/agents/query  →  streams agent events as Server-Sent Events
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.orchestrator import run_query_stream

router = APIRouter()


class QueryRequest(BaseModel):
    equipment_id: str
    query: str
    history: list[dict[str, str]] = []
    plant_id: str | None = None
    project_id: str | None = None


@router.post("/query")
async def stream_agent_query(request: QueryRequest):
    """
    Stream multi-agent analysis as Server-Sent Events.
    Each event: data: <json>\\n\\n
    Final event: data: [DONE]\\n\\n

    Event JSON schema:
      { agent, status: 'active'|'done', message, data? }
    """
    return StreamingResponse(
        run_query_stream(
            request.equipment_id, request.query, request.history,
            plant_id=request.plant_id, project_id=request.project_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
