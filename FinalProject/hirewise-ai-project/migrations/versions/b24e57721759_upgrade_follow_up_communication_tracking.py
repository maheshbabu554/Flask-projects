
"""Upgrade follow-up communication tracking

Revision ID: b24e57721759
Revises: 040ccfe99a1e
Create Date: 2026-11-16 17:30:42.018409
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b24e57721759'
down_revision = '040ccfe99a1e'
branch_labels = None
depends_on = None


def upgrade():
    """Add communication tracking fields to followups."""

    with op.batch_alter_table('followups', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('contact_method', sa.String(length=30), nullable=True)
        )
        batch_op.add_column(
            sa.Column('outcome', sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column('notes', sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column('next_followup_date', sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column('completed_at', sa.DateTime(), nullable=True)
        )


def downgrade():
    """Remove the follow-up communication tracking fields."""

    with op.batch_alter_table('followups', schema=None) as batch_op:
        batch_op.drop_column('completed_at')
        batch_op.drop_column('next_followup_date')
        batch_op.drop_column('notes')
        batch_op.drop_column('outcome')
        batch_op.drop_column('contact_method')
