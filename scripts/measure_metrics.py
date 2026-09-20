#!/usr/bin/env python3
"""
EPIC — Empirical Metric Measurement Script
Measures repository figures, each derived from the code:
- Table and ORM model counts (backend/app/db/models.py)
- Pydantic schema count (BaseModel subclasses under backend/app)
- Frontend page count (page.tsx under frontend/src/app/)
- Concurrent query retrievers (backend/app/agents/orchestrator.py)
- Route counts by HTTP method (the live FastAPI route table)
"""
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

def measure_tables():
    models_path = BACKEND_DIR / "app" / "db" / "models.py"
    content = models_path.read_text(encoding="utf-8")
    tablenames = re.findall(r'__tablename__\s*=\s*["\']([^"\']+)["\']', content)
    return tablenames

def measure_orm_models():
    models_path = BACKEND_DIR / "app" / "db" / "models.py"
    content = models_path.read_text(encoding="utf-8")
    classes = re.findall(r'class\s+([A-Za-z0-9_]+)\s*\(([^)]*Base[^)]*)\):', content)
    return classes

def measure_pydantic_schemas():
    schemas = []
    # Search all python files in backend/app for BaseModel subclasses
    app_dir = BACKEND_DIR / "app"
    for py_file in app_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            matches = re.findall(r'class\s+([A-Za-z0-9_]+)\s*\(([^)]*BaseModel[^)]*)\):', content)
            for m in matches:
                schemas.append((py_file.relative_to(REPO_ROOT), m[0]))
        except Exception:
            pass
    return schemas

def measure_frontend_pages():
    pages_dir = FRONTEND_DIR / "src" / "app"
    pages = list(pages_dir.rglob("page.tsx"))
    return [p.relative_to(pages_dir) for p in pages]

def measure_agents():
    agents_dir = BACKEND_DIR / "app" / "agents"
    agent_files = list(agents_dir.glob("*.py"))
    # Also inspect orchestrator.py for agent definitions
    orch_path = agents_dir / "orchestrator.py"
    retrievers = []
    if orch_path.exists():
        content = orch_path.read_text(encoding="utf-8")
        retrievers = re.findall(r'async def\s+(_equipment_brain|_build_[a-z]+_context)\(', content)
    return agent_files, retrievers

def measure_backend_routes():
    from main import app
    from checkRouteGuards import get_all_routes
    all_routes = get_all_routes(app)
    endpoint_set = set()
    total_endpoints = 0
    route_breakdown = {}
    for path, r, _ in all_routes:
        methods = getattr(r, "methods", set())
        for m in methods:
            if m in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
                endpoint_set.add((m, path))
                route_breakdown[m] = route_breakdown.get(m, 0) + 1
                total_endpoints += 1
    return len(all_routes), total_endpoints, route_breakdown, len(endpoint_set)

if __name__ == "__main__":
    print("================ EPIC EMPIRICAL METRICS ================")
    tables = measure_tables()
    print(f"1. Database Tables (count: {len(tables)}):")
    for t in sorted(tables):
        print(f"   - {t}")

    orm_models = measure_orm_models()
    print(f"\n2. SQLAlchemy ORM Models (count: {len(orm_models)}):")
    for m in orm_models:
        print(f"   - {m[0]}")

    schemas = measure_pydantic_schemas()
    print(f"\n3. Pydantic Schemas (count: {len(schemas)}):")
    print(f"   Total BaseModel classes across backend/app: {len(schemas)}")

    pages = measure_frontend_pages()
    print(f"\n4. Frontend App Router Pages (count: {len(pages)}):")
    for p in sorted(pages):
        print(f"   - {p}")

    agent_files, retrievers = measure_agents()
    print(f"\n5. Backend Agents:")
    print(f"   Agent files in backend/app/agents/: {[f.name for f in agent_files]}")
    print(f"   Concurrent retrievers in orchestrator.py ({len(retrievers)}): {retrievers}")

    all_r_count, total_endpoints, route_breakdown, unique_endpoints = measure_backend_routes()
    print(f"\n6. Backend Routes:")
    print(f"   Total Route objects: {all_r_count}")
    print(f"   Total Method-Endpoint combinations: {total_endpoints}")
    print(f"   Unique (Method, Path) pairs: {unique_endpoints}")
    print(f"   Method breakdown: {route_breakdown}")
