"""
AI Operations Brain — SQLAlchemy ORM Models
Every entity lives in PostgreSQL. The DB starts empty and is populated
through the API and document ingestion.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
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
    status: Mapped[str] = mapped_column(String, default="Unknown", index=True)
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
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), index=True)
    date: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, default="")
    severity: Mapped[str] = mapped_column(String, default="Medium", index=True)
    symptom: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause_category: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
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
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), index=True)
    date: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_date: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String, default="Preventive")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="Completed", index=True)
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
    is_partial: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    extra_steps_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    actual_duration_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
    # Rights come from the route guards in core/roles.py: technician and supervisor act in the field, supervisor and
    # manager approve, manager alone administers. The other accepted role names authenticate and carry no extra rights.
    role: Mapped[str] = mapped_column(String, default="technician")
    certifications: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # PBKDF2 password hash; None means the account has no credential yet, and login
    # refuses it when ENVIRONMENT=production.
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT LOG  (append-only through the application)
# ═══════════════════════════════════════════════════════════════════════════════

class AuditLog(Base):
    """
    Append-only audit trail entry.
    Written when a work order is created or completed, when live telemetry is ingested and
    when an admin purge is requested; README.md section 8 lists the exact call sites.
    No code path updates or deletes these rows and the admin purge refuses them;
    the database itself does not enforce that, so a direct SQL DELETE would succeed.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    # Object context
    object_type: Mapped[str] = mapped_column(String, index=True)   # work_order | sensor | system
    object_id: Mapped[str] = mapped_column(String, index=True)
    equipment_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    # Action
    action: Mapped[str] = mapped_column(String, index=True)        # create | update | complete | purge
    # Actor
    actor: Mapped[str] = mapped_column(String, default="system")   # user name, 'system' or 'threshold_monitor'
    actor_type: Mapped[str] = mapped_column(String, default="system")  # user | system
    # Payload
    changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # summary of the event, e.g. {"readings": {...}}
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Relations (for cross-object tracing)
    related_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)  # reserved: [{"type": "work_order", "id": "WO-xxx"}]
