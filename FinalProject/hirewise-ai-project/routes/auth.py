
"""
Authentication routes for HireWise AI.

Handles recruiter registration, password authentication,
email OTP verification, logout, and password changes.
"""

import hashlib
import hmac
import secrets

from datetime import datetime, timedelta
from math import ceil

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from sqlalchemy import select

from extensions import db
from models import AccountRequest, AuditLog, LoginOTP, User

from services.auth_service import (
    hash_password,
    verify_password,
    change_user_password,
)

from services.email_service import send_login_otp_email


auth_bp = Blueprint("auth", __name__)

OTP_VALIDITY_SECONDS = 60
MAX_OTP_ATTEMPTS = 5

PENDING_USER_KEY = "pending_login_user_id"
PENDING_OTP_KEY = "pending_login_otp_id"


# =========================================================
# OTP HELPER FUNCTIONS
# =========================================================

def _clear_pending_login():
    """Clear temporary login verification information."""

    session.pop(PENDING_USER_KEY, None)
    session.pop(PENDING_OTP_KEY, None)


def _generate_otp():
    """Generate a cryptographically secure six-digit OTP."""

    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp(otp):
    """Create a keyed hash of the OTP using Flask SECRET_KEY."""

    secret_key = current_app.config["SECRET_KEY"]

    return hmac.new(
        secret_key.encode("utf-8"),
        otp.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _verify_otp_hash(stored_hash, entered_otp):
    """Compare OTP hashes securely."""

    if not stored_hash or not entered_otp:
        return False

    entered_hash = _hash_otp(entered_otp)

    return hmac.compare_digest(
        stored_hash,
        entered_hash,
    )


def _create_and_send_otp(user):
    """
    Invalidate previous OTPs, create a new OTP,
    and send it to the user's registered email.
    """

    now = datetime.utcnow()

    previous_otps = db.session.scalars(
        select(LoginOTP).where(
            LoginOTP.user_id == user.id,
            LoginOTP.is_used.is_(False),
        )
    ).all()

    for previous_otp in previous_otps:
        previous_otp.is_used = True

    otp = _generate_otp()

    otp_record = LoginOTP(
        user_id=user.id,
        otp_hash=_hash_otp(otp),
        expires_at=now + timedelta(
            seconds=OTP_VALIDITY_SECONDS
        ),
        attempts=0,
        is_used=False,
    )

    db.session.add(otp_record)
    db.session.flush()

    # Send the OTP before committing the new record.
    send_login_otp_email(user.email, otp)

    db.session.add(AuditLog(
        user_id=user.id,
        action="LOGIN_OTP_SENT",
        entity_type="Authentication",
        entity_id=user.id,
        details_json={
            "result": "Success",
            "reason": "Login OTP sent to registered email",
        },
    ))

    db.session.commit()

    return otp_record


def _render_otp_page():
    """Render the OTP page with the remaining expiry time."""

    otp_id = session.get(PENDING_OTP_KEY)

    otp_record = db.session.get(LoginOTP, otp_id)

    if not otp_record or otp_record.is_used:
        _clear_pending_login()
        flash("Your verification session is invalid. Please log in again.", "warning")
        return redirect(url_for("auth.login"))

    remaining_seconds = max(
        0,
        ceil(
            (otp_record.expires_at - datetime.utcnow()).total_seconds()
        ),
    )

    return render_template(
        "auth/verify_otp.html",
        expires_in_seconds=remaining_seconds,
        max_attempts=MAX_OTP_ATTEMPTS,
        attempts_remaining=max(
            0,
            MAX_OTP_ATTEMPTS - otp_record.attempts,
        ),
    )


# =========================================================
# LOGIN
# =========================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate credentials and begin email OTP verification."""

    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))

        return redirect(url_for("recruiter.dashboard"))

    if request.method == "POST":

        _clear_pending_login()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get("password", "")

        if not email or not password:
            flash("Enter your email and password.", "danger")
            return render_template("auth/login.html")

        user = db.session.scalar(
            select(User).where(User.email == email)
        )

        if user is None or not verify_password(
            user.password_hash if user else None,
            password,
        ):
            db.session.add(AuditLog(
                user_id=user.id if user else None,
                action="LOGIN_FAILED",
                entity_type="Authentication",
                entity_id=user.id if user else None,
                details_json={
                    "result": "Failure",
                    "reason": "Invalid email or password",
                    "email": email,
                },
            ))

            db.session.commit()

            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html")

        if user.status != "active":
            db.session.add(AuditLog(
                user_id=user.id,
                action="LOGIN_FAILED",
                entity_type="Authentication",
                entity_id=user.id,
                details_json={
                    "result": "Failure",
                    "reason": "Account is inactive",
                },
            ))

            db.session.commit()

            flash(
                "Your account is inactive. Contact the administrator.",
                "warning",
            )

            return render_template("auth/login.html")

        if user.role not in (
            "admin",
            "recruiter",
            "placement_coordinator",
        ):
            db.session.add(AuditLog(
                user_id=user.id,
                action="LOGIN_FAILED",
                entity_type="Authentication",
                entity_id=user.id,
                details_json={
                    "result": "Failure",
                    "reason": "Role is not permitted",
                },
            ))

            db.session.commit()

            flash("This account does not have access.", "danger")
            return render_template("auth/login.html")

        try:
            otp_record = _create_and_send_otp(user)

            session[PENDING_USER_KEY] = user.id
            session[PENDING_OTP_KEY] = otp_record.id

            flash(
                "A verification code has been sent to your registered email.",
                "success",
            )

            return redirect(url_for("auth.verify_otp"))

        except Exception:
            db.session.rollback()
            _clear_pending_login()

            current_app.logger.exception(
                "Unable to send login OTP."
            )

            flash(
                "Unable to send the verification code. Please try again.",
                "danger",
            )

            return render_template("auth/login.html")

    return render_template("auth/login.html")


