
"""
Interview management routes for HireWise AI.

Provides:
- Candidate-first Interview Desk
- Interview scheduling and rescheduling
- Automatic interview schedule emails
- Interview notes and AI summary storage
- Recruiter-entered evaluation scores
- Audit logging
- Email activity logging

AI does not score, rank, reject, or make hiring decisions.
"""

from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from extensions import db
from models import (
    AuditLog,
    Candidate,
    EmailLog,
    Interview,
    QuestionPack,
    User,
    Vacancy,
)
from routes.recruiter import recruiter_required
from services.email_service import send_interview_schedule_email


interview_bp = Blueprint("interviews", __name__)


# ---------------------------------------------------------
# OWNERSHIP HELPERS
# ---------------------------------------------------------

def get_owned_candidate(candidate_id):
    """Return a candidate belonging to the current recruiter."""

    candidate = db.session.get(Candidate, candidate_id)

    if not candidate:
        return None

    vacancy = db.session.get(Vacancy, candidate.vacancy_id)

    if not vacancy or vacancy.created_by != current_user.id:
        return None

    return candidate


def get_owned_interview(interview_id):
    """Return an interview belonging to the current recruiter."""

    interview = db.session.get(Interview, interview_id)

    if not interview:
        return None

    if not get_owned_candidate(interview.candidate_id):
        return None

    return interview


def get_available_interviewers():
    """Return recruiter accounts available for interviews."""

    interviewers = (
        User.query
        .filter(db.func.lower(User.role) == "recruiter")
        .order_by(User.full_name.asc())
        .all()
    )

    if current_user.id not in {
        interviewer.id for interviewer in interviewers
    }:
        interviewers.append(current_user)

    return interviewers


def get_pending_interview(candidate):
    """Return the latest interview that is not completed."""

    return (
        Interview.query
        .filter(
            Interview.candidate_id == candidate.id,
            Interview.status != "Completed"
        )
        .order_by(Interview.id.desc())
        .first()
    )


def get_latest_question_pack(candidate_id):
    """Return the latest AI-generated technical question pack."""

    return (
        QuestionPack.query
        .filter_by(candidate_id=candidate_id)
        .order_by(QuestionPack.generated_at.desc())
        .first()
    )


def interview_desk_redirect(candidate_id=None):
    """Return to the Interview Desk with an optional selected candidate."""

    if candidate_id:
        return redirect(
            url_for(
                "interviews.interview_list",
                candidate_id=candidate_id
            )
        )

    return redirect(url_for("interviews.interview_list"))


# ---------------------------------------------------------
# INTERVIEW EMAIL NOTIFICATION
# ---------------------------------------------------------

