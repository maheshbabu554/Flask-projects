
"""
app.py - Health Insurance Claims Processing Simulator

Educational simulation only. No real insurance decisions or payments.

Includes:
- Mandatory username and password login
- Werkzeug password hashing and verification
- Initial passwords for four existing demo accounts
- Server-side authentication and active-account validation
- Role-based access control
- Existing claim workflow, eligibility checks, and settlements
"""

import os
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify,
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import (
    db,
    init_db,
    User, Hospital, Plan, Policy, Member, Claim, ClaimDocument, ClaimHistory, ClaimApprovalHistory, Settlement,
)

# -------------------------------------------------------------------------
# Application Configuration
# -------------------------------------------------------------------------

load_dotenv()

app = Flask(__name__)

app.secret_key = (
    os.environ.get("FLASK_SECRET_KEY")
    or os.environ.get("SECRET_KEY")
)

if not app.secret_key:
    raise RuntimeError(
        "Set SECRET_KEY or FLASK_SECRET_KEY in your .env file."
    )

# Initialize the existing database.
init_db(app)

# Role constants
ROLE_POLICYHOLDER = "policyholder"
ROLE_HOSPITAL = "hospital"
ROLE_CLAIMS_OFFICER = "claims_officer"
ROLE_ADMIN = "admin"

ALL_ROLES = [
    ROLE_POLICYHOLDER,
    ROLE_HOSPITAL,
    ROLE_CLAIMS_OFFICER,
    ROLE_ADMIN,
]

# -------------------------------------------------------------------------
# Initial Passwords for Existing Classroom Demo Accounts
# -------------------------------------------------------------------------

def initialize_demo_passwords():
    """
    Initialize passwords for the four specified demo accounts.

    Required format: username + complete user_id.

    Existing password hashes are not overwritten. Passwords are stored
    as Werkzeug hashes, never as plain text.

    This function only initializes accounts whose password_hash is empty.
    """
    demo_usernames = (
        "aasha", "city_hospital", "officer_meera", "admin_demo",
    )

    with app.app_context():
        try:
            for username in demo_usernames:
                user = User.query.filter_by(
                    username=username
                ).first()

                if user is None:
                    app.logger.warning(
                        "Demo account '%s' was not found.",
                        username,
                    )
                    continue

                if not user.is_active:
                    app.logger.warning(
                        "Demo account '%s' is inactive.",
                        username,
                    )
                    continue

                if not user.password_hash:
                    initial_password = (
                        f"{user.username}{user.user_id}"
                    )

                    user.password_hash = generate_password_hash(
                        initial_password
                    )

            db.session.commit()

        except Exception:
            db.session.rollback()
            app.logger.exception(
                "Unable to initialize demo account passwords."
            )
            raise

initialize_demo_passwords()

# -------------------------------------------------------------------------
# Template Filters and Context
# -------------------------------------------------------------------------

@app.template_filter("currency")
@app.template_filter("format_inr")
def format_currency(value):
    """Format numeric values as Indian Rupees."""
    if value is None:
        return "—"

    try:
        amount = Decimal(str(value))
        return f"₹ {amount:,.2f}"
    except Exception:
        return f"₹ {value}"


@app.template_filter("date_format")
def format_date(value, fmt="%d %b %Y"):
    """Format dates for display in templates."""
    if not value:
        return "—"

    if isinstance(value, (datetime, date)):
        return value.strftime(fmt)

    try:
        parsed_date = datetime.strptime(
            str(value).strip()[:10],
            "%Y-%m-%d",
        )
        return parsed_date.strftime(fmt)
    except Exception:
        return str(value)


@app.context_processor
def inject_global_context():
    """Provide the current user and role constants to templates."""
    current_user = None
    user_id = session.get("user_id")

    if user_id:
        current_user = db.session.get(User, user_id)

        # Do not retain sessions for deleted or inactive accounts.
        if current_user is None or not current_user.is_active:
            session.clear()
            current_user = None

    return {
        "current_user": current_user,

        # Disable quick role switching in templates.
        "demo_mode": False,
        "demo_users": {},

        "ROLE_POLICYHOLDER": ROLE_POLICYHOLDER,
        "ROLE_HOSPITAL": ROLE_HOSPITAL,
        "ROLE_CLAIMS_OFFICER": ROLE_CLAIMS_OFFICER,
        "ROLE_ADMIN": ROLE_ADMIN,
        "today_date": date.today(),
    }


# -------------------------------------------------------------------------
# Authentication and Authorization
# -------------------------------------------------------------------------

def get_logged_in_user():
    """Return the active logged-in user, or None."""
    user_id = session.get("user_id")

    if user_id is None:
        return None

    user = db.session.get(User, user_id)

    if user is None or not user.is_active:
        session.clear()
        return None

    return user


