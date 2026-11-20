
"""
Provider-independent AI service for HireWise AI.

Supports OpenAI-compatible chat completion APIs such as
Groq and Google's Gemini OpenAI-compatible endpoint.

AI workflows:
1. Candidate profile extraction.
2. Resume requirement evidence mapping.
3. Experience-based interview question generation.
4. Plain-text interview notes summarization.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

from dotenv import load_dotenv


load_dotenv()


# =========================================================
# CUSTOM AI EXCEPTION
# =========================================================

class AIServiceError(Exception):
    """Raised when an AI provider request fails."""


# =========================================================
# AI SETTINGS
# =========================================================

def get_ai_settings():
    """Read AI provider settings from environment variables."""

    try:
        timeout = int(os.getenv("AI_TIMEOUT", "60"))
    except ValueError as error:
        raise AIServiceError(
            "AI_TIMEOUT must be a valid integer."
        ) from error

    settings = {
        "provider": os.getenv("AI_PROVIDER", "groq"),
        "base_url": os.getenv(
            "AI_API_BASE_URL",
            "https://api.groq.com/openai/v1"
        ).rstrip("/"),
        "api_key": os.getenv("AI_API_KEY", "").strip(),
        "model": os.getenv("AI_MODEL", "").strip(),
        "json_mode": os.getenv(
            "AI_JSON_MODE", "true"
        ).lower() == "true",
        "timeout": timeout,
    }

    if not settings["api_key"]:
        raise AIServiceError(
            "AI_API_KEY is missing in the environment."
        )

    if not settings["model"]:
        raise AIServiceError(
            "AI_MODEL is missing in the environment."
        )

    if not settings["base_url"]:
        raise AIServiceError(
            "AI_API_BASE_URL is missing."
        )

    if timeout <= 0:
        raise AIServiceError(
            "AI_TIMEOUT must be greater than zero."
        )

    return settings


# =========================================================
# CHAT COMPLETION
# =========================================================

def chat_completion(
    system_prompt,
    user_prompt,
    temperature=0.2,
    json_response=False
):
    """Send a chat completion request to the configured AI provider."""

    settings = get_ai_settings()

    url = f"{settings['base_url']}/chat/completions"

    payload = {
        "model": settings["model"],
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": temperature
    }

    if json_response and settings["json_mode"]:
        payload["response_format"] = {
            "type": "json_object"
        }

    request_data = json.dumps(payload).encode("utf-8")

    api_request = urllib.request.Request(
        url,
        data=request_data,
        headers={
            "Authorization": f"Bearer {settings['api_key']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "HireWiseAI/1.0"
        },
        method="POST"
    )

    start_time = time.perf_counter()

    try:
        with urllib.request.urlopen(
            api_request,
            timeout=settings["timeout"]
        ) as response:

            response_data = json.loads(
                response.read().decode("utf-8")
            )

        latency_ms = int(
            (time.perf_counter() - start_time) * 1000
        )

        choices = response_data.get("choices", [])

        if not choices:
            raise AIServiceError(
                "The AI provider returned no response choices."
            )

        content = choices[0].get(
            "message", {}
        ).get("content")

        if not content or not isinstance(content, str):
            raise AIServiceError(
                "The AI provider returned empty or unsupported content."
            )

        return {
            "content": content.strip(),
            "model": settings["model"],
            "provider": settings["provider"],
            "latency_ms": latency_ms
        }

    except urllib.error.HTTPError as error:
        error_body = error.read().decode(
            "utf-8",
            errors="replace"
        )

        raise AIServiceError(
            f"AI provider returned HTTP {error.code}: "
            f"{error_body[:500]}"
        ) from error

    except urllib.error.URLError as error:
        raise AIServiceError(
            f"Could not connect to the AI provider: {error.reason}"
        ) from error

    except TimeoutError as error:
        raise AIServiceError(
            "The AI provider request timed out."
        ) from error

    except json.JSONDecodeError as error:
        raise AIServiceError(
            "The AI provider returned an invalid JSON response."
        ) from error


# =========================================================
# JSON RESPONSE PARSER
# =========================================================

def parse_json_response(content):
    """Convert generated JSON text into a Python object."""

    try:
        return json.loads(content)

    except json.JSONDecodeError:

        cleaned_content = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            content.strip(),
            flags=re.IGNORECASE
        )

        try:
            return json.loads(cleaned_content)

        except json.JSONDecodeError as error:
            raise AIServiceError(
                "The AI response was not valid JSON."
            ) from error


# =========================================================
# GENERATE JSON
# =========================================================

def generate_json(
    system_prompt,
    user_prompt,
    temperature=0.2
):
    """Generate and parse a structured JSON response."""

    result = chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        json_response=True
    )

    parsed_data = parse_json_response(
        result["content"]
    )

    if not isinstance(parsed_data, dict):
        raise AIServiceError(
            "The AI response must be a JSON object."
        )

    result["data"] = parsed_data

    return result


# =========================================================
# EXPERIENCE VALUE HELPERS
# =========================================================

def _parse_numeric_experience(value):
    """
    Parse a numeric experience value.

    Returns None when the value is not a valid numeric value.
    """

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        return None

    text = value.strip().lower()

    if not text:
        return None

    # Match explicit year-based values.
    year_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:\+?\s*)?"
        r"(?:years?|yrs?|yr)\b",
        text
    )

    if year_match:
        return float(year_match.group(1))

    # Match explicit month-based values.
    month_match = re.search(
        r"(\d+(?:\.\d+)?)\s*months?\b",
        text
    )

    if month_match:
        return float(month_match.group(1)) / 12

    # Accept a plain numeric string only.
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)

    return None


def _extract_experience_from_entries(experience_entries):
    """
    Extract experience only from explicit duration information.

    Does not interpret arbitrary numbers or date years as
    work experience.
    """

    if not isinstance(experience_entries, list):
        return None

    if not experience_entries:
        return 0.0

    durations = []

    for entry in experience_entries:

        if isinstance(entry, dict):

            # Look only at fields that explicitly describe duration.
            for key in (
                "duration",
                "work_experience",
                "experience_duration",
                "total_duration"
            ):
                value = entry.get(key)

                if value is not None:
                    parsed = _parse_numeric_experience(value)

                    if parsed is not None:
                        durations.append(parsed)
                        break

        elif isinstance(entry, str):

            # Only accept explicit phrases such as "2 years".
            parsed = _parse_numeric_experience(entry)

            if parsed is not None:
                durations.append(parsed)

    if durations:
        # Avoid double-counting overlapping jobs.
        # Use the longest explicitly stated duration when
        # individual entries do not provide a reliable total.
        return max(durations)

    return None


def get_candidate_work_experience(profile):
    """
    Read candidate work experience from a verified profile.

    Priority:
    1. work_experience_years
    2. work_experience
    3. total_experience
    4. experience_years
    5. Explicit duration in experience entries

    Empty experience means fresher.
    Non-empty but unclear experience raises an error rather
    than incorrectly treating an experienced candidate as a fresher.
    """

    if not isinstance(profile, dict):
        raise AIServiceError(
            "Verified candidate profile must be a dictionary."
        )

    for field in (
        "work_experience_years",
        "work_experience",
        "total_experience",
        "experience_years"
    ):
        value = profile.get(field)

        if value is None:
            continue

        parsed = _parse_numeric_experience(value)

        if parsed is not None:
            return parsed

        if isinstance(value, str) and value.strip().lower() in {
            "null",
            "none",
            "fresher",
            "fresh graduate",
            "no experience",
            "no work experience"
        }:
            return 0.0

        raise AIServiceError(
            f"Candidate experience field '{field}' "
            "has an unsupported format."
        )

    experience_entries = profile.get("experience", [])

    if not isinstance(experience_entries, list):
        raise AIServiceError(
            "Candidate experience information has an invalid format."
        )

    if not experience_entries:
        return 0.0

    extracted = _extract_experience_from_entries(
        experience_entries
    )

    if extracted is not None:
        return extracted

    raise AIServiceError(
        "Candidate work experience could not be determined "
        "from the verified profile. Please ensure the profile "
        "contains work_experience_years or explicit experience durations."
    )


# =========================================================
# EXPERIENCE LEVEL DETECTION
# =========================================================

def determine_interview_difficulty(work_experience):
    """
    Determine interview difficulty using candidate work experience.

    Rules:
    - Fresher / NULL / 0: Beginner to Intermediate.
    - Above 0 and below 5 years: Intermediate to Basic Advanced.
    - Exactly 5 years or above: Intermediate to Advanced.
    """

    if work_experience is None:
        years = 0.0
    else:
        years = _parse_numeric_experience(
            work_experience
        )

        if years is None:
            text = str(work_experience).strip().lower()

            if text in {
                "",
                "null",
                "none",
                "fresher",
                "fresh graduate",
                "no experience",
                "no work experience"
            }:
                years = 0.0
            else:
                raise AIServiceError(
                    f"Could not determine candidate work experience: "
                    f"{work_experience}"
                )

    if years < 0:
        raise AIServiceError(
            "Work experience cannot be negative."
        )

    if years == 0:
        level = "Fresher"
        difficulty = "Beginner to Intermediate"

    elif years < 5:
        level = "Experienced Professional"
        difficulty = "Intermediate to Basic Advanced"

    else:
        level = "Experienced Professional"
        difficulty = "Intermediate to Advanced"

    return {
        "experience_years": years,
        "experience_level": level,
        "difficulty": difficulty
    }


# =========================================================
# RESUME CONTACT EXTRACTION HELPERS
# =========================================================

def extract_email_from_resume(resume_text):
    """Find the first email address in resume text."""

    email_pattern = (
        r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
    )

    matches = re.findall(
        email_pattern,
        resume_text
    )

    return matches[0].strip() if matches else None


def extract_phone_from_resume(resume_text):
    """Find a possible Indian mobile number."""

    phone_pattern = (
        r"(?<!\d)"
        r"(?:\+?91[\s.-]?)?"
        r"[6-9]\d{4}[\s.-]?\d{5}"
        r"(?!\d)"
    )

    matches = re.findall(
        phone_pattern,
        resume_text
    )

    return matches[0].strip() if matches else None


# =========================================================
# NORMALIZE CANDIDATE PROFILE
# =========================================================

def normalize_candidate_profile(profile):
    """Ensure candidate profile fields have expected types."""

    expected_fields = {
        "full_name": None,
        "email": None,
        "phone": None,
        "location": None,
        "summary": None,
        "work_experience_years": None,
        "skills": [],
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
    }

    for field, default_value in expected_fields.items():

        if field not in profile:
            profile[field] = default_value

    text_fields = [
        "full_name",
        "email",
        "phone",
        "location",
        "summary",
    ]

    for field in text_fields:

        value = profile.get(field)

        if isinstance(value, str):
            value = value.strip()
            profile[field] = value if value else None

        elif value is not None:
            profile[field] = None

    list_fields = [
        "skills",
        "education",
        "experience",
        "projects",
        "certifications",
    ]

    for field in list_fields:

        if not isinstance(profile.get(field), list):
            profile[field] = []

    experience_years = profile.get(
        "work_experience_years"
    )

    if experience_years is not None:

        parsed = _parse_numeric_experience(
            experience_years
        )

        if parsed is None or parsed < 0:
            profile["work_experience_years"] = None
        else:
            profile["work_experience_years"] = parsed

    return profile


# =========================================================
# CANDIDATE PROFILE EXTRACTION
# =========================================================

def extract_candidate_profile(resume_text):
    """
    Extract candidate details from resume text.

    JSON is used because the extracted profile is stored
    in structured database fields.
    """

    if not isinstance(resume_text, str) or not resume_text.strip():
        raise AIServiceError(
            "Resume text is empty."
        )

    system_prompt = """
