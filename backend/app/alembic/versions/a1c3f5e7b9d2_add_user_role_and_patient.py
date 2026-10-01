"""Add user.role and patient table

Revision ID: a1c3f5e7b9d2
Revises: fe56fa70289e
Create Date: 2026-10-01 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a1c3f5e7b9d2'
down_revision = 'fe56fa70289e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'user',
        sa.Column('role', sa.String(length=16), nullable=False, server_default='doctor'),
    )

    op.create_table(
        'patient',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('mrn', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column('family_name', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column('given_name', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('sex', sa.String(length=16), nullable=False),
        sa.Column('bed', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column('admitting_diagnosis', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column('attending_name', sqlmodel.sql.sqltypes.AutoString(length=128), nullable=True),
        sa.Column('admitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_patient_mrn'), 'patient', ['mrn'], unique=True)
    op.create_index(op.f('ix_patient_bed'), 'patient', ['bed'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_patient_bed'), table_name='patient')
    op.drop_index(op.f('ix_patient_mrn'), table_name='patient')
    op.drop_table('patient')
    op.drop_column('user', 'role')
