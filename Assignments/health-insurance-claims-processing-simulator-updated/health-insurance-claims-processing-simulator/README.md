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