You are an expert resume information extraction assistant.

Extract candidate information accurately using only
the information present in the resume.

IMPORTANT INSTRUCTIONS:

1. Inspect the first 20 lines carefully.
2. Extract the candidate's actual name, email and phone.
3. Search the entire resume if contact details are missing.
4. Do not confuse references or emergency contacts
   with the candidate's own details.
5. Extract skills, education, experience, projects
   and certifications.
6. Extract total work experience in years as a number
   when the resume clearly provides it.
7. Use the candidate's explicitly stated total experience
   when available.
8. If the resume provides clear employment dates,
   calculate total experience only when the dates allow
   a reliable calculation.
9. Do not count internships as full-time work experience
   unless the resume explicitly identifies them as employment.
10. If total work experience cannot be reliably determined,
    use null for work_experience_years.
11. Never invent or guess missing information.
12. Use null for unavailable text or numeric fields.
13. Use empty arrays for unavailable list fields.

Return valid JSON only.

Required structure:

{
    "full_name": null,
    "email": null,
    "phone": null,
    "location": null,
    "summary": null,
    "work_experience_years": null,
    "skills": [],
    "education": [],
    "experience": [],
    "projects": [],
    "certifications": []
}
"""

    user_prompt = f"""
Extract the complete candidate profile from this resume.

