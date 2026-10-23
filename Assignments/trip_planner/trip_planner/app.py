
"""Trip Planner - Flask application with private user-owned trips."""

import os
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from mysql.connector import IntegrityError, Error

from database import get_connection, initialize_database


load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "development-key-change-me",
)

CATEGORIES = [
    "Sightseeing",
    "Food",
    "Adventure",
    "Culture",
    "Shopping",
    "Transport",
    "Stay",
    "Other",
]


# --------------------------------------------------
# DATABASE HELPERS
# --------------------------------------------------

def query_db(sql, params=(), one=False, commit=False):
    """Execute a parameterized SQL query and return its results."""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(sql, params)

        if one:
            result = cursor.fetchone()
        elif cursor.with_rows:
            result = cursor.fetchall()
        else:
            result = None

        if commit:
            connection.commit()

        return result

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


def execute_db(sql, params=()):
    """Execute an INSERT, UPDATE, or DELETE statement."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(sql, params)
        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()


# --------------------------------------------------
# LOGIN AND OWNERSHIP HELPERS
# --------------------------------------------------

def login_required(view):
    """Require the user to log in before accessing a page."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(
                url_for("login", next=request.path)
            )

        return view(*args, **kwargs)

    return wrapped


def owned_trip(trip_id):
    """Return a trip only if it belongs to the logged-in user."""
    trip = query_db(
        """
        SELECT *
        FROM trips
        WHERE id = %s AND user_id = %s
        """,
        (trip_id, session["user_id"]),
        one=True,
    )

    if not trip:
        abort(404)

    return trip


# --------------------------------------------------
# VALIDATION HELPERS
# --------------------------------------------------

