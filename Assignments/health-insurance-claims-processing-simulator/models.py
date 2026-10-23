
"""
Database models for the Health Insurance Claims Processing Simulator.

The application is an educational simulation. It does not make real
insurance decisions or transfer real money.
"""

import os
import csv
from datetime import date, datetime
from decimal import Decimal

from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

load_dotenv()

db = SQLAlchemy()


class Hospital(db.Model):
    __tablename__ = "hospitals"

    hospital_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    network_status = db.Column(db.Boolean, nullable=False, default=False)

    users = db.relationship("User", back_populates="hospital")
    claims = db.relationship("Claim", back_populates="hospital")

    def is_network(self):
        """Return whether this hospital is a network hospital."""
        value = self.network_status
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "network")
        return bool(value)


class Plan(db.Model):
    __tablename__ = "plans"

    plan_id = db.Column(db.Integer, primary_key=True)
    plan_name = db.Column(db.String(120), nullable=False)
    covered_treatment_types = db.Column(
        db.String(255), nullable=False, default="inpatient"
    )
    annual_limit_inr = db.Column(
        db.Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    deductible_inr = db.Column(
        db.Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    copay_percent = db.Column(
        db.Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )

    policies = db.relationship("Policy", back_populates="plan")

    def covers_treatment(self, treatment_type):
        """Check treatment coverage using the dataset's pipe-separated values."""
        allowed = {
            item.strip().lower()
            for item in (self.covered_treatment_types or "").replace(",", "|").split("|")
            if item.strip()
        }
        return (treatment_type or "").strip().lower() in allowed


class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(40), nullable=False, index=True)
    hospital_id = db.Column(
        db.Integer, db.ForeignKey("hospitals.hospital_id"), nullable=True
    )
    password_hash = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    hospital = db.relationship("Hospital", back_populates="users")
    policies = db.relationship(
        "Policy", back_populates="holder", foreign_keys="Policy.holder_user_id"
    )
    assigned_claims = db.relationship(
        "Claim", back_populates="officer", foreign_keys="Claim.officer_user_id"
    )
    claim_history_entries = db.relationship(
        "ClaimHistory", back_populates="actor", foreign_keys="ClaimHistory.actor_user_id"
    )
    recorded_settlements = db.relationship(
        "Settlement",
        back_populates="recorder",
        foreign_keys="Settlement.recorded_by_user_id",
    )

    @property
    def id(self):
        """Compatibility alias for code that refers to user.id."""
        return self.user_id


class Policy(db.Model):
    __tablename__ = "policies"

    policy_id = db.Column(db.Integer, primary_key=True)
    holder_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True
    )
    plan_id = db.Column(
        db.Integer, db.ForeignKey("plans.plan_id"), nullable=False
    )
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="active")

    holder = db.relationship(
        "User", back_populates="policies", foreign_keys=[holder_user_id]
    )
    plan = db.relationship("Plan", back_populates="policies")
    members = db.relationship("Member", back_populates="policy")
    claims = db.relationship("Claim", back_populates="policy")

    @property
    def holder_user(self):
        """Compatibility alias used by existing templates."""
        return self.holder

    @property
    def id(self):
        return self.policy_id


class Member(db.Model):
    __tablename__ = "members"

    member_id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(
        db.Integer, db.ForeignKey("policies.policy_id"), nullable=False, index=True
    )
    display_name = db.Column(db.String(120), nullable=False)
    relationship = db.Column(db.String(40), nullable=False)

    policy = db.relationship("Policy", back_populates="members")
    claims = db.relationship("Claim", back_populates="member")

    @property
    def id(self):
        return self.member_id