def send_interview_notification(interview, event_type):
    """
    Send an offline interview schedule or reschedule email.

    The interview must already be committed before this function
    is called. Email failures do not undo the interview schedule.
    """

    candidate = db.session.get(
        Candidate,
        interview.candidate_id
    )

    if not candidate:
        current_app.logger.error(
            "Cannot send interview email: candidate not found."
        )
        return False

    vacancy = db.session.get(
        Vacancy,
        candidate.vacancy_id
    )

    if not vacancy:
        current_app.logger.error(
            "Cannot send interview email: vacancy not found."
        )
        return False

    recipient = (getattr(candidate, "email", None) or "").strip()

    if not recipient:
        current_app.logger.error(
            "Cannot send interview email: candidate email is missing."
        )
        return False

    if not interview.scheduled_at:
        current_app.logger.error(
            "Cannot send interview email: interview date is missing."
        )
        return False

    location = (
        getattr(interview, "interview_location", None) or ""
    ).strip()

    instructions = (
        getattr(interview, "additional_instructions", None) or ""
    ).strip()

    if not location:
        current_app.logger.error(
            "Cannot send interview email: interview location is missing."
        )
        return False

    # A unique key prevents the same notification from being
    # logged and sent twice for the same interview event.
    event_key = (
        f"interview-{interview.id}-"
        f"{event_type}-"
        f"{interview.scheduled_at.isoformat()}"
    )

    existing_log = EmailLog.query.filter_by(
        event_key=event_key
    ).first()

    if existing_log:
        current_app.logger.info(
            "Interview notification already exists: %s",
            event_key
        )
        return existing_log.status == "Sent"

    job_title = (
        getattr(vacancy, "title", None)
        or getattr(vacancy, "job_title", None)
        or "Interview"
    )

    candidate_name = (
        getattr(candidate, "full_name", None)
        or "Candidate"
    )

    interview_date = interview.scheduled_at.strftime(
        "%d %B %Y"
    )

    interview_time = interview.scheduled_at.strftime(
        "%I:%M %p"
    )

    subject_action = (
        "Interview Scheduled"
        if event_type == "scheduled"
        else "Interview Rescheduled"
    )

    subject = f"{subject_action} - {job_title}"

    email_status = "Failed"
    error_message = None

    try:
        send_interview_schedule_email(
            candidate_name=candidate_name,
            recipient=recipient,
            job_title=job_title,
            interview_date=interview_date,
            interview_time=interview_time,
            interview_mode="Offline",
            meeting_link=None,
            interview_location=location,
            additional_instructions=instructions,
        )

        email_status = "Sent"

    except Exception as exc:
        error_message = str(exc)

        current_app.logger.exception(
            "Interview notification email failed."
        )

    try:
        email_log = EmailLog(
            candidate_id=candidate.id,
            interview_id=interview.id,
            email_type=subject_action,
            recipient_email=recipient,
            subject=subject,
            status=email_status,
            event_key=event_key,
            error_message=error_message,
            sent_at=(
                datetime.utcnow()
                if email_status == "Sent"
                else None
            )
        )

        db.session.add(email_log)
        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Could not save interview email log."
        )

    return email_status == "Sent"


# ---------------------------------------------------------
# INTERVIEW DESK
# ---------------------------------------------------------

@interview_bp.route("/interviews")
@recruiter_required
def interview_list():
    """Display the candidate-first Interview Desk."""

    excluded_statuses = [
        "Rejected",
        "Closed",
        "Offer Sent",
        "Deleted"
    ]

    candidates = (
        Candidate.query
        .join(Vacancy, Candidate.vacancy_id == Vacancy.id)
        .filter(
            Vacancy.created_by == current_user.id,
            ~Candidate.interviews.any(
                Interview.status == "Completed"
            ),
            ~Candidate.status.in_(excluded_statuses)
        )
        .order_by(Candidate.full_name.asc())
        .all()
    )

    selected_candidate = None
    selected_interview = None
    question_pack = None

    candidate_id = request.args.get(
        "candidate_id",
        type=int
    )

    if candidate_id:

        selected_candidate = get_owned_candidate(candidate_id)

        if not selected_candidate:
            flash("Candidate not found.", "danger")
            return interview_desk_redirect()

        if any(
            item.status == "Completed"
            for item in selected_candidate.interviews
        ):
            flash(
                "This candidate's interview is already completed. "
                "View the feedback on the candidate record.",
                "info"
            )

            return redirect(
                url_for(
                    "candidates.candidate_detail",
                    candidate_id=selected_candidate.id
                )
            )

        if selected_candidate.status in excluded_statuses:
            flash(
                "An interview cannot be conducted for this candidate "
                "at the current recruitment stage.",
                "warning"
            )

            return interview_desk_redirect()

        selected_interview = get_pending_interview(
            selected_candidate
        )

        question_pack = get_latest_question_pack(
            selected_candidate.id
        )

    interviewers = get_available_interviewers()

    return render_template(
        "recruiter/interviews.html",
        candidates=candidates,
        selected_candidate=selected_candidate,
        selected_interview=selected_interview,
        interviewers=interviewers,
        question_pack=question_pack
    )


# ---------------------------------------------------------
# CREATE / SCHEDULE INTERVIEW
# ---------------------------------------------------------

