
"""Add previous status to candidates.

Revision ID: 040ccfe99a1e
Revises: 1fe4ea79d8d0
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision = "040ccfe99a1e"
down_revision = "1fe4ea79d8d0"
branch_labels = None
depends_on = None


def upgrade():
    """Add previous_status to the candidates table."""

    op.add_column(
        "candidates",
        sa.Column(
            "previous_status",
            sa.String(length=30),
            nullable=True
        )
    )


def downgrade():
    """Remove previous_status from the candidates table."""

    op.drop_column(
        "candidates",
        "previous_status"
    )
