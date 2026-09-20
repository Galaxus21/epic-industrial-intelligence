#!/usr/bin/env python3
"""
EPIC — Schema Reference Generator
Regenerates the machine-derived part of SCHEMA_REFERENCE.md (the block between the GENERATED markers)
from the SQLAlchemy metadata, the comments in backend/app/db/models.py and the audit call sites under
backend/app, so the table, column, foreign-key, index, relationship and audited-event listings cannot drift.

Usage:
    python scripts/generateSchemaReference.py            # rewrite the generated block
    python scripts/generateSchemaReference.py --check    # exit 1 if the file is stale (nothing written)
"""
from __future__ import annotations

import argparse
import ast
import inspect
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
APP_DIRECTORY = BACKEND_DIR / "app"
MODELS_PATH = APP_DIRECTORY / "db" / "models.py"
DOCUMENT_PATH = REPO_ROOT / "SCHEMA_REFERENCE.md"
BEGIN_MARKER = "<!-- BEGIN GENERATED: schema -->"
END_MARKER = "<!-- END GENERATED: schema -->"
EQUIPMENT_TABLE = "equipment"
EQUIPMENT_ID_COLUMN = "equipment_id"
EQUIPMENT_IDS_COLUMN = "equipment_ids"
GROUP_LABEL_MAX_WORDS = 4
AUDIT_MODULES = frozenset({"app.services.audit", "app.core.audit"})
AUDIT_FUNCTIONS = frozenset({"record", "audit", "create_audit_log"})
# Links the code follows by convention (string ids stored in a column) with no database foreign key.
CONVENTION_LINKS = (("graph_nodes", "graph_links", "source and target hold a node id (no FK)"),)

sys.path.insert(0, str(BACKEND_DIR))

from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402

from app.db import models  # noqa: E402,F401  (importing registers every table on Base.metadata)
from app.db.database import Base  # noqa: E402


def headRevision() -> str:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def modelClassesByTable() -> dict[str, type]:
    return {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers}


def isGroupLabel(comment: str) -> bool:
    """A short comment such as `# Actor` heads a group of columns; it is not a note about the next one."""
    return len(comment.split()) <= GROUP_LABEL_MAX_WORDS and ":" not in comment


def columnNotesFromSource(source: str) -> dict[tuple[str, str], str]:
    """(class, column) -> the `#` comments trailing the column or directly above it."""
    notes: dict[tuple[str, str], str] = {}
    className = None
    pending: list[str] = []
    for line in source.splitlines():
        classMatch = re.match(r"class (\w+)\(Base\):", line)
        if classMatch:
            className, pending = classMatch.group(1), []
            continue
        commentMatch = re.match(r"    #\s?(.*)$", line)
        if commentMatch and className:
            pending.append(commentMatch.group(1).strip())
            continue
        columnMatch = re.match(r"    (\w+): Mapped\[", line)
        if columnMatch and className:
            trailing = re.search(r"\s#\s*(.+)$", line)
            parts = ([] if isGroupLabel(" ".join(pending)) else pending) + ([trailing.group(1).strip()] if trailing else [])
            if parts:
                notes[(className, columnMatch.group(1))] = " ".join(parts)
        if line.strip():
            pending = []
    return notes


def renderDefault(column) -> str:
    if column.default is None:
        return "—"
    argument = column.default.arg
    return f"`{getattr(argument, '__name__', repr(argument))}()`" if callable(argument) else f"`{argument!r}`"


def renderNotes(column, sourceNote: str | None) -> str:
    notes: list[str] = []
    if column.primary_key:
        notes.append("primary key")
    for foreignKey in column.foreign_keys:
        cascade = f" ON DELETE {foreignKey.ondelete}" if foreignKey.ondelete else ""
        notes.append(f"FK → `{foreignKey.target_fullname}`{cascade}")
    if column.unique:
        notes.append("unique")
    if sourceNote:
        notes.append(sourceNote)
    return " · ".join(notes).replace("|", "\\|")


def renderTable(table, modelClass: type, sourceNotes: dict[tuple[str, str], str]) -> str:
    lines = [f"### `{table.name}` — {modelClass.__name__}", ""]
    description = inspect.cleandoc(vars(modelClass).get("__doc__") or "").replace("\n", " ")
    if description:
        lines += [description, ""]
    lines += ["| Column | Type | Null | Default | Notes |", "|---|---|---|---|---|"]
    for column in table.columns:
        lines.append(
            f"| `{column.name}` | {column.type} | {'yes' if column.nullable else 'no'} | {renderDefault(column)} "
            f"| {renderNotes(column, sourceNotes.get((modelClass.__name__, column.name)))} |"
        )
    indexes = sorted(table.indexes, key=lambda index: index.name)
    if indexes:
        listed = ", ".join(f"`{index.name}` ({', '.join(column.name for column in index.columns)})" for index in indexes)
        lines += ["", f"Indexes: {listed}"]
    return "\n".join(lines)


