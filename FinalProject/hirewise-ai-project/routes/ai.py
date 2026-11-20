
"""
AI routes for HireWise AI.

Provides AI-assisted resume extraction, skill evidence analysis,
experience-based interview question generation, and interview
note summarization.
"""

from pathlib import Path

from flask import Blueprint, current_app, jsonify
from flask_login import current_user, login_required

from extensions import db
from models import (
    AuditAIRun,
    Candidate,
    Interview,
    QuestionPack,
    ResumeEvidence,
    Vacancy,
)

from services.ai_service import (
    AIServiceError,
    extract_candidate_profile,
    generate_interview_questions,
    get_ai_settings,
    summarize_interview_notes,
)

from services.evidence_service import analyze_requirement_evidence
from services.resume_parser import get_full_resume_text
from routes.recruiter import recruiter_required


ai_bp = Blueprint("ai", __name__)


# =========================================================
# CANDIDATE OWNERSHIP
# =========================================================

def get_owned_candidate(candidate_id):
    """
    Return a candidate only if the current recruiter
    owns the vacancy associated with that candidate.
    """

    candidate = db.session.get(
        Candidate,
        candidate_id
    )

    if not candidate:
        return None

    vacancy = db.session.get(
        Vacancy,
        candidate.vacancy_id
    )

    if not vacancy:
        return None

    if vacancy.created_by != current_user.id:
        return None

    return candidate


# =========================================================
# RESUME FILE ACCESS
# =========================================================

def get_candidate_resume_text(candidate):
    """Read a recruiter's privately stored resume."""

    upload_folder = Path(
        current_app.config["RESUME_UPLOAD_FOLDER"]
    ).resolve()

    if not candidate.resume_path:
        raise FileNotFoundError(
            "Candidate resume path is missing."
        )

    resume_path = (
        upload_folder / Path(candidate.resume_path).name
    ).resolve()

    if resume_path.parent != upload_folder:
        raise ValueError(
            "Invalid resume file path."
        )

    if not resume_path.is_file():
        raise FileNotFoundError(
            "Candidate resume was not found."
        )

    return get_full_resume_text(resume_path)


# =========================================================
# AI AUDIT LOGGING
# =========================================================

def record_ai_run(
    candidate_id,
    operation,
    status,
    model_name="",
    latency_ms=0
):
    """Record an AI operation for auditing."""

    audit = AuditAIRun(
        candidate_id=candidate_id,
        operation=operation,
        model_name=model_name or "unknown",
        status=status,
        latency_ms=latency_ms or 0
    )

    db.session.add(audit)


def record_failed_ai_run(candidate_id, operation):
    """Record a failed AI operation after rolling back."""

    record_ai_run(
        candidate_id=candidate_id,
        operation=operation,
        status="failed"
    )

    db.session.commit()


# =========================================================
# RESUME PROFILE EXTRACTION
# =========================================================

@ai_bp.route(
    "/ai/candidates/<int:candidate_id>/extract-profile",
    methods=["POST"]
)
@login_required
@recruiter_required
def extract_profile(candidate_id):
    """Extract candidate information from the uploaded resume."""

    candidate = get_owned_candidate(candidate_id)

    if not candidate:
        return jsonify({
            "error": "Candidate not found."
        }), 404

    try:
        resume_text = get_candidate_resume_text(
            candidate
        )

        result = extract_candidate_profile(
            resume_text
        )

        candidate.extracted_profile_json = result["data"]

        record_ai_run(
            candidate_id=candidate.id,
            operation="resume_profile_extraction",
            status="success",
            model_name=result["model"],
            latency_ms=result["latency_ms"]
        )

        db.session.commit()

        return jsonify({
            "message": "Resume information extracted successfully.",
            "extracted_profile": candidate.extracted_profile_json
        }), 200

    except (
        AIServiceError,
        ValueError,
        FileNotFoundError
    ) as error:

        db.session.rollback()

        record_failed_ai_run(
            candidate.id,
            "resume_profile_extraction"
        )

        return jsonify({
            "error": str(error)
        }), 400

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Resume extraction failed."
        )

        return jsonify({
            "error": "An unexpected error occurred during extraction."
        }), 500


# =========================================================
# RESUME SKILL EVIDENCE ANALYSIS
# =========================================================

@ai_bp.route(
    "/ai/candidates/<int:candidate_id>/evidence",
    methods=["POST"]
)
@login_required
@recruiter_required
def analyze_evidence(candidate_id):
    """Analyze resume evidence for the vacancy's required skills."""

    candidate = get_owned_candidate(candidate_id)

    if not candidate:
        return jsonify({
            "error": "Candidate not found."
        }), 404

    vacancy = db.session.get(
        Vacancy,
        candidate.vacancy_id
    )

    if not vacancy:
        return jsonify({
            "error": "Associated vacancy not found."
        }), 404

    try:
        required_skills = (
            vacancy.required_skills_json or []
        )

        if not required_skills:
            return jsonify({
                "error": "This vacancy has no required skills."
            }), 400

        resume_text = get_candidate_resume_text(
            candidate
        )

        evidence_items = analyze_requirement_evidence(
            resume_text,
            required_skills
        )

        # Replace previous evidence only after
        # the new evidence analysis succeeds.

        ResumeEvidence.query.filter_by(
            candidate_id=candidate.id
        ).delete()

        for item in evidence_items:

            evidence = ResumeEvidence(
                candidate_id=candidate.id,
                skill=item["skill"],
                evidence_status=item["evidence_status"],
                excerpt=item["excerpt"],
                source_page=item["source_page"]
            )

            db.session.add(evidence)

        settings = get_ai_settings()

        record_ai_run(
            candidate_id=candidate.id,
            operation="skill_evidence_analysis",
            status="success",
            model_name=settings["model"],
            latency_ms=0
        )

        db.session.commit()

        return jsonify({
            "message": "Skill evidence analysis completed.",
            "evidence": evidence_items
        }), 200

    except (
        AIServiceError,
        ValueError,
        FileNotFoundError,
        KeyError
    ) as error:

        db.session.rollback()

        record_failed_ai_run(
            candidate.id,
            "skill_evidence_analysis"
        )

        return jsonify({
            "error": str(error)
        }), 400

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Evidence analysis failed."
        )

        return jsonify({
            "error": "An unexpected error occurred during evidence analysis."
        }), 500


