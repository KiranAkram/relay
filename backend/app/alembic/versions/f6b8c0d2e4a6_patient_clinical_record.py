"""Patient clinical record: conditions, medications, allergies, observations,
bed history; patient.code_status, patient.synthetic; one active patient per bed

Revision ID: f6b8c0d2e4a6
Revises: e5a7b9c1d3f5
Create Date: 2026-10-07 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'f6b8c0d2e4a6'
down_revision = 'e5a7b9c1d3f5'
branch_labels = None
depends_on = None


def _common_columns():
    return [
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('patient_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade():
    # Patient: resuscitation status and the synthetic marker. Existing rows
    # are the seed census, so they are marked synthetic in the same migration.
    op.add_column(
        'patient',
        sa.Column('code_status', sa.String(length=16), nullable=False, server_default='full_code'),
    )
    op.add_column(
        'patient',
        sa.Column('synthetic', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE patient SET synthetic = true WHERE mrn LIKE 'MRN-1000%'")
    # One active patient per bed. Partial: discharged and deleted rows free the bed.
    op.create_index(
        'ux_patient_bed_active',
        'patient',
        ['bed'],
        unique=True,
        postgresql_where=sa.text('active AND deleted_at IS NULL'),
    )

    op.create_table(
        'condition',
        *_common_columns(),
        sa.Column('text', sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_condition_patient_id'), 'condition', ['patient_id'], unique=False)

    op.create_table(
        'medication_statement',
        *_common_columns(),
        sa.Column('medication', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column('dose', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('route', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column('frequency', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('note', sqlmodel.sql.sqltypes.AutoString(length=256), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_medication_statement_patient_id'), 'medication_statement', ['patient_id'], unique=False)

    op.create_table(
        'allergy_intolerance',
        *_common_columns(),
        sa.Column('substance', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column('reaction', sqlmodel.sql.sqltypes.AutoString(length=256), nullable=True),
        sa.Column('severity', sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_allergy_intolerance_patient_id'), 'allergy_intolerance', ['patient_id'], unique=False)

    op.create_table(
        'observation',
        *_common_columns(),
        sa.Column('category', sa.String(length=16), nullable=False),
        sa.Column('code', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('display', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.Column('value_text', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column('interpretation', sa.String(length=16), nullable=False),
        sa.Column('effective_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_observation_patient_id'), 'observation', ['patient_id'], unique=False)
    op.create_index(op.f('ix_observation_code'), 'observation', ['code'], unique=False)
    op.create_index(op.f('ix_observation_effective_at'), 'observation', ['effective_at'], unique=False)

    op.create_table(
        'patient_location',
        *_common_columns(),
        sa.Column('bed', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_patient_location_patient_id'), 'patient_location', ['patient_id'], unique=False)
    op.create_index(op.f('ix_patient_location_bed'), 'patient_location', ['bed'], unique=False)


def downgrade():
    for table in ('patient_location', 'observation', 'allergy_intolerance', 'medication_statement', 'condition'):
        op.drop_table(table)
    op.drop_index('ux_patient_bed_active', table_name='patient')
    op.drop_column('patient', 'synthetic')
    op.drop_column('patient', 'code_status')