@interview_bp.route(
    "/candidates/<int:candidate_id>/interviews/create",
    methods=["GET", "POST"]
)
@recruiter_required
def create_interview(candidate_id):
    """Create an interview and notify the candidate."""

    candidate = get_owned_candidate(candidate_id)

    if not candidate:
        flash("Candidate not found.", "danger")
        return interview_desk_redirect()

    if candidate.status in {
        "Rejected", "Closed", "Offer Sent", "Deleted"
    }:
        flash(
            "An interview cannot be scheduled for this candidate "
            "at the current stage.",
            "warning"
        )
        return interview_desk_redirect()

    if any(
        item.status == "Completed"
        for item in candidate.interviews
    ):
        flash(
            "This candidate already has a completed interview.",
            "info"
        )

        return redirect(
            url_for(
                "candidates.candidate_detail",
                candidate_id=candidate.id
            )
        )

    existing_interview = get_pending_interview(candidate)

    if existing_interview:

        if request.method == "POST":
            flash(
                "An interview already exists. "
                "You can update it from the Interview Desk.",
                "info"
            )

        return interview_desk_redirect(candidate.id)

    if request.method == "GET":
        return interview_desk_redirect(candidate.id)

    scheduled_value = request.form.get(
        "scheduled_at", ""
    ).strip()

    interviewer_value = request.form.get(
        "interviewer_id",
        str(current_user.id)
    ).strip()

    interview_location = request.form.get(
        "interview_location", ""
    ).strip()

    additional_instructions = request.form.get(
        "additional_instructions", ""
    ).strip()

    if not scheduled_value:
        flash(
            "Please select an interview date and time.",
            "danger"
        )
        return interview_desk_redirect(candidate.id)

    if not interview_location:
        flash(
            "Please enter the offline interview location.",
            "danger"
        )
        return interview_desk_redirect(candidate.id)

    if len(interview_location) > 255:
        flash(
            "Interview location cannot exceed 255 characters.",
            "danger"
        )
        return interview_desk_redirect(candidate.id)

    if len(additional_instructions) > 5000:
        flash(
            "Additional instructions cannot exceed 5,000 characters.",
            "danger"
        )
        return interview_desk_redirect(candidate.id)

    try:
        scheduled_at = datetime.fromisoformat(scheduled_value)
    except ValueError:
        flash(
            "Invalid interview date and time.",
            "danger"
        )
        return interview_desk_redirect(candidate.id)

    try:
        interviewer_id = int(interviewer_value)
    except (TypeError, ValueError):
        flash(
            "Please select a valid interviewer.",
            "danger"
        )
        return interview_desk_redirect(candidate.id)

    allowed_interviewer_ids = {
        interviewer.id
        for interviewer in get_available_interviewers()
    }

    if interviewer_id not in allowed_interviewer_ids:
        flash(
            "The selected interviewer is not available.",
            "danger"
        )
        return interview_desk_redirect(candidate.id)

    try:
        interview = Interview(
            candidate_id=candidate.id,
            interviewer_id=interviewer_id,
            scheduled_at=scheduled_at,
            interview_location=interview_location,
            additional_instructions=additional_instructions or None,
            notes_raw="",
            status="Scheduled"
        )

        candidate.status = "Interview Planned"

        db.session.add(interview)
        db.session.flush()

        db.session.add(
            AuditLog(
                user_id=current_user.id,
                action="INTERVIEW_SCHEDULED",
                entity_type="Interview",
                entity_id=interview.id,
                details_json={
                    "candidate_id": candidate.id,
                    "interviewer_id": interviewer_id,
                    "scheduled_at": scheduled_at.isoformat(),
                    "interview_location": interview_location,
                    "result": "Success"
                }
            )
        )

        db.session.commit()

        email_sent = send_interview_notification(
            interview,
            "scheduled"
        )

        if email_sent:
            flash(
                "Interview scheduled successfully. "
                "Candidate notification email sent.",
                "success"
            )
        else:
            flash(
                "Interview scheduled successfully, but the candidate "
                "notification email could not be sent. "
                "Check the email configuration and email logs.",
                "warning"
            )

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Interview scheduling failed."
        )

        flash(
            "Could not schedule the interview.",
            "danger"
        )

    return interview_desk_redirect(candidate.id)


# ---------------------------------------------------------
# UPDATE / RESCHEDULE INTERVIEW
# ---------------------------------------------------------