# =========================================================
# VERIFY LOGIN OTP
# =========================================================

@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    """Verify the email OTP before creating an authenticated session."""

    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))

        return redirect(url_for("recruiter.dashboard"))

    user_id = session.get(PENDING_USER_KEY)
    otp_id = session.get(PENDING_OTP_KEY)

    if not user_id or not otp_id:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    user = db.session.get(User, user_id)
    otp_record = db.session.get(LoginOTP, otp_id)

    if (
        not user
        or not otp_record
        or otp_record.user_id != user.id
        or otp_record.is_used
    ):
        _clear_pending_login()
        flash("Your verification session is invalid. Please log in again.", "warning")
        return redirect(url_for("auth.login"))

    if user.status != "active" or user.role not in (
        "admin",
        "recruiter",
        "placement_coordinator",
    ):
        otp_record.is_used = True
        db.session.commit()

        _clear_pending_login()

        flash("Your account is no longer permitted to log in.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":

        entered_otp = request.form.get(
            "otp", ""
        ).strip()

        if not entered_otp.isdigit() or len(entered_otp) != 6:
            flash("Enter a valid six-digit OTP.", "danger")
            return _render_otp_page()

        if datetime.utcnow() >= otp_record.expires_at:
            otp_record.is_used = True
            db.session.commit()

            flash(
                "Your OTP has expired. You can now request a new one.",
                "warning",
            )

            return _render_otp_page()

        if otp_record.attempts >= MAX_OTP_ATTEMPTS:
            otp_record.is_used = True
            db.session.commit()

            _clear_pending_login()

            flash(
                "Maximum OTP attempts exceeded. Please log in again.",
                "danger",
            )

            return redirect(url_for("auth.login"))

        if not _verify_otp_hash(
            otp_record.otp_hash,
            entered_otp,
        ):
            otp_record.attempts += 1

            db.session.add(AuditLog(
                user_id=user.id,
                action="LOGIN_OTP_FAILED",
                entity_type="Authentication",
                entity_id=user.id,
                details_json={
                    "result": "Failure",
                    "reason": "Incorrect OTP",
                    "attempts": otp_record.attempts,
                },
            ))

            if otp_record.attempts >= MAX_OTP_ATTEMPTS:
                otp_record.is_used = True
                db.session.commit()

                _clear_pending_login()

                flash(
                    "Maximum OTP attempts exceeded. Please log in again.",
                    "danger",
                )

                return redirect(url_for("auth.login"))

            db.session.commit()

            flash(
                "Incorrect OTP. Please try again.",
                "danger",
            )

            return _render_otp_page()

        # OTP is correct. Mark it as used before login.
        otp_record.is_used = True

        db.session.add(AuditLog(
            user_id=user.id,
            action="LOGIN_SUCCESS",
            entity_type="Authentication",
            entity_id=user.id,
            details_json={
                "result": "Success",
                "reason": "Password and email OTP verified",
            },
        ))

        db.session.commit()

        _clear_pending_login()

        # Create the authenticated session only after OTP verification.
        login_user(user)

        flash("Login successful.", "success")

        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))

        return redirect(url_for("recruiter.dashboard"))

    return _render_otp_page()


