
"""
CSV report generation service for HireWise AI.
"""

import csv
import io


def generate_candidate_csv(candidates):
    """Generate a CSV report from a list of candidate records."""

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Candidate ID",
        "Candidate Name",
        "Email",
        "Phone",
        "Vacancy ID",
        "Status",
        "Created Date"
    ])

    for candidate in candidates:
        writer.writerow([
            candidate.id,
            candidate.full_name,
            candidate.email,
            candidate.phone or "",
            candidate.vacancy_id,
            candidate.status,
            (
                candidate.created_at.strftime("%Y-%m-%d %H:%M:%S")
                if candidate.created_at
                else ""
            )
        ])

    return output.getvalue()


def generate_interview_csv(interviews):
    """Generate a CSV report from interview records."""

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Interview ID",
        "Candidate ID",
        "Interviewer ID",
        "Scheduled Date",
        "Raw Notes",
        "Interview Summary"
    ])

    for interview in interviews:
        writer.writerow([
            interview.id,
            interview.candidate_id,
            interview.interviewer_id,
            (
                interview.scheduled_at.strftime("%Y-%m-%d %H:%M:%S")
                if interview.scheduled_at
                else ""
            ),
            interview.notes_raw or "",
            interview.summary_edited or ""
        ])

    return output.getvalue()


def generate_csv_download_response(csv_content, filename):
    """Create a Flask response for downloading a CSV report."""

    from flask import Response

    response = Response(
        csv_content,
        mimetype="text/csv; charset=utf-8"
    )

    response.headers["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    return response
