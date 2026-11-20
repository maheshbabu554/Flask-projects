
"""Restore interview column types

Revision ID: 9a214bda477b
Revises: 60b9faabf816
Create Date: 2026-11-16 18:35:52.411163
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '9a214bda477b'
down_revision = '60b9faabf816'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('interviews', schema=None) as batch_op:

        batch_op.alter_column(
            'status',
            existing_type=mysql.VARCHAR(
                collation='utf8mb4_unicode_ci',
                length=20
            ),
            type_=sa.String(length=30),
            existing_nullable=False,
            existing_server_default=sa.text("'Scheduled'")
        )

        batch_op.alter_column(
            'performance_score',
            existing_type=mysql.INTEGER(),
            type_=sa.Float(),
            existing_nullable=True
        )

        batch_op.alter_column(
            'confidence_score',
            existing_type=mysql.INTEGER(),
            type_=sa.Float(),
            existing_nullable=True
        )

        batch_op.alter_column(
            'communication_score',
            existing_type=mysql.INTEGER(),
            type_=sa.Float(),
            existing_nullable=True
        )

        batch_op.alter_column(
            'overall_score',
            existing_type=mysql.INTEGER(),
            type_=sa.Float(),
            existing_nullable=True
        )


def downgrade():
    with op.batch_alter_table('interviews', schema=None) as batch_op:

        batch_op.alter_column(
            'overall_score',
            existing_type=sa.Float(),
            type_=mysql.INTEGER(),
            existing_nullable=True
        )

        batch_op.alter_column(
            'communication_score',
            existing_type=sa.Float(),
            type_=mysql.INTEGER(),
            existing_nullable=True
        )

        batch_op.alter_column(
            'confidence_score',
            existing_type=sa.Float(),
            type_=mysql.INTEGER(),
            existing_nullable=True
        )

        batch_op.alter_column(
            'performance_score',
            existing_type=sa.Float(),
            type_=mysql.INTEGER(),
            existing_nullable=True
        )

        batch_op.alter_column(
            'status',
            existing_type=sa.String(length=30),
            type_=mysql.VARCHAR(
                collation='utf8mb4_unicode_ci',
                length=20
            ),
            existing_nullable=False,
            existing_server_default=sa.text("'Scheduled'")
        )
