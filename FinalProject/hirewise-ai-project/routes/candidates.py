
"""
Candidate routes for HireWise AI.

Handles:
- Bulk resume uploads
- AI resume extraction and audit logging
- Candidate listing and details
- Secure resume downloads
- Secure candidate document viewing and downloads
- Recruiter-confirmed candidate profiles
- Individual document verification without page refresh
- Overall document verification and notifications
- Forward-only candidate status updates
- Shortlist, selection and rejection emails
- Secure one-time document upload links
- Candidate soft deletion
- Offer letter eligibility, sending and rejection
"""

import hashlib
import re
import secrets
import uuid

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from flask_login import current_user
from sqlalchemy import select
from werkzeug.utils import secure_filename

from extensions import db

from models import (
    AuditAIRun,
    AuditLog,
    Candidate,
    CandidateDocument,
    DocumentSubmission,
    DocumentUploadLink,
    EmailLog,
    Interview,
    QuestionPack,
    ResumeEvidence,
    User,
    Vacancy,
)

from routes.recruiter import recruiter_required

from services.file_service import (
    save_resume,
    delete_resume,
    validate_resume,
    validate_batch_count,
)

from services.resume_parser import get_full_resume_text

from services.ai_service import (
    AIServiceError,
    extract_candidate_profile,
)

from services.email_service import (
    send_shortlist_email,
    send_rejection_email,
    send_selection_email,
    send_document_verification_admin_email,
    send_offer_email,
)


candidate_bp = Blueprint("candidates", __name__)

UPLOAD_LINK_VALIDITY_HOURS = 72

OVERALL_VERIFICATION_SUCCESS = "OVERALL_DOCUMENT_VERIFICATION_SUCCESS"
OVERALL_VERIFICATION_REJECTED = "OVERALL_DOCUMENT_VERIFICATION_REJECTED"

PENDING_DOCUMENT_STATUSES = {
    "Pending",
    "Pending Verification",
}


# =========================================================
# COMMON HELPERS
# =========================================================

def candidate_detail_redirect(candidate_id):
    """Redirect to a candidate detail page."""

    return redirect(
        url_for(
            "candidates.candidate_detail",
            candidate_id=candidate_id,
        )
    )


def is_ajax_request():
    """Check whether the request expects a JSON response."""

    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def get_recruiter_candidate(candidate_id):
    """Retrieve a candidate belonging to the logged-in recruiter."""

    candidate = db.session.get(Candidate, candidate_id)

    if candidate is None or candidate.status == "Deleted":
        abort(404)

    vacancy = db.session.get(Vacancy, candidate.vacancy_id)

    if vacancy is None:
        abort(404)

    if vacancy.created_by != current_user.id:
        abort(403)

    return candidate


# =========================================================
# OVERALL DOCUMENT VERIFICATION HELPERS
# =========================================================

def get_overall_verification_action(candidate_id):
    """Return the final overall verification audit action, if present."""

    return db.session.scalar(
        select(AuditLog.action)
        .where(
            AuditLog.entity_type == "Candidate",
            AuditLog.entity_id == candidate_id,
            AuditLog.action.in_([
                OVERALL_VERIFICATION_SUCCESS,
                OVERALL_VERIFICATION_REJECTED,
            ]),
        )
        .limit(1)
    )


def get_overall_verification_status(candidate_id):
    """Return Accepted, Rejected or None for overall verification."""

    action = get_overall_verification_action(candidate_id)

    if action == OVERALL_VERIFICATION_SUCCESS:
        return "Accepted"

    if action == OVERALL_VERIFICATION_REJECTED:
        return "Rejected"

    return None


def revoke_unused_upload_links(candidate):
    """Revoke all unused document-upload links for a candidate."""

    now = datetime.utcnow()

    for upload_link in candidate.upload_links:
        if upload_link.used_at is None and upload_link.revoked_at is None:
            upload_link.revoked_at = now


def documents_are_all_reviewed(documents):
    """Return True when every document has an Accepted or Rejected decision."""

    return bool(documents) and all(
        (document.verification_status or "").strip()
        in {"Accepted", "Rejected"}
        for document in documents
    )


# =========================================================
# AI AUDIT LOGGING
# =========================================================

def record_ai_run(
    candidate_id,
    status,
    model_name="unknown",
    latency_ms=0,
):
    """Record an AI resume extraction operation."""

    audit = AuditAIRun(
        candidate_id=candidate_id,
        operation="resume_profile_extraction",
        model_name=model_name,
        status=status,
        latency_ms=latency_ms,
    )

    db.session.add(audit)


# =========================================================
# AUTOMATIC AI EXTRACTION
# =========================================================

def automatically_extract_candidate(candidate):
    """
    Extract resume text and send it to the configured AI provider.

    Extracted details are stored separately from the
    recruiter-confirmed profile.
    """

    upload_folder = Path(
        current_app.config["RESUME_UPLOAD_FOLDER"]
    ).resolve()

    filename = Path(candidate.resume_path).name
    resume_path = (upload_folder / filename).resolve()

    if resume_path.parent != upload_folder:
        raise ValueError("Invalid resume file path.")

    if not resume_path.is_file():
        raise FileNotFoundError("Uploaded resume was not found.")

    resume_text = get_full_resume_text(resume_path)

    if not resume_text.strip():
        raise ValueError("No readable text found in the resume.")

    result = extract_candidate_profile(resume_text)
    profile = result.get("data")

    if not isinstance(profile, dict):
        raise AIServiceError(
            "AI returned an invalid candidate profile."
        )

    defaults = {
        "full_name": None,
        "email": None,
        "phone": None,
        "location": None,
        "summary": None,
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
    }

    for key, default_value in defaults.items():
        profile.setdefault(key, default_value)

    candidate.extracted_profile_json = profile

    extracted_name = profile.get("full_name")

    if isinstance(extracted_name, str) and extracted_name.strip():
        candidate.full_name = extracted_name.strip()[:150]

    # AI-extracted contact details are not recruiter-confirmed.
    candidate.email = None
    candidate.phone = None

    record_ai_run(
        candidate_id=candidate.id,
        status="success",
        model_name=result.get("model", "unknown"),
        latency_ms=result.get("latency_ms", 0),
    )

    db.session.commit()


# =========================================================
# BULK RESUME UPLOAD
# =========================================================

