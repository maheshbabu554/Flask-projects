
"""
Database models for HireWise AI.

This module defines all SQLAlchemy ORM models used by the
recruitment management application.
"""

from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

from extensions import db


# =========================================================
# 1. USER MODEL
# =========================================================

class User(UserMixin, db.Model):
    """Store administrator and recruiter accounts."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(100), nullable=False)

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(db.String(255), nullable=False)

    # Supports recruiter and placement_coordinator roles.
    role = db.Column(db.String(30), nullable=False)

    status = db.Column(
        db.String(20),
        default="active",
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    vacancies = db.relationship(
        "Vacancy",
        back_populates="creator"
    )

    interviews = db.relationship(
        "Interview",
        back_populates="interviewer"
    )

    reviewed_requests = db.relationship(
        "AccountRequest",
        back_populates="reviewer"
    )

    audit_logs = db.relationship(
        "AuditLog",
        back_populates="user"
    )
    login_otps = db.relationship(
        "LoginOTP",
        back_populates="user",
        cascade="all, delete-orphan"
    )


# =========================================================
# 2. VACANCY MODEL
# =========================================================

class Vacancy(db.Model):
    """Store job vacancies created by recruiters."""

    __tablename__ = "vacancies"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(150), nullable=False)

    description = db.Column(db.Text, nullable=False)

    required_skills_json = db.Column(db.JSON)

    optional_skills_json = db.Column(db.JSON)

    location = db.Column(db.String(150))

    openings = db.Column(
        db.Integer,
        default=1,
        nullable=False
    )

    status = db.Column(
        db.String(20),
        default="open",
        nullable=False
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    creator = db.relationship(
        "User",
        back_populates="vacancies"
    )

    candidates = db.relationship(
        "Candidate",
        back_populates="vacancy",
        cascade="all, delete-orphan"
    )


# =========================================================
# 3. CANDIDATE MODEL
# =========================================================

class Candidate(db.Model):
    """
    Store candidate information and recruitment data.

    AI-extracted and recruiter-confirmed profile information
    are stored separately.
    """

    __tablename__ = "candidates"

    __table_args__ = (
        UniqueConstraint(
            "vacancy_id",
            "email",
            name="uq_candidate_vacancy_email"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    vacancy_id = db.Column(
        db.Integer,
        db.ForeignKey("vacancies.id"),
        nullable=False
    )

    full_name = db.Column(db.String(120))

    email = db.Column(db.String(120))

    phone = db.Column(db.String(20))

    resume_path = db.Column(db.String(255))

    extracted_profile_json = db.Column(db.JSON)

    confirmed_profile_json = db.Column(db.JSON)

    status = db.Column(
        db.String(30),
        default="New",
        nullable=False
    )

    # Preserve the candidate's previous recruitment status.
    previous_status = db.Column(
        db.String(30),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Onboarding tracking
    onboarding_status = db.Column(
        db.String(30),
        default="Not Started",
        nullable=False
    )

    onboarding_started_at = db.Column(db.DateTime)

    onboarding_email_sent_at = db.Column(db.DateTime)

    # Relationships
    vacancy = db.relationship(
        "Vacancy",
        back_populates="candidates"
    )

    resume_evidence = db.relationship(
        "ResumeEvidence",
        back_populates="candidate",
        cascade="all, delete-orphan"
    )

    interviews = db.relationship(
        "Interview",
        back_populates="candidate",
        cascade="all, delete-orphan"
    )

    question_packs = db.relationship(
        "QuestionPack",
        back_populates="candidate",
        cascade="all, delete-orphan"
    )

    followups = db.relationship(
        "FollowUp",
        back_populates="candidate",
        cascade="all, delete-orphan"
    )

    ai_runs = db.relationship(
        "AuditAIRun",
        back_populates="candidate",
        cascade="all, delete-orphan"
    )

    documents = db.relationship(
        "CandidateDocument",
        back_populates="candidate",
        cascade="all, delete-orphan"
    )

    document_submission = db.relationship(
        "DocumentSubmission",
        back_populates="candidate",
        uselist=False,
        cascade="all, delete-orphan"
    )

    upload_links = db.relationship(
        "DocumentUploadLink",
        back_populates="candidate",
        cascade="all, delete-orphan"
    )

    email_logs = db.relationship(
        "EmailLog",
        back_populates="candidate"
    )


# =========================================================
# 4. RESUME EVIDENCE MODEL
# =========================================================

class ResumeEvidence(db.Model):
    """Store evidence supporting a candidate's claimed skills."""

    __tablename__ = "resume_evidence"

    id = db.Column(db.Integer, primary_key=True)

    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidates.id"),
        nullable=False
    )

    skill = db.Column(db.String(100), nullable=False)

    evidence_status = db.Column(
        db.String(30),
        nullable=False
    )

    excerpt = db.Column(db.Text)

    source_page = db.Column(db.Integer)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    candidate = db.relationship(
        "Candidate",
        back_populates="resume_evidence"
    )


