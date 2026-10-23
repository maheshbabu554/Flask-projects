
"""
Movie Night Planner
A Flask and MySQL application where registered users suggest movie choices,
vote for one movie per night, and the creator selects the final movie.
"""

import os
import re
from datetime import date
from urllib.parse import urlparse

import mysql.connector
from dotenv import load_dotenv
from flask import (
    Flask, abort, flash, redirect, render_template,
    request, session, url_for
)
from mysql.connector import Error, IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY", ""
)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "movie_night_planner"),
}


# --------------------------------------------------
# DATABASE HELPERS
# --------------------------------------------------

def get_connection():
    """Create and return a new MySQL database connection."""
    return mysql.connector.connect(**DB_CONFIG)


def query_db(sql, params=(), fetchone=False):
    """Execute a SELECT query and return rows as dictionaries."""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        if fetchone:
            return cursor.fetchone()
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def execute_db(sql, params=()):
    """Execute an INSERT, UPDATE, or DELETE and commit the changes."""
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


def initialize_database():
    """Create all tables and add demonstration data if the database is empty."""
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movie_nights (
                id INT AUTO_INCREMENT PRIMARY KEY,
                creator_id INT NOT NULL,
                title VARCHAR(150) NOT NULL,
                night_date DATE NOT NULL,
                category ENUM(
                    'Comedy', 'Action', 'Animation', 'Other'
                ) NOT NULL,
                description VARCHAR(500) NOT NULL,
                final_choice_id INT NULL,
                is_finalized BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_night_creator
                    FOREIGN KEY (creator_id) REFERENCES users(id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movie_choices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                night_id INT NOT NULL,
                movie_title VARCHAR(150) NOT NULL,
                genre VARCHAR(80) NOT NULL,
                reason VARCHAR(300) NOT NULL,
                poster_url VARCHAR(500) DEFAULT NULL,
                trailer_url VARCHAR(500) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_choice_night
                    FOREIGN KEY (night_id) REFERENCES movie_nights(id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                night_id INT NOT NULL,
                choice_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_vote (user_id, night_id),
                CONSTRAINT fk_vote_user
                    FOREIGN KEY (user_id) REFERENCES users(id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_vote_night
                    FOREIGN KEY (night_id) REFERENCES movie_nights(id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_vote_choice
                    FOREIGN KEY (choice_id) REFERENCES movie_choices(id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB
        """)

        # Create sample content only when there are no movie nights.
        cursor.execute("SELECT COUNT(*) FROM movie_nights")
        night_count = cursor.fetchone()[0]

        if night_count == 0:
            demo_password = generate_password_hash("Demo123!")

            cursor.execute("""
                INSERT INTO users (name, username, password_hash)
                VALUES (%s, %s, %s)
            """, ("Demo Student", "demo", demo_password))
            demo_user_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO movie_nights
                    (creator_id, title, night_date, category, description)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                demo_user_id,
                "Friday Movie Night",
                date.today().isoformat(),
                "Action",
                "Help us choose a movie for our next movie night."
            ))
            night_id = cursor.lastrowid

            sample_choices = [
                (
                    "Interstellar", "Sci-Fi",
                    "A great space adventure with an emotional story.",
                    "https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
                    "https://www.youtube.com/watch?v=zSWdZVtXT7E"
                ),
                (
                    "The Dark Knight", "Action",
                    "A gripping superhero crime story.",
                    "https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
                    "https://www.youtube.com/watch?v=EXeTwQWrcwY"
                ),
            ]

            cursor.executemany("""
                INSERT INTO movie_choices
                    (night_id, movie_title, genre, reason, poster_url, trailer_url)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, [
                (night_id, title, genre, reason, poster, trailer)
                for title, genre, reason, poster, trailer in sample_choices
            ])

        connection.commit()

    finally:
        cursor.close()
        connection.close()


# --------------------------------------------------
# VALIDATION AND AUTHENTICATION
# --------------------------------------------------

CATEGORIES = ["Comedy", "Action", "Animation", "Other"]


def current_user():
    """Return the logged-in user's database record, or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None

    return query_db(
        "SELECT id, name, username FROM users WHERE id = %s",
        (user_id,),
        fetchone=True
    )


def login_required():
    """Redirect unauthenticated visitors to the login page."""
    if not session.get("user_id"):
        flash("Please log in to continue.", "warning")
        return False
    return True


def valid_text(value, label, maximum, minimum=1):
    """Strip and validate a required text field."""
    value = (value or "").strip()
    if len(value) < minimum or len(value) > maximum:
        raise ValueError(
            f"{label} must contain {minimum} to {maximum} characters."
        )
    return value


def valid_date(value):
    """Validate a date supplied by an HTML date input."""
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError("Please enter a valid date.")


def valid_optional_url(value, label):
    """Allow an empty URL or a valid HTTP(S) URL."""
    value = (value or "").strip()
    if not value:
        return None

    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"{label} must be a valid HTTP or HTTPS URL.")

    return value[:500]


def get_night_or_404(night_id):
    """Return a movie night with its creator's name."""
    night = query_db("""
        SELECT mn.*, u.name AS creator_name, u.username AS creator_username
        FROM movie_nights mn
        JOIN users u ON u.id = mn.creator_id
        WHERE mn.id = %s
    """, (night_id,), fetchone=True)

    if not night:
        abort(404)

    return night


def require_owner(night):
    """Prevent users from changing movie nights created by someone else."""
    if not session.get("user_id"):
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    if night["creator_id"] != session["user_id"]:
        abort(403)

    return None


def youtube_embed_url(url):
    """Convert common YouTube watch and short URLs into embed URLs."""
    if not url:
        return None

    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    video_id = None

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in ("youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            from urllib.parse import parse_qs
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif parsed.path.startswith("/embed/"):
            video_id = parsed.path.split("/embed/", 1)[1].split("/")[0]
        elif parsed.path.startswith("/shorts/"):
            video_id = parsed.path.split("/shorts/", 1)[1].split("/")[0]

    if video_id and re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id):
        return f"https://www.youtube-nocookie.com/embed/{video_id}"

    return None


app.jinja_env.globals["youtube_embed_url"] = youtube_embed_url


# --------------------------------------------------
# HOME / BROWSE
# --------------------------------------------------

@app.route("/")
def index():
    """Browse movie nights with combined title search and category filtering."""
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    if category not in CATEGORIES:
        category = ""

    sql = """
        SELECT mn.*, u.name AS creator_name,
            (SELECT COUNT(*) FROM movie_choices mc
             WHERE mc.night_id = mn.id) AS choice_count,
            (SELECT COUNT(*) FROM votes v
             WHERE v.night_id = mn.id) AS vote_count,
            (SELECT mc.movie_title FROM movie_choices mc
             WHERE mc.id = mn.final_choice_id AND mc.night_id = mn.id)
             AS final_movie_title
        FROM movie_nights mn
        JOIN users u ON u.id = mn.creator_id
        WHERE 1 = 1
    """
    params = []

    if search:
        sql += " AND mn.title LIKE %s"
        params.append(f"%{search}%")

    if category:
        sql += " AND mn.category = %s"
        params.append(category)

    sql += " ORDER BY mn.created_at DESC"

    nights = query_db(sql, tuple(params))

    return render_template(
        "index.html",
        nights=nights,
        search=search,
        category=category,
        categories=CATEGORIES,
        user=current_user()
    )


# --------------------------------------------------
# REGISTRATION, LOGIN, LOGOUT
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register a new user using a securely hashed password."""
    if request.method == "POST":
        try:
            name = valid_text(request.form.get("name"), "Name", 100)
            username = valid_text(
                request.form.get("username"), "Username", 50
            )
            password = request.form.get("password", "")

            if not re.fullmatch(r"[A-Za-z0-9_]{3,50}", username):
                raise ValueError(
                    "Username must be 3–50 characters using letters, "
                    "numbers, and underscores."
                )

            if len(password) < 8 or len(password) > 128:
                raise ValueError("Password must contain 8–128 characters.")

            execute_db("""
                INSERT INTO users (name, username, password_hash)
                VALUES (%s, %s, %s)
            """, (name, username, generate_password_hash(password)))

            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))

        except ValueError as error:
            flash(str(error), "danger")
        except IntegrityError:
            flash("That username is already taken.", "danger")
        except Error:
            app.logger.exception("Registration database error")
            flash("Could not register. Please try again.", "danger")

    return render_template("register.html", user=current_user())


@app.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate a user without storing their password in the session."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = query_db(
            "SELECT * FROM users WHERE username = %s",
            (username,),
            fetchone=True
        )

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("index"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html", user=current_user())


@app.route("/logout", methods=["POST"])
def logout():
    """Log out the current user and clear their session."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# --------------------------------------------------
# CREATE, VIEW, EDIT AND DELETE MOVIE NIGHTS
# --------------------------------------------------

@app.route("/night/create", methods=["GET", "POST"])
def create_night():
    """Create a new movie night for the logged-in user."""
    if not login_required():
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            title = valid_text(request.form.get("title"), "Title", 150)
            night_date = valid_date(request.form.get("night_date", ""))
            category = request.form.get("category", "")
            description = valid_text(
                request.form.get("description"), "Description", 500
            )

            if category not in CATEGORIES:
                raise ValueError("Please select a valid category.")

            night_id = execute_db("""
                INSERT INTO movie_nights
                    (creator_id, title, night_date, category, description)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                session["user_id"], title, night_date, category, description
            ))

            flash("Movie night created. Add some movie choices!", "success")
            return redirect(url_for("night_detail", night_id=night_id))

        except ValueError as error:
            flash(str(error), "danger")
        except Error:
            app.logger.exception("Create movie night database error")
            flash("Could not create the movie night.", "danger")

    return render_template(
        "create_night.html",
        user=current_user(),
        categories=CATEGORIES
    )


@app.route("/night/<int:night_id>")
def night_detail(night_id):
    """Display a movie night, choices, vote counts, and final result."""
    night = get_night_or_404(night_id)

    choices = query_db("""
        SELECT mc.*,
            (SELECT COUNT(*) FROM votes v
             WHERE v.choice_id = mc.id AND v.night_id = mc.night_id)
             AS vote_count
        FROM movie_choices mc
        WHERE mc.night_id = %s
        ORDER BY mc.id
    """, (night_id,))

    my_vote = None
    user = current_user()

    if user:
        vote = query_db("""
            SELECT choice_id FROM votes
            WHERE user_id = %s AND night_id = %s
        """, (user["id"], night_id), fetchone=True)

        if vote:
            my_vote = vote["choice_id"]

    night["final_movie_title"] = None
    if night["final_choice_id"]:
        final_choice = query_db("""
            SELECT movie_title FROM movie_choices
            WHERE id = %s AND night_id = %s
        """, (night["final_choice_id"], night_id), fetchone=True)

        if final_choice:
            night["final_movie_title"] = final_choice["movie_title"]

    return render_template(
        "detail.html",
        night=night,
        choices=choices,
        my_vote=my_vote,
        user=user,
        is_owner=bool(user and user["id"] == night["creator_id"])
    )


@app.route("/night/<int:night_id>/edit", methods=["GET", "POST"])
def edit_night(night_id):
    """Edit a movie night only when the logged-in user owns it."""
    if not login_required():
        return redirect(url_for("login"))

    night = get_night_or_404(night_id)
    response = require_owner(night)
    if response:
        return response

    if night["is_finalized"]:
        flash("A finalized movie night cannot be edited.", "warning")
        return redirect(url_for("night_detail", night_id=night_id))

    if request.method == "POST":
        try:
            title = valid_text(request.form.get("title"), "Title", 150)
            night_date = valid_date(request.form.get("night_date", ""))
            category = request.form.get("category", "")
            description = valid_text(
                request.form.get("description"), "Description", 500
            )

            if category not in CATEGORIES:
                raise ValueError("Please select a valid category.")

            execute_db("""
                UPDATE movie_nights
                SET title = %s, night_date = %s,
                    category = %s, description = %s
                WHERE id = %s AND creator_id = %s
                  AND is_finalized = FALSE
            """, (
                title, night_date, category, description,
                night_id, session["user_id"]
            ))

            flash("Movie night updated.", "success")
            return redirect(url_for("night_detail", night_id=night_id))

        except ValueError as error:
            flash(str(error), "danger")
        except Error:
            app.logger.exception("Edit movie night database error")
            flash("Could not update the movie night.", "danger")

    return render_template(
        "edit_night.html",
        night=night,
        user=current_user(),
        categories=CATEGORIES
    )


@app.route("/night/<int:night_id>/delete", methods=["POST"])
def delete_night(night_id):
    """Delete a movie night only if the current user owns it."""
    if not login_required():
        return redirect(url_for("login"))

    night = get_night_or_404(night_id)
    response = require_owner(night)
    if response:
        return response

    if night["is_finalized"]:
        flash("A finalized movie night cannot be deleted.", "warning")
        return redirect(url_for("night_detail", night_id=night_id))

    try:
        execute_db("""
            DELETE FROM movie_nights
            WHERE id = %s AND creator_id = %s
        """, (night_id, session["user_id"]))

        flash("Movie night deleted.", "success")
        return redirect(url_for("index"))

    except Error:
        app.logger.exception("Delete movie night database error")
        flash("Could not delete the movie night.", "danger")
        return redirect(url_for("night_detail", night_id=night_id))


# --------------------------------------------------
# MOVIE CHOICES
# --------------------------------------------------

@app.route("/night/<int:night_id>/choice/add", methods=["POST"])
def add_choice(night_id):
    """Add a movie choice to the creator's open movie night."""
    if not login_required():
        return redirect(url_for("login"))

    night = get_night_or_404(night_id)
    response = require_owner(night)
    if response:
        return response

    if night["is_finalized"]:
        flash("Voting is closed. No more choices can be added.", "warning")
        return redirect(url_for("night_detail", night_id=night_id))

    try:
        title = valid_text(
            request.form.get("movie_title"), "Movie title", 150
        )
        genre = valid_text(request.form.get("genre"), "Genre", 80)
        reason = valid_text(request.form.get("reason"), "Reason", 300)
        poster_url = valid_optional_url(
            request.form.get("poster_url"), "Poster URL"
        )
        trailer_url = valid_optional_url(
            request.form.get("trailer_url"), "Trailer URL"
        )

        execute_db("""
            INSERT INTO movie_choices
                (night_id, movie_title, genre, reason, poster_url, trailer_url)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (night_id, title, genre, reason, poster_url, trailer_url))

        flash("Movie choice added.", "success")

    except ValueError as error:
        flash(str(error), "danger")
    except Error:
        app.logger.exception("Add movie choice database error")
        flash("Could not add the movie choice.", "danger")

    return redirect(url_for("night_detail", night_id=night_id))


@app.route(
    "/night/<int:night_id>/choice/<int:choice_id>/delete",
    methods=["POST"]
)
def delete_choice(night_id, choice_id):
    """Delete a choice only when its movie night belongs to the current user."""
    if not login_required():
        return redirect(url_for("login"))

    night = get_night_or_404(night_id)
    response = require_owner(night)
    if response:
        return response

    if night["is_finalized"]:
        flash("Choices cannot be deleted after finalization.", "warning")
        return redirect(url_for("night_detail", night_id=night_id))

    choice = query_db("""
        SELECT id FROM movie_choices
        WHERE id = %s AND night_id = %s
    """, (choice_id, night_id), fetchone=True)

    if not choice:
        abort(404)

    try:
        execute_db("""
            DELETE FROM movie_choices
            WHERE id = %s AND night_id = %s
        """, (choice_id, night_id))

        flash("Movie choice deleted.", "success")

    except Error:
        app.logger.exception("Delete movie choice database error")
        flash("Could not delete the movie choice.", "danger")

    return redirect(url_for("night_detail", night_id=night_id))


# --------------------------------------------------
# VOTING
# --------------------------------------------------

@app.route(
    "/night/<int:night_id>/vote/<int:choice_id>",
    methods=["POST"]
)
def vote(night_id, choice_id):
    """Save or replace a user's vote in an open movie night."""
    if not login_required():
        return redirect(url_for("login"))

    night = get_night_or_404(night_id)

    if night["is_finalized"]:
        flash("Voting is closed for this movie night.", "warning")
        return redirect(url_for("night_detail", night_id=night_id))

    choice = query_db("""
        SELECT id FROM movie_choices
        WHERE id = %s AND night_id = %s
    """, (choice_id, night_id), fetchone=True)

    if not choice:
        abort(404)

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO votes (user_id, night_id, choice_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                choice_id = VALUES(choice_id),
                created_at = CURRENT_TIMESTAMP
        """, (session["user_id"], night_id, choice_id))

        connection.commit()
        flash("Your vote has been saved.", "success")

    except Error:
        connection.rollback()
        app.logger.exception("Vote database error")
        flash("Could not save your vote.", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("night_detail", night_id=night_id))


# --------------------------------------------------
# FINAL MOVIE
# --------------------------------------------------

@app.route("/night/<int:night_id>/finalize", methods=["POST"])
def finalize_night(night_id):
    """Let the creator select the final movie after at least two choices exist."""
    if not login_required():
        return redirect(url_for("login"))

    night = get_night_or_404(night_id)
    response = require_owner(night)
    if response:
        return response

    if night["is_finalized"]:
        flash("This movie night has already been finalized.", "warning")
        return redirect(url_for("night_detail", night_id=night_id))

    try:
        choice_id = int(request.form.get("choice_id", ""))
    except (ValueError, TypeError):
        flash("Please select a valid final movie.", "danger")
        return redirect(url_for("night_detail", night_id=night_id))

    choices = query_db("""
        SELECT id FROM movie_choices WHERE night_id = %s
    """, (night_id,))

    if len(choices) < 2:
        flash("Add at least two movie choices before finalizing.", "danger")
        return redirect(url_for("night_detail", night_id=night_id))

    if choice_id not in [choice["id"] for choice in choices]:
        flash("The selected movie does not belong to this movie night.", "danger")
        return redirect(url_for("night_detail", night_id=night_id))

    try:
        execute_db("""
            UPDATE movie_nights
            SET final_choice_id = %s, is_finalized = TRUE
            WHERE id = %s AND creator_id = %s
              AND is_finalized = FALSE
        """, (choice_id, night_id, session["user_id"]))

        flash("Final movie selected! Voting is now closed.", "success")

    except Error:
        app.logger.exception("Finalize movie night database error")
        flash("Could not finalize the movie night.", "danger")

    return redirect(url_for("night_detail", night_id=night_id))


# --------------------------------------------------
# ERROR PAGES
# --------------------------------------------------

@app.errorhandler(403)
def forbidden(_error):
    """Show a friendly message for unauthorized changes."""
    return render_template("base.html", user=current_user(),
                           forbidden_message="You cannot change another user's movie night."), 403


@app.errorhandler(404)
def not_found(_error):
    """Show a friendly message when a page or record does not exist."""
    return "Page or movie night not found.", 404


# --------------------------------------------------
# START APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    try:
        initialize_database()
        print("Database initialized successfully.")
        print("Demo login: username=demo, password=Demo123!")
        app.run(debug=True)
    except Error as error:
        print("Database connection failed.")
        print("Check that MySQL is running and .env credentials are correct.")
        print(f"Details: {error}")