@candidate_bp.route("/candidates/upload", methods=["GET", "POST"])
@recruiter_required
def upload_resumes():
    """Upload multiple resumes for an open vacancy."""

    vacancies = db.session.scalars(
        select(Vacancy)
        .where(
            Vacancy.created_by == current_user.id,
            Vacancy.status == "Open",
        )
        .order_by(Vacancy.id.desc())
    ).all()

    if request.method == "GET":
        return render_template(
            "recruiter/upload_resume.html",
            vacancies=vacancies,
            selected_vacancy_id=request.args.get("vacancy_id", ""),
        )

    vacancy_id = request.form.get("vacancy_id", "").strip()

    try:
        vacancy_id = int(vacancy_id)
    except (TypeError, ValueError):
        flash("Please select a valid vacancy.", "danger")
        return redirect(url_for("candidates.upload_resumes"))

    vacancy = db.session.get(Vacancy, vacancy_id)

    if (
        vacancy is None
        or vacancy.created_by != current_user.id
        or vacancy.status != "Open"
    ):
        abort(403)

    files = [
        file
        for file in request.files.getlist("resumes")
        if file and file.filename
    ]

    try:
        validate_batch_count(files)
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(
            url_for(
                "candidates.upload_resumes",
                vacancy_id=vacancy.id,
            )
        )

    prepared_files = []

    for index, file in enumerate(files, start=1):
        try:
            original_name, extension = validate_resume(file)

            temporary_name = Path(original_name).stem.strip()

            if not temporary_name:
                temporary_name = "Pending AI Extraction"

            prepared_files.append({
                "file": file,
                "temporary_name": temporary_name[:150],
                "original_name": original_name,
            })

        except ValueError as error:
            flash(
                f"Resume {index} ({file.filename}): {error}",
                "warning",
            )

    if not prepared_files:
        flash(
            "No valid resumes were available to upload.",
            "danger",
        )
        return redirect(
            url_for(
                "candidates.upload_resumes",
                vacancy_id=vacancy.id,
            )
        )

    saved_files = []
    uploaded_candidate_ids = []

    try:
        for item in prepared_files:
            saved_file = save_resume(item["file"])
            saved_files.append(saved_file["relative_path"])

            candidate = Candidate(
                vacancy_id=vacancy.id,
                full_name=item["temporary_name"],
                email=None,
                phone=None,
                resume_path=saved_file["relative_path"],
                extracted_profile_json=None,
                confirmed_profile_json=None,
                status="New",
                previous_status=None,
            )

            db.session.add(candidate)
            db.session.flush()
            uploaded_candidate_ids.append(candidate.id)

        db.session.commit()

    except Exception:
        db.session.rollback()

        for file_path in saved_files:
            try:
                delete_resume(file_path)
            except OSError:
                current_app.logger.exception(
                    "Unable to delete resume after upload failure."
                )

        current_app.logger.exception("Resume upload failed.")

        flash(
            "Resume upload failed. Please try again.",
            "danger",
        )

        return redirect(
            url_for(
                "candidates.upload_resumes",
                vacancy_id=vacancy.id,
            )
        )

    success_count = 0
    failed_count = 0

    for candidate_id in uploaded_candidate_ids:
        try:
            candidate = db.session.get(Candidate, candidate_id)
            automatically_extract_candidate(candidate)
            success_count += 1

        except Exception:
            db.session.rollback()
            failed_count += 1

            current_app.logger.exception(
                "AI extraction failed for candidate ID %s.",
                candidate_id,
            )

            try:
                record_ai_run(
                    candidate_id=candidate_id,
                    status="failed",
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
                current_app.logger.exception(
                    "Failed to save AI extraction audit record."
                )

    if failed_count == 0:
        flash(
            f"Successfully uploaded {len(uploaded_candidate_ids)} "
            f"resume(s). AI extracted {success_count} profile(s).",
            "success",
        )
    else:
        flash(
            f"Uploaded {len(uploaded_candidate_ids)} resume(s). "
            f"AI extraction succeeded for {success_count} "
            f"and failed for {failed_count}. Failed resumes are still saved.",
            "warning",
        )

    return redirect(url_for("candidates.candidate_list"))


# =========================================================
# CANDIDATE LIST
# =========================================================

@candidate_bp.route("/candidates")
@recruiter_required
def candidate_list():
    """Display candidates belonging to the logged-in recruiter."""

    candidates = db.session.scalars(
        select(Candidate)
        .join(Vacancy, Candidate.vacancy_id == Vacancy.id)
        .where(
            Vacancy.created_by == current_user.id,
            Candidate.status.notin_(["Rejected", "Deleted"]),
        )
        .order_by(Candidate.id.desc())
    ).all()

    candidate_ids = [candidate.id for candidate in candidates]
    candidate_scores = {}

    if candidate_ids:
        score_records = db.session.execute(
            select(
                Interview.candidate_id,
                Interview.overall_score,
            )
            .join(Candidate, Interview.candidate_id == Candidate.id)
            .join(Vacancy, Candidate.vacancy_id == Vacancy.id)
            .where(
                Interview.candidate_id.in_(candidate_ids),
                Interview.status == "Completed",
                Interview.overall_score.is_not(None),
                Vacancy.created_by == current_user.id,
            )
            .order_by(Interview.id.desc())
        ).all()

        for candidate_id, score in score_records:
            if candidate_id not in candidate_scores:
                candidate_scores[candidate_id] = score

    return render_template(
        "recruiter/candidates.html",
        candidates=candidates,
        candidate_scores=candidate_scores,
    )


# =========================================================
# DELETE CANDIDATE - SOFT DELETE
# =========================================================

@candidate_bp.route(
    "/candidates/<int:candidate_id>/delete",
    methods=["POST"],
)
@recruiter_required
def delete_candidate(candidate_id):
    """Soft-delete a candidate without permanently deleting records."""

    candidate = get_recruiter_candidate(candidate_id)
    previous_status = candidate.status

    candidate.status = "Deleted"
    candidate.previous_status = None

    revoke_unused_upload_links(candidate)

    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action="candidate_deleted",
            entity_type="Candidate",
            entity_id=candidate.id,
            details_json={
                "candidate_name": candidate.full_name,
                "vacancy_id": candidate.vacancy_id,
                "previous_status": previous_status,
                "deletion_type": "soft_delete",
            },
        )
    )

    try:
        db.session.commit()
        flash("Candidate deleted successfully.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Candidate deletion failed for ID %s.",
            candidate_id,
        )
        flash(
            "Unable to delete candidate. Please try again.",
            "danger",
        )

    return redirect(url_for("candidates.candidate_list"))


