"""
app.py - Health Insurance Claims Processing Simulator

Core Flask application handling routing, authentication, role-based authorization,
claims finite state machine workflow, eligibility rules, and financial calculations.
"""

import os
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, abort
)
from models import (
    db, init_db, User, Hospital, Plan, Policy, Member,
    Claim, ClaimDocument, ClaimHistory, Settlement
)

# Load environment configuration
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'health-insurance-simulator-secret-2026')

# Initialize Database with automatic fallback
init_db(app)

# Role Constants
ROLE_POLICYHOLDER = 'policyholder'
ROLE_HOSPITAL = 'hospital'
ROLE_CLAIMS_OFFICER = 'claims_officer'
ROLE_ADMIN = 'admin'

ALL_ROLES = [ROLE_POLICYHOLDER, ROLE_HOSPITAL, ROLE_CLAIMS_OFFICER, ROLE_ADMIN]


# -------------------------------------------------------------------------
# Template Filters & Context Processors
# -------------------------------------------------------------------------

@app.template_filter('currency')
@app.template_filter('format_inr')
def format_currency(value):
    """Format numeric/decimal value as Indian Rupees."""
    if value is None:
        return '—'
    try:
        val = Decimal(str(value))
        return f"₹ {val:,.2f}"
    except Exception:
        return f"₹ {value}"


@app.template_filter('date_format')
def format_date(value, fmt='%d %b %Y'):
    """Format Date object or string to human-readable format."""
    if not value:
        return '—'
    if isinstance(value, (datetime, date)):
        return value.strftime(fmt)
    try:
        dt = datetime.strptime(str(value).strip()[:10], '%Y-%m-%d')
        return dt.strftime(fmt)
    except Exception:
        return str(value)


@app.context_processor
def inject_global_context():
    """Inject current user and role helpers into all templates."""
    current_user = None
    user_id = session.get('user_id')
    if user_id:
        current_user = User.query.get(user_id)

    demo_mode = os.environ.get('DEMO_MODE', 'True').lower() in ('true', '1', 'yes')

    # Demo users for quick switcher
    demo_users = {
        'policyholders': User.query.filter_by(role=ROLE_POLICYHOLDER).limit(4).all(),
        'hospitals': User.query.filter_by(role=ROLE_HOSPITAL).all(),
        'officers': User.query.filter_by(role=ROLE_CLAIMS_OFFICER).all(),
        'admins': User.query.filter_by(role=ROLE_ADMIN).all()
    }

    return {
        'current_user': current_user,
        'demo_mode': demo_mode,
        'demo_users': demo_users,
        'ROLE_POLICYHOLDER': ROLE_POLICYHOLDER,
        'ROLE_HOSPITAL': ROLE_HOSPITAL,
        'ROLE_CLAIMS_OFFICER': ROLE_CLAIMS_OFFICER,
        'ROLE_ADMIN': ROLE_ADMIN,
        'today_date': date.today()
    }


# -------------------------------------------------------------------------
# Authorization Decorators & Helpers
# -------------------------------------------------------------------------

def login_required(f):
    """Ensure user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def roles_required(*allowed_roles):
    """Ensure user possesses one of the allowed roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in first.', 'warning')
                return redirect(url_for('login'))
            user = User.query.get(session['user_id'])
            if not user or user.role not in allowed_roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def verify_claim_access(claim, user):
    """Enforce data ownership and access control for a given claim."""
    if not user or not claim:
        return False
    if user.role == ROLE_ADMIN or user.role == ROLE_CLAIMS_OFFICER:
        return True
    if user.role == ROLE_POLICYHOLDER:
        # Policyholder can only see claims for their own policies
        return claim.policy.holder_user_id == user.user_id
    if user.role == ROLE_HOSPITAL:
        # Hospital user can only see claims for their assigned hospital
        return claim.hospital_id == user.hospital_id
    return False


# -------------------------------------------------------------------------
# Business Logic & Financial Calculations
# -------------------------------------------------------------------------

