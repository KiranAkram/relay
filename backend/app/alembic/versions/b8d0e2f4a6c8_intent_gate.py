"""Intent gate: handover.intent_probability, handover.intent_model

Revision ID: b8d0e2f4a6c8
Revises: a7c9d1e3f5b7
Create Date: 2026-10-08 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'b8d0e2f4a6c8'
down_revision = 'a7c9d1e3f5b7'
branch_labels = None
depends_on = None


def upgrade():
    # Status "rejected" is a new value of the VARCHAR status column; no schema change.
    op.add_column('handover', sa.Column('intent_probability', sa.Float(), nullable=True))
    op.add_column(
        'handover',
        sa.Column('intent_model', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
    )


def downgrade():
    op.drop_column('handover', 'intent_model')
    op.drop_column('handover', 'intent_probability')