# =========================================================
# OFFER LETTER ELIGIBILITY
# =========================================================

def check_offer_eligibility(candidate):
    """Check whether a candidate is eligible for an offer letter."""

    if candidate.status != "Selected":
        return False, "Candidate must be in Selected status."

    if not candidate.email:
        return False, "Candidate email address is missing."

    submission = candidate.document_submission

    if submission is None:
        return False, "Candidate has not submitted documents."

    if submission.status != "Submitted":
        return False, "Candidate document submission is not complete."

    documents = list(candidate.documents)

    if not documents:
        return False, "No candidate documents were found."

    if any(
        document.verification_status != "Accepted"
        for document in documents
    ):
        return False, (
            "All submitted documents must be accepted "
            "before sending an offer letter."
        )

    if get_overall_verification_status(candidate.id) != "Accepted":
        return False, (
            "Overall document verification must be successful "
            "before sending an offer letter."
        )

    return True, None


def candidate_offer_already_sent(candidate):
    """Check whether an offer letter has already been sent."""

    return db.session.scalar(
        select(EmailLog.id)
        .where(
            EmailLog.candidate_id == candidate.id,
            EmailLog.email_type == "offer_letter",
            EmailLog.status == "Sent",
        )
        .limit(1)
    ) is not None


def candidate_offer_is_pending(candidate):
    """Check whether an offer email is currently pending."""

    return db.session.scalar(
        select(EmailLog.id)
        .where(
            EmailLog.candidate_id == candidate.id,
            EmailLog.email_type == "offer_letter",
            EmailLog.status == "Pending",
        )
        .limit(1)
    ) is not None


# =========================================================
# CANDIDATE DETAILS
# =========================================================

@candidate_bp.route("/candidates/<int:candidate_id>")
@recruiter_required
def candidate_detail(candidate_id):
    """Display candidate profile, evidence, questions and documents."""

    candidate = get_recruiter_candidate(candidate_id)

    evidence_records = ResumeEvidence.query.filter_by(
        candidate_id=candidate.id
    ).all()

    question_packs = (
        QuestionPack.query
        .filter_by(candidate_id=candidate.id)
        .order_by(QuestionPack.generated_at.desc())
        .all()
    )

    candidate_documents = sorted(
        candidate.documents,
        key=lambda document: (
            document.uploaded_at or datetime.min
        ),
        reverse=True,
    )

    overall_verification_status = (
        get_overall_verification_status(candidate.id)
    )

    all_documents_reviewed = documents_are_all_reviewed(
        candidate_documents
    )

    offer_eligible, offer_reason = check_offer_eligibility(candidate)

    offer_email_already_sent = candidate_offer_already_sent(candidate)
    offer_email_pending = candidate_offer_is_pending(candidate)

    return render_template(
        "recruiter/candidate_detail.html",
        candidate=candidate,
        evidence_records=evidence_records,
        question_packs=question_packs,
        candidate_documents=candidate_documents,
        overall_verification_status=overall_verification_status,
        all_documents_reviewed=all_documents_reviewed,
        offer_eligible=(
            offer_eligible
            and not offer_email_already_sent
            and not offer_email_pending
        ),
        offer_reason=offer_reason,
        offer_email_already_sent=offer_email_already_sent,
        offer_email_pending=offer_email_pending,
    )


# =========================================================
# SECURE RESUME DOWNLOAD
# =========================================================

@candidate_bp.route(
    "/candidates/<int:candidate_id>/resume",
    methods=["GET"],
)
@recruiter_required
def download_resume(candidate_id):
    """Allow the owning recruiter to download a candidate resume."""

    candidate = get_recruiter_candidate(candidate_id)

    if not candidate.resume_path:
        abort(404)

    upload_folder = Path(
        current_app.config["RESUME_UPLOAD_FOLDER"]
    ).resolve()

    filename = Path(candidate.resume_path).name
    resume_path = (upload_folder / filename).resolve()

    if resume_path.parent != upload_folder or not resume_path.is_file():
        abort(404)

    return send_file(
        resume_path,
        as_attachment=True,
        download_name=filename,
    )


# =========================================================
# PRIVATE CANDIDATE DOCUMENT PATH VALIDATION
# =========================================================

def get_candidate_document_path(candidate, document):
    """Validate and return a file path inside the candidate's folder."""

    if document is None or not document.file_path:
        abort(404)

    configured_folder = current_app.config.get(
        "PRIVATE_DOCUMENT_FOLDER"
    )

    if configured_folder:
        base_folder = Path(configured_folder)
    else:
        base_folder = (
            Path(current_app.instance_path) / "private_documents"
        )

    candidate_folder = (
        base_folder / str(candidate.id)
    ).resolve()

    document_path = Path(document.file_path).resolve()

    try:
        document_path.relative_to(candidate_folder)
    except ValueError:
        current_app.logger.warning(
            "Blocked invalid document path for document ID %s.",
            document.id,
        )
        abort(404)

    if not document_path.is_file():
        abort(404)

    return document_path


# =========================================================
# SECURE CANDIDATE DOCUMENT DOWNLOAD
# =========================================================

@candidate_bp.route(
    "/candidates/<int:candidate_id>/documents/<int:document_id>",
    methods=["GET"],
)
@recruiter_required
def download_candidate_document(candidate_id, document_id):
    """Download a candidate document securely."""

    candidate = get_recruiter_candidate(candidate_id)

    document = db.session.scalar(
        select(CandidateDocument).where(
            CandidateDocument.id == document_id,
            CandidateDocument.candidate_id == candidate.id,
        )
    )

    document_path = get_candidate_document_path(candidate, document)

    download_name = secure_filename(
        document.original_filename or ""
    ) or "candidate_document"

    response = send_file(
        document_path,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=download_name,
    )

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"

    return response


# =========================================================
# SECURE CANDIDATE DOCUMENT VIEW
# =========================================================

