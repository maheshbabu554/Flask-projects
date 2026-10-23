"""
models.py - Health Insurance Claims Processing Simulator

SQLAlchemy models and database initialization.
Maps directly to the existing MySQL schema and dataset.
"""

import os
import csv
from datetime import datetime, date
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

db = SQLAlchemy()


class Hospital(db.Model):
    """Network and non-network healthcare providers."""
    __tablename__ = 'hospitals'

    hospital_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    network_status = db.Column(db.Integer, default=1)  # 1 = Network Empanelled, 0 = Non-Network

    # Relationships
    users = db.relationship('User', backref='hospital', lazy=True)
    claims = db.relationship('Claim', backref='hospital', lazy=True)

    def is_network(self):
        return self.network_status == 1


class Plan(db.Model):
    """Health insurance policy plans with limits, deductibles, and copays."""
    __tablename__ = 'plans'

    plan_id = db.Column(db.Integer, primary_key=True)
    plan_name = db.Column(db.String(100), nullable=False)
    covered_treatment_types = db.Column(db.String(100), nullable=False)  # e.g., 'inpatient' or 'inpatient|daycare'
    annual_limit_inr = db.Column(db.Numeric(12, 2), nullable=False)
    deductible_inr = db.Column(db.Numeric(12, 2), nullable=False)
    copay_percent = db.Column(db.Numeric(5, 2), nullable=False)

    # Relationships
    policies = db.relationship('Policy', backref='plan', lazy=True)

    def covers_treatment(self, treatment_type):
        """Check if treatment type is covered under this plan."""
        if not self.covered_treatment_types or not treatment_type:
            return False
        allowed = [t.strip().lower() for t in self.covered_treatment_types.split('|')]
        return treatment_type.strip().lower() in allowed


class User(db.Model):
    """Application users with role-based permissions."""
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'policyholder', 'hospital', 'claims_officer', 'admin'
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospitals.hospital_id'), nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)

    # Relationships
    policies = db.relationship('Policy', backref='holder_user', lazy=True, foreign_keys='Policy.holder_user_id')
    assigned_claims = db.relationship('Claim', backref='officer_user', lazy=True, foreign_keys='Claim.officer_user_id')


class Policy(db.Model):
    """Insurance contracts held by policyholders."""
    __tablename__ = 'policies'

    policy_id = db.Column(db.Integer, primary_key=True)
    holder_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.plan_id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='active')  # 'active', 'expired'

    # Relationships
    members = db.relationship('Member', backref='policy', lazy=True)
    claims = db.relationship('Claim', backref='policy', lazy=True)

    def is_active_on(self, check_date):
        """Verify policy is active and date falls in inclusive policy window."""
        if self.status != 'active':
            return False
        if not check_date:
            return False
        return self.start_date <= check_date <= self.end_date


class Member(db.Model):
    """Covered family members and policyholders."""
    __tablename__ = 'members'

    member_id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey('policies.policy_id'), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    relationship = db.Column(db.String(20), nullable=False)  # 'self', 'spouse', 'child'

    # Relationships
    claims = db.relationship('Claim', backref='member', lazy=True)


class Claim(db.Model):
    """Insurance claim submissions across their complete lifecycle."""
    __tablename__ = 'claims'

    claim_id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(db.Integer, db.ForeignKey('policies.policy_id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.member_id'), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospitals.hospital_id'), nullable=False)
    claim_type = db.Column(db.String(20), nullable=False)  # 'cashless', 'reimbursement'
    treatment_type = db.Column(db.String(50), nullable=False)  # 'inpatient', 'daycare'
    admission_date = db.Column(db.Date, nullable=False)
    discharge_date = db.Column(db.Date, nullable=False)
    requested_amount_inr = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), default='draft')  # draft, submitted, in_review, more_info, approved, rejected, paid
    eligible_amount_inr = db.Column(db.Numeric(12, 2), nullable=True)
    officer_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    payment_recorded_date = db.Column(db.Date, nullable=True)

    # Relationships
    documents = db.relationship('ClaimDocument', backref='claim', lazy=True, cascade='all, delete-orphan')
    history = db.relationship('ClaimHistory', backref='claim', lazy=True, cascade='all, delete-orphan', order_by='ClaimHistory.sequence_no')
    settlement = db.relationship('Settlement', backref='claim', uselist=False, lazy=True)