def relationshipLines(tables: dict) -> list[str]:
    lines: list[str] = []
    for table in tables.values():
        equipmentIdColumn = table.columns.get(EQUIPMENT_ID_COLUMN)
        if equipmentIdColumn is not None and table.name != EQUIPMENT_TABLE:
            if equipmentIdColumn.foreign_keys:
                lines.append(f'    {EQUIPMENT_TABLE} ||--o{{ {table.name} : "equipment_id FK, ON DELETE CASCADE"')
            else:
                cardinality = "||..o|" if equipmentIdColumn.primary_key else "||..o{"
                lines.append(f'    {EQUIPMENT_TABLE} {cardinality} {table.name} : "equipment_id, no FK"')
        if EQUIPMENT_IDS_COLUMN in table.columns:
            lines.append(f'    {EQUIPMENT_TABLE} }}o..o{{ {table.name} : "equipment_ids JSON list, no FK"')
    for parent, child, label in CONVENTION_LINKS:
        assert parent in tables and child in tables, f"convention link names a missing table: {parent}, {child}"
        lines.append(f'    {parent} ||..o{{ {child} : "{label}"')
    return lines


def auditFunctionAliases(tree: ast.AST) -> set[str]:
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module in AUDIT_MODULES
        for alias in node.names
        if alias.name in AUDIT_FUNCTIONS
    }


def literalAuditArguments(call: ast.Call, path: Path) -> tuple[str, str]:
    arguments = call.args[:2]
    if len(arguments) < 2 or not all(isinstance(argument, ast.Constant) and isinstance(argument.value, str) for argument in arguments):
        raise SystemExit(f"{path}:{call.lineno}: audit call without a literal action and object type; extend {Path(__file__).name}")
    return arguments[0].value, arguments[1].value


def auditedEvents(appDirectory: Path = APP_DIRECTORY) -> list[tuple[str, str, str]]:
    """(object type, action, writing module) for every call into app.services.audit under appDirectory."""
    events: set[tuple[str, str, str]] = set()
    for path in sorted(appDirectory.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = auditFunctionAliases(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in aliases:
                action, objectType = literalAuditArguments(node, path)
                events.add((objectType, action, path.stem))
    return sorted(events)


def renderAuditedEvents() -> str:
    rows = [f"| `{objectType}` | `{action}` | `{module}` |" for objectType, action, module in auditedEvents()]
    return "\n".join([
        "### Audited events", "",
        "`audit_logs` rows are written at exactly these call sites (found by scanning `backend/app` for calls to "
        "`record` and `audit` imported from `app.services.audit`):", "",
        "| Object type | Action | Written by |", "|---|---|---|", *rows,
    ])


def renderGenerated() -> str:
    tables = {table.name: table for table in sorted(Base.metadata.tables.values(), key=lambda table: table.name)}
    classes = modelClassesByTable()
    sourceNotes = columnNotesFromSource(MODELS_PATH.read_text(encoding="utf-8"))
    summary = f"{len(tables)} tables · Alembic head revision `{headRevision()}`."
    diagram = "\n".join(["```mermaid", "erDiagram", *relationshipLines(tables), "```"])
    sections = [renderTable(table, classes[name], sourceNotes) for name, table in tables.items()]
    return "\n\n".join([summary, diagram, *sections, renderAuditedEvents()])


def replaceGeneratedBlock(document: str, generated: str) -> str:
    if document.count(BEGIN_MARKER) != 1 or document.count(END_MARKER) != 1:
        raise SystemExit(f"{DOCUMENT_PATH.name} must contain exactly one {BEGIN_MARKER} / {END_MARKER} pair")
    head, rest = document.split(BEGIN_MARKER)
    _, tail = rest.split(END_MARKER)
    return f"{head}{BEGIN_MARKER}\n\n{generated}\n\n{END_MARKER}{tail}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="exit 1 if SCHEMA_REFERENCE.md is stale; write nothing")
    args = parser.parse_args()
    current = DOCUMENT_PATH.read_text(encoding="utf-8")
    updated = replaceGeneratedBlock(current, renderGenerated())
    if args.check:
        print("SCHEMA_REFERENCE.md is current" if updated == current else "SCHEMA_REFERENCE.md is STALE — run scripts/generateSchemaReference.py")
        return 0 if updated == current else 1
    DOCUMENT_PATH.write_text(updated, encoding="utf-8", newline="")
    print(f"wrote {DOCUMENT_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