def login_required(f):
    """Require a valid, active logged-in account."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        """Check authentication before executing the route."""
        user = get_logged_in_user()

        if user is None:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function


def roles_required(*allowed_roles):
    """Restrict a route to the specified roles."""

    def decorator(f):
        """Create a decorator that checks permitted roles."""

        @wraps(f)
        def decorated_function(*args, **kwargs):
            """Check authentication and role authorization."""
            user = get_logged_in_user()

            if user is None:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))

            if user.role not in allowed_roles:
                abort(403)

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def verify_claim_access(claim, user):
    """Check whether a user may access a particular claim."""
    if not user or not claim:
        return False

    if user.role in (ROLE_ADMIN, ROLE_CLAIMS_OFFICER):
        return True

    if user.role == ROLE_POLICYHOLDER:
        return (
            claim.policy is not None
            and claim.policy.holder_user_id == user.user_id
        )

    if user.role == ROLE_HOSPITAL:
        return claim.hospital_id == user.hospital_id

    return False


# -------------------------------------------------------------------------
# Business Logic and Financial Calculations
# -------------------------------------------------------------------------

def calculate_payout(plan, eligible_amount):
    """
    Calculate the simulated payout.

    Payout = (Eligible Amount - Deductible Applied)
             * (1 - Copay Percentage / 100)
    """
    if eligible_amount is None or eligible_amount <= Decimal("0.00"):
        return {
            "eligible_amount": Decimal("0.00"),
            "deductible_applied": Decimal("0.00"),
            "after_deductible": Decimal("0.00"),
            "copay_percent": Decimal(str(plan.copay_percent)),
            "copay_amount": Decimal("0.00"),
            "final_payout": Decimal("0.00"),
        }

    eligible = Decimal(str(eligible_amount))
    deductible_limit = Decimal(str(plan.deductible_inr))

    deductible_applied = min(eligible, deductible_limit)
    after_deductible = eligible - deductible_applied

    copay_pct = Decimal(str(plan.copay_percent))
    copay_multiplier = copay_pct / Decimal("100.00")

    copay_amount = (
        after_deductible * copay_multiplier
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    final_payout = (
        after_deductible - copay_amount
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    final_payout = max(Decimal("0.00"), final_payout)

    return {
        "eligible_amount": eligible,
        "deductible_applied": deductible_applied,
        "after_deductible": after_deductible,
        "copay_percent": copay_pct,
        "copay_amount": copay_amount,
        "final_payout": final_payout,
    }


def get_policy_financial_summary(policy):
    """Calculate annual coverage used and remaining."""
    annual_limit = Decimal(str(policy.plan.annual_limit_inr))

    paid_claims = Claim.query.filter_by(
        policy_id=policy.policy_id,
        status="paid",
    ).all()

    total_paid = Decimal("0.00")

    for claim in paid_claims:
        if claim.settlement:
            total_paid += Decimal(
                str(claim.settlement.amount_inr)
            )

    remaining_cover = max(
        Decimal("0.00"),
        annual_limit - total_paid,
    )

    return {
        "annual_limit": annual_limit,
        "total_paid": total_paid,
        "remaining_cover": remaining_cover,
    }


def get_remaining_cover(policy):
    """Return the annual limit less settled amounts for this policy."""
    return get_policy_financial_summary(policy)["remaining_cover"]


def perform_eligibility_checks(claim):
    """Run the simulator's claim eligibility checks."""
    checks = []

    policy = claim.policy
    plan = policy.plan
    hospital = claim.hospital
    member = claim.member

    # 1. Policy status
    is_active = policy.status == "active"

    checks.append({
        "rule": "Policy Status",
        "passed": is_active,
        "details": (
            f"Policy #{policy.policy_id} is marked "
            f"'{policy.status}'."
        ),
    })

    # 2. Policy coverage period
    date_in_window = bool(
        claim.admission_date
        and policy.start_date
        and policy.end_date
        and policy.start_date
        <= claim.admission_date
        <= policy.end_date
    )

    checks.append({
        "rule": "Policy Coverage Period",
        "passed": date_in_window,
        "details": (
            f"Admission date ({format_date(claim.admission_date)}) "
            f"falls within policy window "
            f"({format_date(policy.start_date)} to "
            f"{format_date(policy.end_date)})."
            if date_in_window
            else (
                "Admission date is outside policy window "
                f"({format_date(policy.start_date)} to "
                f"{format_date(policy.end_date)})."
            )
        ),
    })

    # 3. Member belongs to policy
    member_valid = (
        member is not None
        and member.policy_id == policy.policy_id
    )

    checks.append({
        "rule": "Member Enrollment",
        "passed": member_valid,
        "details": (
            f"Member '{member.display_name}' "
            f"({member.relationship}) is registered on "
            f"Policy #{policy.policy_id}."
            if member_valid
            else "The selected member does not belong to this policy."
        ),
    })

    # 4. Treatment type
    treatment_covered = plan.covers_treatment(
        claim.treatment_type
    )

    checks.append({
        "rule": "Treatment Coverage",
        "passed": treatment_covered,
        "details": (
            f"Plan '{plan.plan_name}' covers "
            f"[{plan.covered_treatment_types}]. "
            f"Claim treatment: '{claim.treatment_type}'."
        ),
    })

    # 5. Network hospital requirement for cashless claims
    if claim.claim_type == "cashless":
        network_ok = (
            hospital is not None and hospital.is_network()
        )

        checks.append({
            "rule": "Hospital Network Status",
            "passed": network_ok,
            "details": (
                "Cashless claim requires an empanelled hospital. "
                f"Network status: "
                f"{'Empanelled' if network_ok else 'Non-network'}."
            ),
        })
    else:
        checks.append({
            "rule": "Hospital Network Status",
            "passed": True,
            "details": (
                "Reimbursement claims may be submitted for "
                "network or non-network hospitals."
            ),
        })

    # 6. Future admission date
    simulation_baseline = date(2026, 10, 16)

    not_future_date = bool(
        claim.admission_date
        and claim.admission_date <= simulation_baseline
        and claim.admission_date <= date.today()
    )

    checks.append({
        "rule": "Admission Date Timing",
        "passed": not_future_date,
        "details": (
            f"Admission date {format_date(claim.admission_date)} "
            "cannot be in the future."
            if not not_future_date
            else (
                f"Admission date "
                f"({format_date(claim.admission_date)}) is valid."
            )
        ),
    })

    # 7. Required documents
    doc_types = {
        doc.document_type: doc.checklist_status
        for doc in claim.documents
    }

    bill_received = (
        doc_types.get("hospital_bill") == "received"
    )
    summary_received = (
        doc_types.get("discharge_summary") == "received"
    )

    docs_complete = bill_received and summary_received

    checks.append({
        "rule": "Document Checklist",
        "passed": docs_complete,
        "details": (
            f"Hospital Bill: "
            f"{doc_types.get('hospital_bill', 'missing')}, "
            f"Discharge Summary: "
            f"{doc_types.get('discharge_summary', 'missing')}."
        ),
    })

    # 8. Duplicate claim warning
    possible_duplicates = Claim.query.filter(
        Claim.claim_id != claim.claim_id,
        Claim.member_id == claim.member_id,
        Claim.hospital_id == claim.hospital_id,
        Claim.admission_date == claim.admission_date,
        Claim.requested_amount_inr == claim.requested_amount_inr,
    ).all()

    is_duplicate = bool(possible_duplicates)
    duplicate_ids = [
        str(item.claim_id) for item in possible_duplicates
    ]

    checks.append({
        "rule": "Duplicate Claim Detection",
        "passed": not is_duplicate,
        "is_warning_only": True,
        "details": (
            "WARNING: Matches existing claim(s) #"
            + ", #".join(duplicate_ids)
            + "."
            if is_duplicate
            else "No duplicate claim patterns detected."
        ),
    })

    # 9. Positive requested amount
    amount_valid = (
        claim.requested_amount_inr is not None
        and claim.requested_amount_inr > 0
    )

    checks.append({
        "rule": "Requested Amount Validity",
        "passed": amount_valid,
        "details": (
            f"Requested amount is "
            f"{format_currency(claim.requested_amount_inr)}."
        ),
    })

    all_passed = all(
        item["passed"]
        for item in checks
        if not item.get("is_warning_only", False)
    )

    return {
        "checks": checks,
        "all_passed": all_passed,
        "has_duplicate_warning": is_duplicate,
        "duplicate_ids": duplicate_ids,
    }


