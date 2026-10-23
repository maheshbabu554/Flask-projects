"""
Settings in one place. Real values come from the .env file.
Weather comes from Open-Meteo, which is free and needs NO API key.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # reads the .env file

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")

# MySQL connection settings
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "weather_app"),
    "connection_timeout": 5,
}

# City shown on the dashboard when the user has no saved cities
DEFAULT_CITY = "Hyderabad,IN"




