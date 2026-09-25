"""
AI Operations Brain — Agents API
SSE streaming query endpoint — the heart of the demo.
POST /api/v1/agents/query  →  streams agent events as Server-Sent Events
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.orchestrator import run_query_stream
from app.api.chatTurn import ChatHistory, historyDicts
from app.api.eventStream import eventStreamResponse
from app.core.auth import get_current_user
from app.db import models as m

router = APIRouter()


class QueryRequest(BaseModel):
    equipment_id: str | None = None
    query: str = Field(..., max_length=4000)
    history: ChatHistory = []


@router.post("/query")
async def stream_agent_query(request: QueryRequest, user: m.UserProfile = Depends(get_current_user)):
    """
    Stream multi-agent analysis as Server-Sent Events.
    Each event: data: <json>\n\n
    Final event: data: [DONE]\n\n

    Event JSON schema:
      { agent, status: 'active'|'done', message, data? }
    """
    return eventStreamResponse(run_query_stream(request.equipment_id, request.query, historyDicts(request.history)))