# =========================================================
# 5. INTERVIEW MODEL
# =========================================================

class Interview(db.Model):
    """Store interview schedules, notes and evaluations."""

    __tablename__ = "interviews"

    id = db.Column(db.Integer, primary_key=True)

    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidates.id"),
        nullable=False
    )

    interviewer_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    scheduled_at = db.Column(
        db.DateTime,
        nullable=True
    )

    # Existing interview venue field.
    interview_location = db.Column(
        db.String(255),
        nullable=True
    )

    # Existing additional candidate instructions field.
    additional_instructions = db.Column(
        db.Text,
        nullable=True
    )

    status = db.Column(
        db.String(30),
        default="Scheduled",
        nullable=False
    )

    # Evaluation scores support decimal values.
    performance_score = db.Column(db.Float)

    confidence_score = db.Column(db.Float)

    communication_score = db.Column(db.Float)

    overall_score = db.Column(db.Float)

    completed_at = db.Column(db.DateTime)

    notes_raw = db.Column(db.Text)

    summary_edited = db.Column(db.JSON)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    candidate = db.relationship(
        "Candidate",
        back_populates="interviews"
    )

    interviewer = db.relationship(
        "User",
        back_populates="interviews"
    )

    email_logs = db.relationship(
        "EmailLog",
        back_populates="interview"
    )


# =========================================================
# 6. QUESTION PACK MODEL
# =========================================================

class QuestionPack(db.Model):
    """Store AI-generated interview question packs."""

    __tablename__ = "question_packs"

    id = db.Column(db.Integer, primary_key=True)

    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidates.id"),
        nullable=False
    )

    questions_json = db.Column(
        db.JSON,
        nullable=False
    )

    generated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    candidate = db.relationship(
        "Candidate",
        back_populates="question_packs"
    )


# =========================================================
# 7. FOLLOW-UP MODEL
# =========================================================

class FollowUp(db.Model):
    """Store recruiter follow-up actions and communication details."""

    __tablename__ = "followups"

    id = db.Column(db.Integer, primary_key=True)

    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidates.id"),
        nullable=False
    )

    due_date = db.Column(
        db.DateTime,
        nullable=False
    )

    action_text = db.Column(
        db.String(255),
        nullable=False
    )

    done = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Communication tracking
    contact_method = db.Column(
        db.String(30),
        nullable=True
    )

    outcome = db.Column(
        db.String(100),
        nullable=True
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    next_followup_date = db.Column(
        db.DateTime,
        nullable=True
    )

    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    candidate = db.relationship(
        "Candidate",
        back_populates="followups"
    )


# =========================================================
# 8. AI RUN MODEL
# =========================================================

class AuditAIRun(db.Model):
    """Track AI operations performed in HireWise AI."""

    __tablename__ = "audit_ai_runs"

    id = db.Column(db.Integer, primary_key=True)

    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidates.id"),
        nullable=False
    )

    operation = db.Column(
        db.String(100),
        nullable=False
    )

    model_name = db.Column(db.String(100))

    status = db.Column(
        db.String(30),
        nullable=False
    )

    latency_ms = db.Column(db.Integer)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    candidate = db.relationship(
        "Candidate",
        back_populates="ai_runs"
    )


# =========================================================
# 9. ACCOUNT REQUEST MODEL
# =========================================================

class AccountRequest(db.Model):
    """Store registration requests awaiting administrator approval."""

    __tablename__ = "account_requests"

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    # Supports placement_coordinator.
    requested_role = db.Column(
        db.String(30),
        default="recruiter",
        nullable=False
    )

    status = db.Column(
        db.String(20),
        default="pending",
        nullable=False
    )

    reviewed_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    reviewer = db.relationship(
        "User",
        back_populates="reviewed_requests"
    )


# =========================================================
# 10. AUDIT LOG MODEL
# =========================================================

