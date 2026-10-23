"""
WeatherApp - Flask + MySQL + SQLAlchemy ORM + Open-Meteo.
No login/register pages. A shared guest profile owns saved cities and history.
"""
from datetime import datetime
import re

import requests
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

import config

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = config.SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: ("Sunny", "bi-sun-fill wi-sun"), 1: ("Mainly Clear", "bi-brightness-high-fill wi-sun"),
    2: ("Partly Cloudy", "bi-cloud-sun-fill wi-sun"), 3: ("Cloudy", "bi-cloud-fill wi-cloud"),
    45: ("Fog", "bi-cloud-fog2-fill wi-fog"), 48: ("Freezing Fog", "bi-cloud-fog2-fill wi-fog"),
    51: ("Light Drizzle", "bi-cloud-drizzle-fill wi-rain"), 53: ("Drizzle", "bi-cloud-drizzle-fill wi-rain"),
    55: ("Heavy Drizzle", "bi-cloud-drizzle-fill wi-rain"), 56: ("Freezing Drizzle", "bi-cloud-drizzle-fill wi-rain"),
    57: ("Freezing Drizzle", "bi-cloud-drizzle-fill wi-rain"), 61: ("Light Rain", "bi-cloud-rain-fill wi-rain"),
    63: ("Rain", "bi-cloud-rain-fill wi-rain"), 65: ("Heavy Rain", "bi-cloud-rain-heavy-fill wi-rain"),
    66: ("Freezing Rain", "bi-cloud-rain-fill wi-rain"), 67: ("Freezing Rain", "bi-cloud-rain-heavy-fill wi-rain"),
    71: ("Light Snow", "bi-cloud-snow-fill wi-snow"), 73: ("Snow", "bi-cloud-snow-fill wi-snow"),
    75: ("Heavy Snow", "bi-cloud-snow-fill wi-snow"), 77: ("Snow Grains", "bi-cloud-snow-fill wi-snow"),
    80: ("Light Showers", "bi-cloud-rain-fill wi-rain"), 81: ("Showers", "bi-cloud-rain-heavy-fill wi-rain"),
    82: ("Heavy Showers", "bi-cloud-rain-heavy-fill wi-rain"), 85: ("Snow Showers", "bi-cloud-snow-fill wi-snow"),
    86: ("Heavy Snow Showers", "bi-cloud-snow-fill wi-snow"), 95: ("Thunderstorm", "bi-cloud-lightning-rain-fill wi-storm"),
    96: ("Thunderstorm With Hail", "bi-cloud-lightning-rain-fill wi-storm"),
    99: ("Thunderstorm With Hail", "bi-cloud-lightning-rain-fill wi-storm"),
}


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, default="WeatherApp Guest")
    email = db.Column(db.String(150), unique=True, nullable=False, default="guest@weatherapp.local")
    password_hash = db.Column(db.String(255), nullable=False, default="not-used")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SavedCity(db.Model):
    __tablename__ = "saved_cities"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "city", "country", name="unique_user_city"),)


class SearchHistory(db.Model):
    __tablename__ = "search_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(10), nullable=False)
    searched_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class WeatherError(Exception):
    """A friendly, user-facing weather/geocoding error."""


def ensure_guest():
    """Create a shared guest profile to preserve existing user_id relationships."""
    guest = User.query.filter_by(email="guest@weatherapp.local").first()
    if guest is None:
        guest = User(name="WeatherApp Guest", email="guest@weatherapp.local", password_hash="not-used")
        db.session.add(guest)
        db.session.commit()
    return guest


def api_json(url, params):
    try:
        response = requests.get(url, params=params, timeout=8)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout as exc:
        raise WeatherError("The weather service took too long to respond. Please try again.") from exc
    except requests.exceptions.RequestException as exc:
        raise WeatherError("Could not reach the weather service. Check your internet connection.") from exc
    except ValueError as exc:
        raise WeatherError("The weather service sent an unexpected reply.") from exc


def describe_weather(code, is_day=1):
    text, icon = WEATHER_CODES.get(code, ("Unknown", "bi-cloud-fill wi-cloud"))
    if not is_day:
        if code == 0:
            return "Clear", "bi-moon-stars-fill wi-moon"
        if code in (1, 2):
            icon = "bi-cloud-moon-fill wi-moon"
    return text, icon


