
"""
Evidence validation service for HireWise AI.

Validates AI-generated skill evidence before it is
displayed to recruiters or stored in the database.
"""

from services.ai_service import (
    AIServiceError,
    map_requirement_evidence,
)


VALID_STATUSES = {
    "evidence found",
    "not found",
    "uncertain",
}


def validate_evidence_result(ai_result, resume_text, required_skills):
    """Validate and normalize AI-generated skill evidence."""

    if not isinstance(ai_result, dict):
        raise AIServiceError("Invalid AI evidence response.")

    evidence_items = ai_result.get("evidence")

    if not isinstance(evidence_items, list):
        raise AIServiceError(
            "AI response does not contain a valid evidence list."
        )

    validated_items = []

    for item in evidence_items:
        if not isinstance(item, dict):
            continue

        skill = item.get("skill")

        if not isinstance(skill, str) or not skill.strip():
            continue

        # Only accept skills requested for this analysis.
        matched_skill = next(
            (
                required_skill
                for required_skill in required_skills
                if isinstance(required_skill, str)
                and required_skill.casefold() == skill.strip().casefold()
            ),
            None
        )

        if matched_skill is None:
            continue

        status = str(item.get("status", "")).strip().lower()

        if status not in VALID_STATUSES:
            status = "uncertain"

        excerpt = item.get("excerpt")

        if not isinstance(excerpt, str) or not excerpt.strip():
            excerpt = None
        else:
            excerpt = excerpt.strip()

        # Do not accept fabricated or paraphrased excerpts.
        if excerpt and excerpt not in resume_text:
            excerpt = None

            if status == "evidence found":
                status = "uncertain"

        page = item.get("page")

        if (
            not isinstance(page, int)
            or isinstance(page, bool)
            or page < 1
        ):
            page = None

        explanation = item.get("explanation")

        if not isinstance(explanation, str):
            explanation = ""

        validated_items.append({
            "skill": matched_skill,
            "evidence_status": status,
            "excerpt": excerpt,
            "source_page": page,
            "explanation": explanation.strip()
        })

    # Ensure every required skill has a result.
    returned_skills = {
        item["skill"].casefold()
        for item in validated_items
    }

    for skill in required_skills:
        if (
            isinstance(skill, str)
            and skill.casefold() not in returned_skills
        ):
            validated_items.append({
                "skill": skill,
                "evidence_status": "uncertain",
                "excerpt": None,
                "source_page": None,
                "explanation": "AI did not return a result for this skill."
            })

    return validated_items


def analyze_requirement_evidence(resume_text, required_skills):
    """
    Run AI evidence analysis and validate its response.

    Returns:
        A list of validated evidence dictionaries.
    """

    if not isinstance(resume_text, str) or not resume_text.strip():
        raise ValueError("Resume text is required.")

    if not isinstance(required_skills, list) or not required_skills:
        raise ValueError("Required skills must be provided.")

     # Normalize required skills.
    # If a vacancy contains one multiline string,
    # split it into individual skills.

    skills = []

    for item in required_skills:
        if not isinstance(item, str):
            continue

        for skill in item.splitlines():
            skill = skill.strip()

            if skill and skill not in skills:
                skills.append(skill)

    if not skills:
        raise ValueError("No valid required skills were provided.")

    ai_response = map_requirement_evidence(
        resume_text=resume_text,
        required_skills=skills
    )

    return validate_evidence_result(
        ai_result=ai_response.get("data"),
        resume_text=resume_text,
        required_skills=skills
    )
