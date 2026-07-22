"""
AI Operations Brain — SQLAlchemy ORM Models
Every entity that was previously a hardcoded Python dict now lives in PostgreSQL.
demo_data.py is only imported once at startup to seed these tables.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    type: Mapped[str] = mapped_column(String, default="Unknown Equipment")
    location: Mapped[str] = mapped_column(String, default="")
    health_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    failure_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    compliance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    maintenance_due_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    criticality: Mapped[str] = mapped_column(String, default="Unknown")
    status: Mapped[str] = mapped_column(String, default="Unknown")
    manufacturer: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    installed_date: Mapped[str | None] = mapped_column(String, nullable=True)
    technicians: Mapped[list | None] = mapped_column(JSON, nullable=True)
    current_readings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    downstream_equipment: Mapped[list | None] = mapped_column(JSON, nullable=True)
    specifications: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    discovered: Mapped[bool] = mapped_column(Boolean, default=False)
    manually_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    source_documents: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String, index=True)
    date: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, default="")
    severity: Mapped[str] = mapped_column(String, default="Medium")
    symptom: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause_category: Mapped[str | None] = mapped_column(String, nullable=True)
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    lessons_learned: Mapped[str | None] = mapped_column(Text, nullable=True)
    downtime_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    technician: Mapped[str | None] = mapped_column(String, nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String, index=True)
    date: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_date: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String, default="Preventive")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="Completed")
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    technician: Mapped[str | None] = mapped_column(String, nullable=True)
    overdue_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class DocumentRecord(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, default="other")
    equipment_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    date: Mapped[str | None] = mapped_column(String, nullable=True)
    sections: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, default="processed")
    # pipeline_steps stores {step_key: "pending"|"done"}; serialised as "steps" in the API response
    pipeline_steps: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    entities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_step: Mapped[str | None] = mapped_column(String, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Compliance(Base):
    __tablename__ = "compliance"

    equipment_id: Mapped[str] = mapped_column(String, primary_key=True)
    overall_score: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String, default="Compliant")
    issues: Mapped[list | None] = mapped_column(JSON, nullable=True)
    passed: Mapped[list | None] = mapped_column(JSON, nullable=True)


class SparePart(Base):
    __tablename__ = "spare_parts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    equipment_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    part_number: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    reorder_point: Mapped[int] = mapped_column(Integer, default=0)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    unit_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="Available")


class Technician(Base):
    __tablename__ = "technicians"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    expertise: Mapped[list | None] = mapped_column(JSON, nullable=True)
    certifications: Mapped[list | None] = mapped_column(JSON, nullable=True)
    years_experience: Mapped[int] = mapped_column(Integer, default=0)
    equipment_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    contact: Mapped[str | None] = mapped_column(String, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    val: Mapped[int] = mapped_column(Integer, default=10)


class GraphLink(Base):
    __tablename__ = "graph_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, index=True)
    target: Mapped[str] = mapped_column(String, index=True)
    label: Mapped[str] = mapped_column(String)


class SensorHistory(Base):
    __tablename__ = "sensor_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(String, index=True)
    sensor_key: Mapped[str] = mapped_column(String)
    readings: Mapped[list | None] = mapped_column(JSON, nullable=True)


class SavedChecklist(Base):
    """Inspection checklist extracted from an AI query result and saved for execution."""
    __tablename__ = "saved_checklists"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String, index=True)
    query_text: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")  # open | in_progress | completed
    # items: [{text, checked, notes}]
    items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    outcome_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SavedWorkOrder(Base):
    """Work order extracted from an AI query result, with interactive step tracking and feedback."""
    __tablename__ = "saved_work_orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String, index=True)
    query_text: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)
    wo_type: Mapped[str] = mapped_column(String, default="Corrective")
    description: Mapped[str] = mapped_column(Text, default="")
    estimated_duration_hours: Mapped[float] = mapped_column(Float, default=0)
    required_technicians: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String, default="open")  # open | in_progress | completed
    # steps: [{step, phase, title, description, safety_note, expected_duration_minutes, checked, actual_notes}]
    steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    spare_parts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    safety_precautions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    required_permits: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Completion feedback
    solution_worked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    extra_steps_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    actual_duration_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
#  PROJECT / PLANT HIERARCHY
# ═══════════════════════════════════════════════════════════════════════════════

class IntegrationConfig(Base):
    """Stores credentials/settings for external integrations (email, Slack, etc.)."""
    __tablename__ = "integration_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True)   # e.g. "email", "slack"
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # credentials (host, token, etc.)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_test_msg: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Project(Base):
    """Top-level organisational unit. A project owns plants and equipment."""
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True)          # e.g. PRJ-001
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String, default="Industrial")  # Industrial / Shutdown / Turnaround
    phase: Mapped[str] = mapped_column(String, default="Operations") # Planning / Execution / Operations / Closed
    status: Mapped[str] = mapped_column(String, default="Active")    # Active / On-Hold / Closed
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    plant_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)    # [plant_id, …]
    equipment_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    manager_id: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[str | None] = mapped_column(String, nullable=True)
    end_date: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Plant(Base):
    """A facility / process unit within a project (e.g. Crude Distillation Unit)."""
    __tablename__ = "plants"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String)                        # e.g. CDU-01
    name: Mapped[str] = mapped_column(String)
    project_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    type: Mapped[str] = mapped_column(String, default="Process Unit")
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    area: Mapped[str | None] = mapped_column(String, nullable=True)  # geographic or process area
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    equipment_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, default="Operational") # Operational / Shutdown / Mothballed
    responsible_person_id: Mapped[str | None] = mapped_column(String, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
#  USER PROFILES & ROLES
# ═══════════════════════════════════════════════════════════════════════════════

class UserProfile(Base):
    """User with role-based permissions for approval workflows."""
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_id: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    department: Mapped[str | None] = mapped_column(String, nullable=True)
    # Role drives what approvals they can give
    # technician | supervisor | safety_officer | area_authority | authorized_person | manager | quality_inspector
    role: Mapped[str] = mapped_column(String, default="technician")
    certifications: Mapped[list | None] = mapped_column(JSON, nullable=True)
    plant_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)  # plants they cover
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
#  PERMIT TO WORK (PTW)
# ═══════════════════════════════════════════════════════════════════════════════

class PermitToWork(Base):
    """
    Industry-standard Permit to Work.
    Workflow: draft → submitted → area_authority_review → safety_review
              → ap_approval → issued → active → suspended
              → completion_requested → closed | cancelled
    """
    __tablename__ = "permits_to_work"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    permit_number: Mapped[str] = mapped_column(String, unique=True)   # e.g. PTW-2026-001
    # Type: hot_work | cold_work | confined_space | electrical_isolation | height | radiography | excavation
    permit_type: Mapped[str] = mapped_column(String, default="cold_work")
    title: Mapped[str] = mapped_column(String)
    scope_of_work: Mapped[str] = mapped_column(Text, default="")
    project_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    equipment_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    location_description: Mapped[str | None] = mapped_column(String, nullable=True)
    area_classification: Mapped[str | None] = mapped_column(String, nullable=True)  # Zone 0/1/2, Non-hazardous

    # Schedule
    planned_start: Mapped[str | None] = mapped_column(String, nullable=True)
    planned_end: Mapped[str | None] = mapped_column(String, nullable=True)
    actual_start: Mapped[str | None] = mapped_column(String, nullable=True)
    actual_end: Mapped[str | None] = mapped_column(String, nullable=True)

    # Status workflow
    status: Mapped[str] = mapped_column(String, default="draft")

    # Hazard identification
    # [{hazard, likelihood, severity, mitigation}]
    hazards: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # PPE: [{item, specification}]
    ppe_requirements: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Isolation points: [{tag_number, description, isolation_type, verified_by, verified_at}]
    isolation_points: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Gas test certificates: [{tested_by, test_time, result, gas, ppm, lel_percent}]
    gas_tests: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Simultaneous operations that may conflict
    simops_conflicts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Emergency response plan ref
    emergency_response_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    # Associated work order id
    work_order_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Originator (person requesting the permit)
    originator_id: Mapped[str | None] = mapped_column(String, nullable=True)
    originator_name: Mapped[str | None] = mapped_column(String, nullable=True)
    originator_date: Mapped[str | None] = mapped_column(String, nullable=True)
    originator_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Area Authority (equipment owner — validates isolation + scope)
    area_authority_id: Mapped[str | None] = mapped_column(String, nullable=True)
    area_authority_name: Mapped[str | None] = mapped_column(String, nullable=True)
    area_authority_decision: Mapped[str | None] = mapped_column(String, nullable=True)  # approved | rejected
    area_authority_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    area_authority_date: Mapped[str | None] = mapped_column(String, nullable=True)

    # Safety Officer (validates safety measures, JSA)
    safety_officer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    safety_officer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    safety_officer_decision: Mapped[str | None] = mapped_column(String, nullable=True)
    safety_officer_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_officer_date: Mapped[str | None] = mapped_column(String, nullable=True)

    # Authorized Person (AP) — issues and closes the permit
    ap_id: Mapped[str | None] = mapped_column(String, nullable=True)
    ap_name: Mapped[str | None] = mapped_column(String, nullable=True)
    ap_decision: Mapped[str | None] = mapped_column(String, nullable=True)
    ap_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    ap_issue_date: Mapped[str | None] = mapped_column(String, nullable=True)
    ap_close_date: Mapped[str | None] = mapped_column(String, nullable=True)

    # Closure — completed by work team
    closure_requested_by: Mapped[str | None] = mapped_column(String, nullable=True)
    closure_requested_at: Mapped[str | None] = mapped_column(String, nullable=True)
    closure_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit trail [{timestamp, action, user, comments}]
    audit_trail: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
#  SAFETY PROCEDURES (SOP / JSA / MSDS)
# ═══════════════════════════════════════════════════════════════════════════════

class SafetyProcedure(Base):
    """
    Controlled safety document (SOP, JSA, SWMS, MSDS, ERP).
    Workflow: draft → peer_review → technical_review → final_approval → active → obsolete
    Each version is a new row; only one row per code has status='active'.
    """
    __tablename__ = "safety_procedures"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String)                  # e.g. SOP-PUMP-001
    title: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String, default="1.0")
    # Type: SOP | JSA | SWMS | MSDS | ERP | Checklist | Work_Instruction
    doc_type: Mapped[str] = mapped_column(String, default="SOP")
    category: Mapped[str | None] = mapped_column(String, nullable=True)  # Mechanical / Electrical / Process
    project_id: Mapped[str | None] = mapped_column(String, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(String, nullable=True)
    equipment_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Procedure steps [{step_number, title, description, hazards, controls, responsible_role}]
    steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Associated hazards [{hazard, risk_before, risk_after, control_measure}]
    hazard_register: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ppe_requirements: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tools_required: Mapped[list | None] = mapped_column(JSON, nullable=True)
    references: Mapped[list | None] = mapped_column(JSON, nullable=True)  # other docs / standards
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)  # Low | Medium | High | Critical
    status: Mapped[str] = mapped_column(String, default="draft")

    # Author
    author_id: Mapped[str | None] = mapped_column(String, nullable=True)
    author_name: Mapped[str | None] = mapped_column(String, nullable=True)
    authored_date: Mapped[str | None] = mapped_column(String, nullable=True)

    # Peer Reviewer
    peer_reviewer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    peer_reviewer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    peer_review_decision: Mapped[str | None] = mapped_column(String, nullable=True)
    peer_review_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    peer_review_date: Mapped[str | None] = mapped_column(String, nullable=True)

    # Technical Reviewer (e.g. engineer or SME)
    tech_reviewer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    tech_reviewer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    tech_review_decision: Mapped[str | None] = mapped_column(String, nullable=True)
    tech_review_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_review_date: Mapped[str | None] = mapped_column(String, nullable=True)

    # Final Approver (manager / safety officer)
    approver_id: Mapped[str | None] = mapped_column(String, nullable=True)
    approver_name: Mapped[str | None] = mapped_column(String, nullable=True)
    approver_decision: Mapped[str | None] = mapped_column(String, nullable=True)
    approver_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_date: Mapped[str | None] = mapped_column(String, nullable=True)

    effective_date: Mapped[str | None] = mapped_column(String, nullable=True)
    review_due_date: Mapped[str | None] = mapped_column(String, nullable=True)

    # Audit trail
    audit_trail: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
#  MANAGED WORK ORDERS (with full approval chain)
# ═══════════════════════════════════════════════════════════════════════════════

class ManagedWorkOrder(Base):
    """
    Production-grade work order with full approval workflow.
    draft → submitted → pending_approval → approved → scheduled
    → in_progress → pending_verification → verified → closed
    """
    __tablename__ = "managed_work_orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    wo_number: Mapped[str] = mapped_column(String, unique=True)         # e.g. WO-2026-001
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    # Category: preventive | corrective | predictive | emergency | shutdown | modification
    category: Mapped[str] = mapped_column(String, default="corrective")
    # Priority: low | medium | high | critical
    priority: Mapped[str] = mapped_column(String, default="medium")
    status: Mapped[str] = mapped_column(String, default="draft")
    project_id: Mapped[str | None] = mapped_column(String, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(String, nullable=True)
    equipment_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    permit_id: Mapped[str | None] = mapped_column(String, nullable=True)  # linked PTW

    scheduled_start: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_end: Mapped[str | None] = mapped_column(String, nullable=True)
    actual_start: Mapped[str | None] = mapped_column(String, nullable=True)
    actual_end: Mapped[str | None] = mapped_column(String, nullable=True)
    estimated_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_hours: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Tasks / steps [{seq, title, description, trade, estimated_hours, status, notes}]
    tasks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Materials [{part_number, description, qty_required, qty_issued, unit}]
    materials: Mapped[list | None] = mapped_column(JSON, nullable=True)
    safety_requirements: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Creator
    created_by_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Approval (supervisor / maintenance manager)
    approver_id: Mapped[str | None] = mapped_column(String, nullable=True)
    approver_name: Mapped[str | None] = mapped_column(String, nullable=True)
    approval_decision: Mapped[str | None] = mapped_column(String, nullable=True)  # approved | rejected
    approval_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_date: Mapped[str | None] = mapped_column(String, nullable=True)

    # Assigned technicians
    assigned_to: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{id, name, role}]

    # Execution — technician who starts / completes
    started_by_id: Mapped[str | None] = mapped_column(String, nullable=True)
    started_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[str | None] = mapped_column(String, nullable=True)

    completed_by_id: Mapped[str | None] = mapped_column(String, nullable=True)
    completed_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Verification (different person from completer — supervisor / quality inspector)
    verified_by_id: Mapped[str | None] = mapped_column(String, nullable=True)
    verified_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    verification_decision: Mapped[str | None] = mapped_column(String, nullable=True)  # passed | failed
    verification_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[str | None] = mapped_column(String, nullable=True)

    # Audit trail [{timestamp, action, user_id, user_name, field, old_value, new_value, comments}]
    audit_trail: Mapped[list | None] = mapped_column(JSON, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
#  INCIDENT REPORTS (full investigation workflow)
# ═══════════════════════════════════════════════════════════════════════════════

class IncidentReport(Base):
    """
    Formal incident / near-miss report with investigation workflow.
    Workflow: reported → investigation → root_cause_analysis → capa → closed
    """
    __tablename__ = "incident_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_number: Mapped[str] = mapped_column(String, unique=True)   # e.g. INC-2026-001
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    # Type: near_miss | first_aid | medical_treatment | lost_time | fatality | environmental | property_damage | fire | spill
    incident_type: Mapped[str] = mapped_column(String, default="near_miss")
    # Severity: P1 (Fatality) → P5 (Near Miss)
    severity: Mapped[str] = mapped_column(String, default="P5")
    status: Mapped[str] = mapped_column(String, default="reported")
    project_id: Mapped[str | None] = mapped_column(String, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(String, nullable=True)
    equipment_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    location_description: Mapped[str | None] = mapped_column(String, nullable=True)

    occurred_at: Mapped[str | None] = mapped_column(String, nullable=True)
    reported_at: Mapped[str | None] = mapped_column(String, nullable=True)

    # Reporter
    reported_by_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reported_by_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Persons involved [{name, role, injury_description, medical_treatment}]
    persons_involved: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Witnesses [{name, statement}]
    witnesses: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Immediate actions taken at the scene
    immediate_actions: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Investigation
    investigation_lead_id: Mapped[str | None] = mapped_column(String, nullable=True)
    investigation_lead_name: Mapped[str | None] = mapped_column(String, nullable=True)
    investigation_team: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Root causes (5-Why / Bow-Tie): [{level, cause, category}]
    root_causes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    contributing_factors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    timeline: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # CAPA — Corrective and Preventive Actions
    # [{id, type (corrective|preventive), description, assigned_to_id, due_date, status, completed_at}]
    capa_items: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Management sign-off
    reviewed_by_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    review_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(String, nullable=True)

    closed_by_id: Mapped[str | None] = mapped_column(String, nullable=True)
    closed_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    closed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    closure_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Operational impact — populated when the incident is reported or updated
    downtime_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    root_cause_category: Mapped[str | None] = mapped_column(String, nullable=True)
    audit_trail: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
#  QUALITY INSPECTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class QualityInspection(Base):
    """
    Scheduled or ad-hoc quality / HSE inspection.
    scheduled → in_progress → pending_review → closed_satisfactory | closed_with_findings | rejected
    """
    __tablename__ = "quality_inspections"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    inspection_number: Mapped[str] = mapped_column(String, unique=True)   # e.g. QI-2026-001
    title: Mapped[str] = mapped_column(String)
    # Type: equipment | process | safety_audit | environmental | contractor | pre_startup
    inspection_type: Mapped[str] = mapped_column(String, default="equipment")
    project_id: Mapped[str | None] = mapped_column(String, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(String, nullable=True)
    equipment_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, default="scheduled")
    priority: Mapped[str] = mapped_column(String, default="medium")

    scheduled_date: Mapped[str | None] = mapped_column(String, nullable=True)
    actual_date: Mapped[str | None] = mapped_column(String, nullable=True)

    # Inspector
    inspector_id: Mapped[str | None] = mapped_column(String, nullable=True)
    inspector_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Checklist items [{seq, category, check_item, criteria, result (pass|fail|na|obs), findings, evidence_ref}]
    checklist_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Non-conformances [{id, description, severity (critical|major|minor), action_required, due_date, status}]
    non_conformances: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Observations (good practices noted)
    observations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # % pass
    summary_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Reviewer (quality engineer / HSE officer)
    reviewer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_decision: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(String, nullable=True)

    audit_trail: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
#  ACTION ITEMS (CAPA, follow-ups, observations)
# ═══════════════════════════════════════════════════════════════════════════════

class ActionItem(Base):
    """
    Standalone action item arising from any source (incident, inspection, audit, observation).
    open → in_progress → pending_verification → verified | overdue
    """
    __tablename__ = "action_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    action_number: Mapped[str] = mapped_column(String, unique=True)   # e.g. ACT-2026-001
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    # Source
    source_type: Mapped[str | None] = mapped_column(String, nullable=True)  # incident | inspection | audit | observation
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)   # human-readable ref
    # action_type: corrective | preventive | improvement | observation
    action_type: Mapped[str] = mapped_column(String, default="corrective")
    priority: Mapped[str] = mapped_column(String, default="medium")  # low | medium | high | critical
    status: Mapped[str] = mapped_column(String, default="open")
    project_id: Mapped[str | None] = mapped_column(String, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(String, nullable=True)

    assigned_to_id: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_to_name: Mapped[str | None] = mapped_column(String, nullable=True)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)

    completed_by_id: Mapped[str | None] = mapped_column(String, nullable=True)
    completed_by_name: Mapped[str | None] = mapped_column(String, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    completion_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    verifier_id: Mapped[str | None] = mapped_column(String, nullable=True)
    verifier_name: Mapped[str | None] = mapped_column(String, nullable=True)
    verification_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[str | None] = mapped_column(String, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT LOG  (ISO 27001 / OSHA 1910 compliant immutable trail)
# ═══════════════════════════════════════════════════════════════════════════════

class AuditLog(Base):
    """
    Immutable audit trail entry.
    Every create / update / complete / delete on any operational object is recorded.
    Entries must never be deleted (use soft-archival instead).
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    # Object context
    object_type: Mapped[str] = mapped_column(String, index=True)   # work_order | checklist | incident | equipment | sensor | safety | defect | document
    object_id: Mapped[str] = mapped_column(String, index=True)
    equipment_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    # Action
    action: Mapped[str] = mapped_column(String, index=True)        # create | update | complete | delete | submit | check | approve | reject
    # Actor
    actor: Mapped[str] = mapped_column(String, default="system")   # user name, 'system', 'ai_agent', 'threshold_monitor'
    actor_type: Mapped[str] = mapped_column(String, default="system")  # user | system | ai
    # Payload
    changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {field: {old, new}} or summary dict
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Relations (for cross-object tracing)
    related_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{"type": "work_order", "id": "WO-xxx"}]


