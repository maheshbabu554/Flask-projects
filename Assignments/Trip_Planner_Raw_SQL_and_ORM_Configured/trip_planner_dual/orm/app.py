
"""Trip Planner web application built with Flask and SQLAlchemy."""

import os
import re
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Load environment variables BEFORE importing database.py.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=False)

from flask import (
    Flask, abort, flash, redirect, render_template,
    request, session, url_for
)
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from database import db, User, Trip, Activity, PlaceSuggestion, init_db


# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY", "change-this-secret-key"
)

db_user = os.getenv("DB_USER", "root")
db_password = quote_plus(os.getenv("DB_PASSWORD", ""))
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "3306")
db_name = os.getenv("DB_NAME", "trip_planner_raw_sql_orm")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{quote_plus(db_user)}:{db_password}"
    f"@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

CATEGORIES = [
    "Sightseeing", "Food", "Adventure", "Culture",
    "Shopping", "Transport", "Stay", "Other"
]

# Initialize ORM and create missing tables.
init_db(app)


# --------------------------------------------------
# AUTHENTICATION AND HELPERS
# --------------------------------------------------

def login_required(view):
    """Require login before accessing a protected page."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def owned_trip(trip_id):
    """Return a trip only if it belongs to the logged-in user."""
    trip = Trip.query.filter_by(
        id=trip_id,
        user_id=session["user_id"]
    ).first()

    if trip is None:
        abort(404)

    return trip


def parse_date(value, label):
    """Validate and convert a YYYY-MM-DD date."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValueError(f"Please enter a valid {label.lower()}.")


def parse_money(value, label):
    """Validate a non-negative monetary amount."""
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} must be a valid number.")

    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{label} cannot be negative.")

    if amount > Decimal("9999999999.99"):
        raise ValueError(f"{label} is too large.")

    return amount.quantize(Decimal("0.01"))


@app.template_filter("money")
def money(value):
    """Format an amount as Indian rupees."""
    return f"₹{Decimal(str(value or 0)):,.2f}"


@app.template_filter("pretty_date")
def pretty_date(value):
    """Format a date as day, month, and year."""
    if isinstance(value, str):
        value = date.fromisoformat(value)
    return value.strftime("%d %b %Y")


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def home():
    """Display the public home page."""
    return render_template("home.html")


# --------------------------------------------------
# REGISTER
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register a user and automatically log them in."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []

        if not 2 <= len(username) <= 50:
            errors.append("Name must contain 2 to 50 characters.")

        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            errors.append("Enter a valid email address.")

        if len(password) < 8:
            errors.append("Password must contain at least 8 characters.")

        if password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template(
                "register.html",
                username=username,
                email=email
            )

        try:
            new_user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password)
            )

            db.session.add(new_user)
            db.session.commit()

            session.clear()
            session["user_id"] = new_user.id
            session["username"] = new_user.username

            flash("Your account is ready. Start planning your next trip!", "success")
            return redirect(url_for("my_trips"))

        except IntegrityError:
            db.session.rollback()
            flash("An account with this email already exists. Please log in.", "warning")

        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Registration database error")
            flash("Could not create account. Check database settings.", "danger")

    return render_template("register.html")


# --------------------------------------------------
# LOGIN AND LOGOUT
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate a user with email and password."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user_record = User.query.filter_by(email=email).first()

        if (
            user_record
            and check_password_hash(user_record.password_hash, password)
        ):
            session.clear()
            session["user_id"] = user_record.id
            session["username"] = user_record.username

            flash("Welcome back!", "success")

            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)

            return redirect(url_for("my_trips"))

        flash("Email or password is incorrect.", "danger")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    """Clear the login session."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


# --------------------------------------------------
# PERSONAL TRIPS
# --------------------------------------------------

@app.route("/trips")
@login_required
def my_trips():
    """Show the logged-in user's trips and estimated totals."""
    trips = (
        Trip.query
        .filter_by(user_id=session["user_id"])
        .order_by(Trip.start_date.desc(), Trip.id.desc())
        .all()
    )

    for trip in trips:
        trip.total_cost = sum(
            (activity.cost or Decimal("0") for activity in trip.activities),
            Decimal("0")
        )
        trip.activity_count = len(trip.activities)

    return render_template("my_trips.html", trips=trips)


# --------------------------------------------------
# TRIP VALIDATION AND CREATION
# --------------------------------------------------

def validate_trip_form(form):
    """Validate trip destination, dates, and budget."""
    destination = form.get("destination", "").strip()

    if not 2 <= len(destination) <= 120:
        raise ValueError("Destination must contain 2 to 120 characters.")

    start = parse_date(form.get("start_date"), "Start date")
    end = parse_date(form.get("end_date"), "End date")

    if end < start:
        raise ValueError("End date must be on or after the start date.")

    budget = parse_money(form.get("budget", ""), "Budget")
    return destination, start, end, budget


