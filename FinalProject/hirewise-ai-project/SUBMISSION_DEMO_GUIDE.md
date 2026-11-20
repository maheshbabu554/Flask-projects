# HireWise AI — submission demonstration checklist

Use a test database and fictional candidate information for the presentation. Do not demonstrate with real candidate personal data.

## Before the demonstration

- [ ] MySQL server is running and the `hirewise_ai` database exists.
- [ ] `.env` contains a generated Flask `SECRET_KEY`, MySQL connection values and working AI provider credentials.
- [ ] `flask --app app db upgrade` completes successfully.
- [ ] An administrator account exists (`python scripts/create_admin.py` creates the first one).
- [ ] The application starts with `python app.py` and opens at `http://127.0.0.1:5000/`.
- [ ] AI extraction and evidence analysis have been tested with a fictional PDF/DOCX resume.
- [ ] SMTP is configured and tested only if you intend to demonstrate sending an actual offer email. Otherwise demonstrate the draft and explain that delivery requires SMTP credentials.

## Suggested live demo sequence

1. **Login** — show the login page and role-based redirect.
2. **Administrator** — show overview, account requests, create/edit/deactivate workspace users, password reset, vacancies and activity log.
3. **Approval** — register a fictional Recruiter or Placement Coordinator, then approve the request as admin.
4. **Recruiter dashboard** — show vacancy/candidate/interview/follow-up counts, upcoming interviews and recent activities.
5. **Vacancy** — create a vacancy with a description and required skills.
6. **Resume upload** — upload one or more fictional PDF/DOCX resumes (maximum 20 files, 5 MB each).
7. **AI extraction** — open a candidate, run extraction, review the extracted profile and confirm/correct it as recruiter.
8. **Evidence mapping** — run required-skill evidence analysis and show Found / Uncertain / Not Found with excerpts. Explain that Not Found does not mean the person lacks the skill.
9. **Interview preparation** — generate job-related questions from the confirmed profile and evidence.
10. **Interview desk** — schedule an interview, save original notes, generate an AI-organized summary and review/edit it.
11. **Interview completion** — enter recruiter-owned scores (Performance /25, Confidence /10, Communication /15), complete the interview and show that original notes are locked.
12. **Follow-up** — create a due-date action, show overdue state and mark it complete.
13. **Offer letter** — show the draft. Demonstrate either the Send Offer Letter path with SMTP configured or the Reject Candidate path with a reason. Rejected candidates are archived, not permanently deleted.
14. **Human decision safeguard** — emphasize that AI never ranks, scores, selects or rejects candidates; all hiring decisions remain with the recruiter.

## Important live-demo notes

- The ZIP does not include `.env`, a database dump, or uploaded resumes. Those are private and must be configured locally.
- Do not run `flask db init` on this project. The migrations folder is already present.
- Do not delete your existing MySQL database. If its current Alembic revision is `d3f89f9a5834`, apply the included next migration with `flask --app app db upgrade`.
- A real email send requires working SMTP credentials. A successful AI connection check does not test SMTP delivery.