def calculate_payout(plan, eligible_amount):
    """
    Calculate simulated payout breakdown using BRD formula:
    Payout = (Eligible Amount - Deductible Applied) * (1 - Copay Percentage / 100)
    Uses Python Decimal for financial precision.
    """
    if eligible_amount is None or eligible_amount <= Decimal('0.00'):
        return {
            'eligible_amount': Decimal('0.00'),
            'deductible_applied': Decimal('0.00'),
            'after_deductible': Decimal('0.00'),
            'copay_percent': Decimal(str(plan.copay_percent)),
            'copay_amount': Decimal('0.00'),
            'final_payout': Decimal('0.00')
        }

    eligible = Decimal(str(eligible_amount))
    deductible_limit = Decimal(str(plan.deductible_inr))
    deductible_applied = min(eligible, deductible_limit)
    after_deductible = eligible - deductible_applied

    copay_pct = Decimal(str(plan.copay_percent))
    copay_multiplier = copay_pct / Decimal('100.00')
    copay_amount = (after_deductible * copay_multiplier).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    final_payout = (after_deductible - copay_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if final_payout < Decimal('0.00'):
        final_payout = Decimal('0.00')

    return {
        'eligible_amount': eligible,
        'deductible_applied': deductible_applied,
        'after_deductible': after_deductible,
        'copay_percent': copay_pct,
        'copay_amount': copay_amount,
        'final_payout': final_payout
    }


def get_policy_financial_summary(policy):
    """Compute annual coverage limit, total paid claims, and remaining coverage."""
    plan = policy.plan
    annual_limit = Decimal(str(plan.annual_limit_inr))

    # Sum all paid settlements for this policy
    paid_claims = Claim.query.filter_by(policy_id=policy.policy_id, status='paid').all()
    total_paid = Decimal('0.00')
    for c in paid_claims:
        if c.settlement:
            total_paid += Decimal(str(c.settlement.amount_inr))

    remaining_cover = max(Decimal('0.00'), annual_limit - total_paid)
    return {
        'annual_limit': annual_limit,
        'total_paid': total_paid,
        'remaining_cover': remaining_cover
    }


def perform_eligibility_checks(claim):
    """
    Execute all BRD eligibility checks on a claim:
    1. Active policy check
    2. Date window check (inclusive start/end)
    3. Member ownership check
    4. Plan treatment coverage check
    5. Cashless hospital network status
    6. Future admission date check
    7. Document checklist completeness
    8. Possible duplicate claim detection
    9. Positive requested amount
    """
    checks = []
    policy = claim.policy
    plan = policy.plan
    hospital = claim.hospital
    member = claim.member

    # 1. Policy Status
    is_active = (policy.status == 'active')
    checks.append({
        'rule': 'Policy Status',
        'passed': is_active,
        'details': f"Policy #{policy.policy_id} is marked '{policy.status}'."
    })

    # 2. Admission Date in Policy Window
    date_in_window = False
    if claim.admission_date and policy.start_date and policy.end_date:
        date_in_window = (policy.start_date <= claim.admission_date <= policy.end_date)
    checks.append({
        'rule': 'Policy Coverage Period',
        'passed': date_in_window,
        'details': f"Admission date ({format_date(claim.admission_date)}) falls within policy window ({format_date(policy.start_date)} to {format_date(policy.end_date)})." if date_in_window else f"Admission date is outside policy window ({format_date(policy.start_date)} to {format_date(policy.end_date)})."
    })

    # 3. Member Belongs to Policy
    member_valid = (member.policy_id == policy.policy_id)
    checks.append({
        'rule': 'Member Enrollment',
        'passed': member_valid,
        'details': f"Member '{member.display_name}' ({member.relationship}) is registered on Policy #{policy.policy_id}."
    })

    # 4. Plan Treatment Type Coverage
    treatment_covered = plan.covers_treatment(claim.treatment_type)
    checks.append({
        'rule': 'Treatment Coverage',
        'passed': treatment_covered,
        'details': f"Plan '{plan.plan_name}' covers [{plan.covered_treatment_types}]. Claim is for '{claim.treatment_type}'."
    })

    # 5. Hospital Network Status (for Cashless)
    if claim.claim_type == 'cashless':
        network_ok = hospital.is_network()
        checks.append({
            'rule': 'Hospital Network Status',
            'passed': network_ok,
            'details': f"Cashless claim requires empanelled network hospital. {hospital.name} network status: {'Empanelled (Network)' if network_ok else 'Non-Network (Ineligible for Cashless)'}."
        })
    else:
        checks.append({
            'rule': 'Hospital Network Status',
            'passed': True,
            'details': f"Reimbursement claims are permitted for both network and non-network hospitals ({hospital.name})."
        })

    # 6. Future Admission Date Check
    # Reference date for dataset validation (claims 1013 has admission date 2026-10-20 to 2026-10-22)
    # If admission date is in the future compared to current time or filing date
    not_future_date = True
    if claim.admission_date > date.today():
        not_future_date = False
    checks.append({
        'rule': 'Admission Date Timing',
        'passed': not_future_date,
        'details': f"Admission date ({format_date(claim.admission_date)}) cannot be in the future." if not not_future_date else f"Admission date ({format_date(claim.admission_date)}) is valid."
    })

    # 7. Document Checklist Status
    docs = claim.documents
    doc_types = {d.document_type: d.checklist_status for d in docs}
    bill_received = doc_types.get('hospital_bill') == 'received'
    summary_received = doc_types.get('discharge_summary') == 'received'
    docs_complete = bill_received and summary_received
    checks.append({
        'rule': 'Document Checklist',
        'passed': docs_complete,
        'details': f"Hospital Bill: {doc_types.get('hospital_bill', 'missing')}, Discharge Summary: {doc_types.get('discharge_summary', 'missing')}."
    })

    # 8. Duplicate Claim Warning
    possible_duplicates = Claim.query.filter(
        Claim.claim_id != claim.claim_id,
        Claim.member_id == claim.member_id,
        Claim.hospital_id == claim.hospital_id,
        Claim.admission_date == claim.admission_date,
        Claim.requested_amount_inr == claim.requested_amount_inr
    ).all()
    is_duplicate = len(possible_duplicates) > 0
    duplicate_ids = [str(d.claim_id) for d in possible_duplicates]
    checks.append({
        'rule': 'Duplicate Claim Detection',
        'passed': not is_duplicate,
        'is_warning_only': True,
        'details': f"WARNING: Matches existing claim(s) #{', #'.join(duplicate_ids)} with identical member, hospital, admission date, and requested amount." if is_duplicate else "No duplicate claim patterns detected."
    })

    # 9. Positive Requested Amount
    amount_valid = (claim.requested_amount_inr is not None and claim.requested_amount_inr > 0)
    checks.append({
        'rule': 'Requested Amount Validity',
        'passed': amount_valid,
        'details': f"Requested amount is {format_currency(claim.requested_amount_inr)} (must be greater than 0)."
    })

    all_passed = all(c['passed'] for c in checks if not c.get('is_warning_only', False))
    return {
        'checks': checks,
        'all_passed': all_passed,
        'has_duplicate_warning': is_duplicate,
        'duplicate_ids': duplicate_ids
    }


def add_claim_history(claim, from_status, to_status, actor_user, note=None):
    """Atomically append a new state transition entry to the claim's permanent history."""
    next_seq = 1
    if claim.history:
        next_seq = max(h.sequence_no for h in claim.history) + 1

    hist = ClaimHistory(
        claim_id=claim.claim_id,
        sequence_no=next_seq,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=actor_user.user_id if actor_user else None,
        note=note or f"Status changed from {from_status or 'new'} to {to_status}",
        event_date=date.today()
    )
    db.session.add(hist)


# -------------------------------------------------------------------------
# Authentication & Demo Role Switching Routes
# -------------------------------------------------------------------------

@app.route('/')
def index():
    """Home redirect to dashboard or login."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page featuring four one-click role demo buttons and credential form."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        user = User.query.filter_by(username=username).first()

        if user:
            session['user_id'] = user.user_id
            flash(f"Welcome back, {user.display_name}! Logged in as {user.role.replace('_', ' ').title()}.", 'success')
            return redirect(url_for('dashboard'))
        else:
            flash(f"User '{username}' was not found in the database. Please try selecting a demo role account.", 'danger')

    # Group existing users for quick demo login
    role_accounts = {
        'policyholders': User.query.filter_by(role=ROLE_POLICYHOLDER).all(),
        'hospitals': User.query.filter_by(role=ROLE_HOSPITAL).all(),
        'officers': User.query.filter_by(role=ROLE_CLAIMS_OFFICER).all(),
        'admins': User.query.filter_by(role=ROLE_ADMIN).all()
    }

    return render_template('login.html', role_accounts=role_accounts)


@app.route('/switch_user/<int:user_id>')
def switch_user(user_id):
    """Demo-mode quick role switcher without entering passwords."""
    user = User.query.get_or_404(user_id)
    session['user_id'] = user.user_id
    flash(f"Switched role to {user.display_name} ({user.role.replace('_', ' ').title()}).", 'info')
    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    """Clear session and log out."""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))


# -------------------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    """Role-sensitive dashboard displaying authorized statistics, recent claims, and pending actions."""
    user = User.query.get(session['user_id'])

    # Build query based on role
    query = Claim.query
    if user.role == ROLE_POLICYHOLDER:
        # Claims for policies held by this user
        user_policy_ids = [p.policy_id for p in user.policies]
        query = query.filter(Claim.policy_id.in_(user_policy_ids))
    elif user.role == ROLE_HOSPITAL:
        # Claims associated with this hospital
        query = query.filter_by(hospital_id=user.hospital_id)

    all_claims = query.all()

    # Calculate statistics
    stats = {
        'total': len(all_claims),
        'draft': sum(1 for c in all_claims if c.status == 'draft'),
        'submitted': sum(1 for c in all_claims if c.status == 'submitted'),
        'in_review': sum(1 for c in all_claims if c.status == 'in_review'),
        'more_info': sum(1 for c in all_claims if c.status == 'more_info'),
        'approved': sum(1 for c in all_claims if c.status == 'approved'),
        'rejected': sum(1 for c in all_claims if c.status == 'rejected'),
        'paid': sum(1 for c in all_claims if c.status == 'paid')
    }

    # Recent claims (most recent 6)
    recent_claims = query.order_by(Claim.claim_id.desc()).limit(6).all()

    # Pending actions queue
    pending_actions = []
    if user.role == ROLE_POLICYHOLDER:
        # Drafts to submit or more_info queries to reply to
        for c in all_claims:
            if c.status == 'draft':
                pending_actions.append({'claim': c, 'action': 'Submit Draft', 'desc': 'Draft claim ready for review'})
            elif c.status == 'more_info':
                pending_actions.append({'claim': c, 'action': 'Provide Info', 'desc': 'Officer requested documents/info'})
    elif user.role == ROLE_HOSPITAL:
        for c in all_claims:
            if c.status == 'draft':
                pending_actions.append({'claim': c, 'action': 'Submit Cashless', 'desc': 'Cashless request awaiting submission'})
            elif c.status == 'more_info':
                pending_actions.append({'claim': c, 'action': 'Upload Missing Doc', 'desc': 'Missing hospital records requested'})
    elif user.role == ROLE_CLAIMS_OFFICER:
        # Submitted claims awaiting assignment or in_review
        for c in all_claims:
            if c.status == 'submitted':
                pending_actions.append({'claim': c, 'action': 'Review & Assign', 'desc': 'Submitted claim awaiting adjudication'})
            elif c.status == 'in_review' and c.officer_user_id == user.user_id:
                pending_actions.append({'claim': c, 'action': 'Complete Assessment', 'desc': 'Assigned to you for approval/rejection'})
    elif user.role == ROLE_ADMIN:
        # Approved claims awaiting simulated payment
        for c in all_claims:
            if c.status == 'approved':
                pending_actions.append({'claim': c, 'action': 'Record Settlement', 'desc': 'Approved claim ready for simulated disbursement'})

    return render_template(
        'dashboard.html',
        user=user,
        stats=stats,
        recent_claims=recent_claims,
        pending_actions=pending_actions[:6]
    )


# -------------------------------------------------------------------------
# Policies View
# -------------------------------------------------------------------------

@app.route('/policies')
@login_required
def policies():
    """Policy directory with coverage limits and member listings."""
    user = User.query.get(session['user_id'])

    if user.role == ROLE_POLICYHOLDER:
        policy_list = Policy.query.filter_by(holder_user_id=user.user_id).all()
    else:
        # Staff roles can see all policies
        policy_list = Policy.query.all()

    policy_data = []
    for p in policy_list:
        summary = get_policy_financial_summary(p)
        policy_data.append({
            'policy': p,
            'summary': summary,
            'members': p.members
        })

    return render_template('policies.html', policy_data=policy_data, user=user)


# -------------------------------------------------------------------------
# Claims List & Filters
# -------------------------------------------------------------------------

@app.route('/claims')
@login_required
def claims():
    """List claims with status filtering and search query."""
    user = User.query.get(session['user_id'])
    status_filter = request.args.get('status', '').strip().lower()
    claim_type_filter = request.args.get('type', '').strip().lower()
    search_q = request.args.get('q', '').strip()

    query = Claim.query

    # Enforce role-based access
    if user.role == ROLE_POLICYHOLDER:
        user_policy_ids = [p.policy_id for p in user.policies]
        query = query.filter(Claim.policy_id.in_(user_policy_ids))
    elif user.role == ROLE_HOSPITAL:
        query = query.filter_by(hospital_id=user.hospital_id)

    # Apply filters
    if status_filter:
        query = query.filter_by(status=status_filter)
    if claim_type_filter:
        query = query.filter_by(claim_type=claim_type_filter)
    if search_q:
        # Search by claim ID or member name
        query = query.join(Member).filter(
            db.or_(
                Claim.claim_id.like(f"%{search_q}%"),
                Member.display_name.ilike(f"%{search_q}%")
            )
        )

    claims_list = query.order_by(Claim.claim_id.desc()).all()

    return render_template(
        'claims.html',
        claims=claims_list,
        current_status=status_filter,
        current_type=claim_type_filter,
        search_q=search_q,
        user=user
    )


# -------------------------------------------------------------------------
# Claim Detail Audit & Workflow Center
# -------------------------------------------------------------------------

@app.route('/claims/<int:claim_id>')
@login_required
def claim_detail(claim_id):
    """Detailed audit view with eligibility checks, payout calculator, checklist, and audit trail."""
    user = User.query.get(session['user_id'])
    claim = Claim.query.get_or_404(claim_id)

    # Verify horizontal authorization
    if not verify_claim_access(claim, user):
        abort(403)

    eligibility = perform_eligibility_checks(claim)
    policy_summary = get_policy_financial_summary(claim.policy)

    # Payout preview for eligible amount (or requested if not yet set)
    test_amount = claim.eligible_amount_inr if claim.eligible_amount_inr is not None else claim.requested_amount_inr
    payout_breakdown = calculate_payout(claim.policy.plan, test_amount)

    return render_template(
        'claim_detail.html',
        claim=claim,
        user=user,
        eligibility=eligibility,
        policy_summary=policy_summary,
        payout=payout_breakdown
    )


# -------------------------------------------------------------------------
# Claim Creation & Editing
# -------------------------------------------------------------------------

@app.route('/claims/new', methods=['GET', 'POST'])
@login_required
def claim_new():
    """Create a new reimbursement claim (policyholder) or cashless claim (hospital)."""
    user = User.query.get(session['user_id'])

    # Only policyholders and hospital staff can originate claims
    if user.role not in [ROLE_POLICYHOLDER, ROLE_HOSPITAL]:
        flash('Only policyholders and hospital desks can create claim submissions.', 'danger')
        return redirect(url_for('claims'))

    if request.method == 'POST':
        policy_id = request.form.get('policy_id', type=int)
        member_id = request.form.get('member_id', type=int)
        hospital_id = request.form.get('hospital_id', type=int)
        treatment_type = request.form.get('treatment_type', '').strip().lower()
        admission_date_str = request.form.get('admission_date', '').strip()
        discharge_date_str = request.form.get('discharge_date', '').strip()
        requested_amount = request.form.get('requested_amount', type=float)

        # Validation
        policy = Policy.query.get(policy_id)
        member = Member.query.get(member_id)
        hospital = Hospital.query.get(hospital_id)

        errors = []
        if not policy:
            errors.append('Please select a valid policy.')
        elif user.role == ROLE_POLICYHOLDER and policy.holder_user_id != user.user_id:
            errors.append('You can only create claims for your own policies.')

        if not member or (policy and member.policy_id != policy.policy_id):
            errors.append('Selected member does not belong to the selected policy.')

        if not hospital:
            errors.append('Please select a valid hospital.')
        elif user.role == ROLE_HOSPITAL and hospital.hospital_id != user.hospital_id:
            errors.append('Hospital users can only file claims for their own hospital.')

        if treatment_type not in ['inpatient', 'daycare']:
            errors.append('Please select a valid treatment type.')

        adm_date = None
        dis_date = None
        try:
            adm_date = datetime.strptime(admission_date_str, '%Y-%m-%d').date()
            dis_date = datetime.strptime(discharge_date_str, '%Y-%m-%d').date()
            if dis_date < adm_date:
                errors.append('Discharge date cannot be prior to admission date.')
        except Exception:
            errors.append('Invalid admission or discharge date.')

        if requested_amount is None or requested_amount <= 0:
            errors.append('Requested amount must be greater than zero.')

        if errors:
            for err in errors:
                flash(err, 'danger')
        else:
            # Auto-assign claim type based on creator role
            claim_type = 'reimbursement' if user.role == ROLE_POLICYHOLDER else 'cashless'

            # Generate next claim_id
            max_id = db.session.query(db.func.max(Claim.claim_id)).scalar() or 1000
            new_claim_id = max_id + 1

            new_claim = Claim(
                claim_id=new_claim_id,
                policy_id=policy.policy_id,
                member_id=member.member_id,
                hospital_id=hospital.hospital_id,
                claim_type=claim_type,
                treatment_type=treatment_type,
                admission_date=adm_date,
                discharge_date=dis_date,
                requested_amount_inr=Decimal(str(requested_amount)),
                status='draft'
            )
            db.session.add(new_claim)

            # Add default required documents
            doc1 = ClaimDocument(claim_id=new_claim_id, document_type='hospital_bill', checklist_status='received')
            doc2 = ClaimDocument(claim_id=new_claim_id, document_type='discharge_summary', checklist_status='received')
            db.session.add(doc1)
            db.session.add(doc2)

            # Record initial history
            add_claim_history(new_claim, None, 'draft', user, f"Claim draft #{new_claim_id} created by {user.display_name}")

            db.session.commit()
            flash(f"Draft Claim #{new_claim_id} created successfully! You may now review and submit.", 'success')
            return redirect(url_for('claim_detail', claim_id=new_claim_id))

    # Prepare form options
    if user.role == ROLE_POLICYHOLDER:
        available_policies = Policy.query.filter_by(holder_user_id=user.user_id, status='active').all()
        available_hospitals = Hospital.query.all()
    else:
        # Hospital user
        available_policies = Policy.query.filter_by(status='active').all()
        available_hospitals = Hospital.query.filter_by(hospital_id=user.hospital_id).all()

    all_members = Member.query.all()

    return render_template(
        'claim_form.html',
        user=user,
        policies=available_policies,
        hospitals=available_hospitals,
        all_members=all_members,
        claim=None
    )


@app.route('/claims/<int:claim_id>/edit', methods=['GET', 'POST'])
@login_required
def claim_edit(claim_id):
    """Edit draft or more_info claim."""
    user = User.query.get(session['user_id'])
    claim = Claim.query.get_or_404(claim_id)

    if not verify_claim_access(claim, user):
        abort(403)

    if claim.status not in ['draft', 'more_info']:
        flash(f"Claim #{claim.claim_id} is '{claim.status}' and cannot be edited.", 'warning')
        return redirect(url_for('claim_detail', claim_id=claim.claim_id))

    if request.method == 'POST':
        treatment_type = request.form.get('treatment_type', '').strip().lower()
        admission_date_str = request.form.get('admission_date', '').strip()
        discharge_date_str = request.form.get('discharge_date', '').strip()
        requested_amount = request.form.get('requested_amount', type=float)

        errors = []
        try:
            adm_date = datetime.strptime(admission_date_str, '%Y-%m-%d').date()
            dis_date = datetime.strptime(discharge_date_str, '%Y-%m-%d').date()
            if dis_date < adm_date:
                errors.append('Discharge date cannot be prior to admission date.')
        except Exception:
            errors.append('Invalid admission or discharge date.')

        if requested_amount is None or requested_amount <= 0:
            errors.append('Requested amount must be greater than zero.')

        if errors:
            for err in errors:
                flash(err, 'danger')
        else:
            claim.treatment_type = treatment_type
            claim.admission_date = adm_date
            claim.discharge_date = dis_date
            claim.requested_amount_inr = Decimal(str(requested_amount))

            add_claim_history(claim, claim.status, claim.status, user, "Claim details updated by creator")
            db.session.commit()
            flash('Claim updated successfully!', 'success')
            return redirect(url_for('claim_detail', claim_id=claim.claim_id))

    return render_template(
        'claim_form.html',
        user=user,
        policies=[claim.policy],
        hospitals=[claim.hospital],
        all_members=claim.policy.members,
        claim=claim
    )


# -------------------------------------------------------------------------
# Claim Workflow State Actions
# -------------------------------------------------------------------------

@app.route('/claims/<int:claim_id>/submit', methods=['POST'])
@login_required
def claim_submit(claim_id):
    """Submit a draft or resubmit a more_info claim."""
    user = User.query.get(session['user_id'])
    claim = Claim.query.get_or_404(claim_id)

    if not verify_claim_access(claim, user):
        abort(403)

    if user.role not in [ROLE_POLICYHOLDER, ROLE_HOSPITAL]:
        flash('Only the claim creator can submit claims.', 'danger')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    if claim.status not in ['draft', 'more_info']:
        flash(f"Claim #{claim.claim_id} is in status '{claim.status}' and cannot be submitted.", 'warning')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    # BRD rule: Check future admission date before allowing submission
    if claim.admission_date > date.today():
        flash(f"Submission Rejected: Admission date ({format_date(claim.admission_date)}) cannot be in the future. Please update admission date before submitting.", 'danger')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    old_status = claim.status
    claim.status = 'submitted'
    add_claim_history(claim, old_status, 'submitted', user, request.form.get('note', 'Claim submitted for review'))
    db.session.commit()

    flash(f"Claim #{claim.claim_id} has been submitted to the review queue.", 'success')
    return redirect(url_for('claim_detail', claim_id=claim_id))


@app.route('/claims/<int:claim_id>/assign', methods=['POST'])
@login_required
@roles_required(ROLE_CLAIMS_OFFICER)
def claim_assign(claim_id):
    """Claims officer assigns claim to themselves and moves status to in_review."""
    user = User.query.get(session['user_id'])
    claim = Claim.query.get_or_404(claim_id)

    if claim.status != 'submitted':
        flash(f"Claim #{claim.claim_id} is '{claim.status}' and cannot be assigned.", 'warning')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    old_status = claim.status
    claim.status = 'in_review'
    claim.officer_user_id = user.user_id
    add_claim_history(claim, old_status, 'in_review', user, f"Claim assigned to Claims Officer {user.display_name}")
    db.session.commit()

    flash(f"Claim #{claim.claim_id} is now assigned to you and In Review.", 'success')
    return redirect(url_for('claim_detail', claim_id=claim_id))


@app.route('/claims/<int:claim_id>/request_info', methods=['POST'])
@login_required
@roles_required(ROLE_CLAIMS_OFFICER)
def claim_request_info(claim_id):
    """Claims officer requests missing information or documents."""
    user = User.query.get(session['user_id'])
    claim = Claim.query.get_or_404(claim_id)

    if claim.status not in ['submitted', 'in_review']:
        flash(f"Cannot request information for claim in status '{claim.status}'.", 'warning')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('You must provide a specific reason explaining what information or documents are required.', 'danger')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    # Mark discharge summary as missing if specified
    mark_missing = request.form.get('mark_summary_missing')
    if mark_missing:
        summary_doc = ClaimDocument.query.filter_by(claim_id=claim.claim_id, document_type='discharge_summary').first()
        if summary_doc:
            summary_doc.checklist_status = 'missing'

    old_status = claim.status
    claim.status = 'more_info'
    add_claim_history(claim, old_status, 'more_info', user, f"Information Requested: {reason}")
    db.session.commit()

    flash(f"More information requested for Claim #{claim.claim_id}.", 'info')
    return redirect(url_for('claim_detail', claim_id=claim_id))


@app.route('/claims/<int:claim_id>/approve', methods=['POST'])
@login_required
@roles_required(ROLE_CLAIMS_OFFICER)
def claim_approve(claim_id):
    """Approve claim with eligible amount and rationale."""
    user = User.query.get(session['user_id'])
    claim = Claim.query.get_or_404(claim_id)

    if claim.status != 'in_review':
        flash(f"Only claims 'In Review' can be approved. Current status: '{claim.status}'.", 'warning')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    eligible_amt = request.form.get('eligible_amount', type=float)
    reason = request.form.get('reason', '').strip()

    if eligible_amt is None or eligible_amt <= 0:
        flash('An approval requires a positive eligible amount.', 'danger')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    if Decimal(str(eligible_amt)) > claim.requested_amount_inr:
        flash('Eligible amount cannot exceed the requested amount.', 'danger')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    if not reason:
        flash('An approval rationale/note is required.', 'danger')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    # Check eligibility rules
    eligibility = perform_eligibility_checks(claim)
    if not eligibility['all_passed']:
        flash('Warning: One or more critical eligibility checks did not pass. Please verify before approving.', 'warning')

    old_status = claim.status
    claim.status = 'approved'
    claim.eligible_amount_inr = Decimal(str(eligible_amt))
    add_claim_history(claim, old_status, 'approved', user, f"Approved for {format_currency(claim.eligible_amount_inr)}. Note: {reason}")
    db.session.commit()

    flash(f"Claim #{claim.claim_id} approved for {format_currency(claim.eligible_amount_inr)}.", 'success')
    return redirect(url_for('claim_detail', claim_id=claim_id))


@app.route('/claims/<int:claim_id>/reject', methods=['POST'])
@login_required
@roles_required(ROLE_CLAIMS_OFFICER)
def claim_reject(claim_id):
    """Reject claim with mandatory reason."""
    user = User.query.get(session['user_id'])
    claim = Claim.query.get_or_404(claim_id)

    if claim.status != 'in_review':
        flash(f"Only claims 'In Review' can be rejected. Current status: '{claim.status}'.", 'warning')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Rejection requires a documented reason.', 'danger')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    old_status = claim.status
    claim.status = 'rejected'
    claim.eligible_amount_inr = Decimal('0.00')
    add_claim_history(claim, old_status, 'rejected', user, f"Claim Rejected: {reason}")
    db.session.commit()

    flash(f"Claim #{claim.claim_id} has been rejected.", 'danger')
    return redirect(url_for('claim_detail', claim_id=claim_id))


@app.route('/claims/<int:claim_id>/settle', methods=['POST'])
@login_required
@roles_required(ROLE_ADMIN)
def claim_settle(claim_id):
    """Administrator records simulated settlement payout for approved claim."""
    user = User.query.get(session['user_id'])
    claim = Claim.query.get_or_404(claim_id)

    if claim.status != 'approved':
        flash(f"Only approved claims can be settled. Current status: '{claim.status}'.", 'warning')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    if claim.settlement:
        flash(f"Settlement has already been recorded for Claim #{claim.claim_id}.", 'info')
        return redirect(url_for('claim_detail', claim_id=claim_id))

    # Calculate final payout amount
    payout_data = calculate_payout(claim.policy.plan, claim.eligible_amount_inr)
    payout_amt = payout_data['final_payout']
    payee_type = 'hospital' if claim.claim_type == 'cashless' else 'policyholder'

    old_status = claim.status
    claim.status = 'paid'
    claim.payment_recorded_date = date.today()

    settlement = Settlement(
        claim_id=claim.claim_id,
        payee_type=payee_type,
        amount_inr=payout_amt,
        recorded_by_user_id=user.user_id,
        recorded_date=date.today()
    )
    db.session.add(settlement)

    add_claim_history(claim, old_status, 'paid', user, f"Simulated settlement recorded: {format_currency(payout_amt)} payable to {payee_type.title()}")
    db.session.commit()

    flash(f"Simulated settlement of {format_currency(payout_amt)} successfully recorded for Claim #{claim.claim_id}!", 'success')
    return redirect(url_for('claim_detail', claim_id=claim_id))


@app.route('/claims/<int:claim_id>/toggle_document', methods=['POST'])
@login_required
def toggle_document(claim_id):
    """Toggle document status between received and missing."""
    user = User.query.get(session['user_id'])
    claim = Claim.query.get_or_404(claim_id)

    if not verify_claim_access(claim, user):
        abort(403)

    doc_type = request.form.get('document_type')
    doc = ClaimDocument.query.filter_by(claim_id=claim.claim_id, document_type=doc_type).first()
    if not doc:
        doc = ClaimDocument(claim_id=claim.claim_id, document_type=doc_type, checklist_status='received')
        db.session.add(doc)
    else:
        doc.checklist_status = 'missing' if doc.checklist_status == 'received' else 'received'

    db.session.commit()
    flash(f"Document status for '{doc_type.replace('_', ' ').title()}' updated to {doc.checklist_status}.", 'info')
    return redirect(url_for('claim_detail', claim_id=claim_id))


# -------------------------------------------------------------------------
# Review Queue (Claims Officer)
# -------------------------------------------------------------------------

@app.route('/review_queue')
@login_required
@roles_required(ROLE_CLAIMS_OFFICER, ROLE_ADMIN)
def review_queue():
    """Adjudication review queue displaying pending submissions with duplicate & eligibility highlights."""
    user = User.query.get(session['user_id'])

    # Submitted, In Review, and More Info claims
    queue_claims = Claim.query.filter(Claim.status.in_(['submitted', 'in_review', 'more_info'])).order_by(Claim.claim_id.asc()).all()

    queue_data = []
    for c in queue_claims:
        eligibility = perform_eligibility_checks(c)
        queue_data.append({
            'claim': c,
            'eligibility': eligibility,
            'is_assigned_to_me': (c.officer_user_id == user.user_id)
        })

    return render_template('review_queue.html', queue_data=queue_data, user=user)


# -------------------------------------------------------------------------
# Administrator Hub
# -------------------------------------------------------------------------

@app.route('/admin')
@login_required
@roles_required(ROLE_ADMIN)
def admin():
    """Master administration console for hospitals, plans, users, and settlements."""
    user = User.query.get(session['user_id'])

    hospitals = Hospital.query.order_by(Hospital.hospital_id.asc()).all()
    plans = Plan.query.order_by(Plan.plan_id.asc()).all()
    users = User.query.order_by(User.user_id.asc()).all()

    # Approved claims awaiting simulated disbursement
    approved_queue = Claim.query.filter_by(status='approved').order_by(Claim.claim_id.asc()).all()

    # Existing settlements history
    settlements = Settlement.query.order_by(Settlement.id.desc()).all()

    return render_template(
        'admin.html',
        user=user,
        hospitals=hospitals,
        plans=plans,
        users=users,
        approved_queue=approved_queue,
        settlements=settlements
    )


# -------------------------------------------------------------------------
# Reports & Statistics
# -------------------------------------------------------------------------

@app.route('/reports')
@login_required
def reports():
    """Analytical overview with KPI breakdown across claims, statuses, and hospitals."""
    user = User.query.get(session['user_id'])

    # Only admin and claims officers can view enterprise-wide reports
    if user.role not in [ROLE_ADMIN, ROLE_CLAIMS_OFFICER]:
        flash('Reports are reserved for administrative and adjudication officers.', 'warning')
        return redirect(url_for('dashboard'))

    all_claims = Claim.query.all()
    total_count = len(all_claims)

    status_counts = {}
    for st in ['draft', 'submitted', 'in_review', 'more_info', 'approved', 'rejected', 'paid']:
        status_counts[st] = sum(1 for c in all_claims if c.status == st)

    type_counts = {
        'cashless': sum(1 for c in all_claims if c.claim_type == 'cashless'),
        'reimbursement': sum(1 for c in all_claims if c.claim_type == 'reimbursement')
    }

    treatment_counts = {
        'inpatient': sum(1 for c in all_claims if c.treatment_type == 'inpatient'),
        'daycare': sum(1 for c in all_claims if c.treatment_type == 'daycare')
    }

    total_requested = sum(c.requested_amount_inr for c in all_claims if c.requested_amount_inr)
    total_eligible = sum(c.eligible_amount_inr for c in all_claims if c.eligible_amount_inr)

    all_settlements = Settlement.query.all()
    total_settled = sum(s.amount_inr for s in all_settlements)

    # Hospital performance breakdown
    hospital_stats = []
    for h in Hospital.query.all():
        h_claims = [c for c in all_claims if c.hospital_id == h.hospital_id]
        h_paid = sum(c.settlement.amount_inr for c in h_claims if c.settlement)
        hospital_stats.append({
            'hospital': h,
            'claim_count': len(h_claims),
            'paid_amount': h_paid
        })

    return render_template(
        'reports.html',
        user=user,
        total_count=total_count,
        status_counts=status_counts,
        type_counts=type_counts,
        treatment_counts=treatment_counts,
        total_requested=total_requested,
        total_eligible=total_eligible,
        total_settled=total_settled,
        hospital_stats=hospital_stats
    )


# -------------------------------------------------------------------------
# Error Handlers
# -------------------------------------------------------------------------

@app.errorhandler(403)
def forbidden(e):
    """Custom 403 Forbidden page without leaking credentials."""
    return render_template('403.html'), 403


@app.errorhandler(404)
def page_not_found(e):
    """Custom 404 Not Found page."""
    return render_template('404.html'), 404


# -------------------------------------------------------------------------
# Entry Point
# -------------------------------------------------------------------------

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port, debug=True)