class AuditLog(db.Model):
    """Track important user activities in the application."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    action = db.Column(
        db.String(100),
        nullable=False
    )

    entity_type = db.Column(db.String(100))

    entity_id = db.Column(db.Integer)

    details_json = db.Column(db.JSON)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = db.relationship(
        "User",
        back_populates="audit_logs"
    )


# =========================================================
# 11. DOCUMENT UPLOAD LINK MODEL
# =========================================================

class DocumentUploadLink(db.Model):
    """Manage secure candidate document upload links."""

    __tablename__ = "document_upload_links"

    id = db.Column(db.Integer, primary_key=True)

    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidates.id"),
        nullable=False,
        index=True
    )

    token_hash = db.Column(
        db.String(255),
        unique=True,
        nullable=False
    )

    expires_at = db.Column(
        db.DateTime,
        nullable=False
    )

    used_at = db.Column(db.DateTime)

    revoked_at = db.Column(db.DateTime)

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    candidate = db.relationship(
        "Candidate",
        back_populates="upload_links"
    )

    created_by = db.relationship(
        "User",
        foreign_keys=[created_by_id]
    )


# =========================================================
# 12. DOCUMENT SUBMISSION MODEL
# =========================================================

class DocumentSubmission(db.Model):
    """Record the candidate's one-time document submission."""

    __tablename__ = "document_submissions"

    id = db.Column(db.Integer, primary_key=True)

    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidates.id"),
        unique=True,
        nullable=False
    )

    status = db.Column(
        db.String(30),
        default="Submitted",
        nullable=False
    )

    submitted_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    candidate = db.relationship(
        "Candidate",
        back_populates="document_submission"
    )


# =========================================================
# 13. CANDIDATE DOCUMENT MODEL
# =========================================================

class CandidateDocument(db.Model):
    """Store uploaded documents and recruiter verification details."""

    __tablename__ = "candidate_documents"

    id = db.Column(db.Integer, primary_key=True)

    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidates.id"),
        nullable=False,
        index=True
    )

    category = db.Column(
        db.String(100),
        nullable=False
    )

    document_type = db.Column(
        db.String(150),
        nullable=False
    )

    original_filename = db.Column(
        db.String(255),
        nullable=False
    )

    file_path = db.Column(
        db.String(500),
        nullable=False
    )

    mime_type = db.Column(db.String(100))

    file_size = db.Column(db.Integer)

    verification_status = db.Column(
        db.String(30),
        default="Pending Verification",
        nullable=False
    )

    verification_notes = db.Column(db.Text)

    verified_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    verified_at = db.Column(db.DateTime)

    uploaded_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    candidate = db.relationship(
        "Candidate",
        back_populates="documents"
    )

    verified_by = db.relationship(
        "User",
        foreign_keys=[verified_by_id]
    )


# =========================================================
# 14. EMAIL LOG MODEL
# =========================================================

class EmailLog(db.Model):
    """Track candidate emails and their sending status."""

    __tablename__ = "email_logs"

    id = db.Column(db.Integer, primary_key=True)

    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("candidates.id"),
        nullable=False,
        index=True
    )

    interview_id = db.Column(
        db.Integer,
        db.ForeignKey("interviews.id"),
        nullable=True
    )

    email_type = db.Column(
        db.String(100),
        nullable=False
    )

    recipient_email = db.Column(
        db.String(120),
        nullable=False
    )

    subject = db.Column(
        db.String(255),
        nullable=False
    )

    status = db.Column(
        db.String(30),
        default="Pending",
        nullable=False
    )

    event_key = db.Column(
        db.String(255),
        unique=True,
        nullable=False
    )

    error_message = db.Column(db.Text)

    sent_at = db.Column(db.DateTime)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    candidate = db.relationship(
        "Candidate",
        back_populates="email_logs"
    )

    interview = db.relationship(
        "Interview",
        back_populates="email_logs"
    )
# =========================================================
# 15. LOGIN OTP MODEL
# =========================================================

class LoginOTP(db.Model):
    """Store hashed login OTPs for email verification."""

    __tablename__ = "login_otps"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Store only the hashed OTP, never the original OTP.
    otp_hash = db.Column(
        db.String(255),
        nullable=False
    )

    expires_at = db.Column(
        db.DateTime,
        nullable=False
    )

    attempts = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    is_used = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = db.relationship(
        "User",
        back_populates="login_otps"
    )
