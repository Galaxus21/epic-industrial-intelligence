#!/usr/bin/env python3
"""
EPIC — Route Guard Verification Script
Inspects FastAPI's active route table at runtime to verify that all mutating
endpoints (POST, PUT, PATCH, DELETE) require authentication and enforce role barriers.

Usage:
    python scripts/checkRouteGuards.py --check
    python scripts/checkRouteGuards.py --reads
Exits with status 0 if 0 unguarded mutating routes exist; exits with status 1 if any unguarded routes are detected.
A guard here means a session or role dependency is present on the route. It does not say WHICH roles pass;
the role levels are pinned by the HTTP tests. --reads reports the GET endpoints that require no session
(informational, always exits 0): the check above covers mutating routes only.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, List, Set, Tuple

# Ensure backend directory is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import app  # noqa: E402
from app.core.auth import get_current_principal, get_current_user  # noqa: E402

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
READ_METHODS = {"GET"}

PUBLIC_ALLOWLIST = {
    "/api/v1/users/login",
    "/api/v1/users/logout",
}


def _is_allowlisted(path: str) -> bool:
    """Check if route matches the public allowlist (handles prefix variations)."""
    clean_path = path.rstrip("/")
    for allowed in PUBLIC_ALLOWLIST:
        if clean_path == allowed.rstrip("/") or clean_path.endswith(allowed.removeprefix("/api/v1")):
            return True
    return False


def get_all_routes(router: Any, prefix: str = "", parent_deps: list[Any] | None = None) -> list[Tuple[str, Any, list[Any]]]:
    """Recursively collect all endpoints with their path and dependencies."""
    routes: list[Tuple[str, Any, list[Any]]] = []
    parent_deps = parent_deps or []

    for r in getattr(router, "routes", []):
        # Handle modern FastAPI _IncludedRouter
        if type(r).__name__ == "_IncludedRouter":
            inc_prefix = prefix + (r.include_context.prefix or "")
            inc_deps = parent_deps + list(r.include_context.dependencies or [])
            routes.extend(get_all_routes(r.include_context.included_router, inc_prefix, inc_deps))
        elif hasattr(r, "routes"):
            sub_prefix = prefix + getattr(r, "prefix", "")
            sub_deps = parent_deps + list(getattr(r, "dependencies", []))
            routes.extend(get_all_routes(r, sub_prefix, sub_deps))
        else:
            full_path = prefix + getattr(r, "path", "")
            routes.append((full_path, r, parent_deps))

    return routes


def collect_dependency_calls(r: Any, parent_deps: list[Any]) -> list[Any]:
    """Every dependency callable that applies to route r: router-level, route-level and handler-signature."""
    dep_callables: list[Any] = []
    for dep in parent_deps + list(getattr(r, "dependencies", [])):
        dep_callables.append(getattr(dep, "dependency", dep))

    if hasattr(r, "dependant"):
        for sub_dep in r.dependant.dependencies:
            dep_callables.append(sub_dep.call)
            for nested in getattr(sub_dep, "dependencies", []):
                dep_callables.append(nested.call)
    return dep_callables


def inspect_route_guards(checked_methods: Set[str] = MUTATING_METHODS) -> Tuple[List[dict], List[dict]]:
    """Inspect all routes in the application that use one of checked_methods.

    Returns:
        (guarded_or_allowlisted_routes, unguarded_routes)
    """
    all_routes = get_all_routes(app)
    guarded_or_allowed: list[dict] = []
    unguarded: list[dict] = []

    for path, r, parent_deps in all_routes:
        methods = [m for m in getattr(r, "methods", set()) if m in checked_methods]
        if not methods:
            continue

        dep_callables = collect_dependency_calls(r, parent_deps)

        # Check for guard mechanisms
        guards: list[str] = []
        for c in dep_callables:
            if hasattr(c, "required_roles"):
                guards.append(f"roles:{getattr(c, 'required_roles')}")
            elif c == get_current_user or getattr(c, "__name__", "") == "get_current_user":
                guards.append("get_current_user")
            elif c == get_current_principal or getattr(c, "__name__", "") == "get_current_principal":
                guards.append("get_current_principal")
            elif getattr(c, "__name__", "") in ("_check", "_bootstrap_check"):
                guards.append(f"guard:{getattr(c, '__name__')}")

        is_allowed = _is_allowlisted(path)
        is_guarded = len(guards) > 0

        info = {
            "path": path,
            "methods": methods,
            "endpoint": getattr(r, "name", str(r)),
            "guards": guards,
            "is_allowlisted": is_allowed,
            "required_roles": next((tuple(c.required_roles) for c in dep_callables if hasattr(c, "required_roles")), None),
        }

        if is_guarded or is_allowed:
            guarded_or_allowed.append(info)
        else:
            unguarded.append(info)

    return guarded_or_allowed, unguarded


def report_reads() -> int:
    """Informational: which GET endpoints need no session. Never fails the run."""
    guarded, unguarded = inspect_route_guards(READ_METHODS)
    print("=== EPIC Read Endpoint Report (informational) ===")
    print(f"GET endpoints scanned             : {len(guarded) + len(unguarded)}")
    print(f"Requiring a session               : {len(guarded)}")
    print(f"Requiring no session              : {len(unguarded)}")
    for r in sorted(unguarded, key=lambda x: x["path"]):
        print(f"  open: GET {r['path']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify route guards on all mutating FastAPI endpoints.")
    parser.add_argument("--check", action="store_true", help="Exit with non-zero status if unguarded routes exist.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print details for every route.")
    parser.add_argument("--reads", action="store_true", help="Report GET endpoints that require no session, then exit 0.")
    args = parser.parse_args()
    if args.reads:
        return report_reads()

    guarded_or_allowed, unguarded = inspect_route_guards()
    total_mutating = len(guarded_or_allowed) + len(unguarded)
    allowlisted_count = len([r for r in guarded_or_allowed if r["is_allowlisted"] and not r["guards"]])
    guarded_count = len(guarded_or_allowed) - allowlisted_count

    print(f"=== EPIC Route Guard Verification ===")
    print(f"Total mutating endpoints scanned : {total_mutating}")
    print(f"Guarded mutating endpoints        : {guarded_count}")
    print(f"Allowlisted public endpoints      : {allowlisted_count}")
    print(f"Unguarded mutating endpoints      : {len(unguarded)}")

    if args.verbose:
        print("\n--- Route Details ---")
        for r in sorted(guarded_or_allowed, key=lambda x: x["path"]):
            status = "ALLOWLISTED" if r["is_allowlisted"] and not r["guards"] else "GUARDED"
            methods_str = ",".join(r["methods"])
            guards_str = ", ".join(r["guards"]) if r["guards"] else "public allowlist"
            print(f"[{status}] {methods_str:<8} {r['path']:<50} -> {guards_str}")

    if unguarded:
        print("\n[ERROR] Found unguarded mutating endpoints:")
        for r in unguarded:
            methods_str = ",".join(r["methods"])
            print(f"  FAILED: {methods_str:<8} {r['path']} ({r['endpoint']})")
        if args.check:
            print("\nVerification FAILED: unguarded mutating routes detected.")
            return 1
        print("\n(informational run: pass --check to fail on unguarded routes)")
        return 0

    print("\n[PASS] All mutating endpoints are properly guarded. 0 unguarded routes found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
