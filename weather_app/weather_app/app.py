"""
app.py
------
Main file of the Weather App (Flask backend).

Run it with:   python app.py
Then open:     http://127.0.0.1:5000

How the app is organised
~~~~~~~~~~~~~~~~~~~~~~~~
* PAGE routes  (/, /search, /cities, /history, /settings)
      -> only return an HTML page.
* API routes   (/api/...)
      -> return JSON. The JavaScript (fetch) calls these.

HTTP status codes (important!)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* 200 / 201 -> everything is fine
* 400       -> wrong data sent by the user  (e.g. city "123")
* 404       -> city not found
* 409       -> city is already saved
* 503       -> Open-Meteo is not reachable
Wrong city / wrong data NEVER returns 200, so the terminal shows
400 / 404 instead of "200 OK".
"""
from flask import Flask, jsonify, render_template, request

import database as db
import validators as check
from config import Config
from weather_service import (
    CityNotFoundError,
    WeatherServiceError,
    get_brief_weather,
    get_weather,
    search_cities,
)

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)  # create the tables if they do not exist


# ======================================================================
# Small helper functions
# ======================================================================
def error_response(message, status):
    """Build a JSON error answer, e.g. error_response("Bad city", 400)."""
    return jsonify({"success": False, "message": message}), status


def current_unit():
    """Temperature unit chosen on the Settings page ('C' or 'F')."""
    return db.get_setting("unit", "C")


def save_history(place):
    """Store a successful search and keep only the latest N rows."""
    conn = db.get_db()
    conn.execute(
        "INSERT INTO search_history (name, region, country, latitude, longitude) "
        "VALUES (?, ?, ?, ?, ?)",
        (place["name"], place["region"], place["country"],
         place["latitude"], place["longitude"]),
    )
    conn.execute(
        "DELETE FROM search_history WHERE id NOT IN "
        "(SELECT id FROM search_history ORDER BY id DESC LIMIT ?)",
        (app.config["MAX_HISTORY"],),
    )
    conn.commit()


# ======================================================================
# PAGE ROUTES  (return HTML)
# ======================================================================
@app.get("/")
def home_page():
    """Home page: current weather of the default city."""
    return render_template(
        "home.html", active="home",
        user_name=app.config["USER_NAME"],
        default_city=app.config["DEFAULT_CITY"],
    )


@app.get("/search")
def search_page():
    """Search page: search any city and see its weather."""
    return render_template("search.html", active="search")


@app.get("/cities")
def cities_page():
    """My Cities page: list of saved cities."""
    return render_template("cities.html", active="cities")


@app.get("/history")
def history_page():
    """History page: list of previous searches."""
    return render_template("history.html", active="history")


@app.get("/settings")
def settings_page():
    """Settings page: temperature unit and data clean-up."""
    return render_template(
        "settings.html", active="settings",
        user_name=app.config["USER_NAME"], unit=current_unit(),
    )


# ======================================================================
# API: dropdown suggestions
# ======================================================================
@app.get("/api/suggest")
def api_suggest():
    """Return all cities matching the typed text (for the dropdown).

    Example: /api/suggest?q=anan  ->  Anantapur, Anand, Anantnag ...
    """
    text, error = check.validate_search_text(request.args.get("q"))
    if error:
        return error_response(error, 400)

    try:
        places = search_cities(text, app.config["MAX_SUGGESTIONS"])
    except CityNotFoundError:
        return error_response(check.CITY_NOT_FOUND, 404)
    except WeatherServiceError as problem:
        return error_response(str(problem), 503)

    return jsonify({"success": True, "places": places})


# ======================================================================
# API: weather
# ======================================================================
@app.get("/api/weather")
def api_weather():
    """Return the weather of one city.

    Two ways to call it:
      1) By name         : /api/weather?city=Hyderabad
      2) By coordinates  : /api/weather?lat=17.38&lon=78.47&name=Hyderabad
         (used when the user clicks a city in the dropdown)

    Optional:  record=0  -> do not save this search in History.
    """
    args = request.args

    # --- validate the optional "record" flag
    record = args.get("record", "1")
    if record not in ("0", "1"):
        return error_response("Invalid request data.", 400)

    # --- find out WHICH place we need
    if "lat" in args or "lon" in args:
        # Way 2: coordinates (validated on the server!)
        place, error = check.validate_place(
            args.get("name"), args.get("region"), args.get("country"),
            args.get("lat"), args.get("lon"),
        )
        if error:
            return error_response(error, 400)
    else:
        # Way 1: city name
        city, error = check.validate_city_name(args.get("city"))
        if error:
            return error_response(error, 400)
        try:
            place = search_cities(city, 1)[0]  # best match
        except CityNotFoundError:
            return error_response(check.CITY_NOT_FOUND, 404)
        except WeatherServiceError as problem:
            return error_response(str(problem), 503)

    # --- get the weather for that place
    try:
        weather = get_weather(place["latitude"], place["longitude"], current_unit())
    except WeatherServiceError as problem:
        return error_response(str(problem), 503)

    if record == "1":
        save_history(place)

    return jsonify({
        "success": True,
        "message": "City fetched successfully",
        "place": place,
        "weather": weather,
    })