@candidate_bp.route(
    "/candidates/<int:candidate_id>/documents/<int:document_id>/view",
    methods=["GET"],
)
@recruiter_required
def view_candidate_document(candidate_id, document_id):
    """Preview a candidate PDF or image securely in the browser."""

    candidate = get_recruiter_candidate(candidate_id)

    document = db.session.scalar(
        select(CandidateDocument).where(
            CandidateDocument.id == document_id,
            CandidateDocument.candidate_id == candidate.id,
        )
    )

    document_path = get_candidate_document_path(candidate, document)

    allowed_types = {
        "application/pdf",
        "image/jpeg",
        "image/png",
    }

    mime_type = (document.mime_type or "").lower()

    if mime_type not in allowed_types:
        abort(415)

    download_name = secure_filename(
        document.original_filename or ""
    ) or "candidate_document"

    response = send_file(
        document_path,
        mimetype=mime_type,
        as_attachment=False,
        download_name=download_name,
    )

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; sandbox"
    )

    return response


# =========================================================
# INDIVIDUAL DOCUMENT VERIFICATION - AJAX SUPPORTED
# =========================================================

@candidate_bp.route(
    "/candidates/<int:candidate_id>/documents/<int:document_id>/verify",
    methods=["POST"],
)
@recruiter_required
def verify_candidate_document(candidate_id, document_id):
    """
    Accept or reject one document.

    AJAX requests receive JSON so the page does not refresh.
    Normal form requests continue to use redirects.

    This route does not change candidate recruitment status
    and does not send emails.
    """

    ajax = is_ajax_request()

    def respond(success, message, status_code=200, **extra):
        """Return JSON for AJAX or flash-and-redirect for normal forms."""

        if ajax:
            payload = {
                "success": success,
                "message": message,
            }
            payload.update(extra)
            return jsonify(payload), status_code

        flash(
            message,
            "success" if success else "danger",
        )
        return candidate_detail_redirect(candidate_id)

    candidate = get_recruiter_candidate(candidate_id)

    document = db.session.scalar(
        select(CandidateDocument).where(
            CandidateDocument.id == document_id,
            CandidateDocument.candidate_id == candidate.id,
        )
    )

    if document is None:
        if ajax:
            return jsonify({
                "success": False,
                "message": "Document not found.",
            }), 404
        abort(404)

    if candidate.status in {
        "Rejected",
        "Deleted",
        "Closed",
        "Offer Sent",
    }:
        return respond(
            False,
            "Documents cannot be verified for this candidate.",
            409,
        )

    if get_overall_verification_action(candidate.id):
        return respond(
            False,
            "Overall document verification has already been finalized.",
            409,
        )

    decision = request.form.get("decision", "").strip().capitalize()
    remarks = request.form.get("remarks", "").strip()

    if decision not in {"Accepted", "Rejected"}:
        return respond(
            False,
            "Please select a valid document verification decision.",
            400,
        )

    if len(remarks) > 2000:
        return respond(
            False,
            "Verification remarks cannot exceed 2000 characters.",
            400,
        )

    if decision == "Rejected" and not remarks:
        return respond(
            False,
            "Please provide a reason for rejecting this document.",
            400,
        )

    if document.verification_status not in PENDING_DOCUMENT_STATUSES:
        return respond(
            False,
            "This document has already been verified.",
            409,
        )

    now = datetime.utcnow()

    document.verification_status = decision
    document.verification_notes = remarks or None
    document.verified_by_id = current_user.id
    document.verified_at = now

    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action=(
                "CANDIDATE_DOCUMENT_ACCEPTED"
                if decision == "Accepted"
                else "CANDIDATE_DOCUMENT_REJECTED"
            ),
            entity_type="CandidateDocument",
            entity_id=document.id,
            details_json={
                "candidate_id": candidate.id,
                "candidate_name": candidate.full_name,
                "document_name": document.original_filename,
                "decision": decision,
                "remarks": remarks or "No remarks provided",
                "individual_verification_only": True,
                "candidate_status_changed": False,
                "email_sent": False,
            },
        )
    )

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Document verification failed for document ID %s.",
            document_id,
        )

        return respond(
            False,
            "Unable to save the document verification decision.",
            500,
        )

    # Recalculate review completion after committing this decision.
    documents = list(candidate.documents)
    all_reviewed = documents_are_all_reviewed(documents)

    accepted_count = sum(
        1
        for item in documents
        if item.verification_status == "Accepted"
    )

    rejected_count = sum(
        1
        for item in documents
        if item.verification_status == "Rejected"
    )

    message = (
        f"Document {decision.lower()} successfully. "
        "No notification email was sent."
    )

    return respond(
        True,
        message,
        decision=decision,
        document_id=document.id,
        verification_status=decision,
        remarks=remarks,
        verified_at=now.strftime("%d-%m-%Y %I:%M %p"),
        verified_by_id=current_user.id,
        all_documents_reviewed=all_reviewed,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        total_documents=len(documents),
    )


# =========================================================
# FINAL OVERALL DOCUMENT VERIFICATION
# =========================================================

