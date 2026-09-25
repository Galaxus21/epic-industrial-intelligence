"""initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-20 23:20:53.975090

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('object_type', sa.String(), nullable=False),
    sa.Column('object_id', sa.String(), nullable=False),
    sa.Column('equipment_id', sa.String(), nullable=True),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('actor', sa.String(), nullable=False),
    sa.Column('actor_type', sa.String(), nullable=False),
    sa.Column('changes', sa.JSON(), nullable=True),
    sa.Column('risk_level', sa.String(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('related_ids', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_logs_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_equipment_id'), ['equipment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_object_id'), ['object_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_object_type'), ['object_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_timestamp'), ['timestamp'], unique=False)

    op.create_table('compliance',
    sa.Column('equipment_id', sa.String(), nullable=False),
    sa.Column('overall_score', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('issues', sa.JSON(), nullable=True),
    sa.Column('passed', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('equipment_id')
    )
    op.create_table('documents',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('equipment_ids', sa.JSON(), nullable=True),
    sa.Column('date', sa.String(), nullable=True),
    sa.Column('sections', sa.JSON(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('pipeline_steps', sa.JSON(), nullable=True),
    sa.Column('entities', sa.JSON(), nullable=True),
    sa.Column('file_path', sa.String(), nullable=True),
    sa.Column('char_count', sa.Integer(), nullable=True),
    sa.Column('current_step', sa.String(), nullable=True),
    sa.Column('extra', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('equipment',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('location', sa.String(), nullable=False),
    sa.Column('health_score', sa.Float(), nullable=True),
    sa.Column('failure_probability', sa.Float(), nullable=True),
    sa.Column('compliance_score', sa.Float(), nullable=True),
    sa.Column('maintenance_due_days', sa.Integer(), nullable=True),
    sa.Column('criticality', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('manufacturer', sa.String(), nullable=True),
    sa.Column('model', sa.String(), nullable=True),
    sa.Column('installed_date', sa.String(), nullable=True),
    sa.Column('technicians', sa.JSON(), nullable=True),
    sa.Column('current_readings', sa.JSON(), nullable=True),
    sa.Column('downstream_equipment', sa.JSON(), nullable=True),
    sa.Column('specifications', sa.JSON(), nullable=True),
    sa.Column('extra', sa.JSON(), nullable=True),
    sa.Column('discovered', sa.Boolean(), nullable=False),
    sa.Column('manually_registered', sa.Boolean(), nullable=False),
    sa.Column('source_documents', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('equipment', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_equipment_status'), ['status'], unique=False)

    op.create_table('graph_links',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('target', sa.String(), nullable=False),
    sa.Column('label', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('graph_links', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_graph_links_source'), ['source'], unique=False)
        batch_op.create_index(batch_op.f('ix_graph_links_target'), ['target'], unique=False)

    op.create_table('graph_nodes',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('val', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('saved_work_orders',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('equipment_id', sa.String(), nullable=False),
    sa.Column('query_text', sa.Text(), nullable=False),
    sa.Column('risk_level', sa.String(), nullable=True),
    sa.Column('wo_type', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('estimated_duration_hours', sa.Float(), nullable=False),
    sa.Column('required_technicians', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('steps', sa.JSON(), nullable=True),
    sa.Column('spare_parts', sa.JSON(), nullable=True),
    sa.Column('safety_precautions', sa.JSON(), nullable=True),
    sa.Column('required_permits', sa.JSON(), nullable=True),
    sa.Column('solution_worked', sa.Boolean(), nullable=True),
    sa.Column('is_partial', sa.Boolean(), nullable=True),
    sa.Column('extra_steps_taken', sa.Text(), nullable=True),
    sa.Column('outcome_notes', sa.Text(), nullable=True),
    sa.Column('completed_by', sa.String(), nullable=True),
    sa.Column('actual_duration_hours', sa.Float(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('saved_work_orders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_saved_work_orders_equipment_id'), ['equipment_id'], unique=False)

    op.create_table('sensor_history',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('equipment_id', sa.String(), nullable=False),
    sa.Column('sensor_key', sa.String(), nullable=False),
    sa.Column('readings', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('sensor_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sensor_history_equipment_id'), ['equipment_id'], unique=False)

    op.create_table('spare_parts',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('equipment_ids', sa.JSON(), nullable=True),
    sa.Column('part_number', sa.String(), nullable=True),
    sa.Column('quantity_on_hand', sa.Integer(), nullable=False),
    sa.Column('reorder_point', sa.Integer(), nullable=False),
    sa.Column('lead_time_days', sa.Integer(), nullable=True),
    sa.Column('location', sa.String(), nullable=True),
    sa.Column('unit_cost_usd', sa.Float(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('technicians',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('expertise', sa.JSON(), nullable=True),
    sa.Column('certifications', sa.JSON(), nullable=True),
    sa.Column('years_experience', sa.Integer(), nullable=False),
    sa.Column('equipment_ids', sa.JSON(), nullable=True),
    sa.Column('available', sa.Boolean(), nullable=False),
    sa.Column('contact', sa.String(), nullable=True),
    sa.Column('extra', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_profiles',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('employee_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('department', sa.String(), nullable=True),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('certifications', sa.JSON(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('password_hash', sa.String(), nullable=True),
    sa.Column('extra', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('employee_id')
    )
    op.create_table('incidents',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('equipment_id', sa.String(), nullable=False),
    sa.Column('date', sa.String(), nullable=True),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('severity', sa.String(), nullable=False),
    sa.Column('symptom', sa.Text(), nullable=True),
    sa.Column('root_cause', sa.Text(), nullable=True),
    sa.Column('root_cause_category', sa.String(), nullable=True),
    sa.Column('action_taken', sa.Text(), nullable=True),
    sa.Column('lessons_learned', sa.Text(), nullable=True),
    sa.Column('downtime_hours', sa.Integer(), nullable=True),
    sa.Column('cost_usd', sa.Float(), nullable=True),
    sa.Column('technician', sa.String(), nullable=True),
    sa.Column('keywords', sa.JSON(), nullable=True),
    sa.Column('extra', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['equipment_id'], ['equipment.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_incidents_equipment_id'), ['equipment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_incidents_root_cause_category'), ['root_cause_category'], unique=False)
        batch_op.create_index(batch_op.f('ix_incidents_severity'), ['severity'], unique=False)

    op.create_table('maintenance_records',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('equipment_id', sa.String(), nullable=False),
    sa.Column('date', sa.String(), nullable=True),
    sa.Column('scheduled_date', sa.String(), nullable=True),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('findings', sa.Text(), nullable=True),
    sa.Column('technician', sa.String(), nullable=True),
    sa.Column('overdue_days', sa.Integer(), nullable=True),
    sa.Column('extra', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['equipment_id'], ['equipment.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('maintenance_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maintenance_records_equipment_id'), ['equipment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_maintenance_records_status'), ['status'], unique=False)



def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('maintenance_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maintenance_records_status'))
        batch_op.drop_index(batch_op.f('ix_maintenance_records_equipment_id'))

    op.drop_table('maintenance_records')
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_incidents_severity'))
        batch_op.drop_index(batch_op.f('ix_incidents_root_cause_category'))
        batch_op.drop_index(batch_op.f('ix_incidents_equipment_id'))

    op.drop_table('incidents')
    op.drop_table('user_profiles')
    op.drop_table('technicians')
    op.drop_table('spare_parts')
    with op.batch_alter_table('sensor_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sensor_history_equipment_id'))

    op.drop_table('sensor_history')
    with op.batch_alter_table('saved_work_orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_saved_work_orders_equipment_id'))

    op.drop_table('saved_work_orders')
    op.drop_table('graph_nodes')
    with op.batch_alter_table('graph_links', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_graph_links_target'))
        batch_op.drop_index(batch_op.f('ix_graph_links_source'))

    op.drop_table('graph_links')
    with op.batch_alter_table('equipment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_equipment_status'))

    op.drop_table('equipment')
    op.drop_table('documents')
    op.drop_table('compliance')
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_logs_timestamp'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_object_type'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_object_id'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_equipment_id'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_action'))

    op.drop_table('audit_logs')
