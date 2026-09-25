"""
EPIC — The demo plant's people: sign-in profiles and the per-asset technician roster.

Every person the demo records, work orders and sample documents name is listed here, so a name the AI cites can
always be found. The demo users have no password: outside production they sign in with their employee ID alone, and
production refuses them (README section 8). E-mail addresses use the reserved `.example` domain (RFC 2606).
"""
from __future__ import annotations

from typing import Any

EMAIL_DOMAIN = "apex-refinery.example"

RAJESH_KUMAR = "Rajesh Kumar"
AMIT_SHAH = "Amit Shah"
PRIYA_NAIR = "Priya Nair"
ANAND_SHARMA = "Dr. Anand Sharma"
AHMED_KHAN = "Ahmed Khan"
DEEPA_MENON = "Deepa Menon"
SURESH_NAIR = "Suresh Nair"


def demoUsers() -> list[dict[str, Any]]:
    return [
        _user(1, RAJESH_KUMAR, "rajesh.kumar", "Maintenance — Rotating Equipment", "technician",
              ["Vibration Analysis Level I", "Hot Work Safety"]),
        _user(2, AMIT_SHAH, "amit.shah", "Reliability Engineering", "technician",
              ["Vibration Analysis Level II", "Mechanical Seal Maintenance"]),
        _user(3, PRIYA_NAIR, "priya.nair", "HSE", "supervisor", ["Process Safety", "Incident Investigation"]),
        _user(4, ANAND_SHARMA, "anand.sharma", "Inspection & QA", "supervisor",
              ["Pressure Equipment Inspection", "Root Cause Analysis"]),
        _user(5, AHMED_KHAN, "ahmed.khan", "Maintenance", "supervisor", ["Work Permit Issuer"]),
        _user(6, DEEPA_MENON, "deepa.menon", "Management", "manager", ["PMP", "Six Sigma Black Belt"]),
        _user(7, SURESH_NAIR, "suresh.nair", "Operations — Night Shift", "supervisor", ["Work Permit Issuer"]),
    ]


def demoTechnicians() -> list[dict[str, Any]]:
    """Who looks after which asset; the equipment page and the AI read this roster."""
    return [
        _technician("TECH-001", RAJESH_KUMAR, "Maintenance Technician", ["Centrifugal pumps", "Bearings", "Lubrication"],
                    12, ["P-101", "P-202"], "rajesh.kumar"),
        _technician("TECH-002", AMIT_SHAH, "Reliability Engineer", ["Vibration analysis", "Mechanical seals"],
                    8, ["P-101", "P-202", "K-401", "G-101"], "amit.shah"),
        _technician("TECH-003", AHMED_KHAN, "Maintenance Supervisor", ["Compressors", "Work permits", "Planning"],
                    15, ["P-101", "P-202", "K-401", "G-101"], "ahmed.khan"),
        _technician("TECH-004", ANAND_SHARMA, "Inspection Engineer", ["Heat exchangers", "Pressure vessels"],
                    20, ["HX-201", "V-301"], "anand.sharma"),
    ]


def demoPersonNames() -> set[str]:
    return {user["name"] for user in demoUsers()}


def _user(number: int, name: str, mailbox: str, department: str, role: str,
          certifications: list[str]) -> dict[str, Any]:
    return {
        "id": f"USR-DEMO-{number:03d}", "employee_id": f"EMP-{number:03d}", "name": name,
        "email": f"{mailbox}@{EMAIL_DOMAIN}", "department": department, "role": role,
        "certifications": certifications,
    }


def _technician(technicianId: str, name: str, role: str, expertise: list[str], yearsExperience: int,
                equipmentIds: list[str], mailbox: str) -> dict[str, Any]:
    return {
        "id": technicianId, "name": name, "role": role, "expertise": expertise,
        "years_experience": yearsExperience, "equipment_ids": equipmentIds, "available": True,
        "contact": f"{mailbox}@{EMAIL_DOMAIN}",
    }
