
"""
Administrator routes for HireWise AI.

Handles administrator dashboard, recruiter registration
approvals, recruiter account management, password resets,
account status changes, and audit logging.
"""

from functools import wraps

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
from sqlalchemy import func, select

from extensions import db

from models import (
    AccountRequest,
    AuditLog,
    Candidate,
    User,
    Vacancy,
)

from services.auth_service import hash_password


admin_bp = Blueprint("admin", __name__)


# =========================================================
# ADMIN ACCESS CONTROL
# =========================================================

def admin_required(view_function):
    """Allow access only to active administrators."""

    @wraps(view_function)
    @login_required
    def decorated_view(*args, **kwargs):

        if current_user.status != "active":
            abort(403)

        if current_user.role != "admin":
            abort(403)

        return view_function(*args, **kwargs)

    return decorated_view


# =========================================================
# AUDIT LOGGING
# =========================================================

def create_audit_log(
    action,
    entity_type=None,
    entity_id=None,
    details=None,
):
    """Record an administrator action."""

    audit_details = dict(details or {})
    audit_details.setdefault("result", "Success")
    audit_entry = AuditLog(
        user_id=current_user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details_json=audit_details,
    )

    db.session.add(audit_entry)


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@admin_bp.route("/")
@admin_required
def dashboard():
    """Display administrator dashboard statistics."""

    total_users = db.session.scalar(
        select(func.count(User.id))
    ) or 0

    total_recruiters = db.session.scalar(
        select(func.count(User.id)).where(
            User.role.in_(["recruiter", "placement_coordinator"])
        )
    ) or 0

    total_vacancies = db.session.scalar(
        select(func.count(Vacancy.id))
    ) or 0

    total_candidates = db.session.scalar(
        select(func.count(Candidate.id))
    ) or 0

    pending_requests = db.session.scalar(
        select(func.count(AccountRequest.id)).where(
            AccountRequest.status == "pending"
        )
    ) or 0

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_recruiters=total_recruiters,
        total_vacancies=total_vacancies,
        total_candidates=total_candidates,
        pending_requests=pending_requests,
    )


# =========================================================
# VIEW REGISTRATION REQUESTS
# =========================================================

@admin_bp.route("/account-requests")
@admin_required
def account_requests():
    """Display recruiter registration requests."""

    account_requests = db.session.scalars(
        select(AccountRequest)
        .order_by(AccountRequest.created_at.desc())
    ).all()

    return render_template(
        "admin/account_requests.html",
        account_requests=account_requests,
    )


# =========================================================
# APPROVE OR REJECT REGISTRATION REQUEST
# =========================================================

@admin_bp.route(
    "/account-requests/<int:request_id>",
    methods=["POST"],
)
@admin_required
def review_request(request_id):
    """Approve or reject a recruiter registration request."""

    account_request = db.session.get(
        AccountRequest,
        request_id,
    )

    if account_request is None:
        abort(404)

    if account_request.status != "pending":
        flash(
            "This registration request has already been reviewed.",
            "warning",
        )
        return redirect(url_for("admin.account_requests"))

    if account_request.requested_role not in ("recruiter", "placement_coordinator"):
        abort(400)

    decision = request.form.get("decision", "").strip().lower()

    if decision not in ("approved", "rejected"):
        abort(400)

    try:

        if decision == "approved":

            existing_user = db.session.scalar(
                select(User).where(
                    User.email == account_request.email
                )
            )

            if existing_user:

                flash(
                    "A user account with this email already exists.",
                    "warning",
                )

                return redirect(
                    url_for("admin.account_requests")
                )

            new_user = User(
                full_name=account_request.full_name,
                email=account_request.email,
                password_hash=account_request.password_hash,
                role=account_request.requested_role,
                status="active",
            )

            db.session.add(new_user)

            db.session.flush()

            account_request.status = "approved"
            account_request.reviewed_by = current_user.id

            create_audit_log(
                action="Recruiter registration approved",
                entity_type="User",
                entity_id=new_user.id,
                details={
                    "email": new_user.email,
                    "account_request_id": account_request.id,
                },
            )

            message = f"{account_request.requested_role.replace('_', ' ').title()} account created and approved successfully."
            category = "success"

        else:

            account_request.status = "rejected"
            account_request.reviewed_by = current_user.id

            create_audit_log(
                action="Recruiter registration rejected",
                entity_type="AccountRequest",
                entity_id=account_request.id,
                details={
                    "email": account_request.email,
                },
            )

            message = "Recruiter registration request rejected."
            category = "info"

        db.session.commit()

        flash(message, category)

    except Exception:

        db.session.rollback()

        current_app.logger.exception(
            "Recruiter registration review failed."
        )

        flash(
            "Unable to process the registration request. Please try again.",
            "danger",
        )

    return redirect(url_for("admin.account_requests"))