# =========================================================
# RESEND LOGIN OTP
# =========================================================

@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    """Resend OTP only after the previous OTP has expired."""

    if current_user.is_authenticated:
        return redirect(url_for("index"))

    user_id = session.get(PENDING_USER_KEY)
    otp_id = session.get(PENDING_OTP_KEY)

    if not user_id or not otp_id:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    user = db.session.get(User, user_id)
    old_otp = db.session.get(LoginOTP, otp_id)

    if (
        not user
        or not old_otp
        or old_otp.user_id != user.id
        or old_otp.is_used
    ):
        _clear_pending_login()
        flash("Your verification session is invalid. Please log in again.", "warning")
        return redirect(url_for("auth.login"))

    if user.status != "active":
        _clear_pending_login()
        flash("Your account is inactive.", "danger")
        return redirect(url_for("auth.login"))

    # Do not allow resend before the 60-second expiry.
    if datetime.utcnow() < old_otp.expires_at:
        flash(
            "You can resend the OTP only after 60 seconds.",
            "warning",
        )

        return redirect(url_for("auth.verify_otp"))

    try:
        old_otp.is_used = True

        new_otp = _create_and_send_otp(user)

        session[PENDING_OTP_KEY] = new_otp.id

        flash(
            "A new verification code has been sent to your email.",
            "success",
        )

        return redirect(url_for("auth.verify_otp"))

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Unable to resend login OTP."
        )

        flash(
            "Unable to resend the verification code. Please try again.",
            "danger",
        )

        return redirect(url_for("auth.verify_otp"))


