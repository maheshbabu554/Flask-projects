"""
weather_service.py
------------------
Everything that talks to the Open-Meteo API lives here.
(Keeping it in its own file keeps app.py short and easy to read.)

Two Open-Meteo APIs are used (both free, no API key):
    1. Geocoding API : city name  -> latitude / longitude
    2. Forecast API  : latitude / longitude -> weather data
"""
from datetime import date, datetime

import requests
from flask import current_app

# Weather code (from Open-Meteo) -> (text, icon name used by the JavaScript)
WEATHER_CODES = {
    0: ("Clear Sky", "sunny"),
    1: ("Mainly Clear", "sunny"),
    2: ("Partly Cloudy", "partly"),
    3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"),
    48: ("Fog", "fog"),
    51: ("Light Drizzle", "rain"),
    53: ("Drizzle", "rain"),
    55: ("Heavy Drizzle", "rain"),
    56: ("Freezing Drizzle", "rain"),
    57: ("Freezing Drizzle", "rain"),
    61: ("Light Rain", "rain"),
    63: ("Rain", "rain"),
    65: ("Heavy Rain", "rain"),
    66: ("Freezing Rain", "rain"),
    67: ("Freezing Rain", "rain"),
    71: ("Light Snow", "snow"),
    73: ("Snow", "snow"),
    75: ("Heavy Snow", "snow"),
    77: ("Snow Grains", "snow"),
    80: ("Light Showers", "rain"),
    81: ("Showers", "rain"),
    82: ("Heavy Showers", "rain"),
    85: ("Snow Showers", "snow"),
    86: ("Snow Showers", "snow"),
    95: ("Thunderstorm", "storm"),
    96: ("Thunderstorm", "storm"),
    99: ("Thunderstorm", "storm"),
}


class CityNotFoundError(Exception):
    """Raised when Open-Meteo has no city with the given name."""


class WeatherServiceError(Exception):
    """Raised when Open-Meteo cannot be reached or sends bad data."""


# ---------------------------------------------------------------- helpers
def describe_code(code):
    """Turn a weather code into (description, icon_name)."""
    return WEATHER_CODES.get(code, ("Unknown", "cloudy"))


def uv_label(value):
    """Turn a UV number into a word (e.g. 6 -> 'High')."""
    if value < 3:
        return "Low"
    if value < 6:
        return "Moderate"
    if value < 8:
        return "High"
    if value < 11:
        return "Very High"
    return "Extreme"


def format_clock(iso_text):
    """'2026-10-16T06:12' -> '06:12 AM'."""
    return datetime.fromisoformat(iso_text).strftime("%I:%M %p")


def format_date(iso_text):
    """'2026-10-16T11:00' -> 'Fri, 16 Oct 2026'."""
    d = datetime.fromisoformat(iso_text)
    # d.day is used (not %d) so there is no leading zero, on every OS
    return f"{d.strftime('%a')}, {d.day} {d.strftime('%b %Y')}"