@app.route("/trips/new", methods=["GET", "POST"])
@login_required
def create_trip():
    """Create a trip owned by the logged-in user."""
    if request.method == "POST":
        try:
            destination, start, end, budget = validate_trip_form(request.form)

            trip = Trip(
                user_id=session["user_id"],
                destination=destination,
                start_date=start,
                end_date=end,
                budget=budget
            )

            db.session.add(trip)
            db.session.commit()

            flash("Trip created successfully.", "success")
            return redirect(url_for("trip_detail", trip_id=trip.id))

        except ValueError as error:
            flash(str(error), "danger")

        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Create trip failed")
            flash("Unable to save the trip. Check database settings.", "danger")

    return render_template("trip_form.html", trip=None)


# --------------------------------------------------
# TRIP DETAILS
# --------------------------------------------------

@app.route("/trips/<int:trip_id>")
@login_required
def trip_detail(trip_id):
    """Display a trip's itinerary, total cost, and remaining budget."""
    trip = owned_trip(trip_id)

    activities = (
        Activity.query
        .filter_by(trip_id=trip.id)
        .order_by(
            Activity.activity_date,
            Activity.activity_time,
            Activity.id
        )
        .all()
    )

    by_day = {}
    for activity in activities:
        by_day.setdefault(activity.activity_date, []).append(activity)

    total = sum(
        (activity.cost or Decimal("0") for activity in activities),
        Decimal("0")
    )

    difference = Decimal(str(trip.budget)) - total

    return render_template(
        "trip_detail.html",
        trip=trip,
        by_day=by_day,
        total=total,
        difference=difference,
        categories=CATEGORIES,
        today=date.today()
    )


# --------------------------------------------------
# EDIT TRIP
# --------------------------------------------------

@app.route("/trips/<int:trip_id>/edit", methods=["GET", "POST"])
@login_required
def edit_trip(trip_id):
    """Update a trip without excluding its existing activities."""
    trip = owned_trip(trip_id)

    if request.method == "POST":
        try:
            destination, start, end, budget = validate_trip_form(request.form)

            outside = Activity.query.filter(
                Activity.trip_id == trip.id,
                or_(
                    Activity.activity_date < start,
                    Activity.activity_date > end
                )
            ).count()

            if outside:
                raise ValueError(
                    f"These dates would leave {outside} existing "
                    "activity/activities outside the trip. "
                    "Edit or remove those activities first."
                )

            trip.destination = destination
            trip.start_date = start
            trip.end_date = end
            trip.budget = budget
            db.session.commit()

            flash("Trip updated successfully.", "success")
            return redirect(url_for("trip_detail", trip_id=trip.id))

        except ValueError as error:
            flash(str(error), "danger")

        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Update trip failed")
            flash("Unable to update trip right now.", "danger")

    return render_template("trip_form.html", trip=trip)


# --------------------------------------------------
# DELETE TRIP
# --------------------------------------------------

@app.route("/trips/<int:trip_id>/delete", methods=["POST"])
@login_required
def delete_trip(trip_id):
    """Delete a trip and its related activities."""
    trip = owned_trip(trip_id)

    try:
        db.session.delete(trip)
        db.session.commit()
        flash("Trip and its activities were deleted.", "info")

    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Delete trip failed")
        flash("Unable to delete this trip right now.", "danger")

    return redirect(url_for("my_trips"))


# --------------------------------------------------
# ACTIVITY VALIDATION
# --------------------------------------------------

def validate_activity_form(form, trip):
    """Validate activity details and ensure its date is within the trip."""
    name = form.get("name", "").strip()
    place = form.get("place", "").strip()
    category = form.get("category", "").strip()

    if not 2 <= len(name) <= 120:
        raise ValueError("Activity name must contain 2 to 120 characters.")

    if not 2 <= len(place) <= 160:
        raise ValueError("Place must contain 2 to 160 characters.")

    if category not in CATEGORIES:
        raise ValueError("Choose a valid activity category.")

    activity_day = parse_date(form.get("activity_date"), "Activity date")

    if not trip.start_date <= activity_day <= trip.end_date:
        raise ValueError(
            "Activity date must fall within this trip's start and end dates."
        )

    raw_time = form.get("activity_time", "").strip()

    try:
        activity_time = (
            datetime.strptime(raw_time, "%H:%M").time()
            if raw_time else None
        )
    except ValueError:
        raise ValueError("Enter a valid activity time.")

    cost = parse_money(form.get("cost", ""), "Estimated cost")

    return name, activity_day, activity_time, category, place, cost


def get_activity(trip_id, activity_id):
    """Find an activity attached to the specified trip."""
    activity = Activity.query.filter_by(
        id=activity_id,
        trip_id=trip_id
    ).first()

    if activity is None:
        abort(404)

    return activity


# --------------------------------------------------
# CREATE ACTIVITY
# --------------------------------------------------