# =========================================================
# VIEW ALL USERS
# =========================================================

@admin_bp.route("/users")
@admin_required
def users():
    """Display all administrator and recruiter accounts."""

    all_users = db.session.scalars(
        select(User).order_by(User.created_at.desc())
    ).all()

    return render_template(
        "admin/users.html",
        users=all_users,
    )


# =========================================================
# EDIT RECRUITER / PLACEMENT COORDINATOR
# =========================================================

@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    """Edit a workspace user's name, email and recruiter-side role."""
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.role not in ("recruiter", "placement_coordinator"):
        abort(403)
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "recruiter").strip().lower()
        if not full_name or len(full_name) > 100:
            flash("Enter a valid full name.", "danger")
        elif not email or len(email) > 120 or "@" not in email or "." not in email.split("@")[-1]:
            flash("Enter a valid email address.", "danger")
        elif role not in ("recruiter", "placement_coordinator"):
            flash("Select a valid workspace role.", "danger")
        else:
            duplicate = db.session.scalar(select(User).where(User.email == email, User.id != user.id))
            if duplicate:
                flash("That email address is already in use.", "warning")
            else:
                try:
                    user.full_name = full_name
                    user.email = email
                    user.role = role
                    create_audit_log(
                        action="Workspace user updated",
                        entity_type="User",
                        entity_id=user.id,
                        details={"email": email, "role": role},
                    )
                    db.session.commit()
                    flash("User details updated successfully.", "success")
                    return redirect(url_for("admin.users"))
                except Exception:
                    db.session.rollback()
                    flash("Unable to update this user.", "danger")
    return render_template("admin/user_edit.html", user=user)


# =========================================================
# CREATE RECRUITER ACCOUNT
# =========================================================

