
"""
Recruiter routes for HireWise AI.

Handles recruiter dashboard and recruiter access control.
"""

from functools import wraps
from datetime import datetime

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required
from sqlalchemy import func, select

from extensions import db

from models import (
    AuditLog,
    Candidate,
    FollowUp,
    Interview,
    Vacancy,
)


recruiter_bp = Blueprint("recruiter", __name__)


# =========================================================
# RECRUITER ACCESS CONTROL
# =========================================================

def recruiter_required(view_function):
    """Allow access only to active recruiter accounts."""

    @wraps(view_function)
    @login_required
    def decorated_view(*args, **kwargs):

        if current_user.status != "active":
            abort(403)

        if current_user.role not in (
            "recruiter",
            "placement_coordinator"
        ):
            abort(403)

        return view_function(*args, **kwargs)

    return decorated_view


# =========================================================
# RECRUITER DASHBOARD
# =========================================================

@recruiter_bp.route("/")
@recruiter_required
def dashboard():
    """Display dashboard statistics for the logged-in recruiter."""

    recruiter_id = current_user.id

    # -----------------------------------------------------
    # TOTAL VACANCIES
    # -----------------------------------------------------

    total_vacancies = db.session.scalar(
        select(func.count(Vacancy.id)).where(
            Vacancy.created_by == recruiter_id
        )
    ) or 0

    # -----------------------------------------------------
    # TOTAL CANDIDATES
    # -----------------------------------------------------

    total_candidates = db.session.scalar(
        select(func.count(Candidate.id))
        .join(
            Vacancy,
            Candidate.vacancy_id == Vacancy.id
        )
        .where(
            Vacancy.created_by == recruiter_id
        )
    ) or 0

    # -----------------------------------------------------
    # TOTAL INTERVIEWS
    # -----------------------------------------------------

    total_interviews = db.session.scalar(
        select(func.count(Interview.id))
        .join(
            Candidate,
            Interview.candidate_id == Candidate.id
        )
        .join(
            Vacancy,
            Candidate.vacancy_id == Vacancy.id
        )
        .where(
            Vacancy.created_by == recruiter_id
        )
    ) or 0

    # -----------------------------------------------------
    # PENDING FOLLOW-UPS
    # -----------------------------------------------------

    pending_followups = db.session.scalar(
        select(func.count(FollowUp.id))
        .join(
            Candidate,
            FollowUp.candidate_id == Candidate.id
        )
        .join(
            Vacancy,
            Candidate.vacancy_id == Vacancy.id
        )
        .where(
            Vacancy.created_by == recruiter_id,
            FollowUp.done.is_(False)
        )
    ) or 0

    # -----------------------------------------------------
    # CANDIDATE PIPELINE
    # -----------------------------------------------------

    pipeline_stages = [
        "New",
        "Reviewing",
        "Interview Planned",
        "Interviewed",
        "Shortlisted",
        "Selected",
        "On Hold",
        "Rejected",
        "Closed",
    ]

    stage_counts = {
        stage: 0 for stage in pipeline_stages
    }

    pipeline_results = db.session.execute(
        select(
            Candidate.status,
            func.count(Candidate.id)
        )
        .join(
            Vacancy,
            Candidate.vacancy_id == Vacancy.id
        )
        .where(
            Vacancy.created_by == recruiter_id
        )
        .group_by(Candidate.status)
    ).all()

    # Match status values without case sensitivity.
    stage_lookup = {
        stage.lower(): stage
        for stage in pipeline_stages
    }

    for status, count in pipeline_results:

        if status:
            normalized_status = status.strip().lower()

            matching_stage = stage_lookup.get(
                normalized_status
            )

            if matching_stage:
                stage_counts[matching_stage] = count

    # -----------------------------------------------------
    # UPCOMING INTERVIEWS
    # -----------------------------------------------------

    upcoming_interviews = (
        Interview.query
        .join(
            Candidate,
            Interview.candidate_id == Candidate.id
        )
        .join(
            Vacancy,
            Candidate.vacancy_id == Vacancy.id
        )
        .filter(
            Vacancy.created_by == recruiter_id,
            Interview.status != "Completed",
            Interview.scheduled_at >= datetime.now()
        )
        .order_by(Interview.scheduled_at.asc())
        .limit(5)
        .all()
    )

    # -----------------------------------------------------
    # RECENT ACTIVITIES
    # -----------------------------------------------------

    # recent_activities = (
    #     AuditLog.query
    #     .filter_by(user_id=recruiter_id)
    #     .order_by(AuditLog.created_at.desc())
    #     .limit(5)
    #     .all()
    # )

    # -----------------------------------------------------
    # RENDER DASHBOARD
    # -----------------------------------------------------

    return render_template(
        "recruiter/dashboard.html",

        total_vacancies=total_vacancies,
        total_candidates=total_candidates,
        total_interviews=total_interviews,
        pending_followups=pending_followups,

        pipeline_stages=pipeline_stages,
        stage_counts=stage_counts,

        upcoming_interviews=upcoming_interviews,
    #     recent_activities=recent_activities,
    )
