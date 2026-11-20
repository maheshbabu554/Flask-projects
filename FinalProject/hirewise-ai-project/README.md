# HireWise AI — integrated recruitment workflow application

HireWise AI is a Flask + MySQL recruitment workflow application based on the supplied clickable frontend prototype. The live application uses Flask/Jinja templates, SQLAlchemy ORM, Bootstrap 5.3.8 and vanilla JavaScript. The original prototype is preserved in `prototype_reference/` for reference; its sample in-memory JavaScript is not used as the live database or authentication layer.

## Implemented workflows

### Authentication and workspaces
- Login and logout with hashed passwords and Flask-Login sessions.
- Recruiter and Placement Coordinator registration requests; both roles use the recruiter workspace permissions.
- Administrator approval/rejection of account requests.
- Admin-created workspace accounts, profile editing, password reset and account activation/deactivation.
- User profile editing and password changes.

### Recruiter workspace
- Dashboard with vacancy, candidate, interview and follow-up counts, upcoming interviews and recent activity.
- Create, edit and close vacancies.
- Bulk resume upload (up to 20 files; PDF/DOCX only; 5 MB each) into private storage outside `static/`.
- Resume text extraction and configurable OpenAI-compatible AI profile extraction.
- Recruiter confirmation of extracted candidate details.
- Resume evidence mapping with Found / Uncertain / Not Found evidence and source excerpts.
- AI interview-question generation after profile confirmation and evidence analysis.
- Candidate pipeline management, soft deletion, interview scheduling, follow-ups and offer-letter draft.
- Offer letter sending through SMTP and candidate rejection with a recorded reason. Rejected candidates are archived from the active candidate list, not permanently deleted.
- Interview notes, AI-organized summaries, recruiter-entered evaluation (Performance /25, Confidence /10, Communication /15; total /50), and a completion action that locks original notes.

### Administrator workspace
- Dashboard, pending account requests, user management, vacancy overview and activity log.
- Success/failure sign-in attempts and recorded administrative/recruitment events.

## AI and hiring safeguards
- AI supports extraction, evidence organization, interview question preparation and interview-note summarization.
- AI does not rank, score, select or reject candidates.
- Interview scorecard values are entered by the recruiter, not AI.
- Missing resume evidence does not mean a candidate lacks a skill.
- Recruiters must review and confirm AI-extracted information.
- Original resumes and original interviewer notes are preserved; completed interview notes become read-only.

## Requirements
- Python 3.10+
- MySQL 8+
- Internet access for Bootstrap CDN and configured AI/SMTP providers

## Windows setup (Command Prompt)

1. Extract the ZIP to a folder, for example `C:\Mahesh_Mitraz\flask\Assignments\hirewise-ai\hirewise-ai-project`.
2. Activate your Python virtual environment.
3. Install packages:

   ```bat
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` in the project root. Fill in `SECRET_KEY`, MySQL settings and AI settings. Configure SMTP only if you want to send real offer emails. Never share or upload `.env`.
5. Create the MySQL database named `hirewise_ai` in MySQL Workbench (or your preferred MySQL tool).
6. Apply the included migrations. **Do not run `flask db init` again** because the migrations folder is already included:

   ```bat
   flask --app app db upgrade
   ```

7. Create the first administrator account:

   ```bat
   python scripts\create_admin.py
   ```

8. Start the application:

   ```bat
   python app.py
   ```

9. Open `http://127.0.0.1:5000/`.

## Existing database warning

The migration history starts at `d3f89f9a5834` and this package adds `8a42c6b19d10` for interview completion fields and nullable audit-log user IDs. If your database already shows `d3f89f9a5834` as its current revision, run only `flask --app app db upgrade`. Do not delete your database or migrations folder.

## AI configuration

The default example uses Groq's OpenAI-compatible API. You can switch providers by changing `AI_API_BASE_URL`, `AI_API_KEY` and `AI_MODEL` in `.env` to the compatible provider's values. Never paste your actual API key into source code or share it in screenshots.

## Email configuration

Offer-letter email delivery requires valid SMTP credentials. The app cannot send email until the `MAIL_*` values in `.env` are configured and tested with your email provider. If SMTP is not configured, the offer-send action will report an email delivery error and will not mark the candidate as Offer Sent.

## Security and included files

- `.env` is intentionally not included. Use `.env.example`.
- Uploaded candidate resumes are private user data and are intentionally not included. The `uploads/resumes/` directory is created at runtime.
- Do not use Flask's debug server for production deployment.
- This package does not include your MySQL database or candidate records.

## Verification scope

The source files and Jinja templates are checked by the included tests. External MySQL, Groq/Gemini API calls and SMTP delivery require your own credentials and must be tested in your local environment before the final demonstration.