# =========================================================
# RECRUITER REGISTRATION
# =========================================================

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Submit a recruiter registration request.

    Recruiters cannot access the application until an
    administrator approves their registration.
    """

    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("recruiter.dashboard"))

    if request.method == "POST":

        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        requested_role = request.form.get("role", "recruiter").strip().lower()

        if requested_role not in ("recruiter", "placement_coordinator"):
            requested_role = "recruiter"

        if not all([
            full_name,
            email,
            password,
            confirm_password,
        ]):
            flash("Please fill in all required fields.", "danger")
            return render_template("auth/register.html")

        if len(full_name) > 100 or len(email) > 120:
            flash("Name or email exceeds the allowed length.", "danger")
            return render_template("auth/register.html")

        if "@" not in email or "." not in email.split("@")[-1]:
            flash("Please enter a valid email address.", "danger")
            return render_template("auth/register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("auth/register.html")

        existing_user = db.session.scalar(
            select(User).where(User.email == email)
        )

        if existing_user:
            flash(
                "An account with this email already exists.",
                "warning",
            )
            return render_template("auth/register.html")

        existing_request = db.session.scalar(
            select(AccountRequest).where(
                AccountRequest.email == email
            )
        )

        if existing_request:

            if existing_request.status == "pending":
                flash(
                    "Your registration request is already waiting for approval.",
                    "info",
                )
                return redirect(url_for("auth.login"))

            if existing_request.status == "approved":
                flash(
                    "This email has already been approved. Please log in.",
                    "info",
                )
                return redirect(url_for("auth.login"))

        try:
            password_hash = hash_password(password)

            if existing_request:
                existing_request.full_name = full_name
                existing_request.password_hash = password_hash
                existing_request.requested_role = requested_role
                existing_request.status = "pending"
                existing_request.reviewed_by = None

            else:
                account_request = AccountRequest(
                    full_name=full_name,
                    email=email,
                    password_hash=password_hash,
                    requested_role=requested_role,
                    status="pending",
                )

                db.session.add(account_request)

            db.session.commit()

            flash(
                f"{requested_role.replace('_', ' ').title()} registration submitted successfully. "
                "Please wait for administrator approval.",
                "success",
            )

            return redirect(url_for("auth.login"))

        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")

        except Exception:
            db.session.rollback()
            flash(
                "Unable to submit your registration. Please try again.",
                "danger",
            )

    return render_template("auth/register.html")


# =========================================================
# LOGOUT
# =========================================================

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """Log out the currently authenticated user."""

    logout_user()

    flash("You have been logged out.", "success")

    return redirect(url_for("auth.login"))


# =========================================================
# CHANGE PASSWORD
# =========================================================

@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Allow an authenticated user to change their password."""

    if request.method == "POST":

        current_password = request.form.get(
            "current_password",
            "",
        )

        new_password = request.form.get(
            "new_password",
            "",
        )

        confirm_password = request.form.get(
            "confirm_password",
            "",
        )

        if not all([
            current_password,
            new_password,
            confirm_password,
        ]):
            flash("Please fill in all password fields.", "danger")
            return render_template("auth/change_password.html")

        if new_password != confirm_password:
            flash("New passwords do not match.", "danger")
            return render_template("auth/change_password.html")

        try:
            change_user_password(
                current_user,
                current_password,
                new_password,
            )

            db.session.commit()

            flash(
                "Your password has been changed successfully.",
                "success",
            )

            if current_user.role == "admin":
                return redirect(url_for("admin.dashboard"))

            return redirect(url_for("recruiter.dashboard"))

        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")

        except Exception:
            db.session.rollback()
            flash(
                "Unable to change your password. Please try again.",
                "danger",
            )

    return render_template("auth/change_password.html")


# =========================================================
# USER PROFILE
# =========================================================

@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """View and update the signed-in user's basic profile."""

    if request.method == "POST":

        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()

        if not full_name or len(full_name) > 100:
            flash(
                "Enter a valid name (maximum 100 characters).",
                "danger",
            )
            return render_template("auth/profile.html")

        if len(email) > 120 or "@" not in email or "." not in email.split("@")[-1]:
            flash("Enter a valid email address.", "danger")
            return render_template("auth/profile.html")

        existing = db.session.scalar(
            select(User).where(
                User.email == email,
                User.id != current_user.id,
            )
        )

        if existing:
            flash(
                "That email address is already used by another account.",
                "warning",
            )
            return render_template("auth/profile.html")

        try:
            current_user.full_name = full_name
            current_user.email = email

            db.session.add(AuditLog(
                user_id=current_user.id,
                action="PROFILE_UPDATED",
                entity_type="User",
                entity_id=current_user.id,
                details_json={"email": email},
            ))

            db.session.commit()

            flash("Your profile was updated.", "success")

        except Exception:
            db.session.rollback()
            flash(
                "Unable to update your profile. Please try again.",
                "danger",
            )

    return render_template("auth/profile.html")