def add_claim_history(
    claim, from_status, to_status, actor_user, note=None,
):
    """Append an audit entry to the claim history."""
    next_seq = 1

    if claim.history:
        next_seq = (
            max(item.sequence_no for item in claim.history) + 1
        )

    history = ClaimHistory(
        claim_id=claim.claim_id,
        sequence_no=next_seq,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=(
            actor_user.user_id if actor_user else None
        ),
        note=note or (
            f"Status changed from "
            f"{from_status or 'new'} to {to_status}"
        ),
        event_date=date.today(),
    )

    db.session.add(history)


# -------------------------------------------------------------------------
# Authentication Routes
# -------------------------------------------------------------------------

@app.route("/")
def index():
    """Redirect to dashboard or login."""
    if get_logged_in_user():
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate with a mandatory username and password."""
    if get_logged_in_user():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Server-side validation: both fields are mandatory.
        if not username or not password:
            flash(
                "Username and password are required.",
                "danger",
            )
            return render_template("login.html"), 400

        user = User.query.filter_by(
            username=username
        ).first()

        # Display a specific message when the username is invalid.
        if user is None:
            flash("User name invalid or wrong.", "danger")
            return render_template("login.html"), 401

        # Validate account status.
        if not user.is_active:
            flash("This account is inactive.", "danger")
            return render_template("login.html"), 403

        # Display a specific message when the password is incorrect.
        if (
            not user.password_hash
            or not check_password_hash(
                user.password_hash,
                password,
            )
        ):
            flash("Password incorrect.", "danger")
            return render_template("login.html"), 401

        # Prevent session fixation and establish the authenticated session.
        session.clear()
        session["user_id"] = user.user_id

        flash(
            f"Welcome back, {user.display_name}! "
            f"Logged in as "
            f"{user.role.replace('_', ' ').title()}.",
            "success",
        )

        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Clear the authenticated session."""
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))


# -------------------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    """Display role-specific statistics and pending actions."""
    user = get_logged_in_user()

    query = Claim.query

    if user.role == ROLE_POLICYHOLDER:
        policy_ids = [
            policy.policy_id for policy in user.policies
        ]
        query = query.filter(
            Claim.policy_id.in_(policy_ids)
        )
    elif user.role == ROLE_HOSPITAL:
        query = query.filter_by(
            hospital_id=user.hospital_id
        )

    all_claims = query.all()

    stats = {
        "total": len(all_claims),
        "draft": sum(c.status == "draft" for c in all_claims),
        "submitted": sum(c.status == "submitted" for c in all_claims),
        "in_review": sum(c.status == "in_review" for c in all_claims),
        "more_info": sum(c.status == "more_info" for c in all_claims),
        "approved": sum(c.status == "approved" for c in all_claims),
        "rejected": sum(c.status == "rejected" for c in all_claims),
        "paid": sum(c.status == "paid" for c in all_claims),
    }

    recent_claims = query.order_by(
        Claim.claim_id.desc()
    ).limit(6).all()

    pending_actions = []

    if user.role == ROLE_POLICYHOLDER:
        for claim in all_claims:
            if claim.status == "draft":
                pending_actions.append({
                    "claim": claim,
                    "action": "Submit Draft",
                    "desc": "Draft claim ready for review",
                })
            elif claim.status == "more_info":
                pending_actions.append({
                    "claim": claim,
                    "action": "Provide Info",
                    "desc": "Officer requested documents/info",
                })

    elif user.role == ROLE_HOSPITAL:
        for claim in all_claims:
            if claim.status == "draft":
                pending_actions.append({
                    "claim": claim,
                    "action": "Submit Cashless",
                    "desc": "Cashless request awaiting submission",
                })
            elif claim.status == "more_info":
                pending_actions.append({
                    "claim": claim,
                    "action": "Upload Missing Doc",
                    "desc": "Missing hospital records requested",
                })

    elif user.role == ROLE_CLAIMS_OFFICER:
        for claim in all_claims:
            if claim.status == "submitted":
                pending_actions.append({
                    "claim": claim,
                    "action": "Review & Assign",
                    "desc": "Submitted claim awaiting adjudication",
                })
            elif (
                claim.status == "in_review"
                and claim.officer_user_id == user.user_id
            ):
                pending_actions.append({
                    "claim": claim,
                    "action": "Complete Assessment",
                    "desc": "Assigned to you for assessment",
                })

    elif user.role == ROLE_ADMIN:
        for claim in all_claims:
            if claim.status == "approved":
                pending_actions.append({
                    "claim": claim,
                    "action": "Record Settlement",
                    "desc": "Approved claim ready for simulated settlement",
                })

    return render_template(
        "dashboard.html",
        user=user,
        stats=stats,
        recent_claims=recent_claims,
        pending_actions=pending_actions[:6],
    )


