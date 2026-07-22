# EPIC — Enterprise Platform for Industrial Cognition

**AI Operations Brain · Industrial Knowledge Graph + Multi-Agent AI for Plant Operations**

> **Stack**: FastAPI · Next.js 14 · PostgreSQL · Neo4j · Qdrant · GPT-4.1 · Docker Compose

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Prerequisites](#prerequisites)
3. [Installation & First Run](#installation--first-run)
4. [Environment Variables](#environment-variables)
5. [Running the App](#running-the-app)
6. [Loading Demo Data](#loading-demo-data)
7. [Feature Walkthrough](#feature-walkthrough)
8. [Document Upload Pipeline](#document-upload-pipeline)
9. [Running Tests](#running-tests)
10. [Service Ports & URLs](#service-ports--urls)
11. [Architecture](#architecture)
12. [Troubleshooting](#troubleshooting)
13. [Project Structure](#project-structure)
14. [API Quick Reference](#api-quick-reference)

---

## What It Does

EPIC connects equipment, incidents, maintenance records, compliance standards, engineering drawings, and expert documents into a **live knowledge graph**. When an operator asks a question, five specialised AI agents query this graph simultaneously and stream a structured answer — with cited sources, risk scoring, and an auto-generated work order — in under 15 seconds.

**Core demo scenario**: Pump P-101 vibration alarm fires at 2 AM → operator opens EPIC → AI diagnoses 75% bearing failure risk, surfaces 3 compliance issues, matches 2 historical incidents, and issues a work order — all before the senior engineer picks up the phone.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker Desktop | ≥ 4.20 | Must be running |
| Docker Compose | v2 (bundled) | `docker compose version` |
| Git | any | To clone the repo |
| OpenAI API key | optional | App works offline with heuristic fallback |

> **No Python, Node.js, or database installation required** — everything runs in containers.

---

## Installation & First Run

```bash
# 1. Clone the repository
git clone <repo-url> hck123
cd hck123

# 2. Copy environment template
cp .env.example .env

# 3. (Optional) Add your OpenAI key for full AI features
#    Without it, all 5 agents work via heuristic fallback
nano .env

# 4. Build and start all services
docker-compose up --build
# First build takes ~3-4 minutes. Subsequent starts take ~15 seconds.

# 5. Open the app
open http://localhost:3000
```

> **Tip**: Use `docker-compose up --build -d` to run in the background (detached mode).

---

## Environment Variables

Edit `.env` in the project root:

```env
# Required for full LLM features (optional — fallback works without it)
OPENAI_API_KEY=sk-...

# Database passwords (defaults work for local dev)
POSTGRES_PASSWORD=opsbrain2024
NEO4J_PASSWORD=opsbrain2024

# OpenAI model
OPENAI_MODEL=gpt-4.1
```

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | _(empty)_ | GPT-4.1 key. Omit to use offline heuristic fallback. |
| `POSTGRES_PASSWORD` | `opsbrain2024` | PostgreSQL password |
| `NEO4J_PASSWORD` | `opsbrain2024` | Neo4j password |
| `OPENAI_MODEL` | `gpt-4.1` | LLM model name |

---

## Running the App

```bash
# Start (background)
docker-compose up -d

# Start (foreground — see all logs)
docker-compose up

# Stop
docker-compose down

# Stop and wipe all data (full reset)
docker-compose down -v

# Rebuild after code changes
docker-compose up --build

# Logs for a specific service
docker-compose logs -f backend
docker-compose logs -f frontend

# Restart only the backend
docker-compose restart backend
```

---

## Loading Demo Data

### Via the UI (recommended)

1. Open **http://localhost:3000**
2. Click the **sparkle icon** (✨) in the bottom-left sidebar
3. Click **Generate Demo Data**
4. Wait ~10 seconds — 53+ entities are created across all tables
5. The success screen shows **Step 2**: a list of 9 sample documents to download and upload via the Documents page

### What gets created

| Entity | Count |
|---|---|
| Project + Plants | 1 project, 2 plants (CDU Unit 4, VDU Unit 5) |
| Equipment | 6 (P-101 pump with vibration alarm, K-401 compressor, HX-201, V-301, P-202, G-101) |
| Users / Roles | 6 users covering all 7 roles (technician → manager) |
| Spare Parts | 4 with stock levels |
| Legacy Incidents | 4 (AI knowledge base + vector indexed) |
| Incident Reports | 3 (reported / investigation / CAPA stages) |
| Maintenance Records | 5 (completed + overdue) |
| Managed Work Orders | 4 (draft → approved → in_progress → closed) |
| Permits to Work | 3 (issued, under review, closed) |
| Safety Procedures | 3 (active SOP, peer-review JSA, draft) |
| Quality Inspections | 3 (scheduled, in_progress, closed with findings) |
| Action Items / CAPA | 3 |
| Sensor History | 30-day data for P-101 vibration + K-401 pressure |
| Knowledge Graph | Nodes + links for all entities |
| Compliance Records | 1 per equipment with open issues |

Sample documents are **not** inserted into the DB automatically — you upload them manually through the Documents page to demonstrate the live AI extraction pipeline.

### Via the API

```bash
curl -X POST http://localhost:8000/api/v1/admin/generate-demo
```

### Reset all data

```bash
# API
curl -X DELETE "http://localhost:8000/api/v1/admin/purge?entity=all"

# Or: sidebar trash icon → select entity types → confirm
```

---

## Feature Walkthrough

### 1. Dashboard (`/`)
- Plant health score, alarm count, open work orders, compliance status
- Alert feed showing threshold breaches auto-raised by the background monitor
- Equipment health rings with failure probability badges

### 2. AI Query (`/query`)
- Select equipment from the dropdown (e.g. **P-101**)
- Type or **speak** (click microphone) your question:
  > *"Pump vibration increased today. Can I continue operating?"*
- Watch 5 agents stream in real-time: Equipment Brain → Maintenance Advisor → Compliance Agent → Lessons Learned → Synthesizer
- Review: Risk card (Health / Failure Prob / Compliance / Maintenance Due), auto work order, cited sources

### 3. Sensors (`/sensors`)
- Select equipment to see all sensor parameters as live line charts
- Alarm (orange dashed) and trip (red dashed) threshold overlays
- 30-day trending with anomaly periods highlighted

### 4. Equipment (`/equipment`)
- Fleet health dashboard — click any equipment card for the **Equipment Brain**:
  full context including incidents, maintenance, documents, spare parts, compliance

### 5. Root Cause Analysis (`/rca`)
- Live quick events pulled from DB (active alarms, overdue maintenance, critical WOs)
- Click **Run AI RCA** → causal chain with probability scores and evidence citations

### 6. Forms Hub (`/forms`)
- Quick Capture forms: Maintenance Record, Sensor Log, Incident Report, Work Order, Defect Report, Equipment Registration
- AI-generated forms — equipment fields pre-filled from the database
- Submissions dual-write to both AI-agent tables and workflow tables

### 7. Permit to Work (`/permits`)
- Create hot work / cold work / confined space / electrical isolation permits
- Full 10-stage approval workflow: draft → submitted → area_authority_review → safety_review → ap_approval → issued → active → suspended → completion_requested → closed
- Use the **Acting As** picker in the sidebar footer to switch roles and approve each stage without logging out

### 8. Managed Work Orders (`/managed-work-orders`)
- 8-stage workflow with **two-person rule** enforced at the API level
- Try to verify a WO as the same user who completed it → system returns HTTP 403

### 9. Safety Procedures (`/procedures`)
- 6-stage workflow: draft → peer_review → technical_review → final_approval → active → obsolete
- Doc types: SOP, JSA, SWMS, MSDS, ERP, Checklist, Work Instruction

### 10. Incident Reports
- Full 5-stage workflow: reported → investigation → root_cause_analysis → CAPA → closed
- 9 incident types (near miss, first aid, lost time, environmental, fire, spill, etc.)
- Severity P1–P5, cost and downtime tracking

### 11. Quality Inspections (`/inspections`)
- Checklist-based inspections with non-conformance tracking and scoring
- CAPA action items auto-created from findings

### 12. Documents (`/documents`)
- Upload any industrial file (18+ formats: PDF, DOCX, XLSX, PPTX, TXT, CSV, DXF, DWG, STEP, IGES, IFC, SVG, PNG, JPG, and more)
- 6-step AI pipeline shown as a live progress bar
- Extracted entities panel shows equipment IDs, regulations, measurements, people

### 13. Engineering Drawings (`/drawings`)
- Project → Plant → Drawing hierarchy navigator with search
- Upload P&ID drawings for SVG rendering + live analytics (linked incidents, PTWs, WOs)

### 14. Knowledge Graph (`/graph`)
- Force-directed graph — 20+ entity types, 30+ relationship types
- Click any node to explore its subgraph

### 15. Reports (`/reports`)
- 6 tabs: Overview, Equipment, Maintenance, Incidents, Work Orders, Safety
- All charts pull live data from the database

### 16. Custom Dashboards (`/dashboards`)
- Drag-and-drop widget builder with 10+ widget types
- Save and reload multiple dashboards

### 17. Compliance (`/compliance`)
- Per-equipment compliance score 0–100 with open issue register
- AI plant-wide analysis → prioritised remediation action list

### 18. Audit Trail (`/audit`)
- Immutable chronological log of every create/update/approve action
- Filter by type, actor, date range — export to CSV for ISO 45001 audit prep

### 19. Plant Twin (`/plant`)
- Area → Unit → Equipment hierarchy with live status indicators

### 20. Projects (`/projects`)
- Project → Plant → Equipment drill-down
- Types: Industrial / Shutdown / Turnaround

### Sidebar Controls

| Control | Location | Function |
|---|---|---|
| ☀️ / 🌙 toggle | Sidebar header | Switch light / dark theme |
| **Acting As** picker | Sidebar footer | Impersonate any role for workflow demos |
| 🗑️ trash icon | Sidebar bottom | Delete data (select entity types) |
| ✨ sparkle icon | Sidebar bottom | Generate demo data + download sample docs |

---

## Document Upload Pipeline

After generating demo data, download the 9 sample documents and upload them manually to demonstrate the live AI extraction pipeline.

### Steps

1. Open **http://localhost:3000/documents**
2. Click **Upload** or drag files onto the upload zone
3. Watch the 6-step progress bar:
   - **File saved** — stored in uploads volume
   - **Text extracted** — PyMuPDF / docx / openpyxl / pptx parsers
   - **Entities extracted** — GPT-4.1 (or regex fallback) finds equipment IDs, regulations, people
   - **Drawing extracted** — SVG generated for P&IDs and CAD files
   - **Knowledge graph updated** — new nodes and relationships added to Neo4j
   - **Vector index updated** — chunks indexed in Qdrant for semantic search
4. Click the processed document to see the entity panel and AI summary
5. Subsequent AI queries about the same equipment will now cite this document

### Get the sample documents

```bash
# Copy all 9 files from the Docker container to ./abc/
mkdir -p abc
docker cp opsbrain-backend:/app/uploads/demo_samples/. abc/
ls abc/

# Or download via the API
curl -O http://localhost:8000/api/v1/admin/demo-docs/DOC-DEMO-PDF-01.pdf

# List what's available
curl http://localhost:8000/api/v1/admin/demo-docs
```

### Sample document descriptions

| File | Format | Content |
|---|---|---|
| `DOC-DEMO-PDF-01.pdf` | PDF | P-101 Maintenance Inspection Report (2-page styled report with sensor data table and RCA) |
| `DOC-DEMO-PDF-02.pdf` | PDF | K-401 Compressor Incident Investigation Report with 5-Why analysis and CAPA table |
| `DOC-DEMO-DOCX-01.docx` | Word | SOP-P101-BEARING-REV3: Bearing Replacement Procedure (hazards, tools, step table) |
| `DOC-DEMO-DOCX-02.docx` | Word | Night Shift Handover Log — CDU Unit 4 (event timeline, equipment status, pending actions) |
| `DOC-DEMO-XLSX-01.xlsx` | Excel | Equipment Maintenance Schedule 2026 (colour-coded overdue/due/scheduled) |
| `DOC-DEMO-XLSX-02.xlsx` | Excel | Spare Parts Inventory Register (12 SKUs with stock levels and reorder alerts) |
| `DOC-DEMO-PPTX-01.pptx` | PowerPoint | Safety Toolbox Talk — Rotating Equipment (5 slides, dark theme) |
| `DOC-DEMO-TXT-01.txt` | Text | Night Shift Handover Notes (chronological event log + cost avoidance calculation) |
| `DOC-DEMO-CSV-01.csv` | CSV | P-101 Sensor Data Export — 30-day history for 4 parameters |

---

## Running Tests

### Backend (pytest)

```bash
# Inside the running container
docker-compose exec backend python -m pytest tests/ -v

# Locally (Python 3.11 + venv)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -v
```

### Frontend (Vitest)

```bash
# Inside the running container
docker-compose exec frontend npm test

# Locally (Node.js 18+)
cd frontend
npm install && npm test
```

---

## Service Ports & URLs

| Service | URL | Default Credentials |
|---|---|---|
| **Frontend** | http://localhost:3000 | — |
| **Backend API** | http://localhost:8000 | — |
| **Swagger UI** | http://localhost:8000/docs | — |
| **Redoc** | http://localhost:8000/redoc | — |
| **Neo4j Browser** | http://localhost:7474 | `neo4j` / `opsbrain2024` |
| **Qdrant Dashboard** | http://localhost:6333/dashboard | — |
| **PostgreSQL** | `localhost:5432` | user `opsbrain` · db `opsbrain` |

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                   Next.js 14 Frontend                       │
│         Industrial Dark UI · 21 pages · Zustand            │
└──────────────────────┬─────────────────────────────────────┘
                       │  REST + SSE (Server-Sent Events)
┌──────────────────────▼─────────────────────────────────────┐
│                 FastAPI Backend  (Python 3.11)              │
│         25 Routers · 150+ endpoints · Async SQLAlchemy      │
│                                                             │
│  Agent Orchestrator  ──────────────────────────────────→   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │Equipment │ │Maint.    │ │Compliance│ │Lessons   │       │
│  │Brain     │ │Advisor   │ │Agent     │ │Learned   │ Synth │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│                                                             │
│  Background: Threshold Monitor · Document Pipeline          │
└──────┬──────────────────┬────────────────────────┬─────────┘
       │                  │                        │
┌──────▼──────┐  ┌────────▼───┐           ┌───────▼────┐
│ PostgreSQL  │  │   Neo4j    │           │  Qdrant    │
│  25 models  │  │  Knowledge │           │ Vector DB  │
│  async ORM  │  │   Graph    │           │  (RAG)     │
└─────────────┘  └────────────┘           └────────────┘
```

Key data flows:

```
Document Upload → Text Extract → LLM Entity Extraction
  → Equipment auto-register → Knowledge Graph update
  → Vector index → Available for AI queries

Sensor Reading → Threshold Monitor background agent
  → Auto Work Order → Dashboard Alert

AI Query → 5 agents (parallel DB + graph queries)
  → SSE stream to UI → Risk score + Work Order + Citations
```

---

## Troubleshooting

### Port already in use

```bash
lsof -i :3000    # find what is using port 3000
lsof -i :8000
kill -9 <PID>
```

### Backend health check fails / won't start

```bash
docker-compose logs backend | tail -50
docker-compose restart backend
```

### "No equipment found" after generating demo data

```bash
# Check the generate endpoint directly
curl -X POST http://localhost:8000/api/v1/admin/generate-demo | python3 -m json.tool

# Check equipment count
curl http://localhost:8000/api/v1/equipment | python3 -c "import json,sys; print(len(json.load(sys.stdin)), 'equipment records')"
```

### AI query returns no stream or empty agents

The heuristic fallback runs without an API key. If the stream is completely empty:

```bash
docker-compose logs backend | grep -iE "error|agent|llm|exception" | tail -30
```

### Document upload pipeline hangs at a step

```bash
# Check the document status directly
curl http://localhost:8000/api/v1/documents | python3 -m json.tool | grep -A5 "status"
docker-compose logs backend | grep "Pipeline" | tail -20
```

### Full reset (wipe all data, fresh start)

```bash
docker-compose down -v      # removes all Docker volumes (database data)
docker-compose up --build   # fresh build + empty DB
```

### View live resource usage

```bash
docker stats opsbrain-backend opsbrain-frontend opsbrain-postgres opsbrain-neo4j opsbrain-qdrant
```

---

## Project Structure

```
hck123/
├── backend/
│   ├── main.py                      # App entry, router registration
│   ├── requirements.txt
│   ├── app/
│   │   ├── api/                     # 25 REST routers (one per domain)
│   │   │   ├── admin.py             # Demo gen, purge, stats, doc downloads
│   │   │   ├── agents.py            # SSE query endpoint
│   │   │   ├── documents.py         # Upload + pipeline
│   │   │   ├── equipment.py
│   │   │   ├── sensors.py
│   │   │   ├── permits.py
│   │   │   ├── managed_work_orders.py
│   │   │   └── ...
│   │   ├── agents/
│   │   │   └── orchestrator.py      # 5-agent SSE pipeline
│   │   ├── services/
│   │   │   ├── db_service.py        # All DB read/write operations
│   │   │   ├── llm_service.py       # GPT-4.1 + heuristic fallback
│   │   │   ├── demo_docs.py         # Sample document generator (PDF/DOCX/XLSX/PPTX/TXT/CSV)
│   │   │   ├── doc_entity_mapper.py # Document entities → DB tables
│   │   │   ├── vector_service.py    # Qdrant indexing
│   │   │   ├── seed.py              # DB seed on first startup
│   │   │   └── threshold_monitor.py # Background sensor alarm agent
│   │   ├── db/
│   │   │   ├── models.py            # 25 SQLAlchemy models
│   │   │   └── database.py          # Async session factory
│   │   └── core/config.py           # Settings loaded from .env
│   └── tests/                       # pytest suite (13 tests)
│
├── frontend/
│   ├── src/
│   │   ├── app/                     # 21 Next.js App Router pages
│   │   ├── components/
│   │   │   ├── Layout/Sidebar.tsx   # Navigation + demo generator modal
│   │   │   ├── Dashboard/           # Widget components
│   │   │   └── ui/                  # Shared primitives
│   │   └── lib/
│   │       ├── api.ts               # All API fetch helpers
│   │       ├── types.ts             # TypeScript interfaces
│   │       ├── page-state.ts        # Zustand page-state store
│   │       ├── theme-context.tsx    # Light/dark theme
│   │       └── user-context.tsx     # Acting-As user context
│   └── package.json
│
├── docker-compose.yml
├── .env.example
├── abc/                             # Downloaded sample documents
└── README.md
```

---

## API Quick Reference

```bash
# Equipment
GET    /api/v1/equipment                   # List all
GET    /api/v1/equipment/{id}              # Detail
GET    /api/v1/equipment/{id}/brain        # Full knowledge context
GET    /api/v1/equipment/{id}/timeline     # Chronological event history

# AI Query (streaming SSE)
POST   /api/v1/agents/query                # Body: {"query": "...", "equipment_id": "P-101"}

# Documents
GET    /api/v1/documents                   # List
POST   /api/v1/documents/upload            # Upload (multipart/form-data, field: file)
GET    /api/v1/documents/{id}              # Detail + extracted entities

# Sensors
GET    /api/v1/sensors                     # All equipment sensor overview
GET    /api/v1/sensors/{equipment_id}      # Full sensor dashboard + history

# Workflow objects
GET/POST  /api/v1/work-orders              # Managed work orders
GET/POST  /api/v1/permits                  # Permits to Work
GET/POST  /api/v1/incidents                # Incident reports
GET/POST  /api/v1/inspections              # Quality inspections
GET/POST  /api/v1/procedures               # Safety procedures

# Admin
POST   /api/v1/admin/generate-demo         # Seed full demo dataset
GET    /api/v1/admin/stats                 # Record counts per entity type
DELETE /api/v1/admin/purge?entity=all      # Full data reset
GET    /api/v1/admin/demo-docs             # List downloadable sample docs
GET    /api/v1/admin/demo-docs/{filename}  # Download a sample document

# Graph
GET    /api/v1/knowledge-graph/nodes       # All graph nodes
GET    /api/v1/knowledge-graph/links       # All graph edges

# Interactive docs
GET    /docs                               # Swagger UI
GET    /redoc                              # Redoc
```

---