
"""
Secure resume file handling for HireWise AI.
"""

import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_BATCH_FILES = 20


def validate_resume(file):
    """Validate the uploaded resume's name, extension, and size."""

    if not file or not file.filename:
        raise ValueError("No file was selected.")

    original_name = secure_filename(file.filename)

    if not original_name:
        raise ValueError("Invalid filename.")

    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF and DOCX files are allowed.")

    file.stream.seek(0, 2)
    file_size = file.stream.tell()
    file.stream.seek(0)

    if file_size == 0:
        raise ValueError("The uploaded file is empty.")

    if file_size > MAX_FILE_SIZE:
        raise ValueError("Each resume must be 5 MB or smaller.")

    return original_name, extension


def save_resume(file):
    """Save one validated resume using a unique filename."""

    original_name, extension = validate_resume(file)

    upload_folder = Path(current_app.config["RESUME_UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}{extension}"
    destination = upload_folder / unique_filename

    file.save(destination)

    relative_path = f"resumes/{unique_filename}"

    return {
        "original_name": original_name,
        "stored_filename": unique_filename,
        "relative_path": relative_path,
        "absolute_path": str(destination),
    }


def delete_resume(file_path):
    """Delete a stored resume safely."""

    if not file_path:
        return

    upload_folder = Path(current_app.config["RESUME_UPLOAD_FOLDER"]).resolve()
    filename = Path(file_path).name
    target = (upload_folder / filename).resolve()

    if target.parent == upload_folder and target.is_file():
        target.unlink()


def validate_batch_count(files):
    """Ensure a batch contains between 1 and 20 selected files."""

    if not files:
        raise ValueError("Please select at least one resume.")

    if len(files) > MAX_BATCH_FILES:
        raise ValueError("You can upload a maximum of 20 resumes at a time.")
