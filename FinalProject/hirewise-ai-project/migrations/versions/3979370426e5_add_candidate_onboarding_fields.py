
"""Add candidate onboarding fields

Revision ID: 3979370426e5
Revises: 8a42c6b19d10
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = "3979370426e5"
down_revision = "8a42c6b19d10"
branch_labels = None
depends_on = None


def upgrade():

    # Candidate documents table
    op.create_table(
        "candidate_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("document_type", sa.String(length=150), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column(
            "verification_status",
            sa.String(length=30),
            nullable=False
        ),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.Column("verified_by_id", sa.Integer(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"]
        ),
        sa.ForeignKeyConstraint(
            ["verified_by_id"], ["users.id"]
        ),
        sa.PrimaryKeyConstraint("id")
    )

    with op.batch_alter_table("candidate_documents") as batch_op:
        batch_op.create_index(
            "ix_candidate_documents_candidate_id",
            ["candidate_id"],
            unique=False
        )

    # Document submissions table
    op.create_table(
        "document_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id")
    )

    # Document upload links table
    op.create_table(
        "document_upload_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"]
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash")
    )

    with op.batch_alter_table("document_upload_links") as batch_op:
        batch_op.create_index(
            "ix_document_upload_links_candidate_id",
            ["candidate_id"],
            unique=False
        )

    # Email logs table
    op.create_table(
        "email_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=True),
        sa.Column("email_type", sa.String(length=100), nullable=False),
        sa.Column("recipient_email", sa.String(length=120), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["candidates.id"]
        ),
        sa.ForeignKeyConstraint(
            ["interview_id"], ["interviews.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key")
    )

    with op.batch_alter_table("email_logs") as batch_op:
        batch_op.create_index(
            "ix_email_logs_candidate_id",
            ["candidate_id"],
            unique=False
        )

    # Add onboarding fields to existing candidates
    with op.batch_alter_table("candidates") as batch_op:

        batch_op.add_column(
            sa.Column(
                "onboarding_status",
                sa.String(length=30),
                nullable=False,
                server_default="Not Started"
            )
        )

        batch_op.add_column(
            sa.Column(
                "onboarding_started_at",
                sa.DateTime(),
                nullable=True
            )
        )

        batch_op.add_column(
            sa.Column(
                "onboarding_email_sent_at",
                sa.DateTime(),
                nullable=True
            )
        )

        # Remove the database-level default after existing rows
        # have received their initial value.
        batch_op.alter_column(
            "onboarding_status",
            existing_type=sa.String(length=30),
            server_default=None,
            existing_nullable=False
        )


def downgrade():

    # Remove onboarding fields
    with op.batch_alter_table("candidates") as batch_op:
        batch_op.drop_column("onboarding_email_sent_at")
        batch_op.drop_column("onboarding_started_at")
        batch_op.drop_column("onboarding_status")

    # Remove email logs
    with op.batch_alter_table("email_logs") as batch_op:
        batch_op.drop_index("ix_email_logs_candidate_id")

    op.drop_table("email_logs")

    # Remove document upload links
    with op.batch_alter_table("document_upload_links") as batch_op:
        batch_op.drop_index("ix_document_upload_links_candidate_id")

    op.drop_table("document_upload_links")

    # Remove document submissions
    op.drop_table("document_submissions")

    # Remove candidate documents
    with op.batch_alter_table("candidate_documents") as batch_op:
        batch_op.drop_index("ix_candidate_documents_candidate_id")

    op.drop_table("candidate_documents")