# -------------------------------------------------------------------------
# Policies
# -------------------------------------------------------------------------

@app.route("/policies")
@login_required
def policies():
    """Display policies and financial summaries."""
    user = get_logged_in_user()

    if user.role == ROLE_POLICYHOLDER:
        policy_list = Policy.query.filter_by(
            holder_user_id=user.user_id
        ).all()
    else:
        policy_list = Policy.query.all()

    policy_data = []

    for policy in policy_list:
        policy_data.append({
            "policy": policy,
            "summary": get_policy_financial_summary(policy),
            "members": policy.members,
        })

    return render_template(
        "policies.html",
        policy_data=policy_data,
        user=user,
    )


# -------------------------------------------------------------------------
# Claims List
# -------------------------------------------------------------------------

@app.route("/claims")
@login_required
def claims():
    """Display claims with search and filters."""
    user = get_logged_in_user()

    status_filter = request.args.get(
        "status", ""
    ).strip().lower()

    type_filter = request.args.get(
        "type", ""
    ).strip().lower()

    search_q = request.args.get("q", "").strip()

    query = Claim.query

    if user.role == ROLE_POLICYHOLDER:
        policy_ids = [
            policy.policy_id for policy in user.policies
        ]
        query = query.filter(
            Claim.policy_id.in_(policy_ids)
        )
    elif user.role == ROLE_HOSPITAL:
        query = query.filter_by(
            hospital_id=user.hospital_id
        )

    if status_filter:
        query = query.filter_by(status=status_filter)

    if type_filter:
        query = query.filter_by(claim_type=type_filter)

    if search_q:
        query = query.join(Member).filter(
            db.or_(
                Claim.claim_id.like(f"%{search_q}%"),
                Member.display_name.ilike(f"%{search_q}%"),
            )
        )

    claims_list = query.order_by(
        Claim.claim_id.desc()
    ).all()

    return render_template(
        "claims.html",
        claims=claims_list,
        current_status=status_filter,
        current_type=type_filter,
        search_q=search_q,
        user=user,
    )


# -------------------------------------------------------------------------
# Claim Details
# -------------------------------------------------------------------------

@app.route("/claims/<int:claim_id>")
@login_required
def claim_detail(claim_id):
    """Display a claim, eligibility checks, and audit history."""
    user = get_logged_in_user()
    claim = Claim.query.get_or_404(claim_id)

    if not verify_claim_access(claim, user):
        abort(403)

    eligibility = perform_eligibility_checks(claim)
    policy_summary = get_policy_financial_summary(claim.policy)

    test_amount = (
        claim.eligible_amount_inr
        if claim.eligible_amount_inr is not None
        else claim.requested_amount_inr
    )

    payout_breakdown = calculate_payout(
        claim.policy.plan,
        test_amount,
    )

    return render_template(
        "claim_detail.html",
        claim=claim,
        user=user,
        eligibility=eligibility,
        policy_summary=policy_summary,
        payout=payout_breakdown,
    )


