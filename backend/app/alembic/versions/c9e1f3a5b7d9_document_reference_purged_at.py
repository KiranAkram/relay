"""Audio retention: document_reference.purged_at

Revision ID: c9e1f3a5b7d9
Revises: b8d0e2f4a6c8
Create Date: 2026-10-11 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9e1f3a5b7d9'
down_revision = 'b8d0e2f4a6c8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'document_reference',
        sa.Column('purged_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column('document_reference', 'purged_at')