@candidate_bp.route(
    "/candidates/<int:candidate_id>/documents/finalize",
    methods=["POST"],
)
@recruiter_required
def finalize_document_verification(candidate_id):
    """
    Finalize overall document verification.

    Success:
        - Every document must be Accepted.
        - Sends final admin notification.

    Rejection:
        - At least one document must be Rejected.
        - Candidate becomes Rejected.
        - Unused upload links are revoked.
        - Sends final admin notification.
        - Sends candidate rejection email.

    Finalization is recorded in AuditLog and cannot be repeated.
    """

    candidate = get_recruiter_candidate(candidate_id)

    if candidate.status in {
        "Rejected",
        "Deleted",
        "Closed",
        "Offer Sent",
    }:
        flash(
            "Overall verification cannot be finalized for this candidate.",
            "warning",
        )
        return candidate_detail_redirect(candidate.id)

    if get_overall_verification_action(candidate.id):
        flash(
            "Overall document verification has already been finalized.",
            "warning",
        )
        return candidate_detail_redirect(candidate.id)

    documents = list(candidate.documents)

    if not documents:
        flash(
            "There are no submitted documents to verify.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    if not documents_are_all_reviewed(documents):
        flash(
            "Please review every document before finalizing overall verification.",
            "warning",
        )
        return candidate_detail_redirect(candidate.id)

    invalid_documents = [
        document
        for document in documents
        if document.verification_status not in {"Accepted", "Rejected"}
    ]

    if invalid_documents:
        flash(
            "One or more documents have an invalid verification status.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    # Accept both the old template values and canonical values.
    raw_decision = request.form.get(
        "decision",
        "",
    ).strip().lower()

    decision_aliases = {
        "success": "success",
        "accepted": "success",
        "successful": "success",
        OVERALL_VERIFICATION_SUCCESS.lower(): "success",
        "rejected": "rejected",
        OVERALL_VERIFICATION_REJECTED.lower(): "rejected",
    }

    decision = decision_aliases.get(raw_decision, "")

    rejected_documents = [
        document
        for document in documents
        if document.verification_status == "Rejected"
    ]

    all_documents_accepted = all(
        document.verification_status == "Accepted"
        for document in documents
    )

    if decision not in {"success", "rejected"}:
        flash(
            "Please select a valid overall verification decision.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    if decision == "success" and not all_documents_accepted:
        flash(
            "Overall verification cannot be successful because "
            "one or more documents were rejected.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    if decision == "rejected" and not rejected_documents:
        flash(
            "Overall verification can only be rejected when "
            "at least one document has been rejected.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    vacancy = db.session.get(Vacancy, candidate.vacancy_id)

    if vacancy is None:
        abort(404)

    previous_candidate_status = candidate.status
    now = datetime.utcnow()

    if decision == "success":
        audit_action = OVERALL_VERIFICATION_SUCCESS
        overall_status = "Accepted"
    else:
        audit_action = OVERALL_VERIFICATION_REJECTED
        overall_status = "Rejected"

        candidate.status = "Rejected"
        candidate.previous_status = None

        revoke_unused_upload_links(candidate)

    rejected_document_details = [
        {
            "document_name": (
                document.original_filename
                or f"Document {document.id}"
            ),
            "remarks": (
                document.verification_notes
                or "No remarks provided"
            ),
        }
        for document in rejected_documents
    ]

    combined_remarks = "\n".join(
        f"{item['document_name']}: {item['remarks']}"
        for item in rejected_document_details
    )

    if not combined_remarks:
        combined_remarks = "All submitted documents were accepted."

    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action=audit_action,
            entity_type="Candidate",
            entity_id=candidate.id,
            details_json={
                "candidate_name": candidate.full_name,
                "vacancy_id": candidate.vacancy_id,
                "overall_decision": overall_status,
                "previous_candidate_status": previous_candidate_status,
                "new_candidate_status": candidate.status,
                "total_documents": len(documents),
                "accepted_documents": sum(
                    1
                    for document in documents
                    if document.verification_status == "Accepted"
                ),
                "rejected_documents": len(rejected_documents),
                "rejected_document_details": rejected_document_details,
                "finalized_by_id": current_user.id,
                "finalized_at": now.isoformat(),
            },
        )
    )

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Overall document verification failed for candidate ID %s.",
            candidate.id,
        )

        flash(
            "Unable to save the overall verification decision.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    # Final admin notification.
    admin_emails = db.session.scalars(
        select(User.email).where(
            User.role == "admin",
            User.email.is_not(None),
        )
    ).all()

    admin_email_success = bool(admin_emails)

    document_summary = "Overall document verification"

    if rejected_documents:
        document_summary = (
            "Overall document verification "
            f"({len(rejected_documents)} rejected document(s))"
        )

    for admin_email in admin_emails:
        try:
            send_document_verification_admin_email(
                admin_email=admin_email,
                candidate_name=candidate.full_name,
                job_title=vacancy.title,
                document_name=document_summary,
                decision=overall_status,
                remarks=combined_remarks,
                recruiter_name=getattr(
                    current_user,
                    "username",
                    None,
                ),
            )
        except Exception:
            admin_email_success = False

            current_app.logger.exception(
                "Unable to send final document verification "
                "notification to admin for candidate ID %s.",
                candidate.id,
            )

    # Candidate rejection email is sent only for overall rejection.
    candidate_email_success = True

    if decision == "rejected":
        rejection_reason = (
            "Your submitted documents could not be accepted. "
            "One or more documents were missing, incomplete, or invalid.\n\n"
            f"Document review details:\n{combined_remarks}\n\n"
            "Your application has been rejected following the document "
            "verification process. Please contact the recruitment team "
            "if you need further information."
        )

        try:
            candidate_email_success = send_candidate_status_email(
                candidate=candidate,
                vacancy=vacancy,
                new_status="Rejected",
                reason=rejection_reason,
            )
        except Exception:
            candidate_email_success = False
            current_app.logger.exception(
                "Candidate rejection email failed for candidate ID %s.",
                candidate.id,
            )

    if decision == "success":
        if admin_email_success:
            flash(
                "Overall document verification successful. "
                "Final admin notification sent.",
                "success",
            )
        else:
            flash(
                "Overall document verification successful, but "
                "the admin notification could not be sent.",
                "warning",
            )
    else:
        if admin_email_success and candidate_email_success:
            flash(
                "Overall document verification rejected. "
                "Candidate status updated to Rejected. "
                "Final notifications sent to the admin and candidate.",
                "success",
            )
        else:
            flash(
                "Overall verification rejected and candidate status "
                "updated. One or more notification emails could not "
                "be sent. Check the application logs.",
                "warning",
            )

    return candidate_detail_redirect(candidate.id)


# =========================================================
# UPDATE CANDIDATE PROFILE
# =========================================================

@candidate_bp.route(
    "/candidates/<int:candidate_id>/update-profile",
    methods=["POST"],
)
@recruiter_required
def update_candidate_profile(candidate_id):
    """Save recruiter-confirmed candidate information."""

    candidate = get_recruiter_candidate(candidate_id)

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()

    if not full_name or not email:
        flash(
            "Candidate name and email are required.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    if len(full_name) > 150 or len(email) > 120:
        flash(
            "Candidate name or email is too long.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        flash(
            "Please enter a valid email address.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    duplicate = db.session.scalar(
        select(Candidate.id).where(
            Candidate.vacancy_id == candidate.vacancy_id,
            Candidate.email == email,
            Candidate.id != candidate.id,
        )
    )

    if duplicate is not None:
        flash(
            "Another candidate already uses this email for this vacancy.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    candidate.full_name = full_name
    candidate.email = email
    candidate.phone = phone or None

    candidate.confirmed_profile_json = {
        "full_name": full_name,
        "email": email,
        "phone": phone,
    }

    try:
        db.session.commit()
        flash(
            "Candidate profile confirmed successfully.",
            "success",
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Candidate profile update failed."
        )
        flash(
            "Unable to update candidate profile.",
            "danger",
        )

    return candidate_detail_redirect(candidate.id)


# =========================================================
# EMAIL LOG HELPERS
# =========================================================

def create_email_log(candidate, email_type, subject, event_key):
    """Create and flush a pending email log record."""

    email_log = EmailLog(
        candidate_id=candidate.id,
        email_type=email_type,
        recipient_email=candidate.email,
        subject=subject,
        status="Pending",
        event_key=event_key,
    )

    db.session.add(email_log)
    db.session.flush()

    return email_log


def update_email_log(email_log_id, success, error=None):
    """Update a saved email log after a sending attempt."""

    try:
        email_log = db.session.get(EmailLog, email_log_id)

        if email_log is None:
            return

        if success:
            email_log.status = "Sent"
            email_log.sent_at = datetime.utcnow()
            email_log.error_message = None
        else:
            email_log.status = "Failed"
            email_log.error_message = str(error)[:2000]

        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Unable to update email log ID %s.",
            email_log_id,
        )


# =========================================================
# SHORTLIST AND REJECTION EMAILS
# =========================================================

def send_candidate_status_email(
    candidate,
    vacancy,
    new_status,
    reason="",
):
    """Send a shortlist or rejection email and track the attempt."""

    if new_status not in {"Shortlisted", "Rejected"}:
        return True

    if not candidate.email:
        current_app.logger.warning(
            "Cannot send %s email: candidate %s has no email address.",
            new_status,
            candidate.id,
        )
        return False

    if new_status == "Shortlisted":
        email_type = "candidate_shortlisted"
        subject = "Congratulations! You have been shortlisted"
    else:
        email_type = "candidate_rejected"
        subject = "Application Status Update"

    event_key = (
        f"candidate:{candidate.id}:"
        f"{new_status.lower()}:{uuid.uuid4().hex}"
    )

    try:
        email_log = create_email_log(
            candidate=candidate,
            email_type=email_type,
            subject=subject,
            event_key=event_key,
        )

        email_log_id = email_log.id
        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Unable to create candidate email log."
        )
        return False

    try:
        if new_status == "Shortlisted":
            send_shortlist_email(
                candidate_name=candidate.full_name,
                recipient=candidate.email,
                job_title=vacancy.title,
            )
        else:
            send_rejection_email(
                candidate_name=candidate.full_name,
                recipient=candidate.email,
                job_title=vacancy.title,
                additional_message=reason,
            )

        update_email_log(
            email_log_id=email_log_id,
            success=True,
        )
        return True

    except Exception as error:
        db.session.rollback()

        current_app.logger.exception(
            "Email sending failed for candidate ID %s.",
            candidate.id,
        )

        update_email_log(
            email_log_id=email_log_id,
            success=False,
            error=error,
        )
        return False


# =========================================================
# SECURE TOKEN HASHING
# =========================================================

def hash_upload_token(token):
    """Return the SHA-256 hash of a document upload token."""

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


# =========================================================
# CREATE AND SEND SELECTION EMAIL
# =========================================================

def send_candidate_selection_email(candidate, vacancy):
    """Generate a one-time document upload link and send selection email."""

    if not candidate.email:
        raise ValueError(
            "Confirm the candidate's email address before selection."
        )

    existing_submission = db.session.scalar(
        select(DocumentSubmission).where(
            DocumentSubmission.candidate_id == candidate.id
        )
    )

    if existing_submission is not None:
        raise ValueError(
            "This candidate has already submitted documents."
        )

    previous_success = db.session.scalar(
        select(EmailLog.id)
        .where(
            EmailLog.candidate_id == candidate.id,
            EmailLog.email_type == "candidate_selected",
            EmailLog.status == "Sent",
        )
        .limit(1)
    )

    if previous_success is not None:
        return True

    now = datetime.utcnow()

    previous_links = db.session.scalars(
        select(DocumentUploadLink).where(
            DocumentUploadLink.candidate_id == candidate.id,
            DocumentUploadLink.used_at.is_(None),
            DocumentUploadLink.revoked_at.is_(None),
        )
    ).all()

    for old_link in previous_links:
        old_link.revoked_at = now

    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_upload_token(raw_token)

    expires_at = now + timedelta(
        hours=UPLOAD_LINK_VALIDITY_HOURS
    )

    upload_link = DocumentUploadLink(
        candidate_id=candidate.id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_by_id=current_user.id,
    )

    db.session.add(upload_link)

    subject = "Congratulations! Your application has been selected"

    event_key = (
        f"candidate:{candidate.id}:selection:{uuid.uuid4().hex}"
    )

    try:
        email_log = create_email_log(
            candidate=candidate,
            email_type="candidate_selected",
            subject=subject,
            event_key=event_key,
        )

        email_log_id = email_log.id

        db.session.add(
            AuditLog(
                user_id=current_user.id,
                action="CANDIDATE_DOCUMENT_UPLOAD_LINK_CREATED",
                entity_type="Candidate",
                entity_id=candidate.id,
                details_json={
                    "expires_at": expires_at.isoformat(),
                    "validity_hours": UPLOAD_LINK_VALIDITY_HOURS,
                    "token_stored_as_hash": True,
                },
            )
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Unable to create document upload link."
        )
        return False

    document_upload_url = url_for(
        "document_upload.submit_documents",
        token=raw_token,
        _external=True,
    )

    try:
        send_selection_email(
            candidate_name=candidate.full_name,
            recipient=candidate.email,
            job_title=vacancy.title,
            document_upload_link=document_upload_url,
            submission_deadline=expires_at.strftime(
                "%d %B %Y at %I:%M %p UTC"
            ),
        )

        update_email_log(
            email_log_id=email_log_id,
            success=True,
        )
        return True

    except Exception as error:
        current_app.logger.exception(
            "Selection email failed for candidate ID %s.",
            candidate.id,
        )

        try:
            upload_link = db.session.get(
                DocumentUploadLink,
                upload_link.id,
            )

            if upload_link is not None:
                upload_link.revoked_at = datetime.utcnow()

            email_log = db.session.get(EmailLog, email_log_id)

            if email_log is not None:
                email_log.status = "Failed"
                email_log.error_message = str(error)[:2000]

            db.session.commit()

        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "Unable to revoke failed selection upload link."
            )

        return False


# =========================================================
# UPDATE CANDIDATE STATUS - FORWARD ONLY
# =========================================================

@candidate_bp.route(
    "/candidates/<int:candidate_id>/update-status",
    methods=["POST"],
)
@recruiter_required
def update_candidate_status(candidate_id):
    """Update candidate status using forward-only pipeline transitions."""

    candidate = get_recruiter_candidate(candidate_id)

    current_status = candidate.status
    new_status = request.form.get("status", "").strip()
    reason = request.form.get("reason", "").strip()

    pipeline_stages = [
        "New",
        "Reviewing",
        "Interview Planned",
        "Interviewed",
        "Shortlisted",
        "Selected",
    ]

    next_stage = {
        "New": "Reviewing",
        "Reviewing": "Interview Planned",
        "Interview Planned": "Interviewed",
        "Interviewed": "Shortlisted",
        "Shortlisted": "Selected",
    }

    terminal_statuses = {
        "Rejected",
        "Closed",
        "Deleted",
        "Offer Sent",
    }

    allowed_statuses = set(pipeline_stages) | {
        "Rejected",
        "On Hold",
        "Closed",
    }

    if new_status not in allowed_statuses:
        flash("Invalid candidate status.", "danger")
        return candidate_detail_redirect(candidate.id)

    if current_status in terminal_statuses:
        flash(
            f"This candidate is already {current_status}. "
            "No further status changes are allowed.",
            "warning",
        )
        return candidate_detail_redirect(candidate.id)

    if new_status == "On Hold" and not reason:
        flash(
            "Please provide a reason before placing the candidate On Hold.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    if len(reason) > 2000:
        flash("The reason cannot exceed 2000 characters.", "danger")
        return candidate_detail_redirect(candidate.id)

    if current_status == new_status:
        flash("Candidate already has this status.", "info")
        return candidate_detail_redirect(candidate.id)

    previous_status = current_status
    resuming_from_hold = current_status == "On Hold"

    if resuming_from_hold:
        saved_status = candidate.previous_status

        if new_status not in {"Rejected", "Closed"}:
            if not (
                new_status == saved_status
                and saved_status in pipeline_stages
            ):
                flash(
                    "This candidate can only resume the stage they were "
                    "in before being placed On Hold. Rejection or closure "
                    "is also allowed.",
                    "warning",
                )
                return candidate_detail_redirect(candidate.id)

    else:
        if new_status == "On Hold":
            if current_status not in pipeline_stages:
                flash(
                    "This candidate cannot be placed On Hold.",
                    "warning",
                )
                return candidate_detail_redirect(candidate.id)

        elif new_status in {"Rejected", "Closed"}:
            if current_status not in pipeline_stages:
                flash(
                    "This status transition is not allowed.",
                    "warning",
                )
                return candidate_detail_redirect(candidate.id)

        elif next_stage.get(current_status) != new_status:
            flash(
                "Backward transitions and skipped stages are not allowed. "
                "Please select the next stage.",
                "warning",
            )
            return candidate_detail_redirect(candidate.id)

    if new_status in {"Shortlisted", "Selected", "Rejected"}:
        if not candidate.email:
            flash(
                "Please confirm the candidate's email address "
                "before changing this status.",
                "danger",
            )
            return candidate_detail_redirect(candidate.id)

    vacancy = db.session.get(Vacancy, candidate.vacancy_id)

    if vacancy is None:
        abort(404)

    if new_status == "Selected":
        existing_submission = db.session.scalar(
            select(DocumentSubmission).where(
                DocumentSubmission.candidate_id == candidate.id
            )
        )

        if existing_submission is not None:
            flash(
                "This candidate has already submitted documents.",
                "warning",
            )
            return candidate_detail_redirect(candidate.id)

        previous_success = db.session.scalar(
            select(EmailLog.id)
            .where(
                EmailLog.candidate_id == candidate.id,
                EmailLog.email_type == "candidate_selected",
                EmailLog.status == "Sent",
            )
            .limit(1)
        )

        if previous_success is not None:
            flash(
                "The selection email has already been sent.",
                "info",
            )
            return candidate_detail_redirect(candidate.id)

    if new_status == "On Hold":
        candidate.previous_status = current_status
    elif resuming_from_hold:
        candidate.previous_status = None
    elif new_status in {"Rejected", "Closed"}:
        candidate.previous_status = None

    candidate.status = new_status

    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action="CANDIDATE_STATUS_UPDATED",
            entity_type="Candidate",
            entity_id=candidate.id,
            details_json={
                "previous_status": previous_status,
                "new_status": new_status,
                "saved_previous_status": candidate.previous_status,
                "resumed_from_hold": resuming_from_hold,
                "reason": reason or "Not provided",
            },
        )
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Candidate status update failed for ID %s.",
            candidate_id,
        )
        flash(
            "Unable to update candidate status. Please try again.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    if new_status == "Shortlisted":
        email_sent = send_candidate_status_email(
            candidate=candidate,
            vacancy=vacancy,
            new_status="Shortlisted",
        )

        flash(
            (
                "Candidate shortlisted and email sent successfully."
                if email_sent
                else "Candidate shortlisted, but the email could not be sent."
            ),
            "success" if email_sent else "warning",
        )

    elif new_status == "Selected":
        email_sent = send_candidate_selection_email(
            candidate=candidate,
            vacancy=vacancy,
        )

        flash(
            (
                "Candidate selected. The secure document-upload "
                "link has been sent by email."
                if email_sent
                else "Candidate status updated, but the selection email "
                "could not be sent. Check the email log."
            ),
            "success" if email_sent else "warning",
        )

    elif new_status == "Rejected":
        email_sent = send_candidate_status_email(
            candidate=candidate,
            vacancy=vacancy,
            new_status="Rejected",
            reason=reason,
        )

        flash(
            (
                "Candidate rejected and notification email sent."
                if email_sent
                else "Candidate rejected, but the notification email "
                "could not be sent. Check the email log."
            ),
            "success" if email_sent else "warning",
        )

    elif new_status == "On Hold":
        flash(
            f"Candidate placed On Hold. Previous stage saved: "
            f"{candidate.previous_status}.",
            "success",
        )

    elif resuming_from_hold:
        flash(
            f"Candidate successfully resumed at {new_status}.",
            "success",
        )

    elif new_status == "Closed":
        flash("Candidate closed successfully.", "success")

    else:
        flash(
            f"Candidate status updated to {new_status}.",
            "success",
        )

    return candidate_detail_redirect(candidate.id)


# =========================================================
# SEND OFFER LETTER
# =========================================================

@candidate_bp.route(
    "/candidates/<int:candidate_id>/offer/send",
    methods=["POST"],
)
@recruiter_required
def send_candidate_offer(candidate_id):
    """Send the Mitraz offer letter PDF."""

    candidate = get_recruiter_candidate(candidate_id)

    eligible, reason = check_offer_eligibility(candidate)

    if not eligible:
        flash(reason, "danger")
        return candidate_detail_redirect(candidate.id)

    if candidate_offer_already_sent(candidate):
        flash(
            "An offer letter has already been sent to this candidate.",
            "warning",
        )
        return candidate_detail_redirect(candidate.id)

    if candidate_offer_is_pending(candidate):
        flash(
            "An offer email is already marked as pending. "
            "Check the email log before trying again.",
            "warning",
        )
        return candidate_detail_redirect(candidate.id)

    salary_input = request.form.get(
        "salary",
        "",
    ).strip().replace(",", "")

    try:
        salary_value = Decimal(salary_input)

        if not salary_value.is_finite() or salary_value <= 0:
            raise InvalidOperation

    except (InvalidOperation, TypeError, ValueError):
        flash("Please enter a valid positive salary.", "danger")
        return candidate_detail_redirect(candidate.id)

    joining_date_input = request.form.get(
        "joining_date",
        "",
    ).strip()

    try:
        joining_date_object = datetime.strptime(
            joining_date_input,
            "%Y-%m-%d",
        ).date()

        joining_date = joining_date_object.strftime("%d %B %Y")

    except (TypeError, ValueError):
        flash("Please select a valid joining date.", "danger")
        return candidate_detail_redirect(candidate.id)

    additional_message = request.form.get(
        "additional_message",
        "",
    ).strip()

    if len(additional_message) > 2000:
        flash(
            "Additional message cannot exceed 2000 characters.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    vacancy = db.session.get(Vacancy, candidate.vacancy_id)

    if vacancy is None:
        abort(404)

    event_key = (
        f"candidate:{candidate.id}:offer_letter:{uuid.uuid4().hex}"
    )

    try:
        email_log = create_email_log(
            candidate=candidate,
            email_type="offer_letter",
            subject="Your Offer Letter from Mitraz",
            event_key=event_key,
        )

        email_log_id = email_log.id
        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Unable to create offer email log for candidate %s.",
            candidate.id,
        )
        flash(
            "Unable to prepare the offer email. Please try again.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    try:
        send_offer_email(
            candidate_name=candidate.full_name,
            recipient=candidate.email,
            job_title=vacancy.title,
            salary=f"{salary_value:,.2f}",
            joining_date=joining_date,
            additional_message=additional_message,
        )

    except Exception as error:
        current_app.logger.exception(
            "Offer email failed for candidate %s.",
            candidate.id,
        )

        update_email_log(
            email_log_id=email_log_id,
            success=False,
            error=error,
        )

        flash(
            "Offer email could not be sent. Candidate status "
            "has not been changed. Please check your email settings.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    try:
        candidate.status = "Offer Sent"
        candidate.previous_status = None

        offer_log = db.session.get(EmailLog, email_log_id)

        if offer_log is not None:
            offer_log.status = "Sent"
            offer_log.sent_at = datetime.utcnow()
            offer_log.error_message = None

        db.session.add(
            AuditLog(
                user_id=current_user.id,
                action="OFFER_LETTER_SENT",
                entity_type="Candidate",
                entity_id=candidate.id,
                details_json={
                    "candidate_name": candidate.full_name,
                    "recipient": candidate.email,
                    "job_title": vacancy.title,
                    "salary": f"{salary_value:,.2f}",
                    "joining_date": joining_date,
                    "company": "Mitraz",
                },
            )
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Offer email was sent, but the database update failed "
            "for candidate %s.",
            candidate.id,
        )
        flash(
            "The offer email was sent, but the candidate status "
            "could not be updated. Please contact the administrator "
            "before attempting another offer.",
            "warning",
        )
        return candidate_detail_redirect(candidate.id)

    flash(
        "Mitraz offer letter sent successfully. "
        "Candidate status updated to Offer Sent.",
        "success",
    )

    return candidate_detail_redirect(candidate.id)


# =========================================================
# REJECT CANDIDATE FROM OFFER WORKFLOW
# =========================================================

@candidate_bp.route(
    "/candidates/<int:candidate_id>/offer/reject",
    methods=["POST"],
)
@recruiter_required
def reject_candidate_offer(candidate_id):
    """Reject a candidate from the offer workflow without deleting history."""

    candidate = get_recruiter_candidate(candidate_id)

    if candidate.status != "Selected":
        flash(
            "Only a Selected candidate can be rejected from the offer workflow.",
            "warning",
        )
        return candidate_detail_redirect(candidate.id)

    if candidate_offer_already_sent(candidate):
        flash(
            "An offer letter has already been sent. "
            "This rejection action is no longer available.",
            "warning",
        )
        return candidate_detail_redirect(candidate.id)

    if candidate_offer_is_pending(candidate):
        flash(
            "An offer email is currently marked as pending. "
            "Check the email log before rejecting this candidate.",
            "warning",
        )
        return candidate_detail_redirect(candidate.id)

    reason_text = request.form.get("reason", "").strip()

    if not reason_text:
        flash(
            "Please provide a reason for rejecting the candidate.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    if len(reason_text) > 2000:
        flash(
            "Rejection reason cannot exceed 2000 characters.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    vacancy = db.session.get(Vacancy, candidate.vacancy_id)

    if vacancy is None:
        abort(404)

    previous_status = candidate.status

    candidate.status = "Rejected"
    candidate.previous_status = None

    revoke_unused_upload_links(candidate)

    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action="CANDIDATE_REJECTED_FROM_OFFER_WORKFLOW",
            entity_type="Candidate",
            entity_id=candidate.id,
            details_json={
                "candidate_name": candidate.full_name,
                "previous_status": previous_status,
                "new_status": "Rejected",
                "reason": reason_text,
            },
        )
    )

    try:
        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Offer workflow rejection failed for candidate %s.",
            candidate.id,
        )
        flash(
            "Unable to reject the candidate. Please try again.",
            "danger",
        )
        return candidate_detail_redirect(candidate.id)

    email_sent = send_candidate_status_email(
        candidate=candidate,
        vacancy=vacancy,
        new_status="Rejected",
        reason=reason_text,
    )

    if email_sent:
        flash(
            "Candidate rejected successfully. Rejection email sent. "
            "Candidate history has been retained.",
            "success",
        )
    else:
        flash(
            "Candidate rejected and audit history saved, but the "
            "rejection email could not be sent.",
            "warning",
        )

    return redirect(url_for("candidates.candidate_list"))