@interview_bp.route(
    "/interviews/<int:interview_id>/schedule",
    methods=["POST"]
)
@recruiter_required
def update_interview_schedule(interview_id):
    """Update an interview schedule and notify the candidate."""

    interview = get_owned_interview(interview_id)

    if not interview:
        flash("Interview not found.", "danger")
        return interview_desk_redirect()

    if interview.status == "Completed":
        flash(
            "A completed interview cannot be rescheduled.",
            "warning"
        )
        return interview_desk_redirect(interview.candidate_id)

    scheduled_value = request.form.get(
        "scheduled_at", ""
    ).strip()

    interviewer_value = request.form.get(
        "interviewer_id", ""
    ).strip()

    interview_location = request.form.get(
        "interview_location", ""
    ).strip()

    additional_instructions = request.form.get(
        "additional_instructions", ""
    ).strip()

    if not scheduled_value:
        flash(
            "Please select an interview date and time.",
            "danger"
        )
        return interview_desk_redirect(interview.candidate_id)

    if not interview_location:
        flash(
            "Please enter the offline interview location.",
            "danger"
        )
        return interview_desk_redirect(interview.candidate_id)

    if len(interview_location) > 255:
        flash(
            "Interview location cannot exceed 255 characters.",
            "danger"
        )
        return interview_desk_redirect(interview.candidate_id)

    if len(additional_instructions) > 5000:
        flash(
            "Additional instructions cannot exceed 5,000 characters.",
            "danger"
        )
        return interview_desk_redirect(interview.candidate_id)

    try:
        scheduled_at = datetime.fromisoformat(scheduled_value)
        interviewer_id = int(interviewer_value)

    except (TypeError, ValueError):
        flash(
            "Enter a valid date, time, and interviewer.",
            "danger"
        )
        return interview_desk_redirect(interview.candidate_id)

    allowed_interviewer_ids = {
        interviewer.id
        for interviewer in get_available_interviewers()
    }

    if interviewer_id not in allowed_interviewer_ids:
        flash(
            "The selected interviewer is not available.",
            "danger"
        )
        return interview_desk_redirect(interview.candidate_id)

    try:
        old_scheduled_at = (
            interview.scheduled_at.isoformat()
            if interview.scheduled_at
            else None
        )

        old_interviewer_id = interview.interviewer_id
        old_location = interview.interview_location
        old_instructions = interview.additional_instructions

        interview.scheduled_at = scheduled_at
        interview.interviewer_id = interviewer_id
        interview.interview_location = interview_location
        interview.additional_instructions = (
            additional_instructions or None
        )

        db.session.add(
            AuditLog(
                user_id=current_user.id,
                action="INTERVIEW_RESCHEDULED",
                entity_type="Interview",
                entity_id=interview.id,
                details_json={
                    "candidate_id": interview.candidate_id,
                    "old_scheduled_at": old_scheduled_at,
                    "new_scheduled_at": scheduled_at.isoformat(),
                    "old_interviewer_id": old_interviewer_id,
                    "new_interviewer_id": interviewer_id,
                    "old_location": old_location,
                    "new_location": interview_location,
                    "result": "Success"
                }
            )
        )

        db.session.commit()

        email_sent = send_interview_notification(
            interview,
            "rescheduled"
        )

        if email_sent:
            flash(
                "Interview rescheduled successfully. "
                "Updated notification email sent to the candidate.",
                "success"
            )
        else:
            flash(
                "Interview rescheduled successfully, but the updated "
                "notification email could not be sent. "
                "Check the email configuration and email logs.",
                "warning"
            )

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Interview schedule update failed."
        )

        flash(
            "Could not update the interview schedule.",
            "danger"
        )

    return interview_desk_redirect(interview.candidate_id)


# ---------------------------------------------------------
# INTERVIEW DETAIL
# ---------------------------------------------------------

@interview_bp.route("/interviews/<int:interview_id>")
@recruiter_required
def interview_detail(interview_id):
    """Display an individual interview."""

    interview = get_owned_interview(interview_id)

    if not interview:
        flash("Interview not found.", "danger")
        return interview_desk_redirect()

    candidate = get_owned_candidate(interview.candidate_id)

    return render_template(
        "recruiter/interview_detail.html",
        interview=interview,
        candidate=candidate
    )