class ClaimDocument(db.Model):
    """Required document checklist items for a claim."""
    __tablename__ = 'claim_documents'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    claim_id = db.Column(db.Integer, db.ForeignKey('claims.claim_id'), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)  # 'hospital_bill', 'discharge_summary'
    checklist_status = db.Column(db.String(20), default='received')  # 'received', 'missing'


class ClaimHistory(db.Model):
    """Permanent immutable audit trail of claim state transitions."""
    __tablename__ = 'claim_history'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    claim_id = db.Column(db.Integer, db.ForeignKey('claims.claim_id'), nullable=False)
    sequence_no = db.Column(db.Integer, nullable=False)
    from_status = db.Column(db.String(20), nullable=True)
    to_status = db.Column(db.String(20), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    actor = db.relationship('User', foreign_keys=[actor_user_id])
    note = db.Column(db.String(255), nullable=True)
    event_date = db.Column(db.Date, nullable=False)


class Settlement(db.Model):
    """Simulated payment settlements recorded for approved claims."""
    __tablename__ = 'settlements'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    claim_id = db.Column(db.Integer, db.ForeignKey('claims.claim_id'), nullable=False, unique=True)
    payee_type = db.Column(db.String(30), nullable=False)  # 'hospital', 'policyholder'
    amount_inr = db.Column(db.Numeric(12, 2), nullable=False)
    recorded_by_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    recorder = db.relationship('User', foreign_keys=[recorded_by_user_id])
    recorded_date = db.Column(db.Date, nullable=False)


def seed_from_csv(dataset_dir):
    """Populate database from synthetic CSV files if tables are empty (used for fallback replica)."""
    if not os.path.exists(dataset_dir):
        return

    # Helper to parse dates
    def parse_d(val):
        if not val or val.strip() == '':
            return None
        return datetime.strptime(val.strip(), '%Y-%m-%d').date()

    # Helper to parse decimal
    def parse_dec(val):
        if not val or val.strip() == '':
            return None
        return Decimal(val.strip())

    # Helper to parse int
    def parse_int(val):
        if not val or val.strip() == '':
            return None
        return int(val.strip())

    # 1. Hospitals
    hosp_file = os.path.join(dataset_dir, 'hospitals.csv')
    if os.path.exists(hosp_file) and Hospital.query.count() == 0:
        with open(hosp_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                h = Hospital(
                    hospital_id=int(row['hospital_id']),
                    name=row['name'].strip(),
                    city=row['city'].strip(),
                    network_status=int(row['network_status'])
                )
                db.session.add(h)
        db.session.commit()

    # 2. Plans
    plan_file = os.path.join(dataset_dir, 'plans.csv')
    if os.path.exists(plan_file) and Plan.query.count() == 0:
        with open(plan_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                p = Plan(
                    plan_id=int(row['plan_id']),
                    plan_name=row['plan_name'].strip(),
                    covered_treatment_types=row['covered_treatment_types'].strip(),
                    annual_limit_inr=Decimal(row['annual_limit_inr']),
                    deductible_inr=Decimal(row['deductible_inr']),
                    copay_percent=Decimal(row['copay_percent'])
                )
                db.session.add(p)
        db.session.commit()

    # 3. Users
    user_file = os.path.join(dataset_dir, 'users.csv')
    if os.path.exists(user_file) and User.query.count() == 0:
        with open(user_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                u = User(
                    user_id=int(row['user_id']),
                    username=row['username'].strip(),
                    display_name=row['display_name'].strip(),
                    role=row['role'].strip(),
                    hospital_id=parse_int(row['hospital_id'])
                )
                db.session.add(u)
        db.session.commit()

    # 4. Policies
    policy_file = os.path.join(dataset_dir, 'policies.csv')
    if os.path.exists(policy_file) and Policy.query.count() == 0:
        with open(policy_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                pol = Policy(
                    policy_id=int(row['policy_id']),
                    holder_user_id=int(row['holder_user_id']),
                    plan_id=int(row['plan_id']),
                    start_date=parse_d(row['start_date']),
                    end_date=parse_d(row['end_date']),
                    status=row['status'].strip()
                )
                db.session.add(pol)
        db.session.commit()

    # 5. Members
    mem_file = os.path.join(dataset_dir, 'members.csv')
    if os.path.exists(mem_file) and Member.query.count() == 0:
        with open(mem_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                m = Member(
                    member_id=int(row['member_id']),
                    policy_id=int(row['policy_id']),
                    display_name=row['display_name'].strip(),
                    relationship=row['relationship'].strip()
                )
                db.session.add(m)
        db.session.commit()

    # 6. Claims
    claim_file = os.path.join(dataset_dir, 'claims.csv')
    if os.path.exists(claim_file) and Claim.query.count() == 0:
        with open(claim_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                c = Claim(
                    claim_id=int(row['claim_id']),
                    policy_id=int(row['policy_id']),
                    member_id=int(row['member_id']),
                    hospital_id=int(row['hospital_id']),
                    claim_type=row['claim_type'].strip(),
                    treatment_type=row['treatment_type'].strip(),
                    admission_date=parse_d(row['admission_date']),
                    discharge_date=parse_d(row['discharge_date']),
                    requested_amount_inr=Decimal(row['requested_amount_inr']),
                    status=row['status'].strip(),
                    eligible_amount_inr=parse_dec(row['eligible_amount_inr']),
                    officer_user_id=parse_int(row['officer_user_id']),
                    payment_recorded_date=parse_d(row['payment_recorded_date'])
                )
                db.session.add(c)
        db.session.commit()

    # 7. Claim Documents
    doc_file = os.path.join(dataset_dir, 'claim_documents.csv')
    if os.path.exists(doc_file) and ClaimDocument.query.count() == 0:
        with open(doc_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                cd = ClaimDocument(
                    claim_id=int(row['claim_id']),
                    document_type=row['document_type'].strip(),
                    checklist_status=row['checklist_status'].strip()
                )
                db.session.add(cd)
        db.session.commit()

    # 8. Claim History
    hist_file = os.path.join(dataset_dir, 'claim_history.csv')
    if os.path.exists(hist_file) and ClaimHistory.query.count() == 0:
        with open(hist_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                ch = ClaimHistory(
                    claim_id=int(row['claim_id']),
                    sequence_no=int(row['sequence_no']),
                    from_status=row['from_status'].strip() if row['from_status'] else None,
                    to_status=row['to_status'].strip(),
                    actor_user_id=parse_int(row['actor_user_id']),
                    note=row['note'].strip() if row['note'] else None,
                    event_date=parse_d(row['event_date'])
                )
                db.session.add(ch)
        db.session.commit()

    # 9. Settlements
    settle_file = os.path.join(dataset_dir, 'settlements.csv')
    if os.path.exists(settle_file) and Settlement.query.count() == 0:
        with open(settle_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                s = Settlement(
                    claim_id=int(row['claim_id']),
                    payee_type=row['payee_type'].strip(),
                    amount_inr=Decimal(row['amount_inr']),
                    recorded_by_user_id=int(row['recorded_by_user_id']),
                    recorded_date=parse_d(row['recorded_date'])
                )
                db.session.add(s)
        db.session.commit()


def init_db(app):
    """
    Initializes the database connection.
    Attempts primary MySQL connection first.
    If MySQL server is offline/unreachable, gracefully switches to SQLite replica.
    """
    database_url = os.environ.get('DATABASE_URL', 'mysql+pymysql://root:12345@localhost:3306/insurance_db')
    fallback_path = os.environ.get('FALLBACK_SQLITE_PATH', 'insurance_sim.db')

    # Try connecting to MySQL first
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    is_connected = False
    try:
        from sqlalchemy import create_engine
        engine = create_engine(database_url, connect_args={'connect_timeout': 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[Database] Successfully connected to primary MySQL database at localhost.")
        is_connected = True
    except Exception as e:
        print(f"[Database] Primary MySQL is offline or unreachable ({e}).")
        print(f"[Database] Switching to fallback SQLite replica: {fallback_path}")
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{fallback_path}'
        is_connected = False

    db.init_app(app)

    with app.app_context():
        if not is_connected:
            # In fallback mode, ensure tables exist and data from synthetic dataset is seeded
            db.create_all()
            # Find dataset directory
            candidates = [
                'health_claims_synthetic_dataset',
                os.path.join(os.path.dirname(__file__), 'health_claims_synthetic_dataset'),
                '../health_claims_synthetic_dataset',
                '/app/applet/health_claims_synthetic_dataset'
            ]
            found_dir = None
            for c in candidates:
                if os.path.exists(os.path.join(c, 'users.csv')):
                    found_dir = c
                    break
            if found_dir:
                seed_from_csv(found_dir)
                print(f"[Database] Populated SQLite replica from synthetic dataset at {found_dir}.")