class Claim(db.Model):
    __tablename__ = "claims"

    claim_id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(
        db.Integer, db.ForeignKey("policies.policy_id"), nullable=False, index=True
    )
    member_id = db.Column(
        db.Integer, db.ForeignKey("members.member_id"), nullable=False
    )
    hospital_id = db.Column(
        db.Integer, db.ForeignKey("hospitals.hospital_id"), nullable=False
    )
    claim_type = db.Column(db.String(30), nullable=False)
    treatment_type = db.Column(db.String(40), nullable=False)
    admission_date = db.Column(db.Date, nullable=False)
    discharge_date = db.Column(db.Date, nullable=False)
    requested_amount_inr = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="draft", index=True)
    eligible_amount_inr = db.Column(db.Numeric(12, 2), nullable=True)
    officer_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=True
    )
    payment_recorded_date = db.Column(db.Date, nullable=True)

    policy = db.relationship("Policy", back_populates="claims")
    member = db.relationship("Member", back_populates="claims")
    hospital = db.relationship("Hospital", back_populates="claims")
    officer = db.relationship(
        "User", back_populates="assigned_claims", foreign_keys=[officer_user_id]
    )
    documents = db.relationship(
        "ClaimDocument", back_populates="claim", cascade="all, delete-orphan"
    )
    history = db.relationship(
        "ClaimHistory",
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by="ClaimHistory.event_date",
    )
    settlement = db.relationship(
        "Settlement", back_populates="claim", uselist=False
    )

    @property
    def id(self):
        return self.claim_id

    @property
    def requested_amount(self):
        return self.requested_amount_inr

    @requested_amount.setter
    def requested_amount(self, value):
        self.requested_amount_inr = value

    @property
    def eligible_amount(self):
        return self.eligible_amount_inr

    @eligible_amount.setter
    def eligible_amount(self, value):
        self.eligible_amount_inr = value


class ClaimDocument(db.Model):
    __tablename__ = "claim_documents"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    claim_id = db.Column(
        db.Integer, db.ForeignKey("claims.claim_id"), nullable=False, index=True
    )
    document_type = db.Column(db.String(100), nullable=False)
    checklist_status = db.Column(
        db.String(30), nullable=False, default="pending"
    )

    claim = db.relationship("Claim", back_populates="documents")


class ClaimHistory(db.Model):
    __tablename__ = "claim_history"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    claim_id = db.Column(
        db.Integer, db.ForeignKey("claims.claim_id"), nullable=False, index=True
    )
    sequence_no = db.Column(db.Integer, nullable=False, default=1)
    from_status = db.Column(db.String(30), nullable=True)
    to_status = db.Column(db.String(30), nullable=False)
    actor_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False
    )
    note = db.Column(db.Text, nullable=True, default="")
    event_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    claim = db.relationship("Claim", back_populates="history")
    actor = db.relationship(
        "User", back_populates="claim_history_entries",
        foreign_keys=[actor_user_id]
    )


class Settlement(db.Model):
    __tablename__ = "settlements"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    claim_id = db.Column(
        db.Integer, db.ForeignKey("claims.claim_id"), nullable=False, unique=True
    )
    payee_type = db.Column(db.String(30), nullable=False)
    amount_inr = db.Column(db.Numeric(12, 2), nullable=False)
    recorded_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False
    )
    recorded_date = db.Column(db.Date, nullable=False, default=date.today)

    claim = db.relationship("Claim", back_populates="settlement")
    recorder = db.relationship(
        "User", back_populates="recorded_settlements",
        foreign_keys=[recorded_by_user_id]
    )

    @property
    def amount(self):
        return self.amount_inr

    @property
    def recorded_at(self):
        return self.recorded_date


def init_db(app):
    """
    Configure SQLAlchemy and create missing tables.

    Important: create_all() creates missing tables; it does not alter existing
    tables. This function deliberately does not silently switch to SQLite.
    """
    database_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL")

    if not database_url:
        raise RuntimeError(
            "Database URL is missing. Set DATABASE_URL in your .env file."
        )

    # Validate that the configured URL is readable before initializing SQLAlchemy.
    try:
        make_url(database_url)
    except Exception as exc:
        raise RuntimeError("The database URL in .env is invalid.") from exc

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        # Creates only tables that do not already exist.
        db.create_all()

        # Confirm that the connection points to the expected database.
        inspector = inspect(db.engine)
        app.logger.info(
            "Database initialized. Existing tables: %s",
            ", ".join(inspector.get_table_names()) or "(none)",
        )
