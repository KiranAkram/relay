"""Add task.cancel_reason (why a clinical task was dropped)

Revision ID: e5a7b9c1d3f5
Revises: d4f6a8b0c2e4
Create Date: 2026-10-05 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5a7b9c1d3f5'
down_revision = 'd4f6a8b0c2e4'
branch_labels = None
depends_on = None


def upgrade():
    # A cancelled task must say why; it stays visible on the patient record.
    op.add_column('task', sa.Column('cancel_reason', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('task', 'cancel_reason')
