"""Add handover, handover_patient and document_reference tables

Revision ID: b2d4f6a8c0e1
Revises: a1c3f5e7b9d2
Create Date: 2026-10-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'b2d4f6a8c0e1'
down_revision = 'a1c3f5e7b9d2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'handover',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('author_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('shift_label', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column('audio_key', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column('audio_content_type', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column('audio_duration_s', sa.Float(), nullable=True),
        sa.Column('transcript_text', sa.Text(), nullable=True),
        sa.Column('transcript_provider', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column('transcript_model', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column('extraction_raw', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('extraction_model', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column('extraction_prompt_version', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('confirmed_by_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['confirmed_by_id'], ['user.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_handover_author_id'), 'handover', ['author_id'], unique=False)
    op.create_index(op.f('ix_handover_status'), 'handover', ['status'], unique=False)

    op.create_table(
        'handover_patient',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('handover_id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('mention_verbatim', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('match_status', sa.String(length=32), nullable=False),
        sa.Column('match_candidates', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('illness_severity', sa.String(length=16), nullable=False),
        sa.Column('severity_evidence', sa.Text(), nullable=True),
        sa.Column('patient_summary', sa.Text(), nullable=True),
        sa.Column('situation_awareness', sa.Text(), nullable=True),
        sa.Column('contingencies', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('pending_results', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('transcript_excerpt', sa.Text(), nullable=True),
        sa.Column('edited_by_doctor', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['handover_id'], ['handover.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_handover_patient_handover_id'), 'handover_patient', ['handover_id'], unique=False)
    op.create_index(op.f('ix_handover_patient_patient_id'), 'handover_patient', ['patient_id'], unique=False)

    op.create_table(
        'document_reference',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('handover_id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=True),
        sa.Column('type', sa.String(length=32), nullable=False),
        sa.Column('storage_key', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column('content_type', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('sha256', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column('author_id', sa.Uuid(), nullable=False),
        sa.Column('authored_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['user.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['handover_id'], ['handover.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_document_reference_handover_id'), 'document_reference', ['handover_id'], unique=False)
    op.create_index(op.f('ix_document_reference_patient_id'), 'document_reference', ['patient_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_document_reference_patient_id'), table_name='document_reference')
    op.drop_index(op.f('ix_document_reference_handover_id'), table_name='document_reference')
    op.drop_table('document_reference')
    op.drop_index(op.f('ix_handover_patient_patient_id'), table_name='handover_patient')
    op.drop_index(op.f('ix_handover_patient_handover_id'), table_name='handover_patient')
    op.drop_table('handover_patient')
    op.drop_index(op.f('ix_handover_status'), table_name='handover')
    op.drop_index(op.f('ix_handover_author_id'), table_name='handover')
    op.drop_table('handover')
