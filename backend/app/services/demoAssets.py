"""
EPIC — The demo plant's assets: equipment with live readings, compliance findings and spare parts.

Six assets in two units. P-101 carries the main story (DE bearing damage found 8 days ago, vibration now above the
alarm, no installed spare); K-401 carries the second (a new filter did not stop a pressure decline, so the cause is
elsewhere). Days come from demoTimeline, and each live reading is the last point of its seeded series
(demoSensorSeries). Compliance scores are not stored here: the seed derives them from the issues (complianceScore).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services import demoTimeline as timeline

LOW_STOCK = "Low Stock"
AVAILABLE = "Available"
OUT_OF_STOCK = "Out of Stock"


def demoEquipment() -> list[dict[str, Any]]:
    return [
        {"id": "P-101", "name": "Crude Oil Feed Pump", "type": "Centrifugal Pump", "location": "Unit 4 — CDU",
         "health_score": 72.0, "failure_probability": 31.0,
         "maintenance_due_days": -timeline.P101_ROUTE_OVERDUE_DAYS, "criticality": "Critical",
         "status": "Running — Alert", "manufacturer": "Flowserve", "model": "PVXM-100", "installed_date": "2018-04-15",
         "current_readings": {
             "vibration_de": _reading(7.4, "mm/s", 4.5, 7.1, 11.2),
             "bearing_temp_de": _reading(78, "°C", 55, 75, 90),
             "discharge_pressure": _reading(8.2, "bar", 8.5, 6.0),
             "flow_rate": _reading(242, "m³/hr", 250, 200),
         },
         "downstream_equipment": ["HX-201"], "technicians": ["Rajesh Kumar", "Amit Shah"],
         "specifications": {"rated_flow": "250 m³/hr", "rated_head": "70 m", "motor_power": "75 kW",
                            "speed": "2,960 rpm", "bearings": "SKF 6311/C3 DE and NDE, grease-lubricated",
                            "installed_spare": "None: stopping P-101 stops crude feed to the CDU"}},
        {"id": "P-202", "name": "Reflux Pump", "type": "Centrifugal Pump", "location": "Unit 4 — CDU",
         "health_score": 85.0, "failure_probability": 8.0,
         "maintenance_due_days": timeline.P202_ROUTE_INTERVAL_DAYS - timeline.P202_LAST_ROUTE_DAYS_AGO,
         "criticality": "High", "status": "Running", "manufacturer": "Sulzer", "model": "MBN50-160",
         "installed_date": "2020-07-10",
         "current_readings": {
             "vibration_de": _reading(3.1, "mm/s", 4.5, 7.1, 11.2),
             "bearing_temp_de": _reading(51, "°C", 55, 75, 90),
         },
         "technicians": ["Rajesh Kumar", "Amit Shah"],
         "specifications": {"rated_flow": "180 m³/hr", "rated_head": "50 m", "motor_power": "37 kW",
                            "installed_spare": "None"}},
        {"id": "HX-201", "name": "Crude Feed Pre-heater", "type": "Heat Exchanger", "location": "Unit 4 — CDU",
         "health_score": 88.0, "failure_probability": 7.0,
         "maintenance_due_days": timeline.HX201_PERFORMANCE_INTERVAL_DAYS - timeline.HX201_PERFORMANCE_CHECK_DAYS_AGO,
         "criticality": "High", "status": "Running", "manufacturer": "GEA", "model": "HX-ST-450",
         "installed_date": "2017-09-01",
         "current_readings": {
             "tube_side_dp": _reading(1.8, "bar", 2.0, 3.5),
             "shell_side_temp_out": _reading(142, "°C", 145, 160),
         },
         "upstream_equipment": ["P-101"], "downstream_equipment": ["V-301"], "technicians": ["Dr. Anand Sharma"],
         "specifications": {"duty": "12.5 MW", "area": "450 m²", "tubes": "450"}},
        {"id": "V-301", "name": "Crude Feed Surge Drum", "type": "Pressure Vessel", "location": "Unit 4 — CDU",
         "health_score": 95.0, "failure_probability": 2.0,
         "maintenance_due_days": timeline.V301_INSPECTION_INTERVAL_DAYS - timeline.V301_EXTERNAL_INSPECTION_DAYS_AGO,
         "criticality": "Critical", "status": "Running", "manufacturer": "L&T Heavy Engineering",
         "model": "V-H-3200", "installed_date": "2016-11-20",
         "current_readings": {
             "level": _reading(65, "%", 60, 85, 90),
             "pressure": _reading(3.2, "barg", 3.5, 5.0, 6.0),
         },
         "upstream_equipment": ["HX-201"], "technicians": ["Dr. Anand Sharma"],
         "specifications": {"volume": "120 m³", "design_pressure": "6 barg", "design_temp": "200°C",
                            "retirement_thickness": "16.0 mm"}},
        {"id": "K-401", "name": "Process Air Compressor", "type": "Compressor", "location": "Unit 5 — VDU",
         "health_score": 68.0, "failure_probability": 18.0,
         "maintenance_due_days": timeline.K401_FILTER_INTERVAL_DAYS - timeline.K401_FILTER_CHANGE_DAYS_AGO,
         "criticality": "High", "status": "Running — Degraded", "manufacturer": "Atlas Copco", "model": "ZH350",
         "installed_date": "2019-03-15",
         "current_readings": {
             "discharge_pressure": _reading(11.2, "bar", 12.5, 9.0),
             "discharge_temp": _reading(186, "°C", 175, 200),
             "vibration": _reading(3.4, "mm/s", 3.5, 5.5),
         },
         "upstream_equipment": ["G-101"], "technicians": ["Ahmed Khan", "Amit Shah"],
         "specifications": {"capacity": "35 000 Nm³/hr", "rated_discharge_pressure": "12.5 bar",
                            "intercooler_design_approach": "8 °C", "inlet_filter_interval": "60 days"}},
        {"id": "G-101", "name": "Cooling Tower Fan", "type": "Fan", "location": "Unit 5 — VDU",
         "health_score": 78.0, "failure_probability": 12.0,
         "maintenance_due_days": timeline.G101_BLADE_INSPECTION_INTERVAL_DAYS - timeline.G101_BLADE_INSPECTION_DAYS_AGO,
         "criticality": "Medium", "status": "Running", "manufacturer": "Howden", "model": "AF-1800",
         "installed_date": "2021-05-10",
         "current_readings": {
             "vibration": _reading(2.8, "mm/s", 3.0, 5.0),
             "current": _reading(145, "A", 150, 175),
         },
         "downstream_equipment": ["K-401"], "technicians": ["Ahmed Khan"],
         "specifications": {"airflow": "850 000 m³/hr", "motor_power": "110 kW", "blades": "8"}},
    ]


def demoCompliance(now: datetime) -> list[dict[str, Any]]:
    """Open issues and passed checks per asset. Issue IDs are stable; the texts cite site procedures only."""
    k401Incident = timeline.k401IncidentId(now)
    return [
        {"equipment_id": "P-101", "issues": [
            _issue("CI-P101-1", "DE vibration 7.4 mm/s is above the site alarm limit of 7.1 mm/s; SOP-ROT-VIB asks "
                   "for a documented run-or-stop decision within 4 hours of an alarm.", "High", "SOP-ROT-VIB"),
            _issue("CI-P101-2", "DE bearing temperature 78 °C is above the site alarm limit of 75 °C.",
                   "High", "SOP-ROT-VIB"),
            _issue("CI-P101-3", f"Monthly regrease and vibration route MR-P101-034 is "
                   f"{timeline.P101_ROUTE_OVERDUE_DAYS} days overdue; SOP-P101-BEARING sets a "
                   f"{timeline.P101_REGREASE_INTERVAL_DAYS}-day interval.", "Medium", "SOP-P101-BEARING"),
         ], "passed": [
            {"item": "SOP-P101-SEAL: seal inspection at the 36-month mark is current"},
            {"item": "SOP-SAFE-LOTO: isolation points for P-101 are listed and tagged"},
            {"item": "Every maintenance visit in the last 12 months has a CMMS record"},
         ]},
        {"equipment_id": "P-202", "issues": [
            _issue("CI-P202-1", "Seal flush line insulation damaged near the gland (found on route MR-P202-021); "
                   "repair requested.", "Low", "SOP-P202-SEAL"),
         ], "passed": [
            {"item": "SOP-ROT-VIB: vibration and bearing temperature within limits"},
            {"item": "SOP-P202-SEAL: annual seal inspection current"},
         ]},
        {"equipment_id": "HX-201", "issues": [], "passed": [
            {"item": "SOP-HX-INSP: annual tube-bundle inspection current (2 of 450 tubes plugged; limit 5%)"},
            {"item": "Quarterly thermal performance check current"},
        ]},
        {"equipment_id": "V-301", "issues": [], "passed": [
            {"item": "Statutory pressure-vessel inspection certificate current (site register PV-301)"},
            {"item": "PSV-301 tested and recertified within its 24-month interval"},
            {"item": "Ultrasonic thickness survey: minimum 17.6 mm against 16.0 mm retirement thickness"},
        ]},
        {"equipment_id": "K-401", "issues": [
            _issue("CI-K401-1", "Discharge pressure 11.2 bar is 10% below the rated 12.5 bar; SOP-K401-PERF asks for "
                   "an investigation when the drop stays above 5% for 3 days.", "Medium", "SOP-K401-PERF"),
            _issue("CI-K401-2", f"Corrective action CA-K401-3 from {k401Incident} (inlet-filter differential-pressure "
                   "transmitter) is still open.", "Low", "CAPA register"),
         ], "passed": [
            {"item": f"CMMS inlet-filter interval is {timeline.K401_FILTER_INTERVAL_DAYS} days "
                     f"(CA-K401-2 closed after {k401Incident})"},
            {"item": "Pressure relief valve test current"},
            {"item": "Motor insulation resistance test: pass"},
         ]},
        {"equipment_id": "G-101", "issues": [
            _issue("CI-G101-1", "Six-monthly fan blade erosion-coating inspection falls due in "
                   f"{timeline.G101_BLADE_INSPECTION_INTERVAL_DAYS - timeline.G101_BLADE_INSPECTION_DAYS_AGO} days; "
                   "scaffold not yet booked.", "Low", "OEM manual"),
         ], "passed": [
            {"item": "Motor thermal protection functional"},
            {"item": "SOP-ROT-VIB: fan vibration within limits"},
         ]},
    ]


def demoSpareParts() -> list[dict[str, Any]]:
    return [
        _part("SP-DEMO-001", "Deep groove ball bearing SKF 6311/C3", "SKF-6311-C3", ["P-101", "P-202"],
              3, 2, 7, "Warehouse A — Rack 4", 280),
        _part("SP-DEMO-002", "Cartridge mechanical seal, 50 mm", "JC-8B1-50", ["P-101", "P-202"],
              1, 2, 14, "Warehouse A — Rack 5", 3200),
        _part("SP-DEMO-003", "HX-201 tube-bundle gasket set", "GEA-HX450-GS", ["HX-201"], 2, 1, 21,
              "Warehouse B — Row 2", 1850),
        _part("SP-DEMO-004", "K-401 inlet filter element", "AC-ZH350-FE", ["K-401"], 3, 3, 5,
              "Warehouse B — Row 6", 450),
        _part("SP-DEMO-005", "Bearing grease SKF LGMT 2, 400 g cartridge", "SKF-LGMT2-04", ["P-101", "P-202"],
              12, 6, 5, "Warehouse A — Rack 1", 18),
        _part("SP-DEMO-006", "K-401 stage-2 intercooler gasket set", "AC-ZH350-ICG", ["K-401"], 1, 1, 30,
              "Warehouse B — Row 6", 620),
    ]


def stockStatus(quantityOnHand: int, reorderPoint: int) -> str:
    if quantityOnHand == 0:
        return OUT_OF_STOCK
    return LOW_STOCK if quantityOnHand <= reorderPoint else AVAILABLE


def _reading(value: float, unit: str, normal: float, alarm: float, trip: float | None = None) -> dict[str, Any]:
    reading = {"value": value, "unit": unit, "normal": normal, "alarm": alarm}
    if trip is not None:
        reading["trip"] = trip
    return reading


def _issue(issueId: str, item: str, severity: str, standard: str) -> dict[str, str]:
    return {"id": issueId, "item": item, "severity": severity, "standard": standard}


def _part(partId: str, name: str, partNumber: str, equipmentIds: list[str], quantityOnHand: int, reorderPoint: int,
          leadTimeDays: int, location: str, unitCostUsd: float) -> dict[str, Any]:
    return {
        "id": partId, "name": name, "part_number": partNumber, "equipment_ids": equipmentIds,
        "quantity_on_hand": quantityOnHand, "reorder_point": reorderPoint, "lead_time_days": leadTimeDays,
        "location": location, "unit_cost_usd": unitCostUsd, "status": stockStatus(quantityOnHand, reorderPoint),
    }
