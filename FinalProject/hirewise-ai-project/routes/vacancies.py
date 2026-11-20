
"""
Vacancy routes for HireWise AI.

Allows recruiters to create, view, edit, and close
their own job vacancies.
"""

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import current_user
from sqlalchemy import select

from extensions import db
from models import Vacancy

from routes.recruiter import recruiter_required


vacancy_bp = Blueprint("vacancies", __name__)


# =========================================================
# LIST VACANCIES
# =========================================================

@vacancy_bp.route("/vacancies")
@recruiter_required
def vacancy_list():
    """Display vacancies created by the logged-in recruiter."""

    vacancies = db.session.scalars(
        select(Vacancy)
        .where(Vacancy.created_by == current_user.id)
        .order_by(Vacancy.id.desc())
    ).all()

    return render_template(
        "recruiter/vacancies.html",
        vacancies=vacancies,
    )


# =========================================================
# CREATE VACANCY
# =========================================================

@vacancy_bp.route("/vacancies/create", methods=["GET", "POST"])
@recruiter_required
def create_vacancy():



    
    """Create a new job vacancy."""

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()

        required_skills = [
            skill.strip()
            for skill in request.form.get(
                "required_skills", ""
            ).split(",")
            if skill.strip()
        ]

        optional_skills = [
            skill.strip()
            for skill in request.form.get(
                "optional_skills", ""
            ).split(",")
            if skill.strip()
        ]

        openings_text = request.form.get("openings", "1").strip()

        if not title or not description:
            flash(
                "Job title and description are required.",
                "danger",
            )
            return render_template(
                "recruiter/vacancy_form.html",
                vacancy=None,
            )

        try:
            openings = int(openings_text)

            if openings < 1:
                raise ValueError

        except ValueError:
            flash(
                "Number of openings must be a positive whole number.",
                "danger",
            )
            return render_template(
                "recruiter/vacancy_form.html",
                vacancy=None,
            )

        vacancy = Vacancy(
            title=title,
            description=description,
            required_skills_json=required_skills,
            optional_skills_json=optional_skills,
            location=location or None,
            openings=openings,
            status="Open",
            created_by=current_user.id,
        )

        try:
            db.session.add(vacancy)
            db.session.commit()

            flash("Vacancy created successfully.", "success")

            return redirect(url_for("vacancies.vacancy_list"))

        except Exception:
            db.session.rollback()

            flash(
                "Unable to create vacancy. Please try again.",
                "danger",
            )

    return render_template(
        "recruiter/vacancy_form.html",
        vacancy=None,
    )


# =========================================================
# VACANCY DETAILS
# =========================================================

@vacancy_bp.route("/vacancies/<int:vacancy_id>")
@recruiter_required
def vacancy_detail(vacancy_id):
    """Display details of a recruiter's vacancy."""

    vacancy = db.session.get(Vacancy, vacancy_id)

    if vacancy is None:
        abort(404)

    if vacancy.created_by != current_user.id:
        abort(403)

    return render_template(
        "recruiter/vacancy_detail.html",
        vacancy=vacancy,
    )


# =========================================================
# EDIT VACANCY
# =========================================================

@vacancy_bp.route(
    "/vacancies/<int:vacancy_id>/edit",
    methods=["GET", "POST"],
)
@recruiter_required
def edit_vacancy(vacancy_id):
    """Edit an existing vacancy."""

    vacancy = db.session.get(Vacancy, vacancy_id)

    if vacancy is None:
        abort(404)

    if vacancy.created_by != current_user.id:
        abort(403)

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()

        required_skills = [
            skill.strip()
            for skill in request.form.get(
                "required_skills", ""
            ).split(",")
            if skill.strip()
        ]

        optional_skills = [
            skill.strip()
            for skill in request.form.get(
                "optional_skills", ""
            ).split(",")
            if skill.strip()
        ]

        openings_text = request.form.get("openings", "1").strip()

        if not title or not description:
            flash(
                "Job title and description are required.",
                "danger",
            )

            return render_template(
                "recruiter/vacancy_form.html",
                vacancy=vacancy,
            )

        try:
            openings = int(openings_text)

            if openings < 1:
                raise ValueError

        except ValueError:
            flash(
                "Number of openings must be a positive whole number.",
                "danger",
            )

            return render_template(
                "recruiter/vacancy_form.html",
                vacancy=vacancy,
            )

        vacancy.title = title
        vacancy.description = description
        vacancy.required_skills_json = required_skills
        vacancy.optional_skills_json = optional_skills
        vacancy.location = location or None
        vacancy.openings = openings

        try:
            db.session.commit()

            flash("Vacancy updated successfully.", "success")

            return redirect(
                url_for(
                    "vacancies.vacancy_detail",
                    vacancy_id=vacancy.id,
                )
            )

        except Exception:
            db.session.rollback()

            flash(
                "Unable to update vacancy. Please try again.",
                "danger",
            )

    return render_template(
        "recruiter/vacancy_form.html",
        vacancy=vacancy,
    )


# =========================================================
# CLOSE VACANCY
# =========================================================

@vacancy_bp.route(
    "/vacancies/<int:vacancy_id>/close",
    methods=["POST"],
)
@recruiter_required
def close_vacancy(vacancy_id):
    """Close a vacancy without deleting its history."""

    vacancy = db.session.get(Vacancy, vacancy_id)

    if vacancy is None:
        abort(404)

    if vacancy.created_by != current_user.id:
        abort(403)

    vacancy.status = "Closed"

    try:
        db.session.commit()

        flash("Vacancy closed successfully.", "success")

    except Exception:
        db.session.rollback()

        flash(
            "Unable to close vacancy. Please try again.",
            "danger",
        )

    return redirect(url_for("vacancies.vacancy_list"))
