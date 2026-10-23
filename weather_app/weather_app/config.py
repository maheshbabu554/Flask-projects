"""
config.py
---------
All the settings of the Weather App live in this one file,
so you never have to hunt through the code to change something.
"""
import os

# Folder where this file is saved (used to build the database path)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Settings used by the Flask application."""

    SECRET_KEY = "change-this-secret-key"

    # SQLite database file (created automatically on first run)
    DATABASE_PATH = os.path.join(BASE_DIR, "weather.db")

    # Open-Meteo API addresses (free, no API key needed)
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    # How many seconds we wait for Open-Meteo before giving up
    REQUEST_TIMEOUT = 8

    # Name shown in the top-right corner ("Welcome Mahesh")
    USER_NAME = "Mahesh"

    # City shown on the Home page when it opens
    DEFAULT_CITY = "Hyderabad"

    # How many dropdown suggestions to show
    MAX_SUGGESTIONS = 8

    # History keeps only the latest N searches
    MAX_HISTORY = 50

    # Maximum number of saved cities in "My Cities"
    MAX_SAVED_CITIES = 20