# ═══════════════════════════════════════════════════════════════════════════════
#  CUSTOM DASHBOARDS
# ═══════════════════════════════════════════════════════════════════════════════

class CustomDashboard(Base):
    """User-defined widget dashboard configuration."""
    __tablename__ = "custom_dashboards"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{id, type, title, equipment_id, sensor_key, config, col_span}]
    widgets: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Layout hint: 1, 2, or 3 columns
    columns: Mapped[int] = mapped_column(Integer, default=2)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
#  ENGINEERING DRAWINGS
# ═══════════════════════════════════════════════════════════════════════════════

class Drawing(Base):
    """
    Engineering drawing / CAD document linked to a project and plant/site.
    Supports: PNG, JPG, TIFF, BMP, WebP, PDF, SVG, DXF, DWG, STEP, IGES, IFC, DGN.
    Hierarchy: Project → Plant/Site → Drawing (one project → many plants → many drawings).
    On upload the server extracts P&ID structure via GPT-4V vision (images/PDF)
    or ezdxf (DXF/DWG) and renders a dark-theme SVG for the viewer.
    Analytics are computed live from IncidentReport, PermitToWork, and ManagedWorkOrder
    tables filtered by plant_id.
    """
    __tablename__ = "drawings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    drawing_number: Mapped[str] = mapped_column(String)            # e.g. DRW-CDU-001
    title: Mapped[str] = mapped_column(String)
    revision: Mapped[str] = mapped_column(String, default="A")     # Rev A, 1, 1.0 …

    # Drawing classification
    # pid | pfd | electrical | mechanical | civil | hvac | isometric | layout | general
    drawing_type: Mapped[str] = mapped_column(String, default="general")
    discipline: Mapped[str | None] = mapped_column(String, nullable=True)  # Mechanical | Electrical | Civil | Process
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Hierarchy — Project → Plant → Drawing
    project_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    plant_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)

    # File storage
    original_filename: Mapped[str] = mapped_column(String)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)      # path to stored original
    file_format: Mapped[str] = mapped_column(String, default="unknown")       # png|pdf|dwg|dxf|svg|tiff|jpg|step|iges
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)     # bytes

    # Processing status: uploaded | processing | ready | failed
    status: Mapped[str] = mapped_column(String, default="uploaded")

    # Extracted / rendered artefacts
    extracted_svg_path: Mapped[str | None] = mapped_column(String, nullable=True)
    # {title, drawing_type, equipment:[…], instruments:[…], connections:[…], key_annotations:[…]}
    extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # pending | processing | done | failed | unsupported
    extraction_status: Mapped[str] = mapped_column(String, default="pending")
    extraction_error: Mapped[str | None] = mapped_column(String, nullable=True)

    # Analytics cache (counts for the linked plant, refreshed on demand)
    # {incident_count, active_ptw_count, open_wo_count, open_inspection_count, last_incident_date, risk_score}
    analytics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analytics_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Metadata
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

