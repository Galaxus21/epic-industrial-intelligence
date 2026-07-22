"""
Backend Tests — Agent Orchestrator
Tests the streaming pipeline and context builders.
"""
import asyncio
import json
import pytest
from app.agents.orchestrator import run_query_stream, _build_maintenance_context, _build_compliance_context, _build_lessons_context


@pytest.mark.asyncio
async def test_stream_produces_six_events_for_p101():
    """Orchestrator must yield exactly six agent events + [DONE]."""
    events = []
    async for raw in run_query_stream("P-101", "Pump vibration increased today"):
        if raw.startswith("data: "):
            payload = raw[6:].strip()
            if payload != "[DONE]":
                events.append(json.loads(payload))

    agents_seen = {e["agent"] for e in events}
    expected_agents = {"equipment_brain", "maintenance_advisor", "compliance_agent", "lessons_learned", "document_intelligence", "synthesizer"}
    assert expected_agents == agents_seen


@pytest.mark.asyncio
async def test_stream_ends_with_done():
    """Stream must end with the [DONE] sentinel."""
    last_event = None
    async for raw in run_query_stream("P-101", "vibration"):
        last_event = raw
    assert last_event == "data: [DONE]\n\n"


@pytest.mark.asyncio
async def test_synthesizer_returns_risk_level():
    """Synthesizer data must include a risk_level field."""
    synthesizer_event = None
    async for raw in run_query_stream("P-101", "Pump vibration increased today"):
        if raw.startswith("data: ") and raw.strip() != "data: [DONE]":
            evt = json.loads(raw[6:])
            if evt.get("agent") == "synthesizer" and evt.get("status") == "done":
                synthesizer_event = evt
                break

    assert synthesizer_event is not None
    assert "data" in synthesizer_event
    assert synthesizer_event["data"].get("risk_level") in ("Critical", "High", "Medium", "Low")


@pytest.mark.asyncio
async def test_maintenance_context_detects_overdue():
    ctx = await _build_maintenance_context("P-101", "vibration bearing")
    assert any(t.get("status") == "Overdue" for t in ctx["overdue_tasks"])


@pytest.mark.asyncio
async def test_compliance_context_has_high_severity_issues():
    ctx = await _build_compliance_context("P-101")
    high = [i for i in ctx.get("issues", []) if i.get("severity") == "High"]
    assert len(high) >= 1


@pytest.mark.asyncio
async def test_lessons_context_finds_pattern():
    ctx = await _build_lessons_context("pump vibration bearing", "P-101")
    assert ctx["pattern_found"] is True
    assert len(ctx["lessons"]) >= 1
