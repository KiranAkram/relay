"""Add handover_patient.action_items (draft action items before confirm)

Revision ID: d4f6a8b0c2e4
Revises: c3e5a7b9d1f3
Create Date: 2026-10-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'd4f6a8b0c2e4'
down_revision = 'c3e5a7b9d1f3'
branch_labels = None
depends_on = None


def upgrade():
    # Drafts live here until confirm materialises them as `task` rows.
    op.add_column(
        'handover_patient',
        sa.Column(
            'action_items',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade():
    op.drop_column('handover_patient', 'action_items')