def find_places(query, count=10):
    query = (query or "").strip()
    if len(query) < 2:
        return []
    if len(query) > 100:
        raise WeatherError("City name is too long.")
    data = api_json(GEOCODING_URL, {"name": query, "count": count, "language": "en", "format": "json"})
    results = data.get("results") or []
    places = []
    for item in results:
        places.append({
            "name": item.get("name", ""),
            "state": item.get("admin1", ""),
            "country": item.get("country", item.get("country_code", "")),
            "country_code": item.get("country_code", ""),
            "lat": item["latitude"], "lon": item["longitude"],
        })
    return places


def find_place(city):
    city = (city or "").strip()
    if not city:
        raise WeatherError("Please enter a city name.")
    # Autocomplete values are encoded as "City|latitude|longitude|country_code".
    parts = city.split("|")
    if len(parts) == 4:
        name, lat, lon, country_code = parts
        try:
            return {"name": name, "state": "", "country": country_code, "country_code": country_code,
                    "lat": float(lat), "lon": float(lon)}
        except ValueError:
            pass
    name, comma, country_code = city.partition(",")
    name, country_code = name.strip(), country_code.strip().upper()
    if not name:
        raise WeatherError("Please enter a city name.")
    results = find_places(name, 10)
    if not results:
        raise WeatherError(f'City "{name}" was not found. Please check the spelling and try again.')
    place = results[0]
    if country_code:
        match = next((p for p in results if p["country_code"].upper() == country_code), None)
        if match:
            place = match
    return place


def uv_text(value):
    if value is None:
        return "N/A"
    value = round(float(value), 1)
    label = "Low" if value < 3 else "Moderate" if value < 6 else "High" if value < 8 else "Very High" if value < 11 else "Extreme"
    return f"{value:g} ({label})"


def get_weather(city):
    place = find_place(city)
    data = api_json(FORECAST_URL, {
        "latitude": place["lat"], "longitude": place["lon"],
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,pressure_msl,wind_speed_10m,visibility,dew_point_2m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max",
        "wind_speed_unit": "kmh", "timezone": "auto", "forecast_days": 5,
    })
    try:
        current, daily = data["current"], data["daily"]
        local_time = datetime.fromisoformat(current["time"])
        condition, icon = describe_weather(current["weather_code"], current.get("is_day", 1))
        visibility = current.get("visibility")
        visibility_text = "N/A" if visibility is None else f"{round(visibility / 1000, 1):g} km"
        forecast = []
        for i, date_text in enumerate(daily["time"]):
            day = datetime.strptime(date_text, "%Y-%m-%d")
            day_condition, day_icon = describe_weather(daily["weather_code"][i])
            forecast.append({"day": day.strftime("%a"), "date": day.strftime("%d %b"),
                             "max": round(daily["temperature_2m_max"][i]), "min": round(daily["temperature_2m_min"][i]),
                             "icon": day_icon, "condition": day_condition})
        return {
            "city": place["name"], "state": place["state"], "country": place["country"],
            "country_code": place["country_code"], "date": local_time.strftime("%a, %d %b %Y"),
            "time": local_time.strftime("%I:%M %p"), "temp": round(current["temperature_2m"]),
            "feels_like": round(current["apparent_temperature"]), "humidity": round(current["relative_humidity_2m"]),
            "Dewpoint": round(current["dew_point_2m"]), "pressure": round(current["pressure_msl"]),
            "wind": round(current["wind_speed_10m"]), "visibility": visibility_text, "condition": condition,
            "icon": icon, "sunrise": datetime.fromisoformat(daily["sunrise"][0]).strftime("%I:%M %p"),
            "sunset": datetime.fromisoformat(daily["sunset"][0]).strftime("%I:%M %p"),
            "uv": uv_text(daily["uv_index_max"][0]), "forecast": forecast,
        }
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise WeatherError("The weather service sent incomplete data. Please try again.") from exc


def save_search(weather):
    guest = ensure_guest()
    db.session.add(SearchHistory(user_id=guest.id, city=weather["city"], country=weather["country_code"]))
    db.session.commit()


def default_city():
    guest = ensure_guest()
    saved = SavedCity.query.filter_by(user_id=guest.id).order_by(SavedCity.id).first()
    return f"{saved.city},{saved.country}" if saved else config.DEFAULT_CITY


def greeting():
    hour = datetime.now().hour
    return "Good Morning" if hour < 12 else "Good Afternoon" if hour < 17 else "Good Evening"