# =========================================================
# INTERVIEW QUESTION GENERATION
# =========================================================

@ai_bp.route(
    "/ai/candidates/<int:candidate_id>/interview-questions",
    methods=["POST"]
)
@login_required
@recruiter_required
def create_interview_questions(candidate_id):
    """
    Generate interview questions using the verified candidate profile.

    Difficulty is selected automatically based on
    the candidate's work experience.
    """

    candidate = get_owned_candidate(
        candidate_id
    )

    if not candidate:
        return jsonify({
            "error": "Candidate not found."
        }), 404

    vacancy = db.session.get(
        Vacancy,
        candidate.vacancy_id
    )

    if not vacancy:
        return jsonify({
            "error": "Associated vacancy not found."
        }), 404

    # Questions must use the recruiter-confirmed profile.
    if not candidate.confirmed_profile_json:
        return jsonify({
            "error": "Please confirm the candidate profile first."
        }), 400

    evidence_records = ResumeEvidence.query.filter_by(
        candidate_id=candidate.id
    ).all()

    evidence = [
        {
            "skill": item.skill,
            "status": item.evidence_status,
            "excerpt": item.excerpt,
            "page": item.source_page
        }
        for item in evidence_records
    ]

    vacancy_data = {
        "title": vacancy.title,
        "description": vacancy.description,
        "required_skills": (
            vacancy.required_skills_json or []
        ),
        "optional_skills": (
            vacancy.optional_skills_json or []
        )
    }

    try:
        result = generate_interview_questions(
            vacancy_data,
            candidate.confirmed_profile_json,
            evidence
        )

        questions = result["data"].get(
            "questions"
        )

        experience_details = result["data"].get(
            "experience_details"
        )

        if (
            not isinstance(questions, list)
            or not questions
        ):
            raise AIServiceError(
                "AI did not generate valid interview questions."
            )

        if not isinstance(experience_details, dict):
            raise AIServiceError(
                "AI service did not return candidate experience details."
            )

        # Save only the questions in QuestionPack.
        # Experience details are returned separately.
        question_pack = QuestionPack(
            candidate_id=candidate.id,
            questions_json=questions
        )

        db.session.add(question_pack)

        record_ai_run(
            candidate_id=candidate.id,
            operation="interview_question_generation",
            status="success",
            model_name=result["model"],
            latency_ms=result["latency_ms"]
        )

        db.session.commit()

        return jsonify({
            "message": "Interview questions generated successfully.",
            "questions": questions,
            "experience_details": experience_details
        }), 200

    except (
        AIServiceError,
        ValueError,
        KeyError
    ) as error:

        db.session.rollback()

        record_failed_ai_run(
            candidate.id,
            "interview_question_generation"
        )

        return jsonify({
            "error": str(error)
        }), 400

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Interview question generation failed."
        )

        return jsonify({
            "error": "Could not generate interview questions."
        }), 500


# =========================================================
# INTERVIEW NOTES SUMMARIZATION
# =========================================================

@ai_bp.route(
    "/ai/interviews/<int:interview_id>/summarize",
    methods=["POST"]
)
@login_required
@recruiter_required
def summarize_interview(interview_id):
    """
    Generate an editable plain-text summary
    from the recruiter's raw interview notes.
    """

    interview = db.session.get(
        Interview,
        interview_id
    )

    if not interview:
        return jsonify({
            "error": "Interview not found."
        }), 404

    candidate = get_owned_candidate(
        interview.candidate_id
    )

    if not candidate:
        return jsonify({
            "error": "Interview not found."
        }), 404

    if not interview.notes_raw or not interview.notes_raw.strip():
        return jsonify({
            "error": "Please add interview notes before summarizing."
        }), 400

    try:
        result = summarize_interview_notes(
            interview.notes_raw
        )

        # IMPORTANT:
        # Interview notes summarization returns plain text,
        # not structured JSON.

        summary = result["content"]

        if not isinstance(summary, str) or not summary.strip():
            raise AIServiceError(
                "AI generated an empty interview summary."
            )

        # Save the plain-text summary.
        interview.summary_edited = summary.strip()

        record_ai_run(
            candidate_id=candidate.id,
            operation="interview_note_summarization",
            status="success",
            model_name=result["model"],
            latency_ms=result["latency_ms"]
        )

        db.session.commit()

        return jsonify({
            "message": "Interview summary generated successfully.",
            "summary": interview.summary_edited
        }), 200

    except (
        AIServiceError,
        ValueError,
        KeyError
    ) as error:

        db.session.rollback()

        record_failed_ai_run(
            candidate.id,
            "interview_note_summarization"
        )

        return jsonify({
            "error": str(error)
        }), 400

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Interview summarization failed."
        )

        return jsonify({
            "error": "Could not summarize interview notes."
        }), 500
