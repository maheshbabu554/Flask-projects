
"""
Offer letter routes for HireWise AI.

Allows recruiters to preview and send PDF offer letters
or reject candidates while retaining recruitment history.
"""

from datetime import datetime, timezone

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import current_user, login_required

from extensions import db
from models import Candidate, AuditLog
from routes.recruiter import recruiter_required
from services.email_service import send_offer_email


offer_letters_bp = Blueprint("offer_letters", __name__)


def get_recruiter_candidate(candidate_id):
    """Return a candidate belonging to the logged-in recruiter."""

    candidate = db.session.get(Candidate, candidate_id)

    if not candidate:
        abort(404)

    if not candidate.vacancy:
        abort(404)

    if candidate.vacancy.created_by != current_user.id:
        abort(403)

    return candidate


def has_completed_interview(candidate):
    """Check whether the candidate has completed an interview."""

    return any(
        interview.status == "Completed"
        for interview in candidate.interviews
    )


def redirect_to_candidate(candidate):
    """Redirect to the candidate detail page."""

    return redirect(
        url_for(
            "candidates.candidate_detail",
            candidate_id=candidate.id,
        )
    )


@offer_letters_bp.route(
    "/candidates/<int:candidate_id>/offer-letter",
    methods=["GET"],
)
@login_required
@recruiter_required
def preview_offer_letter(candidate_id):
    """Display the offer letter preview form."""

    candidate = get_recruiter_candidate(candidate_id)

    if candidate.status in ["Rejected", "Closed"]:
        flash(
            "An offer cannot be created for this candidate.",
            "warning",
        )
        return redirect_to_candidate(candidate)

    if candidate.status == "Offer Sent":
        flash(
            "An offer letter has already been sent.",
            "info",
        )
        return redirect_to_candidate(candidate)

    if not has_completed_interview(candidate):
        flash(
            "An offer letter is available only after "
            "a completed interview.",
            "warning",
        )
        return redirect_to_candidate(candidate)

    return render_template(
        "recruiter/offer_letter_preview.html",
        candidate=candidate,
    )


@offer_letters_bp.route(
    "/candidates/<int:candidate_id>/offer-letter/send",
    methods=["POST"],
)
@login_required
@recruiter_required
def send_offer_letter(candidate_id):
    """Generate a PDF offer letter and email it to the candidate."""

    candidate = get_recruiter_candidate(candidate_id)

    if candidate.status in ["Rejected", "Closed", "Offer Sent"]:
        flash(
            "This candidate is not eligible for another offer.",
            "warning",
        )
        return redirect_to_candidate(candidate)

    if not has_completed_interview(candidate):
        flash(
            "A completed interview is required before sending an offer.",
            "warning",
        )
        return redirect_to_candidate(candidate)

    salary = request.form.get("salary", "").strip()
    joining_date = request.form.get("joining_date", "").strip()
    additional_message = request.form.get(
        "offer_message", ""
    ).strip()

    if not salary or not joining_date:
        flash(
            "Salary and joining date are required.",
            "danger",
        )
        return redirect(
            url_for(
                "offer_letters.preview_offer_letter",
                candidate_id=candidate.id,
            )
        )

    if not candidate.email:
        flash(
            "The candidate does not have a registered email address.",
            "danger",
        )
        return redirect_to_candidate(candidate)

    job_title = candidate.vacancy.title

    # Step 1: Generate PDF and send the email.
    try:
        send_offer_email(
            candidate_name=candidate.full_name,
            recipient=candidate.email,
            job_title=job_title,
            salary=salary,
            joining_date=joining_date,
            additional_message=additional_message,
        )

    except Exception:
        current_app.logger.exception(
            "Offer email delivery failed for candidate ID %s",
            candidate.id,
        )

        flash(
            "Unable to send the offer letter. "
            "Check the Flask terminal for the actual error.",
            "danger",
        )

        return redirect_to_candidate(candidate)

    # Step 2: Update candidate status and save audit history.
    try:
        previous_status = candidate.status

        candidate.status = "Offer Sent"

        audit = AuditLog(
            user_id=current_user.id,
            action="OFFER_LETTER_SENT",
            entity_type="Candidate",
            entity_id=candidate.id,
            details_json={
                "candidate_email": candidate.email,
                "job_title": job_title,
                "salary": salary,
                "joining_date": joining_date,
                "sent_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "previous_status": previous_status,
                "new_status": "Offer Sent",
            },
        )

        db.session.add(audit)
        db.session.commit()

        flash(
            "Offer letter PDF sent successfully to the candidate.",
            "success",
        )

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Offer email was sent, but database update failed "
            "for candidate ID %s",
            candidate.id,
        )

        flash(
            "The email may have been sent, but the database "
            "update failed. Verify email delivery before retrying.",
            "danger",
        )

    return redirect_to_candidate(candidate)


@offer_letters_bp.route(
    "/candidates/<int:candidate_id>/reject",
    methods=["POST"],
)
@login_required
@recruiter_required
def reject_candidate(candidate_id):
    """Reject a candidate without deleting recruitment history."""

    candidate = get_recruiter_candidate(candidate_id)

    if candidate.status == "Rejected":
        flash(
            "This candidate has already been rejected.",
            "info",
        )
        return redirect_to_candidate(candidate)

    if candidate.status in ["Offer Sent", "Closed"]:
        flash(
            "This candidate cannot be rejected through this action.",
            "warning",
        )
        return redirect_to_candidate(candidate)

    reason = request.form.get("reason", "").strip()

    if not reason:
        flash(
            "Please provide a reason for rejecting this candidate.",
            "danger",
        )
        return redirect(
            url_for(
                "offer_letters.preview_offer_letter",
                candidate_id=candidate.id,
            )
        )

    previous_status = candidate.status

    try:
        candidate.status = "Rejected"

        audit = AuditLog(
            user_id=current_user.id,
            action="CANDIDATE_REJECTED",
            entity_type="Candidate",
            entity_id=candidate.id,
            details_json={
                "candidate_email": candidate.email,
                "previous_status": previous_status,
                "new_status": "Rejected",
                "reason": reason,
                "rejected_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            },
        )

        db.session.add(audit)
        db.session.commit()

        flash(
            "Candidate rejected and archived successfully.",
            "success",
        )

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Candidate rejection failed for candidate ID %s",
            candidate.id,
        )

        flash(
            "Unable to reject the candidate. "
            "Check the Flask terminal for details.",
            "danger",
        )

    return redirect_to_candidate(candidate)
