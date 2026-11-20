
"""
Gemini API diagnostic test for HireWise AI.

Checks:
1. Gemini API authentication and model access.
2. Gemini text generation.
3. JSON response parsing.

Run from the project root:

    python scripts/check_gemini_connection.py
"""

import json
import sys
"""
Gemini API diagnostic for HireWise AI.

Tests whether Gemini can generate a JSON response
without using the response_format parameter.
"""

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def test_gemini_generation():
    """Send a simple JSON-generation request to Gemini."""

    load_dotenv()

    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv(
        "AI_API_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ).rstrip("/")
    model = os.getenv("AI_MODEL", "gemini-3.8-flash")

    if not api_key:
        print("ERROR: AI_API_KEY is missing from .env")
        return

    endpoint = f"{base_url}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Return only a valid JSON object. Do not use Markdown.",
            },
            {
                "role": "user",
                "content": (
                    'Return this JSON: '
                    '{"status": "connected", '
                    '"message": "Gemini API connection successful."}'
                ),
            },
        ],
        "temperature": 0.1,
    }

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    print("\nHireWise AI - Gemini Generation Test")
    print("------------------------------------")
    print(f"Model: {model}")
    print("JSON mode: Disabled")
    print("Sending request...\n")

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))

        content = result["choices"][0]["message"]["content"]

        print("Gemini response received:")
        print(content)

        parsed_json = json.loads(content)

        print("\nJSON validation: SUCCESS")
        print(json.dumps(parsed_json, indent=4))

    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        print(f"HTTP ERROR: {error.code}")
        print(f"Provider response: {error_body or 'No response body'}")

    except (urllib.error.URLError, TimeoutError) as error:
        print(f"CONNECTION ERROR: {error}")

    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        print(f"RESPONSE VALIDATION ERROR: {error}")

    except Exception as error:
        print(f"UNEXPECTED ERROR: {error}")


if __name__ == "__main__":
    test_gemini_generation()

import urllib.error
import urllib.parse
import urllib.request

from pathlib import Path


# =========================================================
# PROJECT CONFIGURATION
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(PROJECT_ROOT))

from services.ai_service import (
    call_ai,
    get_ai_settings,
)


TIMEOUT_SECONDS = 30


# =========================================================
# MODEL ACCESS TEST
# =========================================================

def test_model_access(api_base_url, api_key, model_name):
    """
    Verify API authentication and whether the model is accessible.

    Returns:
        bool: True if model access succeeds.
    """

    print("\nSTEP 1: Checking Gemini model access...")
    print("--------------------------------------")

    encoded_model = urllib.parse.quote(
        model_name,
        safe="",
    )

    endpoint = (
        f"{api_base_url}/models/{encoded_model}"
    )

    request = urllib.request.Request(
        endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:

            response_body = response.read().decode(
                "utf-8",
                errors="replace",
            )

        model_data = json.loads(response_body)

        print("Model access successful!")

        print(
            "Model:",
            model_data.get("id", model_name),
        )

        return True

    except urllib.error.HTTPError as exc:

        print("Model access failed.")
        print("HTTP status:", exc.code)

        try:
            error_body = exc.read().decode(
                "utf-8",
                errors="replace",
            )

            print("Google response:", error_body[:1500])

        except Exception:
            print("Google response body unavailable.")

        return False

    except urllib.error.URLError as exc:

        print("Network connection failed.")
        print("Reason:", exc.reason)

        return False

    except (TimeoutError, json.JSONDecodeError) as exc:

        print("Model access test failed.")
        print("Reason:", exc)

        return False


# =========================================================
# JSON GENERATION TEST
# =========================================================

def test_json_generation():
    """
    Test Gemini text generation and JSON response parsing.

    Returns:
        bool: True if valid JSON is returned.
    """

    print("\nSTEP 2: Testing Gemini JSON generation...")
    print("-----------------------------------------")

    system_prompt = """
You are a connection testing assistant.

Return a valid JSON object containing:
- status
- message

Do not include Markdown formatting.
"""

    user_prompt = """
Return this JSON response:

{
    "status": "connected",
    "message": "Gemini API connection successful."
}
"""

    try:
        result = call_ai(
            system_prompt,
            user_prompt,
            temperature=0.1,
        )

        print("JSON generation successful!")

        print("\nGemini response:")

        print(
            json.dumps(
                result,
                indent=4,
                ensure_ascii=False,
            )
        )

        return True

    except (RuntimeError, ValueError) as exc:

        print("JSON generation failed.")
        print("Reason:", exc)

        return False


# =========================================================
# MAIN DIAGNOSTIC
# =========================================================

def main():
    """
    Run the Gemini diagnostic tests.
    """

    print("\nHireWise AI - Gemini API Diagnostic")
    print("===================================")

    try:
        api_base_url, api_key, model_name = get_ai_settings()

    except RuntimeError as exc:

        print("\nConfiguration error:")
        print(exc)

        return False

    # Never display the API key.
    print("\nConfiguration loaded successfully.")
    print("API endpoint:", api_base_url)
    print("Model:", model_name)

    model_access = test_model_access(
        api_base_url,
        api_key,
        model_name,
    )

    if not model_access:

        print("\nDiagnostic stopped.")
        print("Resolve the model access issue first.")

        return False

    generation_success = test_json_generation()

    print("\nDIAGNOSTIC RESULT")
    print("=================")

    if generation_success:

        print("Gemini API is working correctly.")
        print("Model access: SUCCESS")
        print("JSON generation: SUCCESS")

        return True

    print("Model access: SUCCESS")
    print("JSON generation: FAILED")

    print(
        "The model is accessible, but generation "
        "is currently unsuccessful."
    )

    return False


if __name__ == "__main__":

    success = main()

    if not success:
        sys.exit(1)