def _get_json(url, params):
    """Call an Open-Meteo URL and return the JSON answer.

    Any network problem is converted into WeatherServiceError so the
    rest of the code only has to handle one kind of error.
    """
    try:
        response = requests.get(
            url, params=params, timeout=current_app.config["REQUEST_TIMEOUT"]
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        raise WeatherServiceError("Weather service is not available right now.")


# ------------------------------------------------------------ geocoding
def search_cities(text, count=8):
    """Find cities whose name matches ``text`` (used by dropdown + search).

    Returns a list like:
        [{"name": "Anantapur", "region": "Andhra Pradesh",
          "country": "India", "latitude": 14.68, "longitude": 77.6}, ...]
    Raises CityNotFoundError when nothing matches.
    """
    data = _get_json(
        current_app.config["GEOCODING_URL"],
        {"name": text, "count": count, "language": "en", "format": "json"},
    )

    places = []
    seen = set()
    for item in data.get("results") or []:
        try:
            place = {
                "name": item["name"],
                "region": item.get("admin1", ""),
                "country": item.get("country", ""),
                "latitude": round(float(item["latitude"]), 4),
                "longitude": round(float(item["longitude"]), 4),
            }
        except (KeyError, TypeError, ValueError):
            continue  # skip broken rows

        key = (place["name"], place["region"], place["country"])
        if key not in seen:  # remove duplicates
            seen.add(key)
            places.append(place)

    if not places:
        raise CityNotFoundError(text)
    return places


# -------------------------------------------------------------- weather
def get_weather(lat, lon, unit="C"):
    """Get the full weather (now + highlights + 5 day forecast).

    ``unit`` is "C" or "F". The returned dictionary is exactly what the
    JavaScript needs, so the browser does no calculations.
    """
    data = _get_json(
        current_app.config["FORECAST_URL"],
        {
            "latitude": lat,
            "longitude": lon,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,surface_pressure,wind_speed_10m,is_day,visibility"
            ),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "sunrise,sunset,uv_index_max"
            ),
            "timezone": "auto",
            "forecast_days": 5,
            "temperature_unit": "fahrenheit" if unit == "F" else "celsius",
        },
    )

    try:
        now = data["current"]
        daily = data["daily"]
        description, icon = describe_code(now["weather_code"])
        uv = daily["uv_index_max"][0] or 0
        visibility_km = round((now.get("visibility") or 0) / 1000, 1)

        forecast = []
        for i, day_text in enumerate(daily["time"]):
            day = date.fromisoformat(day_text)
            day_desc, day_icon = describe_code(daily["weather_code"][i])
            forecast.append({
                "day": day.strftime("%a"),
                "date": f"{day.day} {day.strftime('%b')}",
                "icon": day_icon,
                "description": day_desc,
                "max": round(daily["temperature_2m_max"][i]),
                "min": round(daily["temperature_2m_min"][i]),
            })

        return {
            "unit": unit,
            "current": {
                "temperature": round(now["temperature_2m"]),
                "feels_like": round(now["apparent_temperature"]),
                "humidity": round(now["relative_humidity_2m"]),
                "wind": round(now["wind_speed_10m"]),
                "pressure": round(now["surface_pressure"]),
                "description": description,
                "icon": icon,
                "is_day": bool(now["is_day"]),
                "date_text": format_date(now["time"]),
                "time_text": format_clock(now["time"]),
            },
            "highlights": {
                "sunrise": format_clock(daily["sunrise"][0]),
                "sunset": format_clock(daily["sunset"][0]),
                "uv_index": round(uv),
                "uv_text": uv_label(uv),
                "visibility": f"{visibility_km:g}",
            },
            "forecast": forecast,
        }
    except (KeyError, TypeError, ValueError, IndexError):
        raise WeatherServiceError("Weather service sent unexpected data.")


def get_brief_weather(places, unit="C"):
    """Get only the current temperature for MANY places in ONE request.

    Used by the "My Cities" page so it loads fast.
    Returns a list (same order as ``places``) of small dictionaries.
    """
    data = _get_json(
        current_app.config["FORECAST_URL"],
        {
            "latitude": ",".join(str(p["latitude"]) for p in places),
            "longitude": ",".join(str(p["longitude"]) for p in places),
            "current": "temperature_2m,weather_code,is_day",
            "timezone": "auto",
            "temperature_unit": "fahrenheit" if unit == "F" else "celsius",
        },
    )
    if isinstance(data, dict):  # one place -> Open-Meteo sends a single object
        data = [data]

    try:
        result = []
        for item in data:
            now = item["current"]
            description, icon = describe_code(now["weather_code"])
            result.append({
                "temperature": round(now["temperature_2m"]),
                "icon": icon,
                "is_day": bool(now["is_day"]),
                "description": description,
            })
        return result
    except (KeyError, TypeError):
        raise WeatherServiceError("Weather service sent unexpected data.")