Inspect the resume header for:

- Candidate full name
- Candidate email address
- Candidate phone number

Then inspect the remaining resume for:

- Location
- Professional summary
- Technical and other skills
- Education
- Work experience
- Total work experience in years
- Projects
- Certifications

RESUME TEXT:

{resume_text}

Return the extracted information in the required JSON structure.
"""

    result = generate_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.0
    )

    profile = result.get("data")

    if not isinstance(profile, dict):
        raise AIServiceError(
            "AI returned an invalid candidate profile."
        )

    profile = normalize_candidate_profile(profile)

    if not profile.get("email"):
        profile["email"] = extract_email_from_resume(
            resume_text
        )

    if not profile.get("phone"):
        profile["phone"] = extract_phone_from_resume(
            resume_text
        )

    result["data"] = profile

    return result


# =========================================================
# REQUIREMENT EVIDENCE MAPPING
# =========================================================

def map_requirement_evidence(
    resume_text,
    required_skills
):
    """Find resume evidence for each required skill."""

    system_prompt = """
You are a recruitment evidence analysis assistant.

Check each requested skill against the resume.

Use only these evidence statuses:
- evidence found
- not found
- uncertain

Rules:

1. Never invent evidence.
2. Include an exact supporting excerpt when evidence is found.
3. Use null when no reliable excerpt exists.
4. Do not treat missing information as proof of inability.
5. Return valid JSON only.