@app.route("/")
def home():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    city = request.args.get("city", "").strip()
    searched = bool(city)
    empty_search = "city" in request.args and not searched
    city = city or default_city()
    weather = error = None
    try:
        weather = get_weather(city)
        if searched:
            save_search(weather)
            flash(f"{weather['city']} weather fetched successfully!", "success")
    except WeatherError as exc:
        error = "Please enter a city name." if empty_search else str(exc)
    return render_template("dashboard.html", weather=weather, error=error, greeting=greeting(), show_highlights=True)


@app.route("/search")
def search():
    city = request.args.get("city", "").strip()
    weather = error = None
    if city:
        try:
            weather = get_weather(city)
            save_search(weather)
            flash(f"{weather['city']} weather fetched successfully!", "success")
        except WeatherError as exc:
            error = str(exc)
    elif "city" in request.args:
        error = "Please enter a city name."
    return render_template("search.html", weather=weather, error=error, show_highlights=False)


@app.route("/api/suggestions")
def api_suggestions():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify(ok=True, suggestions=[])
    try:
        places = find_places(query, 8)
        suggestions = [{
            "label": ", ".join(part for part in [p["name"], p["state"], p["country"]] if part),
            "value": f"{p['name']}|{p['lat']}|{p['lon']}|{p['country_code']}",
            "name": p["name"], "state": p["state"], "country": p["country"]
        } for p in places]
        return jsonify(ok=True, suggestions=suggestions)
    except WeatherError as exc:
        return jsonify(ok=False, error=str(exc)), 503


@app.route("/cities")
def cities():
    guest = ensure_guest()
    rows = SavedCity.query.filter_by(user_id=guest.id).order_by(SavedCity.id).all()
    return render_template("cities.html", cities=rows)


@app.route("/cities/add", methods=["POST"])
def cities_add():
    try:
        place = find_place(request.form.get("city", ""))
        guest = ensure_guest()
        db.session.add(SavedCity(user_id=guest.id, city=place["name"], country=place["country_code"]))
        db.session.commit()
        flash(f"{place['name']} was added to My Cities.", "success")
    except WeatherError as exc:
        db.session.rollback()
        flash(str(exc), "error")
    except IntegrityError:
        db.session.rollback()
        flash("That city is already in your list.", "error")
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Could not save city")
        flash("Could not save the city. Check your database connection.", "error")
    return redirect(request.referrer or url_for("cities"))


@app.route("/cities/remove/<int:city_id>", methods=["POST"])
def cities_remove(city_id):
    guest = ensure_guest()
    city = SavedCity.query.filter_by(id=city_id, user_id=guest.id).first()
    if city:
        db.session.delete(city)
        db.session.commit()
        flash("City removed.", "success")
    else:
        flash("City not found.", "error")
    return redirect(url_for("cities"))


@app.route("/history")
def history():
    guest = ensure_guest()
    rows = SearchHistory.query.filter_by(user_id=guest.id).order_by(SearchHistory.searched_at.desc(), SearchHistory.id.desc()).limit(30).all()
    return render_template("history.html", history=rows)


@app.route("/settings")
def settings():
    guest = ensure_guest()
    return render_template("settings.html", user=guest)


@app.route("/api/weather")
def api_weather():
    try:
        weather = get_weather(request.args.get("city", ""))
        save_search(weather)
        return jsonify(ok=True, weather=weather, message=f"{weather['city']} weather fetched successfully!")
    except WeatherError as exc:
        return jsonify(ok=False, error=str(exc)), 400


@app.route("/api/cities")
def api_cities():
    guest = ensure_guest()
    rows = SavedCity.query.filter_by(user_id=guest.id).order_by(SavedCity.id).all()
    return jsonify(ok=True, cities=[{"id": c.id, "city": c.city, "country": c.country} for c in rows])


@app.route("/api/history")
def api_history():
    guest = ensure_guest()
    rows = SearchHistory.query.filter_by(user_id=guest.id).order_by(SearchHistory.searched_at.desc()).limit(30).all()
    return jsonify(ok=True, history=[{"city": h.city, "country": h.country, "searched_at": h.searched_at.isoformat()} for h in rows])


@app.errorhandler(SQLAlchemyError)
def database_error(error):
    db.session.rollback()
    app.logger.exception("Database error: %s", error)
    message = "Could not connect to MySQL. Check that MySQL is running and your .env settings are correct."
    if request.path.startswith("/api/"):
        return jsonify(ok=False, error=message), 500
    return render_template("error.html", message=message), 500


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", message="Page not found."), 404


with app.app_context():
    db.create_all()
    ensure_guest()


if __name__ == "__main__":
    app.run(debug=True)