@app.route("/trips/<int:trip_id>/activities/new", methods=["GET", "POST"])
@login_required
def create_activity(trip_id):
    """Add an activity to a trip owned by the logged-in user."""
    trip = owned_trip(trip_id)

    if request.method == "POST":
        try:
            values = validate_activity_form(request.form, trip)

            activity = Activity(
                trip_id=trip.id,
                name=values[0],
                activity_date=values[1],
                activity_time=values[2],
                category=values[3],
                place=values[4],
                cost=values[5]
            )

            db.session.add(activity)
            db.session.commit()

            flash("Activity added. Your total has been recalculated.", "success")
            return redirect(url_for("trip_detail", trip_id=trip.id))

        except ValueError as error:
            flash(str(error), "danger")

        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Create activity failed")
            flash("Unable to save activity right now.", "danger")

    return render_template(
        "activity_form.html",
        trip=trip,
        activity=None,
        categories=CATEGORIES
    )


# --------------------------------------------------
# EDIT ACTIVITY
# --------------------------------------------------

@app.route(
    "/trips/<int:trip_id>/activities/<int:activity_id>/edit",
    methods=["GET", "POST"]
)
@login_required
def edit_activity(trip_id, activity_id):
    """Update an activity after validating all submitted fields."""
    trip = owned_trip(trip_id)
    activity = get_activity(trip_id, activity_id)

    if request.method == "POST":
        try:
            values = validate_activity_form(request.form, trip)

            (
                activity.name,
                activity.activity_date,
                activity.activity_time,
                activity.category,
                activity.place,
                activity.cost
            ) = values

            db.session.commit()

            flash("Activity updated. Your total has been recalculated.", "success")
            return redirect(url_for("trip_detail", trip_id=trip.id))

        except ValueError as error:
            flash(str(error), "danger")

        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Update activity failed")
            flash("Unable to update activity right now.", "danger")

    return render_template(
        "activity_form.html",
        trip=trip,
        activity=activity,
        categories=CATEGORIES
    )


# --------------------------------------------------
# DELETE ACTIVITY
# --------------------------------------------------

@app.route(
    "/trips/<int:trip_id>/activities/<int:activity_id>/delete",
    methods=["POST"]
)
@login_required
def delete_activity(trip_id, activity_id):
    """Delete an activity after checking trip ownership."""
    owned_trip(trip_id)
    activity = get_activity(trip_id, activity_id)

    try:
        db.session.delete(activity)
        db.session.commit()
        flash("Activity removed and total recalculated.", "info")

    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Delete activity failed")
        flash("Unable to remove this activity right now.", "danger")

    return redirect(url_for("trip_detail", trip_id=trip_id))


# --------------------------------------------------
# PUBLIC EXPLORE
# --------------------------------------------------

@app.route("/explore")
def explore():
    """Search community place suggestions and filter by category."""
    search = request.args.get("q", "").strip()[:120]
    category = request.args.get("category", "").strip()

    query = PlaceSuggestion.query

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                PlaceSuggestion.name.ilike(pattern),
                PlaceSuggestion.destination.ilike(pattern),
                PlaceSuggestion.description.ilike(pattern)
            )
        )

    if category in CATEGORIES:
        query = query.filter_by(category=category)

    places = query.order_by(
        PlaceSuggestion.destination,
        PlaceSuggestion.name
    ).all()

    return render_template(
        "explore.html",
        places=places,
        search=search,
        selected_category=category,
        categories=CATEGORIES
    )


# --------------------------------------------------
# SUGGEST A PLACE
# --------------------------------------------------

@app.route("/explore/suggest", methods=["GET", "POST"])
@login_required
def suggest_place():
    """Allow logged-in users to submit community place suggestions."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        destination = request.form.get("destination", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()

        errors = []

        if not 2 <= len(name) <= 120:
            errors.append("Place name must contain 2 to 120 characters.")

        if not 2 <= len(destination) <= 120:
            errors.append("Destination must contain 2 to 120 characters.")

        if category not in CATEGORIES:
            errors.append("Choose a valid category.")

        if not 10 <= len(description) <= 500:
            errors.append("Description must contain 10 to 500 characters.")

        if errors:
            for error in errors:
                flash(error, "danger")

        else:
            try:
                suggestion = PlaceSuggestion(
                    name=name,
                    destination=destination,
                    category=category,
                    description=description,
                    created_by=session["user_id"]
                )

                db.session.add(suggestion)
                db.session.commit()

                flash(
                    "Thanks! Your place suggestion is now visible on Explore.",
                    "success"
                )
                return redirect(url_for("explore"))

            except SQLAlchemyError:
                db.session.rollback()
                app.logger.exception("Place suggestion database error")
                flash("Unable to save your suggestion right now.", "danger")

    return render_template(
        "suggest_place.html",
        categories=CATEGORIES
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
    """Display a friendly page for unexpected errors."""
    app.logger.error("Unhandled application error: %s", _error)
    return render_template("500.html"), 500


# --------------------------------------------------
# START APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").strip().lower() == "true"
    )
