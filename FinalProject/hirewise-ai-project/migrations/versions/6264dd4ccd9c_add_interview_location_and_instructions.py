
"""Add interview location and instructions

Revision ID: 6264dd4ccd9c
Revises: 3979370426e5
Create Date: 2026-11-14 17:31:30.465762

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6264dd4ccd9c'
down_revision = '3979370426e5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('interviews', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('interview_location', sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column('additional_instructions', sa.Text(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('interviews', schema=None) as batch_op:
        batch_op.drop_column('additional_instructions')
        batch_op.drop_column('interview_location')
