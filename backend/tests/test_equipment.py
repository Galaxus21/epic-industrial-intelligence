"""
Backend Tests — Equipment API and Demo Data
Tests equipment data accessors and timeline construction.
"""
import pytest
from app.services.demo_data import (
    get_equipment,
    get_equipment_incidents,
    get_maintenance_records,
    get_equipment_documents,
    find_similar_incidents,
    get_all_equipment_list,
)


def test_p101_exists():
    eq = get_equipment("P-101")
    assert eq is not None
    assert eq["id"] == "P-101"
    assert eq["health_score"] < 100


def test_p101_has_incidents():
    incidents = get_equipment_incidents("P-101")
    assert len(incidents) >= 2


def test_p101_has_overdue_maintenance():
    records = get_maintenance_records("P-101")
    overdue = [r for r in records if r.get("status") == "Overdue"]
    assert len(overdue) >= 1


def test_p101_has_documents():
    docs = get_equipment_documents("P-101")
    assert len(docs) >= 3
    doc_names = [d["name"] for d in docs]
    assert any("OEM" in n for n in doc_names)
    assert any("OISD" in n for n in doc_names)


def test_similar_incidents_vibration_bearing():
    results = find_similar_incidents(["vibration", "bearing"])
    assert len(results) >= 1
    assert any("INC-2022-034" in r["id"] for r in results)


def test_all_equipment_returns_multiple():
    all_eq = get_all_equipment_list()
    assert len(all_eq) >= 4


def test_unknown_equipment_returns_none():
    assert get_equipment("NONEXISTENT-999") is None