# ======================================================================
# API: My Cities
# ======================================================================
@app.get("/api/cities")
def api_cities_list():
    """Return all saved cities together with their current temperature."""
    rows = db.get_db().execute("SELECT * FROM saved_cities ORDER BY id").fetchall()
    cities = [dict(row) for row in rows]
    unit = current_unit()

    if cities:
        try:
            for city, brief in zip(cities, get_brief_weather(cities, unit)):
                city.update(brief)
        except WeatherServiceError:
            pass  # show the cities without temperature

    return jsonify({"success": True, "cities": cities, "unit": unit})


@app.post("/api/cities")
def api_cities_add():
    """Save a city. Body (JSON): name, region, country, latitude, longitude."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("Invalid request data.", 400)

    place, error = check.validate_place(
        data.get("name"), data.get("region"), data.get("country"),
        data.get("latitude"), data.get("longitude"),
    )
    if error:
        return error_response(error, 400)

    conn = db.get_db()
    total = conn.execute("SELECT COUNT(*) FROM saved_cities").fetchone()[0]
    if total >= app.config["MAX_SAVED_CITIES"]:
        return error_response(
            f"You can save only {app.config['MAX_SAVED_CITIES']} cities.", 400)

    exists = conn.execute(
        "SELECT id FROM saved_cities WHERE latitude = ? AND longitude = ?",
        (place["latitude"], place["longitude"]),
    ).fetchone()
    if exists:
        return error_response(f"{place['name']} is already in My Cities.", 409)

    conn.execute(
        "INSERT INTO saved_cities (name, region, country, latitude, longitude) "
        "VALUES (?, ?, ?, ?, ?)",
        (place["name"], place["region"], place["country"],
         place["latitude"], place["longitude"]),
    )
    conn.commit()
    return jsonify({"success": True, "message": f"{place['name']} added to My Cities"}), 201


@app.delete("/api/cities/<int:city_id>")
def api_cities_delete(city_id):
    """Remove one saved city."""
    conn = db.get_db()
    cursor = conn.execute("DELETE FROM saved_cities WHERE id = ?", (city_id,))
    conn.commit()
    if cursor.rowcount == 0:
        return error_response("City not found in My Cities.", 404)
    return jsonify({"success": True, "message": "City removed"})


@app.delete("/api/cities")
def api_cities_clear():
    """Remove ALL saved cities."""
    conn = db.get_db()
    conn.execute("DELETE FROM saved_cities")
    conn.commit()
    return jsonify({"success": True, "message": "All cities removed"})


# ======================================================================
# API: History
# ======================================================================
@app.get("/api/history")
def api_history_list():
    """Return previous searches, newest first."""
    rows = db.get_db().execute(
        "SELECT * FROM search_history ORDER BY id DESC"
    ).fetchall()
    return jsonify({"success": True, "history": [dict(row) for row in rows]})


@app.delete("/api/history")
def api_history_clear():
    """Delete the whole search history."""
    conn = db.get_db()
    conn.execute("DELETE FROM search_history")
    conn.commit()
    return jsonify({"success": True, "message": "History cleared"})


# ======================================================================
# API: Settings
# ======================================================================
@app.post("/api/settings")
def api_settings_save():
    """Save the temperature unit. Body (JSON): {"unit": "C"} or {"unit": "F"}."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("Invalid request data.", 400)

    unit, error = check.validate_unit(data.get("unit"))
    if error:
        return error_response(error, 400)

    db.set_setting("unit", unit)
    return jsonify({"success": True, "message": "Settings saved", "unit": unit})


# ======================================================================
# Error pages (always answer API errors with JSON, never HTML)
# ======================================================================
@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return error_response("API address not found.", 404)
    return render_template("404.html", active=""), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return error_response("This method is not allowed here.", 405)


@app.errorhandler(500)
def server_error(error):
    return error_response("Something went wrong on the server.", 500)


if __name__ == "__main__":
    app.run(debug=True)
