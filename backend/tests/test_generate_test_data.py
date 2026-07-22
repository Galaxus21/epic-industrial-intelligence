"""
Generator Tests — Manifest Parsing and Multi-format Output Validation
Tests the root-level dataset generator for deterministic parsing and file output.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generate_test_data import (  # noqa: E402
    CATEGORY_DIRS,
    DocumentSpec,
    generate_documents,
    parse_doc_id_filter,
    parse_manifest_from_plan,
)


@pytest.fixture
def plan_path() -> Path:
    return ROOT / "plan.md"


@pytest.fixture
def temp_output_dir() -> Path:
    out = Path(tempfile.mkdtemp(prefix="hck123-gen-"))
    yield out
    shutil.rmtree(out, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def seed_test_db() -> None:
    """Override backend autouse DB seeding fixture for file-generation tests."""
    return None


def test_manifest_parses_110_rows(plan_path: Path) -> None:
    specs = parse_manifest_from_plan(plan_path)
    assert len(specs) == 110
    assert specs[0].doc_id == 1
    assert specs[-1].doc_id == 110


def test_manifest_category_distribution(plan_path: Path) -> None:
    specs = parse_manifest_from_plan(plan_path)
    counts: dict[str, int] = {}
    for spec in specs:
        counts[spec.category] = counts.get(spec.category, 0) + 1

    assert counts == {
        "project_management": 15,
        "engineering_drawings": 15,
        "safety_compliance": 15,
        "maintenance_equipment": 15,
        "quality_management": 15,
        "procurement_contracts": 10,
        "emails": 15,
        "reports_presentations": 10,
    }


def test_parse_doc_id_filter() -> None:
    parsed = parse_doc_id_filter("1-3,8,10-11")
    assert parsed == {1, 2, 3, 8, 10, 11}


def test_sample_generation_multi_format(plan_path: Path, temp_output_dir: Path) -> None:
    specs = parse_manifest_from_plan(plan_path)
    wanted_ids = {1, 2, 9, 16, 18, 20, 21, 24, 31, 46, 55, 61, 76, 86, 101}
    subset = [s for s in specs if s.doc_id in wanted_ids]

    generated = generate_documents(temp_output_dir, specs=subset, plan_path=plan_path)
    assert len(generated) == len(subset)

    # Key by stem (without extension) so eml→txt renaming doesn't break lookup.
    expected_by_stem = {Path(spec.filename).stem: spec for spec in subset}
    for out_file in generated:
        assert out_file.exists()
        assert out_file.stat().st_size > 0
        spec = expected_by_stem[out_file.stem]
        category_dir = CATEGORY_DIRS[spec.category]
        assert out_file.parent.name == category_dir

    generated_exts = {p.suffix.lower() for p in generated}
    assert generated_exts == {
        ".docx",
        ".pdf",
        ".xlsx",
        ".pptx",
        ".dxf",
        ".svg",
        ".png",
        ".txt",
    }


def test_docx_pdf_contains_expected_headers(plan_path: Path, temp_output_dir: Path) -> None:
    specs = parse_manifest_from_plan(plan_path)
    subset = [
        next(spec for spec in specs if spec.doc_id == 1),
        next(spec for spec in specs if spec.doc_id == 31),
        next(spec for spec in specs if spec.doc_id == 86),
    ]

    generated = generate_documents(temp_output_dir, specs=subset, plan_path=plan_path)
    docx_path = next(path for path in generated if path.suffix.lower() == ".docx")
    pdf_path = next(path for path in generated if path.suffix.lower() == ".pdf")
    email_txt_path = next(path for path in generated if path.parent.name == "07_emails")

    # Quick sanity checks on binary and textual outputs.
    assert docx_path.read_bytes()[:2] == b"PK"
    assert pdf_path.read_bytes()[:5] == b"%PDF-"

    email_text = email_txt_path.read_text(encoding="utf-8", errors="replace")
    assert "Subject:" in email_text
    assert "Project: NH47-BPB-24" in email_text
    assert "Linked Entities:" in email_text


def test_all_specs_have_supported_format(plan_path: Path) -> None:
    specs = parse_manifest_from_plan(plan_path)
    supported = {"docx", "pdf", "xlsx", "pptx", "dxf", "svg", "png", "txt", "eml"}

    unsupported: list[DocumentSpec] = [s for s in specs if s.fmt not in supported]
    assert unsupported == []
