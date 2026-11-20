
"""
Resume text extraction for HireWise AI.

Supports PDF and DOCX files.
AI processing is handled separately by ai_service.py.
"""

import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader


def clean_extracted_text(text):   
    """Clean extracted text without removing useful contact details."""

    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_pdf_text(file_path):
    """Extract text from every page of a PDF resume."""

    reader = PdfReader(str(file_path))

    if reader.is_encrypted:
        raise ValueError(
            "Password-protected PDF files are not supported."
        )

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):

        try:
            page_text = page.extract_text(
                extraction_mode="layout"
            ) or ""
        except TypeError:
            # Compatibility with versions that do not support
            # extraction_mode="layout".
            page_text = page.extract_text() or ""

        page_text = clean_extracted_text(page_text)

        if page_text:
            pages.append({
                "page": page_number,
                "text": page_text
            })

    if not pages:
        raise ValueError(
            "No readable text found in this PDF. "
            "It may be a scanned image or contain text "
            "that cannot be extracted."
        )

    return pages


def extract_docx_text(file_path):
    """Extract text from DOCX paragraphs, tables and headers."""

    document = Document(str(file_path))

    sections = []

    # Extract document headers.
    for section in document.sections:
        for paragraph in section.header.paragraphs:
            text = clean_extracted_text(paragraph.text)

            if text:
                sections.append(text)

        for table in section.header.tables:
            for row in table.rows:
                for cell in row.cells:
                    text = clean_extracted_text(cell.text)

                    if text:
                        sections.append(text)

    # Extract normal paragraphs.
    for paragraph in document.paragraphs:
        text = clean_extracted_text(paragraph.text)

        if text:
            sections.append(text)

    # Extract tables.
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                text = clean_extracted_text(cell.text)

                if text:
                    sections.append(text)

    # Extract document footers.
    for section in document.sections:
        for paragraph in section.footer.paragraphs:
            text = clean_extracted_text(paragraph.text)

            if text:
                sections.append(text)

    if not sections:
        raise ValueError(
            "No readable text found in this DOCX file."
        )

    return [{
        "page": None,
        "text": "\n".join(sections)
    }]


def extract_resume_text(file_path):
    """
    Extract text from PDF or DOCX resumes.

    Returns a list of sections containing extracted text.
    """

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(
            "Resume file was not found."
        )

    extension = path.suffix.lower()

    if extension == ".pdf":
        return extract_pdf_text(path)

    if extension == ".docx":
        return extract_docx_text(path)

    raise ValueError(
        "Only PDF and DOCX files are supported."
    )


def get_full_resume_text(file_path):
    """Combine extracted sections into one text string."""

    sections = extract_resume_text(file_path)

    return "\n\n".join(
        section["text"]
        for section in sections
        if section.get("text")
    )
