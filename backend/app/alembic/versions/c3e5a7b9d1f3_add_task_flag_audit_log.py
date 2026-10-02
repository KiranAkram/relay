"""Add task, flag and audit_log tables; make audit_log append-only

Revision ID: c3e5a7b9d1f3
Revises: b2d4f6a8c0e1
Create Date: 2026-10-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c3e5a7b9d1f3'
down_revision = 'b2d4f6a8c0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'task',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('handover_patient_id', sa.Uuid(), nullable=False),
        sa.Column('handover_id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('due_kind', sa.String(length=16), nullable=False),
        sa.Column('due_phrase', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        sa.Column('priority', sa.String(length=16), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('verbatim', sa.Text(), nullable=True),
        sa.Column('acknowledged_by_id', sa.Uuid(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_by_id', sa.Uuid(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['acknowledged_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['completed_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['handover_id'], ['handover.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['handover_patient_id'], ['handover_patient.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_task_handover_patient_id'), 'task', ['handover_patient_id'], unique=False)
    op.create_index(op.f('ix_task_handover_id'), 'task', ['handover_id'], unique=False)
    op.create_index(op.f('ix_task_patient_id'), 'task', ['patient_id'], unique=False)
    op.create_index(op.f('ix_task_due_at'), 'task', ['due_at'], unique=False)
    op.create_index(op.f('ix_task_status'), 'task', ['status'], unique=False)

    op.create_table(
        'flag',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('handover_id', sa.Uuid(), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=True),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('fire_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fired_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by_id', sa.Uuid(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['acknowledged_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['handover_id'], ['handover.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['task_id'], ['task.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_flag_patient_id'), 'flag', ['patient_id'], unique=False)
    op.create_index(op.f('ix_flag_handover_id'), 'flag', ['handover_id'], unique=False)
    op.create_index(op.f('ix_flag_task_id'), 'flag', ['task_id'], unique=False)
    op.create_index(op.f('ix_flag_status'), 'flag', ['status'], unique=False)
    op.create_index(op.f('ix_flag_fire_at'), 'flag', ['fire_at'], unique=False)

    op.create_table(
        'audit_log',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('handover_id', sa.Uuid(), nullable=True),
        sa.Column('patient_id', sa.Uuid(), nullable=True),
        sa.Column('action', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('entity_type', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('entity_id', sa.Uuid(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('request_id', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_log_occurred_at'), 'audit_log', ['occurred_at'], unique=False)
    op.create_index(op.f('ix_audit_log_actor_id'), 'audit_log', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_log_handover_id'), 'audit_log', ['handover_id'], unique=False)
    op.create_index(op.f('ix_audit_log_patient_id'), 'audit_log', ['patient_id'], unique=False)
    op.create_index(op.f('ix_audit_log_action'), 'audit_log', ['action'], unique=False)

    # Append-only: reject row-level UPDATE and DELETE. (TRUNCATE is still
    # allowed so test teardown can reset the table.)
    op.execute(
        """
        CREATE FUNCTION audit_log_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only: % not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_append_only
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
        """
    )


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_append_only()")

    op.drop_index(op.f('ix_audit_log_action'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_patient_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_handover_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_actor_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_occurred_at'), table_name='audit_log')
    op.drop_table('audit_log')

    op.drop_index(op.f('ix_flag_fire_at'), table_name='flag')
    op.drop_index(op.f('ix_flag_status'), table_name='flag')
    op.drop_index(op.f('ix_flag_task_id'), table_name='flag')
    op.drop_index(op.f('ix_flag_handover_id'), table_name='flag')
    op.drop_index(op.f('ix_flag_patient_id'), table_name='flag')
    op.drop_table('flag')

    op.drop_index(op.f('ix_task_status'), table_name='task')
    op.drop_index(op.f('ix_task_due_at'), table_name='task')
    op.drop_index(op.f('ix_task_patient_id'), table_name='task')
    op.drop_index(op.f('ix_task_handover_id'), table_name='task')
    op.drop_index(op.f('ix_task_handover_patient_id'), table_name='task')
    op.drop_table('task')
