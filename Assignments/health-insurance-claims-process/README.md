# Health Insurance Claims Processing Simulator

Educational full-stack Flask + MySQL project using synthetic data only. It does not provide real insurance advice, make real claim decisions, or transfer real money.

## Setup

1. Install Python 3.10+ and MySQL. Create the database configured in `DATABASE_URL` (for example, `insurance_db`).
2. Copy `.env.example` to `.env` and set your MySQL username/password and a private `FLASK_SECRET_KEY`. Do not share your `.env` file.
3. Install dependencies: `pip install -r requirements.txt`.
4. Run: `python app.py`.
5. Open `http://127.0.0.1:3000`.

SQLAlchemy `create_all()` creates missing tables, including `claim_approval_history`, without altering existing table schemas.

## Changes included

- Policyholder claim amounts are validated against remaining eligible policy coverage on the server.
- Hospital desk policy/member lookup uses searchable text and retrieves covered members for the selected active policy.
- Authorized admins and claims officers can approve or reject claims in review; approval amount is capped by the requested bill and remaining coverage.
- Approval requires a rationale and evidence reference; rejection requires a reason.
- Each approval/rejection and its amounts, reviewer, reason, evidence reference, and timestamp are saved transactionally in `claim_approval_history` and shown in the admin Approval History tab.

## Notes

- The dataset is synthetic and for classroom demonstrations only.
- The provided schema does not include a direct hospital-to-policy relationship. Hospital search therefore returns active policy/member matches, while claim creation still enforces that the logged-in hospital can submit only for its own hospital ID.

## Administrator account management

- From **Admin → System Users & Roles**, use **Add User / Admin** to create a policyholder, claims officer, or another administrator.
- A new policyholder is created with a selected plan, policy dates, and a primary member record so the account can use the claim workflow.
- Use **Add Hospital + Login** to create a hospital registry entry and its linked hospital login together.
- Use **Edit / Reset Password** to update a user's details or set a new password. Leave the new-password fields blank to keep the existing password.
- Passwords entered by the administrator are stored as Werkzeug password hashes. The application does not display or store the original plain-text password.
- Existing password hashes are preserved. The application no longer creates username-derived passwords at startup. If no administrator can log in because its password hash is empty, run `python set_initial_admin_password.py` and enter the existing admin username and a password manually.

## MySQL schema note

The existing `users` model already includes `password_hash VARCHAR(255)`, `is_active`, and `hospital_id`. The new account-management routes use the existing `users`, `hospitals`, `policies`, `members`, and `plans` tables, so **no new MySQL table or schema change should be needed** when your database matches this project version. `db.create_all()` does not add missing columns to existing tables.

Before making any manual schema changes, select your configured database and run:

```sql
SHOW COLUMNS FROM users LIKE 'password_hash';
SHOW COLUMNS FROM users LIKE 'is_active';
SHOW COLUMNS FROM users LIKE 'hospital_id';
SHOW TABLES LIKE 'policies';
SHOW TABLES LIKE 'members';
```

Only if `password_hash` is genuinely missing, take a backup first and run:

```sql
ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL;
```

Do not run that `ALTER TABLE` if the column already exists. Never store plain-text passwords in MySQL. Keep your local `.env` private; use `.env.example` as a template.
