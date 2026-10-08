"""Add usage_counter (per-day demo limits: visitor, ip, global)

Revision ID: a7c9d1e3f5b7
Revises: f6b8c0d2e4a6
Create Date: 2026-10-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a7c9d1e3f5b7'
down_revision = 'f6b8c0d2e4a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'usage_counter',
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('scope', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column('key', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('recordings', sa.Integer(), nullable=False),
        sa.Column('seconds', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('day', 'scope', 'key'),
    )


def downgrade():
    op.drop_table('usage_counter')
