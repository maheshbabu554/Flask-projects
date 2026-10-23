"""
WeatherApp - Flask + MySQL + Open-Meteo (free weather API, no API key needed)
Simple student project. Sections:
  1. Database helpers
  2. Weather (Open-Meteo) helpers
  3. Login / Register / Logout
  4. Pages (dashboard, search, cities, history, settings)
  5. API routes (JSON, used by script.js)
  6. Error handlers
"""
import re
from datetime import datetime
from functools import wraps

import mysql.connector
import requests
from flask import (Flask, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Open-Meteo gives a "weather code" (WMO). Here we turn it into text + an icon.
# icon = Bootstrap Icons name + a color class (wi-...) from style.css
WEATHER_CODES = {
    0: ("Sunny", "bi-sun-fill wi-sun"),
    1: ("Mainly Clear", "bi-brightness-high-fill wi-sun"),
    2: ("Partly Cloudy", "bi-cloud-sun-fill wi-sun"),
    3: ("Cloudy", "bi-cloud-fill wi-cloud"),
    45: ("Fog", "bi-cloud-fog2-fill wi-fog"),
    48: ("Freezing Fog", "bi-cloud-fog2-fill wi-fog"),
    51: ("Light Drizzle", "bi-cloud-drizzle-fill wi-rain"),
    53: ("Drizzle", "bi-cloud-drizzle-fill wi-rain"),
    55: ("Heavy Drizzle", "bi-cloud-drizzle-fill wi-rain"),
    56: ("Freezing Drizzle", "bi-cloud-drizzle-fill wi-rain"),
    57: ("Freezing Drizzle", "bi-cloud-drizzle-fill wi-rain"),
    61: ("Light Rain", "bi-cloud-rain-fill wi-rain"),
    63: ("Rain", "bi-cloud-rain-fill wi-rain"),
    65: ("Heavy Rain", "bi-cloud-rain-heavy-fill wi-rain"),
    66: ("Freezing Rain", "bi-cloud-rain-fill wi-rain"),
    67: ("Freezing Rain", "bi-cloud-rain-heavy-fill wi-rain"),
    71: ("Light Snow", "bi-cloud-snow-fill wi-snow"),
    73: ("Snow", "bi-cloud-snow-fill wi-snow"),
    75: ("Heavy Snow", "bi-cloud-snow-fill wi-snow"),
    77: ("Snow Grains", "bi-cloud-snow-fill wi-snow"),
    80: ("Light Showers", "bi-cloud-rain-fill wi-rain"),
    81: ("Showers", "bi-cloud-rain-heavy-fill wi-rain"),
    82: ("Heavy Showers", "bi-cloud-rain-heavy-fill wi-rain"),
    85: ("Snow Showers", "bi-cloud-snow-fill wi-snow"),
    86: ("Heavy Snow Showers", "bi-cloud-snow-fill wi-snow"),
    95: ("Thunderstorm", "bi-cloud-lightning-rain-fill wi-storm"),
    96: ("Thunderstorm With Hail", "bi-cloud-lightning-rain-fill wi-storm"),
    99: ("Thunderstorm With Hail", "bi-cloud-lightning-rain-fill wi-storm"),
}


# =====================================================================
# 1. DATABASE HELPERS
# =====================================================================
def run_query(sql, params=(), fetch="all"):
    """
    Run ONE SQL query using %s placeholders (safe from SQL injection).
      fetch="all"  -> returns a list of rows (dictionaries)
      fetch="one"  -> returns one row or None
      fetch="none" -> for INSERT / UPDATE / DELETE (commits changes)
    """
    db = mysql.connector.connect(**config.DB_CONFIG)
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute(sql, params)
        if fetch == "all":
            result = cursor.fetchall()
        elif fetch == "one":
            result = cursor.fetchone()
        else:
            db.commit()
            result = cursor.rowcount
        cursor.close()
        return result
    finally:
        db.close()


# =====================================================================
# 2. WEATHER HELPERS (Open-Meteo API)
# =====================================================================
class WeatherError(Exception):
    """Raised with a friendly message when weather data cannot be loaded."""


def call_open_meteo(url, params):
    """Call Open-Meteo and return JSON. Raises WeatherError on any problem."""
    try:
        response = requests.get(url, params=params, timeout=8)
    except requests.exceptions.Timeout:
        raise WeatherError("The weather service took too long to respond. Please try again.")
    except requests.exceptions.RequestException:
        raise WeatherError("Could not reach the weather service. Check your internet connection.")

    if response.status_code == 429:
        raise WeatherError("Too many weather requests. Please wait a minute and try again.")
    if response.status_code != 200:
        raise WeatherError("The weather service had a problem. Please try again later.")
    try:
        return response.json()
    except ValueError:
        raise WeatherError("The weather service sent an unexpected reply.")


def describe_weather(code, is_day=1):
    """Weather code -> (text, icon classes). Uses a moon icon at night."""
    text, icon = WEATHER_CODES.get(code, ("Unknown", "bi-cloud-fill wi-cloud"))
    if not is_day:
        if code == 0:
            text, icon = "Clear", "bi-moon-stars-fill wi-moon"
        elif code in (1, 2):
            icon = "bi-cloud-moon-fill wi-moon"
    return text, icon


def find_place(city):
    """
    Look up a city name. Accepts "Hyderabad" or "Hyderabad,IN" (name,country code).
    Returns a dictionary: name, state, country, country_code, lat, lon.
    """
    city = (city or "").strip()
    if not city:
        raise WeatherError("Please enter a city name.")
    if len(city) > 100:
        raise WeatherError("That city name is too long.")

    name, _, country_code = city.partition(",")
    name = name.strip()
    country_code = country_code.strip().upper()
    if not name:
        raise WeatherError("Please enter a city name.")

    data = call_open_meteo(GEOCODING_URL, {"name": name, "count": 10,
                                           "language": "en", "format": "json"})
    results = data.get("results") or []
    if not results:
        raise WeatherError(f'City "{name}" was not found. Check the spelling and try again.')

    place = results[0]
    if country_code:  # prefer the result from the requested country
        for item in results:
            if item.get("country_code", "").upper() == country_code:
                place = item
                break

    return {
        "name": place["name"],
        "state": place.get("admin1", ""),
        "country": place.get("country", place.get("country_code", "")),
        "country_code": place.get("country_code", ""),
        "lat": place["latitude"],
        "lon": place["longitude"],
    }


def uv_text(value):
    """UV number -> text like '6 (High)'."""
    if value is None:
        return "N/A"
    value = round(float(value), 1)
    if value < 3:
        label = "Low"
    elif value < 6:
        label = "Moderate"
    elif value < 8:
        label = "High"
    elif value < 11:
        label = "Very High"
    else:
        label = "Extreme"
    return f"{value:g} ({label})"


def get_weather(city):
    """Get current weather + 5-day forecast for a city (all values from the API)."""
    place = find_place(city)
    
    data = call_open_meteo(FORECAST_URL, {
        "latitude": place["lat"],
        "longitude": place["lon"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                   "is_day,weather_code,pressure_msl,wind_speed_10m,visibility,dew_point_2m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "sunrise,sunset,uv_index_max",
        "wind_speed_unit": "kmh",   # km/
        "timezone": "auto",         # times are in the city's own time zone
        "forecast_days": 5,
      
    })

    try:
        current = data["current"]
        daily = data["daily"]

        local_time = datetime.fromisoformat(current["time"])
        text, icon = describe_weather(current["weather_code"], current.get("is_day", 1))

        visibility = current.get("visibility")  # metres
        if visibility is None:
            visibility_text = "N/A"
        else:
            km = visibility / 1000
            visibility_text = f"{int(km) if km == int(km) else round(km, 1)} km"

        # 5 forecast cards (first card = today)
        forecast = []
        for i, day_text in enumerate(daily["time"]):
            day = datetime.strptime(day_text, "%Y-%m-%d")
            day_condition, day_icon = describe_weather(daily["weather_code"][i])
            forecast.append({
                "day": day.strftime("%a"),
                "date": day.strftime("%d %b"),
                "max": round(daily["temperature_2m_max"][i]),
                "min": round(daily["temperature_2m_min"][i]),
                "icon": day_icon,
                "condition": day_condition,
            })

        return {
            "city": place["name"],
            "state": place["state"],
            "country": place["country"],
            "country_code": place["country_code"],
            "date": local_time.strftime("%a, %d %b %Y"),
            "time": local_time.strftime("%I:%M %p"),
            "temp": round(current["temperature_2m"]),
            "feels_like": round(current["apparent_temperature"]),
            "humidity":round(current["relative_humidity_2m"]),
            "Dewpoint":round(current["dew_point_2m"]),
            "pressure": round(current["pressure_msl"]),
            "wind": round(current["wind_speed_10m"]),
            "visibility": visibility_text,
            "condition": text,
            "icon": icon,
            "sunrise": datetime.fromisoformat(daily["sunrise"][0]).strftime("%I:%M %p"),
            "sunset": datetime.fromisoformat(daily["sunset"][0]).strftime("%I:%M %p"),
            "uv": uv_text(daily["uv_index_max"][0]),
            "forecast": forecast,
            
        }
    except (KeyError, IndexError, TypeError, ValueError):
        raise WeatherError("The weather service sent incomplete data. Please try again.")


def load_weather(city, save_history=False):
    """Returns (weather, error_message). Optionally saves the search to history."""
    try:
        weather = get_weather(city)
    except WeatherError as error:
        return None, str(error)
    if save_history:
        run_query(
            "INSERT INTO search_history (user_id, city, country) VALUES (%s, %s, %s)",
            (session["user_id"], weather["city"], weather["country_code"]), "none")
    return weather, None


def get_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good Morning"
    if hour < 17:
        return "Good Afternoon"
    return "Good Evening"


def default_city():
    """The user's first saved city, or the default city from config.py."""
    row = run_query(
        "SELECT city, country FROM saved_cities WHERE user_id = %s ORDER BY id LIMIT 1",
        (session["user_id"],), "one")
    if row:
        return f"{row['city']},{row['country']}"
    return config.DEFAULT_CITY


# =====================================================================
# 3. LOGIN / REGISTER / LOGOUT
# =====================================================================
def login_required(view):
    """Put @login_required under @app.route to protect a page."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify(ok=False, error="Please log in first."), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        # Validate the form
        error = None
        if len(name) < 2 or len(name) > 100:
            error = "Please enter your name (at least 2 characters)."
        elif not EMAIL_PATTERN.match(email) or len(email) > 150:
            error = "Please enter a valid email address."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm:
            error = "Passwords do not match."
        elif run_query("SELECT id FROM users WHERE email = %s", (email,), "one"):
            error = "An account with this email already exists."

        if error:
            flash(error, "error")
        else:
            try:
                run_query(
                    "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                    (name, email, generate_password_hash(password)), "none")
            except mysql.connector.IntegrityError:  # email taken at the same moment
                flash("An account with this email already exists.", "error")
                return render_template("register.html")
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter your email and password.", "error")
        else:
            user = run_query("SELECT * FROM users WHERE email = %s", (email,), "one")
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                return redirect(url_for("dashboard"))
            flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# =====================================================================
# 4. PAGES
# =====================================================================
@app.route("/dashboard")
@login_required
def dashboard():
    city = request.args.get("city", "").strip()
    searched = city != ""
    empty_search = "city" in request.args and not searched
    if not searched:
        city = default_city()

    weather, error = load_weather(city, save_history=searched)
    if empty_search:
        error = "Please enter a city name."
    return render_template("dashboard.html", weather=weather, error=error,
                           greeting=get_greeting(), show_highlights=True)


@app.route("/search")
@login_required
def search():
    city = request.args.get("city", "").strip()
    weather = error = None
    if city:
        weather, error = load_weather(city, save_history=True)
    elif "city" in request.args:
        error = "Please enter a city name."
    return render_template("search.html", weather=weather, error=error,
                           show_highlights=False)


@app.route("/cities")
@login_required
def cities():
    # Only this user's cities (user_id check)
    rows = run_query("SELECT id, city, country FROM saved_cities "
                     "WHERE user_id = %s ORDER BY id", (session["user_id"],))
    return render_template("cities.html", cities=rows)


@app.route("/cities/add", methods=["POST"])
@login_required
def cities_add():
    try:
        place = find_place(request.form.get("city", ""))
    except WeatherError as error:
        flash(str(error), "error")
        return redirect(url_for("cities"))

    try:
        run_query("INSERT INTO saved_cities (user_id, city, country) VALUES (%s, %s, %s)",
                  (session["user_id"], place["name"], place["country_code"]), "none")
        flash(f"{place['name']} was added to My Cities.", "success")
    except mysql.connector.IntegrityError:  # UNIQUE (user_id, city, country)
        flash(f"{place['name']} is already in your list.", "error")
    return redirect(url_for("cities"))


@app.route("/cities/remove/<int:city_id>", methods=["POST"])
@login_required
def cities_remove(city_id):
    # "AND user_id" makes sure users can only delete their OWN cities
    deleted = run_query("DELETE FROM saved_cities WHERE id = %s AND user_id = %s",
                        (city_id, session["user_id"]), "none")
    flash("City removed." if deleted else "City not found.",
          "success" if deleted else "error")
    return redirect(url_for("cities"))


@app.route("/history")
@login_required
def history():
    rows = run_query("SELECT city, country, searched_at FROM search_history "
                     "WHERE user_id = %s ORDER BY searched_at DESC, id DESC LIMIT 30",
                     (session["user_id"],))
    return render_template("history.html", history=rows)


@app.route("/settings")
@login_required
def settings():
    user = run_query("SELECT name, email FROM users WHERE id = %s",
                     (session["user_id"],), "one")
    return render_template("settings.html", user=user)


# =====================================================================
# 5. API ROUTES (return JSON)
# =====================================================================
@app.route("/api/weather")
@login_required
def api_weather():
    try:
        return jsonify(ok=True, weather=get_weather(request.args.get("city", "")))
    except WeatherError as error:
        return jsonify(ok=False, error=str(error)), 400


@app.route("/api/cities")
@login_required
def api_cities():
    rows = run_query("SELECT id, city, country FROM saved_cities "
                     "WHERE user_id = %s ORDER BY id", (session["user_id"],))
    return jsonify(ok=True, cities=rows)


@app.route("/api/history")
@login_required
def api_history():
    rows = run_query("SELECT city, country, searched_at FROM search_history "
                     "WHERE user_id = %s ORDER BY searched_at DESC, id DESC LIMIT 30",
                     (session["user_id"],))
    return jsonify(ok=True, history=rows)


# =====================================================================
# 6. ERROR HANDLERS (friendly messages, no raw Python errors)
# =====================================================================
@app.errorhandler(mysql.connector.Error)
def database_error(error):
    app.logger.error("MySQL error: %s", error)
    message = ("Could not connect to the database. Make sure MySQL is running "
               "and your .env settings are correct.")
    if request.path.startswith("/api/"):
        return jsonify(ok=False, error=message), 500
    return f"<h2>Database error</h2><p>{message}</p>", 500


@app.errorhandler(404)
def not_found(error):
    return "<h2>Page not found</h2><p><a href='/'>Go back home</a></p>", 404


@app.errorhandler(500)
def server_error(error):
    return "<h2>Something went wrong</h2><p><a href='/'>Go back home</a></p>", 500


if __name__ == "__main__":
    app.run(debug=True)