@app.route("/api/hospital/policy-search")
@login_required
@roles_required(ROLE_HOSPITAL)
def hospital_policy_search():
    """Search active policies and return policy-linked covered members to hospital staff."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"results": []})

    # There is no hospital-policy mapping in the supplied schema. This endpoint only
    # exposes active policy/member matches; every submitted claim is separately checked
    # against the logged-in hospital's hospital_id in claim_new().
    policies = Policy.query.filter_by(status="active").all()
    query_lower = query.lower()
    results = []
    for policy in policies:
        holder_name = policy.holder.display_name if policy.holder else ""
        id_match = str(policy.policy_id).startswith(query)
        holder_match = query_lower in holder_name.lower()
        members = []
        for member in policy.members:
            if id_match or holder_match or query_lower in member.display_name.lower():
                members.append({
                    "member_id": member.member_id,
                    "display_name": member.display_name,
                    "relationship": member.relationship,
                })
        if id_match or holder_match or members:
            results.append({
                "policy_id": policy.policy_id,
                "plan_name": policy.plan.plan_name,
                "holder_name": holder_name,
                "start_date": policy.start_date.isoformat(),
                "end_date": policy.end_date.isoformat(),
                "remaining_cover": str(get_remaining_cover(policy)),
                "members": members,
            })
    return jsonify({"results": results[:10]})


# -------------------------------------------------------------------------
# Create Claims
# -------------------------------------------------------------------------

@app.route("/claims/new", methods=["GET", "POST"])
@login_required
def claim_new():
    """Create a reimbursement or cashless claim."""
    user = get_logged_in_user()

    if user.role not in (
        ROLE_POLICYHOLDER,
        ROLE_HOSPITAL,
    ):
        flash(
            "Only policyholders and hospital desks can create claims.",
            "danger",
        )
        return redirect(url_for("claims"))

    if request.method == "POST":
        policy_id = request.form.get("policy_id", type=int)
        member_id = request.form.get("member_id", type=int)
        hospital_id = request.form.get("hospital_id", type=int)

        treatment_type = request.form.get(
            "treatment_type", ""
        ).strip().lower()

        admission_date_str = request.form.get(
            "admission_date", ""
        ).strip()

        discharge_date_str = request.form.get(
            "discharge_date", ""
        ).strip()

        amount_str = request.form.get(
            "requested_amount", ""
        ).strip()

        policy = db.session.get(Policy, policy_id) if policy_id else None
        member = db.session.get(Member, member_id) if member_id else None
        hospital = (
            db.session.get(Hospital, hospital_id)
            if hospital_id else None
        )

        errors = []

        if not policy:
            errors.append("Please select a valid policy.")
        elif policy.status != "active":
            errors.append("The selected policy is not active.")
        elif (
            user.role == ROLE_POLICYHOLDER
            and policy.holder_user_id != user.user_id
        ):
            errors.append(
                "You can only create claims for your own policies."
            )

        if (
            not member
            or not policy
            or member.policy_id != policy.policy_id
        ):
            errors.append(
                "Selected member does not belong to the selected policy."
            )

        if not hospital:
            errors.append("Please select a valid hospital.")
        elif (
            user.role == ROLE_HOSPITAL
            and hospital.hospital_id != user.hospital_id
        ):
            errors.append(
                "Hospital users can only file claims for their own hospital."
            )

        if treatment_type not in ("inpatient", "daycare"):
            errors.append("Please select a valid treatment type.")

        admission_date = None
        discharge_date = None

        try:
            admission_date = datetime.strptime(
                admission_date_str, "%Y-%m-%d"
            ).date()

            discharge_date = datetime.strptime(
                discharge_date_str, "%Y-%m-%d"
            ).date()

            if discharge_date < admission_date:
                errors.append(
                    "Discharge date cannot be before admission date."
                )
        except ValueError:
            errors.append("Invalid admission or discharge date.")

        try:
            requested_amount = Decimal(amount_str)

            if (
                not requested_amount.is_finite()
                or requested_amount <= 0
            ):
                errors.append(
                    "Requested amount must be greater than zero."
                )
        except Exception:
            requested_amount = None
            errors.append("Enter a valid requested amount.")

        if requested_amount is not None and requested_amount.is_finite() and requested_amount > 0 and policy:
            remaining_cover = get_remaining_cover(policy)
            if requested_amount.quantize(Decimal("0.01")) > remaining_cover:
                errors.append(
                    f"Requested amount ₹{requested_amount:,.2f} exceeds remaining eligible policy coverage "
                    f"of ₹{remaining_cover:,.2f}. Claim submission was blocked."
                )

        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            claim_type = (
                "reimbursement"
                if user.role == ROLE_POLICYHOLDER
                else "cashless"
            )

            max_id = (
                db.session.query(
                    db.func.max(Claim.claim_id)
                ).scalar()
                or 1000
            )

            new_claim_id = max_id + 1

            new_claim = Claim(
                claim_id=new_claim_id,
                policy_id=policy.policy_id,
                member_id=member.member_id,
                hospital_id=hospital.hospital_id,
                claim_type=claim_type,
                treatment_type=treatment_type,
                admission_date=admission_date,
                discharge_date=discharge_date,
                requested_amount_inr=requested_amount.quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                ),
                status="draft",
            )

            db.session.add(new_claim)

            db.session.add_all([
                ClaimDocument(
                    claim_id=new_claim_id,
                    document_type="hospital_bill",
                    checklist_status="received",
                ),
                ClaimDocument(
                    claim_id=new_claim_id,
                    document_type="discharge_summary",
                    checklist_status="received",
                ),
            ])

            add_claim_history(
                new_claim,
                None,
                "draft",
                user,
                f"Claim draft #{new_claim_id} created.",
            )

            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                app.logger.exception("Claim creation failed.")
                flash(
                    "Unable to create the claim. Please try again.",
                    "danger",
                )
                return redirect(url_for("claim_new"))

            flash(
                f"Draft Claim #{new_claim_id} created successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "claim_detail",
                    claim_id=new_claim_id,
                )
            )

    if user.role == ROLE_POLICYHOLDER:
        available_policies = Policy.query.filter_by(
            holder_user_id=user.user_id,
            status="active",
        ).all()

        available_hospitals = Hospital.query.all()
    else:
        available_policies = Policy.query.filter_by(
            status="active"
        ).all()

        available_hospitals = Hospital.query.filter_by(
            hospital_id=user.hospital_id
        ).all()

    all_members = Member.query.all()

    return render_template(
        "claim_form.html",
        user=user,
        policies=available_policies,
        hospitals=available_hospitals,
        all_members=all_members,
        claim=None,
    )


# -------------------------------------------------------------------------
# Edit Claims
# -------------------------------------------------------------------------

@app.route("/claims/<int:claim_id>/edit", methods=["GET", "POST"])
@login_required
def claim_edit(claim_id):
    """Edit an authorized draft or more-info claim."""
    user = get_logged_in_user()
    claim = Claim.query.get_or_404(claim_id)

    if not verify_claim_access(claim, user):
        abort(403)

    if user.role not in (ROLE_POLICYHOLDER, ROLE_HOSPITAL):
        abort(403)

    if claim.status not in ("draft", "more_info"):
        flash(
            f"Claim #{claim.claim_id} cannot be edited in its current status.",
            "warning",
        )
        return redirect(
            url_for("claim_detail", claim_id=claim.claim_id)
        )

    if request.method == "POST":
        treatment_type = request.form.get(
            "treatment_type", ""
        ).strip().lower()

        admission_str = request.form.get(
            "admission_date", ""
        ).strip()

        discharge_str = request.form.get(
            "discharge_date", ""
        ).strip()

        amount_str = request.form.get(
            "requested_amount", ""
        ).strip()

        errors = []

        if treatment_type not in ("inpatient", "daycare"):
            errors.append("Please select a valid treatment type.")

        try:
            admission_date = datetime.strptime(
                admission_str, "%Y-%m-%d"
            ).date()

            discharge_date = datetime.strptime(
                discharge_str, "%Y-%m-%d"
            ).date()

            if discharge_date < admission_date:
                errors.append(
                    "Discharge date cannot be before admission date."
                )
        except ValueError:
            admission_date = None
            discharge_date = None
            errors.append("Invalid admission or discharge date.")

        try:
            requested_amount = Decimal(amount_str)

            if (
                not requested_amount.is_finite()
                or requested_amount <= 0
            ):
                errors.append(
                    "Requested amount must be greater than zero."
                )
        except Exception:
            requested_amount = None
            errors.append("Enter a valid requested amount.")

        if requested_amount is not None and requested_amount.is_finite() and requested_amount > 0:
            remaining_cover = get_remaining_cover(claim.policy)
            if requested_amount.quantize(Decimal("0.01")) > remaining_cover:
                errors.append(
                    f"Requested amount ₹{requested_amount:,.2f} exceeds remaining eligible policy coverage "
                    f"of ₹{remaining_cover:,.2f}. Please correct the amount."
                )

        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            claim.treatment_type = treatment_type
            claim.admission_date = admission_date
            claim.discharge_date = discharge_date
            claim.requested_amount_inr = requested_amount.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            add_claim_history(
                claim,
                claim.status,
                claim.status,
                user,
                "Claim details updated by creator.",
            )

            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                app.logger.exception("Claim update failed.")
                flash("Unable to update the claim.", "danger")
                return redirect(
                    url_for("claim_detail", claim_id=claim_id)
                )

            flash("Claim updated successfully.", "success")
            return redirect(
                url_for("claim_detail", claim_id=claim_id)
            )

    return render_template(
        "claim_form.html",
        user=user,
        policies=[claim.policy],
        hospitals=[claim.hospital],
        all_members=claim.policy.members,
        claim=claim,
    )


# -------------------------------------------------------------------------
# Claim Workflow: Submit
# -------------------------------------------------------------------------

@app.route("/claims/<int:claim_id>/submit", methods=["POST"])
@login_required
def claim_submit(claim_id):
    """Submit or resubmit a claim."""
    user = get_logged_in_user()
    claim = Claim.query.get_or_404(claim_id)

    if not verify_claim_access(claim, user):
        abort(403)

    if user.role not in (ROLE_POLICYHOLDER, ROLE_HOSPITAL):
        abort(403)

    if claim.status not in ("draft", "more_info"):
        flash(
            f"Claim #{claim_id} cannot be submitted in its current status.",
            "warning",
        )
        return redirect(url_for("claim_detail", claim_id=claim_id))

    if claim.admission_date is None:
        flash("An admission date is required.", "danger")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    simulation_baseline = date(2026, 10, 16)

    if (
        claim.admission_date > simulation_baseline
        or claim.admission_date > date.today()
    ):
        flash(
            "Submission rejected: admission date cannot be in the future.",
            "danger",
        )
        return redirect(url_for("claim_detail", claim_id=claim_id))

    old_status = claim.status
    claim.status = "submitted"

    add_claim_history(
        claim,
        old_status,
        "submitted",
        user,
        request.form.get(
            "note", "Claim submitted for review"
        ).strip() or "Claim submitted for review",
    )

    db.session.commit()

    flash(
        f"Claim #{claim_id} submitted to the review queue.",
        "success",
    )
    return redirect(url_for("claim_detail", claim_id=claim_id))


# -------------------------------------------------------------------------
# Claim Workflow: Assign
# -------------------------------------------------------------------------

@app.route("/claims/<int:claim_id>/assign", methods=["POST"])
@login_required
@roles_required(ROLE_CLAIMS_OFFICER, ROLE_ADMIN)
def claim_assign(claim_id):
    """Assign a submitted claim to the current authorized reviewer."""
    user = get_logged_in_user()
    claim = Claim.query.get_or_404(claim_id)

    if claim.status != "submitted":
        flash("Only submitted claims can be assigned.", "warning")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    old_status = claim.status
    claim.status = "in_review"
    claim.officer_user_id = user.user_id

    add_claim_history(
        claim,
        old_status,
        "in_review",
        user,
        f"Assigned for review to {user.display_name} ({user.role.replace('_', ' ')}).",
    )

    db.session.commit()

    flash(
        f"Claim #{claim_id} is now assigned to you for review.",
        "success",
    )
    return redirect(url_for("claim_detail", claim_id=claim_id))


# -------------------------------------------------------------------------
# Claim Workflow: Request Information
# -------------------------------------------------------------------------

@app.route("/claims/<int:claim_id>/request_info", methods=["POST"])
@login_required
@roles_required(ROLE_CLAIMS_OFFICER)
def claim_request_info(claim_id):
    """Request missing information from the claim creator."""
    user = get_logged_in_user()
    claim = Claim.query.get_or_404(claim_id)

    if claim.status not in ("submitted", "in_review"):
        flash(
            "Information cannot be requested in this claim status.",
            "warning",
        )
        return redirect(url_for("claim_detail", claim_id=claim_id))

    reason = request.form.get("reason", "").strip()

    if not reason:
        flash("A reason for requesting information is required.", "danger")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    if request.form.get("mark_summary_missing"):
        summary_doc = ClaimDocument.query.filter_by(
            claim_id=claim.claim_id,
            document_type="discharge_summary",
        ).first()

        if summary_doc:
            summary_doc.checklist_status = "missing"

    old_status = claim.status
    claim.status = "more_info"

    add_claim_history(
        claim, old_status, "more_info", user,
        f"Information requested: {reason}",
    )

    db.session.commit()

    flash(
        f"More information requested for Claim #{claim_id}.",
        "info",
    )
    return redirect(url_for("claim_detail", claim_id=claim_id))


# -------------------------------------------------------------------------
# Claim Workflow: Approve
# -------------------------------------------------------------------------

@app.route("/claims/<int:claim_id>/approve", methods=["POST"])
@login_required
@roles_required(ROLE_CLAIMS_OFFICER, ROLE_ADMIN)
def claim_approve(claim_id):
    """Approve within both the requested amount and remaining policy coverage; write audit history atomically."""
    user = get_logged_in_user()
    claim = Claim.query.get_or_404(claim_id)

    if claim.status != "in_review":
        flash("Only claims in review can be approved.", "warning")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    amount_str = request.form.get("eligible_amount", "").strip()
    reason = request.form.get("reason", "").strip()
    evidence_reference = request.form.get("evidence_reference", "").strip()

    try:
        eligible_amount = Decimal(amount_str).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if not eligible_amount.is_finite() or eligible_amount <= 0:
            raise ValueError
    except Exception:
        flash("Enter a valid positive eligible amount.", "danger")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    requested_amount = Decimal(str(claim.requested_amount_inr)).quantize(Decimal("0.01"))
    remaining_cover = get_remaining_cover(claim.policy)
    max_allowed = min(requested_amount, remaining_cover)
    if eligible_amount > max_allowed:
        flash(
            f"Approval blocked: requested approval ₹{eligible_amount:,.2f} exceeds the permitted amount. "
            f"Maximum allowed is ₹{max_allowed:,.2f}.",
            "danger",
        )
        return redirect(url_for("claim_detail", claim_id=claim_id))

    if not reason:
        flash("An approval rationale is required.", "danger")
        return redirect(url_for("claim_detail", claim_id=claim_id))
    if not evidence_reference:
        flash("A supporting evidence reference is required to approve the claim.", "danger")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    eligibility = perform_eligibility_checks(claim)
    if not eligibility["all_passed"]:
        flash(
            "Eligibility checks failed. Review and resolve policy/document issues before approval; evidence does not override coverage limits.",
            "danger",
        )
        return redirect(url_for("claim_detail", claim_id=claim_id))

    old_status = claim.status
    claim.status = "approved"
    claim.eligible_amount_inr = eligible_amount
    add_claim_history(
        claim, old_status, "approved", user,
        f"Approved for {format_currency(eligible_amount)}. Reason: {reason[:180]}. Evidence: {evidence_reference[:80]}",
    )
    db.session.add(ClaimApprovalHistory(
        claim_id=claim.claim_id,
        admin_user_id=user.user_id,
        decision="approved",
        requested_amount_inr=requested_amount,
        approved_amount_inr=eligible_amount,
        reason=reason,
        evidence_reference=evidence_reference,
        created_at=datetime.utcnow(),
    ))

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to save claim approval and approval history")
        flash("Approval was not saved. Please retry.", "danger")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    flash(
        f"Claim #{claim_id} approved for {format_currency(eligible_amount)}. Approval history recorded.",
        "success",
    )
    return redirect(url_for("claim_detail", claim_id=claim_id))


# -------------------------------------------------------------------------
# Claim Workflow: Reject
# -------------------------------------------------------------------------

@app.route("/claims/<int:claim_id>/reject", methods=["POST"])
@login_required
@roles_required(ROLE_CLAIMS_OFFICER, ROLE_ADMIN)
def claim_reject(claim_id):
    """Reject a claim with a mandatory reason and append-only decision history."""
    user = get_logged_in_user()
    claim = Claim.query.get_or_404(claim_id)

    if claim.status != "in_review":
        flash("Only claims in review can be rejected.", "warning")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    reason = request.form.get("reason", "").strip()
    evidence_reference = request.form.get("evidence_reference", "").strip()
    if not reason:
        flash("A rejection reason is required.", "danger")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    requested_amount = Decimal(str(claim.requested_amount_inr)).quantize(Decimal("0.01"))
    old_status = claim.status
    claim.status = "rejected"
    claim.eligible_amount_inr = Decimal("0.00")
    add_claim_history(claim, old_status, "rejected", user, f"Claim rejected: {reason[:180]}")
    db.session.add(ClaimApprovalHistory(
        claim_id=claim.claim_id,
        admin_user_id=user.user_id,
        decision="rejected",
        requested_amount_inr=requested_amount,
        approved_amount_inr=None,
        reason=reason,
        evidence_reference=evidence_reference or None,
        created_at=datetime.utcnow(),
    ))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Failed to save claim rejection and approval history")
        flash("Rejection was not saved. Please retry.", "danger")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    flash(f"Claim #{claim_id} has been rejected and the reason was recorded.", "danger")
    return redirect(url_for("claim_detail", claim_id=claim_id))


# -------------------------------------------------------------------------
# Claim Workflow: Settlement
# -------------------------------------------------------------------------

@app.route("/claims/<int:claim_id>/settle", methods=["POST"])
@login_required
@roles_required(ROLE_ADMIN)
def claim_settle(claim_id):
    """Record a simulated settlement for an approved claim."""
    user = get_logged_in_user()
    claim = Claim.query.get_or_404(claim_id)

    if claim.status != "approved":
        flash("Only approved claims can be settled.", "warning")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    if claim.settlement:
        flash("Settlement has already been recorded.", "info")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    payout_data = calculate_payout(
        claim.policy.plan,
        claim.eligible_amount_inr,
    )

    payout_amount = payout_data["final_payout"]

    payee_type = (
        "hospital"
        if claim.claim_type == "cashless"
        else "policyholder"
    )

    old_status = claim.status
    claim.status = "paid"
    claim.payment_recorded_date = date.today()

    settlement = Settlement(
        claim_id=claim.claim_id,
        payee_type=payee_type,
        amount_inr=payout_amount,
        recorded_by_user_id=user.user_id,
        recorded_date=date.today(),
    )

    db.session.add(settlement)

    add_claim_history(
        claim,
        old_status,
        "paid",
        user,
        (
            f"Simulated settlement recorded: "
            f"{format_currency(payout_amount)} "
            f"payable to {payee_type.title()}."
        ),
    )

    db.session.commit()

    flash(
        f"Simulated settlement of "
        f"{format_currency(payout_amount)} recorded.",
        "success",
    )
    return redirect(url_for("claim_detail", claim_id=claim_id))


# -------------------------------------------------------------------------
# Claim Documents
# -------------------------------------------------------------------------

@app.route(
    "/claims/<int:claim_id>/toggle_document",
    methods=["POST"],
)
@login_required
def toggle_document(claim_id):
    """Toggle a document between received and missing."""
    user = get_logged_in_user()
    claim = Claim.query.get_or_404(claim_id)

    if not verify_claim_access(claim, user):
        abort(403)

    if user.role not in (
        ROLE_POLICYHOLDER,
        ROLE_HOSPITAL,
        ROLE_CLAIMS_OFFICER,
    ):
        abort(403)

    if claim.status not in ("draft", "more_info", "submitted", "in_review"):
        flash(
            "Documents cannot be changed in this claim status.",
            "warning",
        )
        return redirect(url_for("claim_detail", claim_id=claim_id))

    doc_type = request.form.get("document_type", "").strip()

    allowed_document_types = {
        "hospital_bill",
        "discharge_summary",
    }

    if doc_type not in allowed_document_types:
        flash("Invalid document type.", "danger")
        return redirect(url_for("claim_detail", claim_id=claim_id))

    doc = ClaimDocument.query.filter_by(
        claim_id=claim.claim_id,
        document_type=doc_type,
    ).first()

    if doc is None:
        doc = ClaimDocument(
            claim_id=claim.claim_id,
            document_type=doc_type,
            checklist_status="received",
        )
        db.session.add(doc)
    else:
        doc.checklist_status = (
            "missing"
            if doc.checklist_status == "received"
            else "received"
        )

    db.session.commit()

    flash(
        f"Document status updated to {doc.checklist_status}.",
        "info",
    )
    return redirect(url_for("claim_detail", claim_id=claim_id))


# -------------------------------------------------------------------------
# Claims Officer Review Queue
# -------------------------------------------------------------------------

@app.route("/review_queue")
@login_required
@roles_required(ROLE_CLAIMS_OFFICER, ROLE_ADMIN)
def review_queue():
    """Display claims awaiting review or additional information."""
    user = get_logged_in_user()

    queue_claims = Claim.query.filter(
        Claim.status.in_(
            ["submitted", "in_review", "more_info"]
        )
    ).order_by(Claim.claim_id.asc()).all()

    queue_data = []

    for claim in queue_claims:
        queue_data.append({
            "claim": claim,
            "eligibility": perform_eligibility_checks(claim),
            "is_assigned_to_me": (
                claim.officer_user_id == user.user_id
            ),
        })

    return render_template(
        "review_queue.html",
        queue_data=queue_data,
        user=user,
    )


# -------------------------------------------------------------------------
# Administrator Hub
# -------------------------------------------------------------------------

@app.route("/admin")
@login_required
@roles_required(ROLE_ADMIN)
def admin():
    """Display administrative information and settlements."""
    user = get_logged_in_user()

    hospitals = Hospital.query.order_by(
        Hospital.hospital_id.asc()
    ).all()

    plans = Plan.query.order_by(
        Plan.plan_id.asc()
    ).all()

    users = User.query.order_by(
        User.user_id.asc()
    ).all()

    approved_queue = Claim.query.filter_by(
        status="approved"
    ).order_by(Claim.claim_id.asc()).all()

    settlements = Settlement.query.order_by(
        Settlement.id.desc()
    ).all()
    approval_history = ClaimApprovalHistory.query.order_by(
        ClaimApprovalHistory.created_at.desc()
    ).all()

    return render_template(
        "admin.html",
        user=user,
        hospitals=hospitals,
        plans=plans,
        users=users,
        approved_queue=approved_queue,
        settlements=settlements,
        approval_history=approval_history,
    )


# -------------------------------------------------------------------------
# Reports
# -------------------------------------------------------------------------

@app.route("/reports")
@login_required
def reports():
    """Display operational reports for staff roles."""
    user = get_logged_in_user()

    if user.role not in (ROLE_ADMIN, ROLE_CLAIMS_OFFICER):
        flash(
            "Reports are reserved for administrative and claims officers.",
            "warning",
        )
        return redirect(url_for("dashboard"))

    all_claims = Claim.query.all()
    total_count = len(all_claims)

    status_counts = {
        status: sum(
            claim.status == status for claim in all_claims
        )
        for status in (
            "draft",
            "submitted",
            "in_review",
            "more_info",
            "approved",
            "rejected",
            "paid",
        )
    }

    type_counts = {
        "cashless": sum(
            claim.claim_type == "cashless"
            for claim in all_claims
        ),
        "reimbursement": sum(
            claim.claim_type == "reimbursement"
            for claim in all_claims
        ),
    }

    treatment_counts = {
        "inpatient": sum(
            claim.treatment_type == "inpatient"
            for claim in all_claims
        ),
        "daycare": sum(
            claim.treatment_type == "daycare"
            for claim in all_claims
        ),
    }

    total_requested = sum(
        (
            Decimal(str(claim.requested_amount_inr))
            for claim in all_claims
            if claim.requested_amount_inr is not None
        ),
        Decimal("0.00"),
    )

    total_eligible = sum(
        (
            Decimal(str(claim.eligible_amount_inr))
            for claim in all_claims
            if claim.eligible_amount_inr is not None
        ),
        Decimal("0.00"),
    )

    all_settlements = Settlement.query.all()

    total_settled = sum(
        (
            Decimal(str(settlement.amount_inr))
            for settlement in all_settlements
        ),
        Decimal("0.00"),
    )

    hospital_stats = []

    for hospital in Hospital.query.all():
        hospital_claims = [
            claim
            for claim in all_claims
            if claim.hospital_id == hospital.hospital_id
        ]

        hospital_paid = sum(
            (
                Decimal(str(claim.settlement.amount_inr))
                for claim in hospital_claims
                if claim.settlement
            ),
            Decimal("0.00"),
        )

        hospital_stats.append({
            "hospital": hospital,
            "claim_count": len(hospital_claims),
            "paid_amount": hospital_paid,
        })

    return render_template(
        "reports.html",
        user=user,
        total_count=total_count,
        status_counts=status_counts,
        type_counts=type_counts,
        treatment_counts=treatment_counts,
        total_requested=total_requested,
        total_eligible=total_eligible,
        total_settled=total_settled,
        hospital_stats=hospital_stats,
    )


# -------------------------------------------------------------------------
# Error Handlers
# -------------------------------------------------------------------------

@app.errorhandler(403)
def forbidden(error):
    """Render the custom forbidden page."""
    return render_template("403.html"), 403


@app.errorhandler(404)
def page_not_found(error):
    """Render the custom not-found page."""
    return render_template("404.html"), 404


# -------------------------------------------------------------------------
# Entry Point
# -------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3000"))

    # Debug mode is configurable; defaults to off for safer operation.
    debug_enabled = (
        os.environ.get("FLASK_DEBUG", "false").lower()
        in ("true", "1", "yes")
    )

    app.run(host="127.0.0.1",port=port,debug=debug_enabled,)
