
"""
Follow-up management routes for HireWise AI.

Handles:
- Listing recruiter follow-ups
- Selecting candidates for follow-ups
- Creating follow-ups
- Recording communication details
- Completing follow-ups
- Scheduling the next follow-up
- Reopening completed follow-ups
- Deleting follow-ups
"""

from datetime import date, datetime, time

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from extensions import db
from models import Candidate, FollowUp, Vacancy
from routes.recruiter import recruiter_required


followup_bp = Blueprint("followups", __name__)


# =========================================================
# OWNERSHIP HELPERS
# =========================================================

def get_owned_candidate(candidate_id):
    """Return a candidate belonging to the current recruiter."""

    candidate = db.session.get(Candidate, candidate_id)

    if not candidate:
        return None

    vacancy = db.session.get(Vacancy, candidate.vacancy_id)

    if not vacancy or vacancy.created_by != current_user.id:
        return None

    return candidate


def get_owned_followup(followup_id):
    """Return a follow-up belonging to the current recruiter."""

    followup = db.session.get(FollowUp, followup_id)

    if not followup:
        return None

    if not get_owned_candidate(followup.candidate_id):
        return None

    return followup


# =========================================================
# DATE VALIDATION
# =========================================================

def parse_date_input(value, field_name):
    """Convert an HTML date input into a Python datetime."""

    if not value:
        raise ValueError(f"{field_name} is required.")

    try:
        parsed_date = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Invalid {field_name.lower()}.")

    return datetime.combine(parsed_date, time.min)


# =========================================================
# FOLLOW-UP LIST
# =========================================================

@followup_bp.route("/followups")
@recruiter_required
def followup_list():
    """Display all follow-ups belonging to the recruiter."""

    followups = (
        FollowUp.query
        .join(Candidate, FollowUp.candidate_id == Candidate.id)
        .join(Vacancy, Candidate.vacancy_id == Vacancy.id)
        .filter(Vacancy.created_by == current_user.id)
        .order_by(
            FollowUp.done.asc(),
            FollowUp.due_date.asc()
        )
        .all()
    )

    today = date.today()

    return render_template(
        "recruiter/followups.html",
        followups=followups,
        today=today
    )


# =========================================================
# SELECT CANDIDATE
# =========================================================

@followup_bp.route("/followups/create", methods=["GET"])
@recruiter_required
def select_candidate_for_followup():
    """Display candidates so the recruiter can select one."""

    candidates = (
        Candidate.query
        .join(Vacancy, Candidate.vacancy_id == Vacancy.id)
        .filter(Vacancy.created_by == current_user.id)
        .order_by(Candidate.full_name.asc())
        .all()
    )

    candidates = [
        candidate
        for candidate in candidates
        if candidate.status not in ("Rejected", "Deleted")
    ]

    return render_template(
        "recruiter/followup_candidate_select.html",
        candidates=candidates
    )


# =========================================================
# CREATE FOLLOW-UP
# =========================================================

@followup_bp.route(
    "/candidates/<int:candidate_id>/followups/create",
    methods=["GET", "POST"]
)
@recruiter_required
def create_followup(candidate_id):
    """Create a follow-up activity for a candidate."""

    candidate = get_owned_candidate(candidate_id)

    if not candidate:
        flash("Candidate not found.", "danger")
        return redirect(url_for("candidates.candidate_list"))

    if candidate.status in ("Rejected", "Deleted"):
        flash(
            "Follow-ups cannot be created for rejected or deleted candidates.",
            "warning"
        )
        return redirect(url_for("followups.followup_list"))

    if request.method == "POST":

        due_date_value = request.form.get(
            "due_date", ""
        ).strip()

        action_text = request.form.get(
            "action_text", ""
        ).strip()

        try:
            due_date = parse_date_input(
                due_date_value,
                "Due date"
            )

            if due_date.date() < date.today():
                raise ValueError(
                    "Follow-up due date cannot be in the past."
                )

            if not action_text:
                raise ValueError(
                    "Action description is required."
                )

            if len(action_text) > 255:
                raise ValueError(
                    "Action description cannot exceed 255 characters."
                )

            followup = FollowUp(
                candidate_id=candidate.id,
                due_date=due_date,
                action_text=action_text,
                done=False
            )

            db.session.add(followup)
            db.session.commit()

            flash(
                "Follow-up created successfully.",
                "success"
            )

            return redirect(
                url_for("followups.followup_list")
            )

        except ValueError as error:
            flash(str(error), "danger")

        except Exception:
            db.session.rollback()
            flash(
                "Could not create the follow-up.",
                "danger"
            )

    return render_template(
        "recruiter/followup_form.html",
        candidate=candidate,
        today=date.today()
    )


# =========================================================
# COMPLETE FOLLOW-UP AND RECORD COMMUNICATION
# =========================================================