def parse_date(value, label):
    """Convert a YYYY-MM-DD string into a date."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()

    except (ValueError, TypeError):
        raise ValueError(
            f"Please enter a valid {label.lower()}."
        )


def parse_money(value, label):
    """Validate a non-negative monetary amount."""
    try:
        amount = Decimal(value)

    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(
            f"{label} must be a valid number."
        )

    if not amount.is_finite() or amount < 0:
        raise ValueError(
            f"{label} cannot be negative."
        )

    if amount > Decimal("9999999999.99"):
        raise ValueError(
            f"{label} is too large."
        )

    return amount.quantize(Decimal("0.01"))


def get_trip_total(trip_id):
    """Calculate the total estimated cost of a trip."""
    row = query_db(
        """
        SELECT COALESCE(SUM(cost), 0) AS total
        FROM activities
        WHERE trip_id = %s
        """,
        (trip_id,),
        one=True,
    )

    return Decimal(str(row["total"] or 0))


# --------------------------------------------------
# TEMPLATE FILTERS
# --------------------------------------------------

@app.template_filter("money")
def money(value):
    """Format a value as Indian rupees."""
    return f"₹{Decimal(str(value or 0)):,.2f}"


@app.template_filter("pretty_date")
def pretty_date(value):
    """Format dates for display."""
    if isinstance(value, str):
        value = date.fromisoformat(value)

    return value.strftime("%d %b %Y")


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def home():
    """Display the home page."""
    return render_template("home.html")


# --------------------------------------------------
# REGISTRATION
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register a user with a securely hashed password."""
    if request.method == "POST":
        username = request.form.get(
            "username", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []

        if not 2 <= len(username) <= 50:
            errors.append(
                "Name must contain 2 to 50 characters."
            )

        if not re.fullmatch(
            r"[^\s@]+@[^\s@]+\.[^\s@]+",
            email,
        ):
            errors.append(
                "Enter a valid email address."
            )

        if len(password) < 8:
            errors.append(
                "Password must contain at least 8 characters."
            )

        if password != confirm:
            errors.append(
                "Passwords do not match."
            )

        if errors:
            for error in errors:
                flash(error, "danger")

            return render_template(
                "register.html",
                username=username,
                email=email,
            )

        try:
            user_id = execute_db(
                """
                INSERT INTO users
                    (username, email, password_hash)
                VALUES (%s, %s, %s)
                """,
                (
                    username,
                    email,
                    generate_password_hash(password),
                ),
            )

            session.clear()
            session["user_id"] = user_id
            session["username"] = username

            flash(
                "Your account is ready. Start planning your next trip!",
                "success",
            )

            return redirect(url_for("my_trips"))

        except IntegrityError:
            flash(
                "An account with this email already exists. Please log in.",
                "warning",
            )

        except Error:
            app.logger.exception(
                "Registration database error"
            )

            flash(
                "We could not create your account. "
                "Check the database configuration and try again.",
                "danger",
            )

    return render_template("register.html")


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate a user using email and password."""
    if request.method == "POST":
        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get("password", "")

        try:
            user = query_db(
                """
                SELECT id, username, email, password_hash
                FROM users
                WHERE email = %s
                """,
                (email,),
                one=True,
            )

        except Error:
            app.logger.exception(
                "Login database error"
            )

            flash(
                "Unable to log in right now. Please try again.",
                "danger",
            )

            return render_template("login.html")

        if user and check_password_hash(
            user["password_hash"],
            password,
        ):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            flash("Welcome back!", "success")

            next_url = request.args.get("next", "")

            if (
                next_url.startswith("/")
                and not next_url.startswith("//")
            ):
                return redirect(next_url)

            return redirect(url_for("my_trips"))

        flash(
            "Email or password is incorrect.",
            "danger",
        )

    return render_template("login.html")


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout", methods=["POST"])
def logout():
    """Log out the current user."""
    session.clear()

    flash(
        "You have been logged out.",
        "info",
    )

    return redirect(url_for("home"))


# --------------------------------------------------
# MY TRIPS
# --------------------------------------------------

@app.route("/trips")
@login_required
def my_trips():
    """Display only the signed-in user's trips."""
    trips = query_db(
        """
        SELECT
            t.*,
            COALESCE(SUM(a.cost), 0) AS total_cost,
            COUNT(a.id) AS activity_count
        FROM trips AS t
        LEFT JOIN activities AS a
            ON a.trip_id = t.id
        WHERE t.user_id = %s
        GROUP BY t.id
        ORDER BY t.start_date DESC, t.id DESC
        """,
        (session["user_id"],),
    )

    return render_template(
        "my_trips.html",
        trips=trips,
    )


# --------------------------------------------------
# TRIP VALIDATION
# --------------------------------------------------

def validate_trip_form(form):
    """Validate the trip destination, dates, and budget."""
    destination = form.get(
        "destination", ""
    ).strip()

    if not 2 <= len(destination) <= 120:
        raise ValueError(
            "Destination must contain 2 to 120 characters."
        )

    start = parse_date(
        form.get("start_date"),
        "Start date",
    )

    end = parse_date(
        form.get("end_date"),
        "End date",
    )

    if end < start:
        raise ValueError(
            "End date must be on or after the start date."
        )

    budget = parse_money(
        form.get("budget", ""),
        "Budget",
    )

    return destination, start, end, budget


# --------------------------------------------------
# CREATE TRIP
# --------------------------------------------------

@app.route("/trips/new", methods=["GET", "POST"])
@login_required
def create_trip():
    """Create a trip for the signed-in user."""
    if request.method == "POST":
        try:
            destination, start, end, budget = (
                validate_trip_form(request.form)
            )

            trip_id = execute_db(
                """
                INSERT INTO trips
                    (user_id, destination, start_date,
                     end_date, budget)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    session["user_id"],
                    destination,
                    start,
                    end,
                    budget,
                ),
            )

            flash(
                "Trip created successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "trip_detail",
                    trip_id=trip_id,
                )
            )

        except ValueError as error:
            flash(str(error), "danger")

        except Error:
            app.logger.exception(
                "Could not create trip"
            )

            flash(
                "Unable to save the trip. "
                "Please check your database configuration.",
                "danger",
            )

    return render_template(
        "trip_form.html",
        trip=None,
    )


# --------------------------------------------------
# TRIP DETAILS
# --------------------------------------------------

@app.route("/trips/<int:trip_id>")
@login_required
def trip_detail(trip_id):
    """Display a trip and its day-wise activities."""
    trip = owned_trip(trip_id)

    activities = query_db(
        """
        SELECT *,
               TIME_FORMAT(
                   activity_time, '%h:%i %p'
               ) AS display_time
        FROM activities
        WHERE trip_id = %s
        ORDER BY
            activity_date,
            activity_time IS NULL,
            activity_time,
            id
        """,
        (trip_id,),
    )

    by_day = {}

    for activity in activities:
        activity_day = activity["activity_date"]

        by_day.setdefault(
            activity_day, []
        ).append(activity)

    total = sum(
        (
            Decimal(str(item["cost"]))
            for item in activities
        ),
        Decimal("0.00"),
    )

    difference = (
        Decimal(str(trip["budget"])) - total
    )

    return render_template(
        "trip_detail.html",
        trip=trip,
        by_day=by_day,
        total=total,
        difference=difference,
        categories=CATEGORIES,
        today=date.today(),
    )


# --------------------------------------------------
# EDIT TRIP
# --------------------------------------------------

@app.route(
    "/trips/<int:trip_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_trip(trip_id):
    """Update a trip without leaving activities outside its dates."""
    trip = owned_trip(trip_id)

    if request.method == "POST":
        try:
            destination, start, end, budget = (
                validate_trip_form(request.form)
            )

            outside = query_db(
                """
                SELECT COUNT(*) AS count
                FROM activities
                WHERE trip_id = %s
                  AND (
                      activity_date < %s
                      OR activity_date > %s
                  )
                """,
                (trip_id, start, end),
                one=True,
            )["count"]

            if outside:
                raise ValueError(
                    f"These dates would leave {outside} "
                    "existing activity/activities outside "
                    "the trip. Edit or remove those activities first."
                )

            execute_db(
                """
                UPDATE trips
                SET destination = %s,
                    start_date = %s,
                    end_date = %s,
                    budget = %s
                WHERE id = %s AND user_id = %s
                """,
                (
                    destination,
                    start,
                    end,
                    budget,
                    trip_id,
                    session["user_id"],
                ),
            )

            flash(
                "Trip updated successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "trip_detail",
                    trip_id=trip_id,
                )
            )

        except ValueError as error:
            flash(str(error), "danger")

        except Error:
            app.logger.exception(
                "Could not update trip"
            )

            flash(
                "Unable to update the trip right now.",
                "danger",
            )

    return render_template(
        "trip_form.html",
        trip=trip,
    )


# --------------------------------------------------
# DELETE TRIP
# --------------------------------------------------

@app.route(
    "/trips/<int:trip_id>/delete",
    methods=["POST"],
)
@login_required
def delete_trip(trip_id):
    """Delete a trip belonging to the current user."""
    owned_trip(trip_id)

    execute_db(
        """
        DELETE FROM trips
        WHERE id = %s AND user_id = %s
        """,
        (trip_id, session["user_id"]),
    )

    flash(
        "Trip and its activities were deleted.",
        "info",
    )

    return redirect(url_for("my_trips"))


# --------------------------------------------------
# ACTIVITY VALIDATION
# --------------------------------------------------

def validate_activity_form(form, trip):
    """Validate an activity and its date, time, category, and cost."""
    name = form.get("name", "").strip()
    place = form.get("place", "").strip()
    category = form.get("category", "").strip()

    if not 2 <= len(name) <= 120:
        raise ValueError(
            "Activity name must contain 2 to 120 characters."
        )

    if not 2 <= len(place) <= 160:
        raise ValueError(
            "Place must contain 2 to 160 characters."
        )

    if category not in CATEGORIES:
        raise ValueError(
            "Choose a valid activity category."
        )

    activity_date = parse_date(
        form.get("activity_date"),
        "Activity date",
    )

    if not (
        trip["start_date"]
        <= activity_date
        <= trip["end_date"]
    ):
        raise ValueError(
            "Activity date must fall within this trip's "
            "start and end dates."
        )

    time_text = form.get(
        "activity_time", ""
    ).strip()

    if time_text:
        try:
            datetime.strptime(
                time_text, "%H:%M"
            )

        except ValueError:
            raise ValueError(
                "Enter a valid activity time."
            )

        activity_time = time_text

    else:
        activity_time = None

    cost = parse_money(
        form.get("cost", ""),
        "Estimated cost",
    )

    return (
        name,
        activity_date,
        activity_time,
        category,
        place,
        cost,
    )


def get_activity(trip_id, activity_id):
    """Find an activity belonging to the specified trip."""
    activity = query_db(
        """
        SELECT *,
               TIME_FORMAT(
                   activity_time, '%H:%i'
               ) AS time_value
        FROM activities
        WHERE id = %s AND trip_id = %s
        """,
        (activity_id, trip_id),
        one=True,
    )

    if not activity:
        abort(404)

    return activity


# --------------------------------------------------
# CREATE ACTIVITY
# --------------------------------------------------

@app.route(
    "/trips/<int:trip_id>/activities/new",
    methods=["GET", "POST"],
)
@login_required
def create_activity(trip_id):
    """Add an activity to an owned trip."""
    trip = owned_trip(trip_id)

    if request.method == "POST":
        try:
            values = validate_activity_form(
                request.form,
                trip,
            )

            execute_db(
                """
                INSERT INTO activities
                    (trip_id, name, activity_date,
                     activity_time, category, place, cost)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (trip_id, *values),
            )

            flash(
                "Activity added. Your total has been recalculated.",
                "success",
            )

            return redirect(
                url_for(
                    "trip_detail",
                    trip_id=trip_id,
                )
            )

        except ValueError as error:
            flash(str(error), "danger")

        except Error:
            app.logger.exception(
                "Could not add activity"
            )

            flash(
                "Unable to save the activity right now.",
                "danger",
            )

    return render_template(
        "activity_form.html",
        trip=trip,
        activity=None,
        categories=CATEGORIES,
    )


# --------------------------------------------------
# EDIT ACTIVITY
# --------------------------------------------------

@app.route(
    "/trips/<int:trip_id>/activities/<int:activity_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_activity(trip_id, activity_id):
    """Update an activity belonging to an owned trip."""
    trip = owned_trip(trip_id)

    activity = get_activity(
        trip_id,
        activity_id,
    )

    if request.method == "POST":
        try:
            values = validate_activity_form(
                request.form,
                trip,
            )

            execute_db(
                """
                UPDATE activities
                SET name = %s,
                    activity_date = %s,
                    activity_time = %s,
                    category = %s,
                    place = %s,
                    cost = %s
                WHERE id = %s AND trip_id = %s
                """,
                (
                    *values,
                    activity_id,
                    trip_id,
                ),
            )

            flash(
                "Activity updated. Your total has been recalculated.",
                "success",
            )

            return redirect(
                url_for(
                    "trip_detail",
                    trip_id=trip_id,
                )
            )

        except ValueError as error:
            flash(str(error), "danger")

        except Error:
            app.logger.exception(
                "Could not update activity"
            )

            flash(
                "Unable to update the activity right now.",
                "danger",
            )

    return render_template(
        "activity_form.html",
        trip=trip,
        activity=activity,
        categories=CATEGORIES,
    )


# --------------------------------------------------
# DELETE ACTIVITY
# --------------------------------------------------

@app.route(
    "/trips/<int:trip_id>/activities/<int:activity_id>/delete",
    methods=["POST"],
)
@login_required
def delete_activity(trip_id, activity_id):
    """Delete an activity from an owned trip."""
    owned_trip(trip_id)

    get_activity(
        trip_id,
        activity_id,
    )

    execute_db(
        """
        DELETE FROM activities
        WHERE id = %s AND trip_id = %s
        """,
        (activity_id, trip_id),
    )

    flash(
        "Activity removed and total recalculated.",
        "info",
    )

    return redirect(
        url_for(
            "trip_detail",
            trip_id=trip_id,
        )
    )


# --------------------------------------------------
# EXPLORE PLACES
# --------------------------------------------------

@app.route("/explore")
def explore():
    """Display public place suggestions with search and filtering."""
    search = request.args.get(
        "q", ""
    ).strip()[:120]

    category = request.args.get(
        "category", ""
    ).strip()

    conditions = []
    params = []

    if search:
        conditions.append(
            """
            (
                name LIKE %s
                OR destination LIKE %s
                OR description LIKE %s
            )
            """
        )

        pattern = f"%{search}%"

        params.extend([
            pattern,
            pattern,
            pattern,
        ])

    if category in CATEGORIES:
        conditions.append(
            "category = %s"
        )

        params.append(category)

    sql = "SELECT * FROM place_suggestions"

    if conditions:
        sql += " WHERE " + " AND ".join(
            conditions
        )

    sql += " ORDER BY destination, name"

    try:
        places = query_db(
            sql,
            tuple(params),
        )

    except Error:
        app.logger.exception(
            "Could not load Explore places"
        )

        flash(
            "Unable to load places right now.",
            "danger",
        )

        places = []

    return render_template(
        "explore.html",
        places=places,
        search=search,
        selected_category=category,
        categories=CATEGORIES,
    )


# --------------------------------------------------
# SUGGEST A PLACE
# --------------------------------------------------

@app.route(
    "/explore/suggest",
    methods=["GET", "POST"],
)
@login_required
def suggest_place():
    """Save a place suggestion from the logged-in user."""
    if request.method == "POST":
        name = request.form.get(
            "name", ""
        ).strip()

        destination = request.form.get(
            "destination", ""
        ).strip()

        category = request.form.get(
            "category", ""
        ).strip()

        description = request.form.get(
            "description", ""
        ).strip()

        errors = []

        if not 2 <= len(name) <= 120:
            errors.append(
                "Place name must contain 2 to 120 characters."
            )

        if not 2 <= len(destination) <= 120:
            errors.append(
                "Destination must contain 2 to 120 characters."
            )

        if category not in CATEGORIES:
            errors.append(
                "Choose a valid category."
            )

        if not 10 <= len(description) <= 500:
            errors.append(
                "Description must contain 10 to 500 characters."
            )

        if errors:
            for error in errors:
                flash(error, "danger")

            return render_template(
                "suggest_place.html",
                categories=CATEGORIES,
            )

        try:
            # FIX: The actual MySQL column is user_id,
            # not created_by.
            execute_db(
                """
                INSERT INTO place_suggestions
                    (
                        name,
                        destination,
                        category,
                        description,
                        user_id
                    )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    name,
                    destination,
                    category,
                    description,
                    session["user_id"],
                ),
            )

            flash(
                "Thanks! Your place suggestion is now visible on Explore.",
                "success",
            )

            return redirect(
                url_for("explore")
            )

        except Error:
            app.logger.exception(
                "Could not save place suggestion"
            )

            flash(
                "Unable to save your place suggestion. "
                "Please check the database table and try again.",
                "danger",
            )

    return render_template(
        "suggest_place.html",
        categories=CATEGORIES,
    )


# --------------------------------------------------
# ERROR HANDLERS
# --------------------------------------------------

@app.errorhandler(404)
def not_found(_error):
    """Display the custom not-found page."""
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_error):
    """Display the custom server-error page."""
    app.logger.exception(
        "Unhandled application error"
    )

    return render_template("500.html"), 500


# --------------------------------------------------
# APPLICATION ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    try:
        initialize_database()

        app.logger.info(
            "Database tables are ready."
        )

    except Error as error:
        raise SystemExit(
            "Could not connect to MySQL. "
            "Create the database and check your .env settings. "
            f"Details: {error}"
        )

    app.run(
        debug=(
            os.getenv("FLASK_DEBUG", "false").lower()
            == "true"
        )
    )