Required structure:

{
    "evidence": [
        {
            "skill": "Python",
            "status": "evidence found",
            "excerpt": "Exact resume text",
            "page": null,
            "explanation": "Brief explanation"
        }
    ]
}
"""

    user_prompt = f"""
Check these required skills:

{json.dumps(required_skills, ensure_ascii=False)}

RESUME TEXT:

{resume_text}
"""

    return generate_json(
        system_prompt,
        user_prompt
    )


# =========================================================
# INTERVIEW QUESTION GENERATION
# =========================================================

def generate_interview_questions(
    vacancy,
    verified_profile,
    evidence
):
    """
    Generate interview questions using candidate experience.

    Questions remain structured JSON because the application
    stores each question separately.
    """

    if not isinstance(verified_profile, dict):
        raise AIServiceError(
            "Verified candidate profile must be a dictionary."
        )

    work_experience = get_candidate_work_experience(
        verified_profile
    )

    experience_details = determine_interview_difficulty(
        work_experience
    )

    difficulty = experience_details["difficulty"]

    system_prompt = f"""
You are an experienced technical interviewer
working for a professional recruitment team.

Generate relevant, fair and role-specific interview questions.

CANDIDATE EXPERIENCE:

Experience: {experience_details["experience_years"]} years
Experience category: {experience_details["experience_level"]}
Required difficulty: {difficulty}

STRICT DIFFICULTY RULES:

1. Follow the required difficulty level exactly.
2. Do not generate unnecessarily complex questions.
3. Questions must relate to the vacancy.
4. Questions must relate to the candidate's verified skills.
5. Consider the candidate's actual work experience.
6. Do not assume skills that are not in the profile.
7. Include a balanced combination of:
   - Conceptual questions.
   - Practical questions.
   - Real-world scenario questions.
8. Avoid advanced architecture, optimization,
   distributed systems and deep internal concepts
   for freshers unless clearly appropriate to the vacancy.
9. Do not ask candidates to explain technologies
   they have never worked with as if they are experienced.
10. Do not rank, score, accept or reject candidates.

DIFFICULTY GUIDELINES:

