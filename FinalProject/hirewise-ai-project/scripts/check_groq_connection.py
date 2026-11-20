
"""
Groq API diagnostic for HireWise AI.

Tests model access and text generation independently
of the Gemini-specific AI service configuration.
"""

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv


def send_request(url, api_key, payload=None):
    """Send an authenticated GET or POST request to Groq."""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "HireWiseAI/1.0",
    }

    if payload is None:
        request = urllib.request.Request(
            url,
            headers=headers,
            method="GET",
        )
    else:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def test_groq_connection():
    """Check Groq model access and generate a JSON response."""

    load_dotenv()

    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv(
        "AI_API_BASE_URL",
        "https://api.groq.com/openai/v1",
    ).rstrip("/")
    model = os.getenv("AI_MODEL", "openai/gpt-oss-20b")

    print("\nHireWise AI - Groq API Diagnostic")
    print("=================================")

    if not api_key:
        print("ERROR: AI_API_KEY is missing from .env")
        return

    if "api.groq.com/openai/v1" not in base_url:
        print("ERROR: Incorrect Groq API base URL.")
        return

    print("Configuration loaded successfully.")
    print(f"API endpoint: {base_url}")
    print(f"Model: {model}")

    # STEP 1: Check model access.
    print("\nSTEP 1: Checking Groq model access...")
    print("------------------------------------")

    try:
        models = send_request(
            f"{base_url}/models",
            api_key,
        )

        available_models = [
            item["id"] for item in models.get("data", [])
        ]

        if model not in available_models:
            print("Model is not listed in the available models.")
            print("Check the model ID in your .env file.")
            return

        print("Model access successful!")
        print(f"Model: {model}")

    except urllib.error.HTTPError as error:
        print(f"Model access failed: HTTP {error.code}")
        print(error.read().decode("utf-8", errors="replace"))
        return

    except Exception as error:
        print(f"Model access error: {error}")
        return

    # STEP 2: Test text generation.
    print("\nSTEP 2: Testing JSON generation...")
    print("---------------------------------")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return only a valid JSON object. "
                    "Do not include Markdown or explanations."
                ),
            },
            {
                "role": "user",
                "content": (
                    'Return this JSON: {"status": "connected", '
                    '"message": "Groq API connection successful."}'
                ),
            },
        ],
        "response_format": {
            "type": "json_object"
        },
    }

    try:
        result = send_request(
            f"{base_url}/chat/completions",
            api_key,
            payload,
        )

        content = result["choices"][0]["message"]["content"]

        print("Generation successful!")
        print("\nGroq response:")
        print(content)

        parsed = json.loads(content)

        print("\nJSON validation: SUCCESS")
        print(json.dumps(parsed, indent=4))

    except urllib.error.HTTPError as error:
        print(f"Generation failed: HTTP {error.code}")
        print(
            "Provider response:",
            error.read().decode("utf-8", errors="replace"),
        )

    except json.JSONDecodeError as error:
        print(f"Invalid JSON response: {error}")

    except Exception as error:
        print(f"Generation error: {error}")


if __name__ == "__main__":
    test_groq_connection()