@admin_bp.route("/users/create", methods=["GET", "POST"])
@admin_required
def create_recruiter():
    """Allow an administrator to create a recruiter account."""

    if request.method == "POST":

        full_name = request.form.get(
            "full_name", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get("password", "")

        confirm_password = request.form.get(
            "confirm_password", ""
        )
        requested_role = request.form.get("role", "recruiter").strip().lower()
        if requested_role not in ("recruiter", "placement_coordinator"):
            requested_role = "recruiter"

        if not all([
            full_name,
            email,
            password,
            confirm_password,
        ]):
            flash(
                "Please fill in all required fields.",
                "danger",
            )
            return render_template("admin/recruiter_form.html")

        if len(full_name) > 100 or len(email) > 120:
            flash(
                "Name or email exceeds the allowed length.",
                "danger",
            )
            return render_template("admin/recruiter_form.html")

        if "@" not in email or "." not in email.split("@")[-1]:
            flash(
                "Please enter a valid email address.",
                "danger",
            )
            return render_template("admin/recruiter_form.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("admin/recruiter_form.html")

        existing_user = db.session.scalar(
            select(User).where(User.email == email)
        )

        if existing_user:
            flash(
                "An account with this email already exists.",
                "warning",
            )
            return render_template("admin/recruiter_form.html")

        pending_request = db.session.scalar(
            select(AccountRequest).where(
                AccountRequest.email == email,
                AccountRequest.status == "pending",
            )
        )

        if pending_request:
            flash(
                "A pending registration request already exists for this email. "
                "Review that request first.",
                "warning",
            )
            return render_template("admin/recruiter_form.html")

        try:

            new_user = User(
                full_name=full_name,
                email=email,
                password_hash=hash_password(password),
                role=requested_role,
                status="active",
            )

            db.session.add(new_user)
            db.session.flush()

            create_audit_log(
                action="Recruiter account created by admin",
                entity_type="User",
                entity_id=new_user.id,
                details={
                    "email": new_user.email,
                },
            )

            db.session.commit()

            flash(
                "Recruiter account created successfully.",
                "success",
            )

            return redirect(url_for("admin.users"))

        except ValueError as error:

            db.session.rollback()
            flash(str(error), "danger")

        except Exception:

            db.session.rollback()

            flash(
                "Unable to create recruiter account. Please try again.",
                "danger",
            )

    return render_template("admin/recruiter_form.html")


# =========================================================
# RESET RECRUITER PASSWORD
# =========================================================

@admin_bp.route(
    "/users/<int:user_id>/reset-password",
    methods=["POST"],
)
@admin_required
def reset_recruiter_password(user_id):
    """Allow an administrator to reset a recruiter's password."""

    user = db.session.get(User, user_id)

    if user is None:
        abort(404)

    if user.role not in ("recruiter", "placement_coordinator"):
        abort(403)

    new_password = request.form.get("new_password", "")

    confirm_password = request.form.get(
        "confirm_password", ""
    )

    if not new_password or not confirm_password:
        flash(
            "Enter and confirm the new password.",
            "danger",
        )
        return redirect(url_for("admin.users"))

    if new_password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("admin.users"))

    try:

        user.password_hash = hash_password(new_password)

        create_audit_log(
            action="Recruiter password reset by admin",
            entity_type="User",
            entity_id=user.id,
            details={
                "email": user.email,
            },
        )

        db.session.commit()

        flash(
            f"Password reset successfully for {user.full_name}.",
            "success",
        )

    except ValueError as error:

        db.session.rollback()
        flash(str(error), "danger")

    except Exception:

        db.session.rollback()

        flash(
            "Unable to reset the password. Please try again.",
            "danger",
        )

    return redirect(url_for("admin.users"))


# =========================================================
# ACTIVATE / DEACTIVATE RECRUITER
# =========================================================

@admin_bp.route(
    "/users/<int:user_id>/toggle-status",
    methods=["POST"],
)
@admin_required
def toggle_user_status(user_id):
    """Activate or deactivate a recruiter account."""

    user = db.session.get(User, user_id)

    if user is None:
        abort(404)

    if user.id == current_user.id:
        flash(
            "You cannot change your own account status.",
            "warning",
        )
        return redirect(url_for("admin.users"))

    if user.role not in ("recruiter", "placement_coordinator"):
        abort(403)

    if user.status == "active":

        user.status = "inactive"
        action = "Recruiter account deactivated"
        message = "Recruiter account deactivated."
        category = "info"

    else:

        user.status = "active"
        action = "Recruiter account activated"
        message = "Recruiter account activated."
        category = "success"

    create_audit_log(
        action=action,
        entity_type="User",
        entity_id=user.id,
        details={
            "email": user.email,
            "new_status": user.status,
        },
    )

    try:

        db.session.commit()
        flash(message, category)

    except Exception:

        db.session.rollback()

        flash(
            "Unable to update recruiter account status.",
            "danger",
        )

    return redirect(url_for("admin.users"))


# =========================================================
# ADMIN VACANCY OVERVIEW
# =========================================================

@admin_bp.route("/vacancies")
@admin_required
def vacancies():
    """Show all vacancies across recruiter accounts."""
    all_vacancies = db.session.scalars(
        select(Vacancy).order_by(Vacancy.created_at.desc())
    ).all()
    return render_template("admin/vacancies.html", vacancies=all_vacancies)


# =========================================================
# ADMIN ACTIVITY LOG
# =========================================================

@admin_bp.route("/activity")
@admin_required
def activity_log():
    """Show recorded system actions with their user and context."""
    entries = db.session.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(500)
    ).all()
    result_filter = request.args.get("result", "all").lower()
    if result_filter in ("success", "failure"):
        entries = [
            entry for entry in entries
            if str((entry.details_json or {}).get("result", "Success")).lower() == result_filter
        ]
    return render_template("admin/activity_log.html", entries=entries, result_filter=result_filter)