Beginner to Intermediate:
- Basic concepts and definitions.
- Syntax and fundamentals.
- Small coding problems.
- Simple practical examples.
- Basic real-world scenarios.

Intermediate to Basic Advanced:
- Practical implementation.
- Problem-solving and debugging.
- Moderate coding problems.
- Applied technical concepts.
- Basic advanced scenarios.

Intermediate to Advanced:
- In-depth technical concepts.
- Complex problem-solving.
- Real-world architecture and design scenarios.
- Performance considerations.
- Advanced coding and debugging.
- Technical decision-making.

QUESTION QUALITY:

- Generate 5 to 8 questions.
- Keep each question clear and understandable.
- Avoid repeating the same question.
- Match questions to the candidate's experience.
- Prefer questions that allow the candidate to explain
  their actual knowledge and practical experience.
- Do not make every question difficult.

Return valid JSON only.

Required structure:

{{
    "questions": [
        {{
            "question": "Question text",
            "topic": "Technical topic",
            "related_evidence": "Relevant candidate evidence",
            "what_to_listen_for": "Expected discussion points"
        }}
    ]
}}
"""

    user_prompt = f"""
VACANCY:

{json.dumps(vacancy, ensure_ascii=False, default=str)}

VERIFIED CANDIDATE PROFILE:

{json.dumps(verified_profile, ensure_ascii=False, default=str)}

RESUME EVIDENCE:

{json.dumps(evidence, ensure_ascii=False, default=str)}

EXPERIENCE-BASED DIFFICULTY:

{difficulty}

CANDIDATE EXPERIENCE:

{experience_details["experience_years"]} years

Generate 5 to 8 relevant interview questions.

Follow the required difficulty level.
Do not include candidate scores or hiring decisions.

Return the questions in the specified JSON structure.
"""

    result = generate_json(
        system_prompt,
        user_prompt,
        temperature=0.3
    )

    questions = result["data"].get("questions")

    if (
        not isinstance(questions, list)
        or not questions
        or not all(isinstance(item, dict) for item in questions)
    ):
        raise AIServiceError(
            "AI did not generate a valid interview question list."
        )

    result["data"]["experience_details"] = experience_details

    return result


# =========================================================
# INTERVIEW NOTES SUMMARIZATION - PLAIN TEXT
# =========================================================

def summarize_interview_notes(raw_notes):
    """
    Generate a readable plain-text interview summary.

    Interview notes do not require JSON.
    """

    if not isinstance(raw_notes, str) or not raw_notes.strip():
        raise AIServiceError(
            "Interview notes are empty."
        )

    system_prompt = """
You are a professional interview notes organization assistant.

Organize the recruiter's raw interview notes into
a clear, professional and readable text summary.

IMPORTANT RULES:

1. Return PLAIN TEXT ONLY.
2. Do not return JSON.
3. Do not use JSON objects, arrays or key-value structures.
4. Do not wrap the response in code fences.
5. Do not invent candidate information.
6. Do not add details absent from the original notes.
7. Preserve the original meaning.
8. Correct grammar and improve readability.
9. Do not assign scores or ratings.
10. Do not make hiring decisions.
11. Do not recommend accepting or rejecting the candidate.
12. If a section has no information, write:
    "Not mentioned in the interview notes."

Use these headings:

INTERVIEW SUMMARY

TECHNICAL KNOWLEDGE

STRENGTHS

AREAS FOR IMPROVEMENT

FOLLOW-UP POINTS

ADDITIONAL NOTES

Write short, professional paragraphs or bullet points
under the headings.

The entire response must be plain readable text.
"""

    user_prompt = f"""
Organize the following recruiter's interview notes.

Preserve all important information.
Do not invent missing details.

ORIGINAL INTERVIEW NOTES:

{raw_notes}

Return a professional plain-text interview summary.
"""

    result = chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.2,
        json_response=False
    )

    summary = result.get("content", "").strip()

    if not summary:
        raise AIServiceError(
            "AI generated an empty interview summary."
        )

    # Remove accidental Markdown code fences.
    summary = re.sub(
        r"^```(?:text|markdown)?\s*|\s*```$",
        "",
        summary,
        flags=re.IGNORECASE
    ).strip()

    result["content"] = summary

    return result
