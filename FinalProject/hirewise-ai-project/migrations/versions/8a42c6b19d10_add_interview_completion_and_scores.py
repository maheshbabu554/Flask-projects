"""Add interview completion state and recruiter-entered scores.

Revision ID: 8a42c6b19d10
Revises: d3f89f9a5834
Create Date: 2026-11-11
"""
from alembic import op
import sqlalchemy as sa

revision = "8a42c6b19d10"
down_revision = "d3f89f9a5834"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("audit_logs", "user_id", existing_type=sa.Integer(), existing_nullable=False, nullable=True)
    op.add_column("interviews", sa.Column("status", sa.String(length=20), nullable=False, server_default="Scheduled"))
    op.add_column("interviews", sa.Column("performance_score", sa.Integer(), nullable=True))
    op.add_column("interviews", sa.Column("confidence_score", sa.Integer(), nullable=True))
    op.add_column("interviews", sa.Column("communication_score", sa.Integer(), nullable=True))
    op.add_column("interviews", sa.Column("overall_score", sa.Integer(), nullable=True))
    op.add_column("interviews", sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.alter_column("interviews", "status", server_default=None)


def downgrade():
    op.alter_column("audit_logs", "user_id", existing_type=sa.Integer(), existing_nullable=True, nullable=False)
    op.drop_column("interviews", "completed_at")
    op.drop_column("interviews", "overall_score")
    op.drop_column("interviews", "communication_score")
    op.drop_column("interviews", "confidence_score")
    op.drop_column("interviews", "performance_score")
    op.drop_column("interviews", "status")
