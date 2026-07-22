# EPIC — Enterprise Platform for Industrial Cognition

**AI Operations Brain · Industrial Knowledge Graph + Multi-Agent AI for Plant Operations**

> **Stack**: FastAPI · Next.js 14 · PostgreSQL · Neo4j · Qdrant · GPT-4.1 · Docker

---

## 30-second pitch

Most teams will build "upload PDFs → chatbot". We build an **AI that thinks like the plant's senior engineer** — connecting equipment, incidents, manuals, regulations, and expert knowledge into a unified intelligence layer.

**Demo scenario**: Operator reports *"Pump P-101 vibration increased today."* → 5 AI agents respond in real-time → comprehensive answer with root cause analysis, compliance issues, historical pattern match, auto work order, and cited sources — all in under 15 seconds.

---

## Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env → add OPENAI_API_KEY (optional — fallback responses work without it)

# 2. One-command startup
docker-compose up -d

# 3. Open dashboard
open http://localhost:3000

# 4. Run the demo
# Click Pump P-101 → open Query page → type:
# "Pump vibration increased today. Can I continue operating?"
```

---

## Architecture

```
Documents (PDF/P&ID/Excel)
          │
          ▼
Document Intelligence Agent
(OCR + Entity Extraction)
          │
    ┌─────┴────────┐
    ▼              ▼
Knowledge Graph   Vector DB
  (Neo4j)         (Qdrant)
    │              │
    └──────┬───────┘
           ▼
   Agent Orchestrator (SSE Stream)
   ┌────────┬────────┬────────┐
   ▼        ▼        ▼        ▼
Equipment Maintenance Compliance Lessons
  Brain    Advisor    Agent   Learned
           │
           ▼
      GPT-4.1 Synthesis
           │
           ▼
  Next.js Industrial Dashboard
```

---

## The 5 Agents

| Agent | Role | Output |
|---|---|---|
| **Equipment Brain** | Loads all knowledge connected to the equipment from the graph | Maintenance history, incidents, manuals, technicians, sensor state |
| **Maintenance Advisor** | Searches history for similar symptoms and patterns | Probable causes with probabilities, inspection checklist |
| **Compliance Agent** | Checks OISD-117, ISO 10816, Factory Act, SOPs | Open issues, regulatory gaps, required actions |
| **Lessons Learned** | Correlates historical incident patterns | Matched incidents, failure timeline prediction |
| **Synthesizer** | GPT-4.1 merges all contexts into one structured answer | Risk level, actions, work order, sources |

---

## Key Features

- **Knowledge Graph** — Neo4j graph with 20+ entity types and 30+ relationship types
- **Streaming multi-agent UI** — Watch 5 agents activate in real-time via SSE
- **Explainability** — Every answer cites source document, section, and confidence %
- **Equipment Brain** — Each piece of equipment has a rich connected memory
- **Predictive** — Lessons learned agent warns before failure using historical patterns
- **Voice Input** — Web Speech API for hands-free operation
- **Industrial Dark UI** — Built for plant floor operators

---

## Business Impact (Prototype Estimates)

| Metric | Before | After |
|---|---|---|
| Document search | 30 min | 10 sec |
| RCA preparation | 4 hrs | 2 min |
| Compliance audit | 2 days | 15 min |
| Relevant doc retrieval | 55% | 95% |

> *All metrics are prototype/simulated estimates unless validated with real industrial data.*

---

## Tech Stack

| | Technology |
|---|---|
| Frontend | Next.js 14, Tailwind CSS, Framer Motion |
| Charts | recharts (SVG line charts) |
| Graph Viz | react-force-graph-2d (D3-force) |
| Backend | FastAPI (Python 3.11) |
| LLM | GPT-4.1 (OpenAI) |
| Knowledge Graph | Neo4j 5 |
| Vector DB | Qdrant |
| Database | PostgreSQL |
| Deployment | Docker Compose |

---

## Services

| Service | Port | UI |
|---|---|---|
| Frontend | 3000 | http://localhost:3000 |
| Backend API | 8000 | http://localhost:8000/docs |
| Neo4j Browser | 7474 | http://localhost:7474 |
| Qdrant UI | 6333 | http://localhost:6333/dashboard |

---

## Running Tests

```bash
# Backend tests
cd backend && python -m pytest tests/ -v

# Frontend tests
cd frontend && npm test
```