# ---------------------------------------------------------
# SAVE INTERVIEW NOTES
# ---------------------------------------------------------

@interview_bp.route(
    "/interviews/<int:interview_id>/notes",
    methods=["POST"]
)
@recruiter_required
def update_interview_notes(interview_id):
    """Save original interview notes and edited AI summary."""

    interview = get_owned_interview(interview_id)

    if not interview:
        flash("Interview not found.", "danger")
        return interview_desk_redirect()

    if interview.status == "Completed":
        flash(
            "Original interview notes are locked after completion.",
            "warning"
        )
        return interview_desk_redirect(interview.candidate_id)

    notes = request.form.get(
        "notes_raw", ""
    ).strip()

    summary = request.form.get(
        "summary_edited", ""
    ).strip()

    if len(notes) > 15000:
        flash(
            "Interview notes cannot exceed 15,000 characters.",
            "danger"
        )
        return interview_desk_redirect(interview.candidate_id)

    try:
        interview.notes_raw = notes
        interview.summary_edited = summary or None

        db.session.commit()

        flash(
            "Interview notes saved successfully.",
            "success"
        )

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Saving interview notes failed."
        )

        flash(
            "Could not save interview notes.",
            "danger"
        )

    return interview_desk_redirect(interview.candidate_id)


# ---------------------------------------------------------
# COMPLETE INTERVIEW
# ---------------------------------------------------------

@interview_bp.route(
    "/interviews/<int:interview_id>/complete",
    methods=["POST"]
)
@recruiter_required
def complete_interview(interview_id):
    """
    Complete an interview using recruiter-entered scores only.

    AI never assigns scores or makes hiring decisions.
    """

    interview = get_owned_interview(interview_id)

    if not interview:
        flash("Interview not found.", "danger")
        return interview_desk_redirect()

    if interview.status == "Completed":
        flash(
            "This interview is already completed.",
            "info"
        )
        return redirect(
            url_for(
                "candidates.candidate_detail",
                candidate_id=interview.candidate_id
            )
        )

    if not (interview.notes_raw or "").strip():
        flash(
            "Save the original interview notes before completing "
            "the interview.",
            "danger"
        )
        return interview_desk_redirect(interview.candidate_id)

    try:
        performance = int(
            request.form.get("performance_score", "")
        )

        confidence = int(
            request.form.get("confidence_score", "")
        )

        communication = int(
            request.form.get("communication_score", "")
        )

    except (TypeError, ValueError):
        flash(
            "Enter valid whole-number scores for all three categories.",
            "danger"
        )
        return interview_desk_redirect(interview.candidate_id)

    if not (
        0 <= performance <= 25
        and 0 <= confidence <= 10
        and 0 <= communication <= 15
    ):
        flash(
            "Scores must be Performance 0–25, Confidence 0–10 "
            "and Communication 0–15.",
            "danger"
        )
        return interview_desk_redirect(interview.candidate_id)

    try:
        interview.performance_score = performance
        interview.confidence_score = confidence
        interview.communication_score = communication

        interview.overall_score = (
            performance + confidence + communication
        )

        interview.status = "Completed"
        interview.completed_at = datetime.utcnow()

        interview.candidate.status = "Interviewed"

        db.session.add(
            AuditLog(
                user_id=current_user.id,
                action="INTERVIEW_COMPLETED",
                entity_type="Interview",
                entity_id=interview.id,
                details_json={
                    "candidate_id": interview.candidate_id,
                    "performance_score": performance,
                    "confidence_score": confidence,
                    "communication_score": communication,
                    "overall_score": interview.overall_score,
                    "result": "Success"
                }
            )
        )

        db.session.commit()

        flash(
            "Interview completed successfully. "
            "Original notes are now locked.",
            "success"
        )

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Interview completion failed."
        )

        flash(
            "Could not complete the interview. Please try again.",
            "danger"
        )

    return redirect(
        url_for(
            "candidates.candidate_detail",
            candidate_id=interview.candidate_id
        )
    )
