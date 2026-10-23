"""
validators.py
-------------
SERVER-SIDE VALIDATION.

Never trust data coming from the browser: anyone can send any value
to our API (using Postman, curl, or by editing the JavaScript).
So every value is checked here before we use it.

Every function returns a pair:  (clean_value, error_message)
    * If the data is good  -> (value, None)
    * If the data is bad   -> (None, "message to show the user")
"""
import math
import re

# Message shown when a city is wrong / not found
CITY_NOT_FOUND = "City not found - incorrect city"

# A city must start with a letter and may then contain letters,
# spaces, dots, commas, hyphens and apostrophes. (No digits, no symbols.)
CITY_PATTERN = re.compile(r"^[^\W\d_](?:[^\W\d_]|[ .,'\-])*$")

# Characters that should never appear in a place label
BAD_LABEL_CHARS = re.compile(r"[<>{}\[\]\\\x00-\x1f]")

ALLOWED_UNITS = ("C", "F")


def validate_city_name(raw):
    """Check a city name typed by the user.

    Rules: 2-60 characters, letters / spaces / . , - ' only.
    Example: "Anantapur" is OK, "123" or "<script>" is rejected.
    """
    if raw is None:
        return None, "Please enter a city name."

    cleaned = " ".join(str(raw).split())  # remove extra spaces
    if not cleaned:
        return None, "Please enter a city name."
    if len(cleaned) < 2:
        return None, "City name must have at least 2 letters."
    if len(cleaned) > 60:
        return None, "City name is too long (maximum 60 characters)."
    if not CITY_PATTERN.match(cleaned):
        return None, CITY_NOT_FOUND

    # "Hyderabad, India" -> we only search for the part before the comma
    city_only = cleaned.split(",")[0].strip()
    if not city_only:
        return None, CITY_NOT_FOUND
    return city_only, None


def validate_coordinates(lat, lon):
    """Check latitude (-90 to 90) and longitude (-180 to 180)."""
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return None, "Latitude and longitude must be numbers."

    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None, "Latitude and longitude must be valid numbers."
    if not -90 <= lat <= 90:
        return None, "Latitude must be between -90 and 90."
    if not -180 <= lon <= 180:
        return None, "Longitude must be between -180 and 180."
    return (round(lat, 4), round(lon, 4)), None


def validate_label(value, label, required=False):
    """Check a text such as a region or a country name (max 80 chars)."""
    text = " ".join(str(value or "").split())
    if required and not text:
        return None, f"{label} is required."
    if len(text) > 80:
        return None, f"{label} is too long (maximum 80 characters)."
    if BAD_LABEL_CHARS.search(text):
        return None, f"{label} contains invalid characters."
    return text, None


def validate_place(name, region, country, lat, lon):
    """Check a complete place (name + region + country + coordinates)."""
    name, error = validate_label(name, "City name", required=True)
    if error:
        return None, error
    region, error = validate_label(region, "Region")
    if error:
        return None, error
    country, error = validate_label(country, "Country")
    if error:
        return None, error
    coords, error = validate_coordinates(lat, lon)
    if error:
        return None, error

    place = {
        "name": name,
        "region": region,
        "country": country,
        "latitude": coords[0],
        "longitude": coords[1],
    }
    return place, None


def validate_unit(value):
    """Temperature unit must be 'C' or 'F'."""
    value = str(value or "").strip().upper()
    if value not in ALLOWED_UNITS:
        return None, "Temperature unit must be C or F."
    return value, None


def validate_search_text(raw):
    """Check the text typed in the search box for the dropdown list.

    Only 2-60 letters / spaces / . - ' are allowed.
    """
    text = " ".join(str(raw or "").split())
    if len(text) < 2:
        return None, "Type at least 2 letters."
    if len(text) > 60 or not CITY_PATTERN.match(text):
        return None, CITY_NOT_FOUND
    return text, None