@followup_bp.route(
    "/followups/<int:followup_id>/complete",
    methods=["POST"]
)
@recruiter_required
def complete_followup(followup_id):
    """
    Complete a follow-up and record the actual communication.

    If another follow-up is needed, create it as a separate task.
    """

    followup = get_owned_followup(followup_id)

    if not followup:
        flash(
            "Follow-up not found.",
            "danger"
        )
        return redirect(
            url_for("followups.followup_list")
        )

    if followup.done:
        flash(
            "This follow-up is already completed.",
            "info"
        )
        return redirect(
            url_for("followups.followup_list")
        )

    contact_method = request.form.get(
        "contact_method", ""
    ).strip()

    outcome = request.form.get(
        "outcome", ""
    ).strip()

    notes = request.form.get(
        "notes", ""
    ).strip()

    next_date_value = request.form.get(
        "next_followup_date", ""
    ).strip()

    next_action_text = request.form.get(
        "next_action_text", ""
    ).strip()

    allowed_methods = {
        "Call",
        "Email",
        "WhatsApp",
        "Meeting",
        "Other"
    }

    allowed_outcomes = {
        "Candidate Responded",
        "No Answer",
        "Requested Callback",
        "Interested",
        "Not Interested",
        "Documents Pending",
        "Interview Confirmation Pending",
        "Other"
    }

    try:
        # Validate communication method.
        if contact_method not in allowed_methods:
            raise ValueError(
                "Please select a valid contact method."
            )

        # Validate communication outcome.
        if outcome not in allowed_outcomes:
            raise ValueError(
                "Please select a valid communication outcome."
            )

        # Validate notes.
        if not notes:
            raise ValueError(
                "Communication notes are required."
            )

        if len(notes) > 10000:
            raise ValueError(
                "Notes cannot exceed 10,000 characters."
            )

        next_followup_date = None

        # Validate next follow-up details.
        if next_date_value or next_action_text:

            if not next_date_value:
                raise ValueError(
                    "Select a date for the next follow-up."
                )

            if not next_action_text:
                raise ValueError(
                    "Enter the action for the next follow-up."
                )

            if len(next_action_text) > 255:
                raise ValueError(
                    "Next follow-up action cannot exceed 255 characters."
                )

            next_followup_date = parse_date_input(
                next_date_value,
                "Next follow-up date"
            )

            if next_followup_date.date() < date.today():
                raise ValueError(
                    "The next follow-up date cannot be in the past."
                )

        # Record communication details.
        followup.contact_method = contact_method
        followup.outcome = outcome
        followup.notes = notes

        # Complete the current follow-up.
        followup.done = True
        followup.completed_at = datetime.utcnow()

        # Schedule another follow-up as a separate task.
        if next_followup_date:

            followup.next_followup_date = next_followup_date

            next_followup = FollowUp(
                candidate_id=followup.candidate_id,
                due_date=next_followup_date,
                action_text=next_action_text,
                done=False
            )

            db.session.add(next_followup)

        db.session.commit()

        if next_followup_date:
            flash(
                "Communication recorded, current follow-up completed, "
                "and next follow-up scheduled successfully.",
                "success"
            )
        else:
            flash(
                "Communication recorded and follow-up completed successfully.",
                "success"
            )

    except ValueError as error:
        db.session.rollback()
        flash(str(error), "danger")

    except Exception:
        db.session.rollback()
        flash(
            "Could not complete the follow-up.",
            "danger"
        )

    return redirect(
        url_for("followups.followup_list")
    )


# =========================================================
# REOPEN FOLLOW-UP
# =========================================================

@followup_bp.route(
    "/followups/<int:followup_id>/reopen",
    methods=["POST"]
)
@recruiter_required
def reopen_followup(followup_id):
    """Reopen a completed follow-up activity."""

    followup = get_owned_followup(followup_id)

    if not followup:
        flash(
            "Follow-up not found.",
            "danger"
        )
        return redirect(
            url_for("followups.followup_list")
        )

    try:
        followup.done = False
        followup.completed_at = None

        db.session.commit()

        flash(
            "Follow-up reopened successfully.",
            "success"
        )

    except Exception:
        db.session.rollback()
        flash(
            "Could not reopen the follow-up.",
            "danger"
        )

    return redirect(
        url_for("followups.followup_list")
    )


# =========================================================
# DELETE FOLLOW-UP
# =========================================================

@followup_bp.route(
    "/followups/<int:followup_id>/delete",
    methods=["POST"]
)
@recruiter_required
def delete_followup(followup_id):
    """Delete a follow-up belonging to the recruiter."""

    followup = get_owned_followup(followup_id)

    if not followup:
        flash(
            "Follow-up not found.",
            "danger"
        )
        return redirect(
            url_for("followups.followup_list")
        )

    try:
        db.session.delete(followup)
        db.session.commit()

        flash(
            "Follow-up deleted successfully.",
            "success"
        )

    except Exception:
        db.session.rollback()
        flash(
            "Could not delete the follow-up.",
            "danger"
        )

    return redirect(
        url_for("followups.followup_list")
    )
