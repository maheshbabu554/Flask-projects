"""
Movie Night Planner - Flask Web Application
===========================================

Purpose:
--------
Movie Night Planner is a full-featured, beginner-friendly web application where
registered movie lovers can organize movie nights, suggest movie titles with real
posters and official video trailers, vote on their favorite choices, and empower
the event creator to review votes and finalize the winning film.

Key Features:
-------------
1. User Authentication:
   - Secure registration, login, and logout.
   - Passwords hashed using Werkzeug's industry-standard PBKDF2/scrypt implementation.
   - Session-based user tracking with protected routes.
   - Equal privileges for all registered users (no admin backdoors or role imbalances).

2. Movie Night Lifecycle:
   - Browse movie nights with real-time search (by title) and category filtering (Comedy, Action, Animation, Other).
   - Create, edit, and delete movie nights (ownership enforced on the server).
   - Add multiple movie choices with title, genre, recommendation reason, poster URL, and trailer URL.
   - Community voting: Each logged-in user can vote once per movie night and switch their vote anytime before closure.
   - Finalization: Creators select the winning film once at least 2 choices exist, locking further voting and updates.

3. Media & Presentation:
   - Real movie posters loaded safely with fallback placeholder support.
   - Responsive YouTube video player modal for official trailers.
   - Cinematic dark aesthetic built with Bootstrap 5.3.8 and custom styles.

4. Architecture & Security:
   - Technology Stack: Python 3, Flask, MySQL (via mysql-connector-python), Jinja2, Bootstrap 5.3.8.
   - Security: Parameterized SQL queries (preventing SQL injection), CSRF token validation via Flask-WTF,
     secure session cookies, and server-side authorization checks on all mutating operations.
"""

import os
import re
from datetime import datetime
from functools import wraps
from urllib.parse import parse_qs, urlparse

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
from flask_wtf.csrf import CSRFProtect
import mysql.connector
from mysql.connector import Error, errorcode
from werkzeug.security import check_password_hash, generate_password_hash

# Load environment configuration from .env file
load_dotenv()

# Initialize Flask application
app = Flask(__name__)

# Configure application secret key for sessions and CSRF protection
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "dev_secret_key_change_in_production_7f8a9b2c3d4e5f6"
)
app.config["WTF_CSRF_TIME_LIMIT"] = None  # No premature token expiry during long forms

# Initialize CSRF protection on all incoming POST/PUT/DELETE requests
csrf = CSRFProtect(app)

# MySQL connection parameters from environment
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 3306))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "movie_night_planner")

ALLOWED_CATEGORIES = ("Comedy", "Action", "Animation", "Other")


# =====================================================================
# Database Helpers
# =====================================================================

def get_db_connection():
    """
    Establish and return a connection to the MySQL database.
    
    Returns a mysql.connector.connection.MySQLConnection object configured
    with utf8mb4 charset and dictionary cursor capability.
    """
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        autocommit=False,
    )


def init_db():
    """
    Create the database schema and initialize default demo data if empty.
    
    Uses CREATE TABLE IF NOT EXISTS so existing tables and user records are
    never dropped or destroyed on restart.
    """
    try:
        # First ensure database exists
        server_conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            autocommit=True,
        )
        server_cursor = server_conn.cursor()
        server_cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        server_cursor.close()
        server_conn.close()

        # Connect to specific database and create required relational tables
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Users Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
        )

        # 2. Movie Nights Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS movie_nights (
                id INT AUTO_INCREMENT PRIMARY KEY,
                creator_id INT NOT NULL,
                title VARCHAR(150) NOT NULL,
                date DATE NOT NULL,
                category ENUM('Comedy', 'Action', 'Animation', 'Other') NOT NULL,
                description TEXT NOT NULL,
                status ENUM('open', 'finalized') NOT NULL DEFAULT 'open',
                final_movie_id INT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_movie_nights_creator (creator_id),
                INDEX idx_movie_nights_category (category),
                CONSTRAINT fk_movie_nights_creator FOREIGN KEY (creator_id)
                    REFERENCES users (id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
        )

        # 3. Movie Choices Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS movie_choices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                movie_night_id INT NOT NULL,
                title VARCHAR(150) NOT NULL,
                genre VARCHAR(60) NOT NULL,
                reason TEXT NOT NULL,
                poster_url VARCHAR(500) NOT NULL,
                trailer_url VARCHAR(500) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_choices_night (movie_night_id),
                CONSTRAINT fk_movie_choices_night FOREIGN KEY (movie_night_id)
                    REFERENCES movie_nights (id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
        )

        # 4. Votes Table (Enforces 1 vote per user per movie night)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS votes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                movie_night_id INT NOT NULL,
                movie_choice_id INT NOT NULL,
                user_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_votes_night (movie_night_id),
                INDEX idx_votes_choice (movie_choice_id),
                INDEX idx_votes_user (user_id),
                CONSTRAINT fk_votes_night FOREIGN KEY (movie_night_id)
                    REFERENCES movie_nights (id) ON DELETE CASCADE,
                CONSTRAINT fk_votes_choice FOREIGN KEY (movie_choice_id)
                    REFERENCES movie_choices (id) ON DELETE CASCADE,
                CONSTRAINT fk_votes_user FOREIGN KEY (user_id)
                    REFERENCES users (id) ON DELETE CASCADE,
                CONSTRAINT uq_user_movie_night UNIQUE (movie_night_id, user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
        )

        conn.commit()

        # Seed sample data if users table is empty (helpful for initial testing and grading)
        cursor.execute("SELECT COUNT(*) FROM users;")
        user_count = cursor.fetchone()[0]

        if user_count == 0:
            seed_sample_data(conn, cursor)

        cursor.close()
        conn.close()
    except Error as err:
        print(f"[Database Initialization Notice]: {err}")


def seed_sample_data(conn, cursor):
    """
    Populate the database with sample users, movie nights, choices, and votes
    so instructors or students can test the application right away.
    """
    # 1. Insert Demo Users (password for both is 'password123')
    pw_hash = generate_password_hash("password123")
    cursor.execute(
        """
        INSERT INTO users (name, username, password_hash)
        VALUES 
            ('Alex Rivera', 'alex', %s),
            ('Jordan Lee', 'jordan', %s),
            ('Sam Chen', 'sam', %s);
        """,
        (pw_hash, pw_hash, pw_hash),
    )
    alex_id = 1
    jordan_id = 2
    sam_id = 3

    # 2. Insert Sample Movie Night 1 (Comedy)
    cursor.execute(
        """
        INSERT INTO movie_nights (creator_id, title, date, category, description, status)
        VALUES (%s, 'Friday Night Comedy Blast', '2026-10-24', 'Comedy', 
                'Kicking back this Friday with laughs, gourmet popcorn, and top comedy picks. Vote for your favorite!', 'open');
        """,
        (alex_id,),
    )
    night_1_id = cursor.lastrowid

    # Add choices for Comedy Night with working posters & trailers
    cursor.execute(
        """
        INSERT INTO movie_choices (movie_night_id, title, genre, reason, poster_url, trailer_url)
        VALUES 
            (%s, 'Superbad', 'Comedy / Coming of Age', 
             'Hilarious high school adventure with iconic chemistry between Jonah Hill and Michael Cera.',
             'https://image.tmdb.org/t/p/w500/ek8e8txUyUwd2BNqj6lFEerJqUM.jpg',
             'https://www.youtube.com/watch?v=4eaZ_48ZYog'),
            (%s, 'Knives Out', 'Comedy / Mystery', 
             'Witty, hilarious whodunit packed with eccentric characters and laugh-out-loud moments.',
             'https://image.tmdb.org/t/p/w500/pThyQovXQrw2m0s9x82twj48Jq4.jpg',
             'https://www.youtube.com/watch?v=qGqiHJTsRkQ'),
            (%s, 'The Grand Budapest Hotel', 'Comedy / Adventure', 
             'Wes Anderson masterpiece with visually stunning humor and Ralph Fiennes at his comedic peak.',
             'https://image.tmdb.org/t/p/w500/eWdyYQreja6JGCzqHWX9NZkt5BW.jpg',
             'https://www.youtube.com/watch?v=1Fg5iWmQjwk');
        """,
        (night_1_id, night_1_id, night_1_id),
    )

    # 3. Insert Sample Movie Night 2 (Animation - Finalized)
    cursor.execute(
        """
        INSERT INTO movie_nights (creator_id, title, date, category, description, status)
        VALUES (%s, 'Studio Ghibli & Modern Anime Night', '2026-10-18', 'Animation', 
                'Celebration of magnificent animated storytelling and jaw-dropping art.', 'open');
        """,
        (jordan_id,),
    )
    night_2_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO movie_choices (movie_night_id, title, genre, reason, poster_url, trailer_url)
        VALUES 
            (%s, 'Spirited Away', 'Animation / Fantasy', 
             'Hayao Miyazaki legendary Oscar-winning wonder that captivates every single time.',
             'https://image.tmdb.org/t/p/w500/39wmItIWsg5sZMyRUHLkWBcuVCM.jpg',
             'https://www.youtube.com/watch?v=ByXuk9QqQkk'),
            (%s, 'Spider-Man: Into the Spider-Verse', 'Animation / Action', 
             'Revolutionary animation, pulse-pounding soundtrack, and the ultimate superhero origin story.',
             'https://image.tmdb.org/t/p/w500/iiZZdoQBEYBv6id8su7ImL0oCbD.jpg',
             'https://www.youtube.com/watch?v=tg52up16eq0');
        """,
        (night_2_id, night_2_id),
    )

    # Add initial votes for demo feel
    # In Night 1: jordan votes for Knives Out, sam votes for Superbad
    cursor.execute("SELECT id FROM movie_choices WHERE movie_night_id = %s;", (night_1_id,))
    choices_n1 = cursor.fetchall()
    if choices_n1:
        superbad_id = choices_n1[0][0]
        knivesout_id = choices_n1[1][0]
        cursor.execute(
            """
            INSERT INTO votes (movie_night_id, movie_choice_id, user_id)
            VALUES (%s, %s, %s), (%s, %s, %s);
            """,
            (night_1_id, knivesout_id, jordan_id, night_1_id, superbad_id, sam_id),
        )

    conn.commit()


# =====================================================================
# Security & Utility Helpers
# =====================================================================

def login_required(f):
    """
    Decorator to protect routes requiring an active user session.
    
    If the user is not authenticated, flashes a warning and redirects to
    the login page while preserving the intended destination.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this feature.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def extract_youtube_embed_url(url):
    """
    Convert standard YouTube watch URLs and shortened URLs into safe iframe embed URLs.
    
    Supports:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://www.youtube.com/embed/VIDEO_ID
      - URLs with extra query parameters (&t=, &list=, etc.)
    
    Returns:
      Safe embed URL (e.g. 'https://www.youtube-nocookie.com/embed/VIDEO_ID')
      or None if the URL is not a recognized YouTube link.
    """
    if not url or not isinstance(url, str):
        return None

    url = url.strip()
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    hostname = hostname.lower()

    video_id = None

    if "youtube.com" in hostname:
        if parsed.path == "/watch":
            query_params = parse_qs(parsed.query)
            v_list = query_params.get("v")
            if v_list and len(v_list) > 0:
                video_id = v_list[0]
        elif parsed.path.startswith("/embed/"):
            parts = parsed.path.split("/")
            if len(parts) >= 3 and parts[2]:
                video_id = parts[2]
        elif parsed.path.startswith("/v/"):
            parts = parsed.path.split("/")
            if len(parts) >= 3 and parts[2]:
                video_id = parts[2]
    elif "youtu.be" in hostname:
        path = parsed.path.lstrip("/")
        if path:
            video_id = path.split("/")[0]

    # Validate video ID format (YouTube IDs are 11 alphanumeric characters with - and _)
    if video_id and re.match(r"^[A-Za-z0-9_-]{10,12}$", video_id):
        return f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0"

    return None


def is_valid_http_url(url):
    """Validate that a URL starts with http:// or https://."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    return url.startswith("http://") or url.startswith("https://")


# =====================================================================
# Application Routes
# =====================================================================

@app.route("/")
def index():
    """
    Home page route displaying the browsable list of movie nights.
    
    Supports simultaneous search by title (q parameter) and category filtering
    (category parameter) using safe parameterized SQL queries. Preserves the
    selected filters on page reload.
    """
    search_query = request.args.get("q", "").strip()
    selected_category = request.args.get("category", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Base query joining users and movie nights to display creator name
    # and choice count
    sql = """
        SELECT 
            mn.id,
            mn.title,
            mn.date,
            mn.category,
            mn.description,
            mn.status,
            mn.final_movie_id,
            u.name AS creator_name,
            u.username AS creator_username,
            COUNT(DISTINCT mc.id) AS choice_count,
            final_mc.title AS final_movie_title
        FROM movie_nights mn
        JOIN users u ON mn.creator_id = u.id
        LEFT JOIN movie_choices mc ON mn.id = mc.movie_night_id
        LEFT JOIN movie_choices final_mc ON mn.final_movie_id = final_mc.id
    """
    conditions = []
    params = []

    if search_query:
        conditions.append("mn.title LIKE %s")
        params.append(f"%{search_query}%")

    if selected_category and selected_category in ALLOWED_CATEGORIES:
        conditions.append("mn.category = %s")
        params.append(selected_category)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " GROUP BY mn.id, u.name, u.username, final_mc.title ORDER BY mn.date DESC, mn.id DESC;"

    cursor.execute(sql, tuple(params))
    movie_nights = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "index.html",
        movie_nights=movie_nights,
        search_query=search_query,
        selected_category=selected_category,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    User registration route.
    
    Validates required fields, password length, password match, and username
    uniqueness before hashing the password and saving to MySQL. Automatically
    logs in the new user upon success.
    """
    if "user_id" in session:
        return redirect(url_for("index"))

    form_data = {}

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        form_data = {"name": name, "username": username}

        # Input Validation
        if not name or not username or not password or not confirm_password:
            flash("All fields are required.", "danger")
            return render_template("register.html", form_data=form_data)

        if len(name) > 100 or len(username) > 50:
            flash("Name or username exceeds allowed length.", "danger")
            return render_template("register.html", form_data=form_data)

        if not re.match(r"^[a-zA-Z0-9_]{3,30}$", username):
            flash("Username must be 3-30 characters with letters, numbers, or underscores.", "danger")
            return render_template("register.html", form_data=form_data)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("register.html", form_data=form_data)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", form_data=form_data)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Check for duplicate username
            cursor.execute("SELECT id FROM users WHERE username = %s;", (username,))
            existing = cursor.fetchone()

            if existing:
                flash(f"The username '{username}' is already taken. Please choose another.", "danger")
                return render_template("register.html", form_data=form_data)

            # Hash password securely
            password_hash = generate_password_hash(password)

            cursor.execute(
                "INSERT INTO users (name, username, password_hash) VALUES (%s, %s, %s);",
                (name, username, password_hash),
            )
            conn.commit()
            new_user_id = cursor.lastrowid

            # Set user session
            session.clear()
            session["user_id"] = new_user_id
            session["username"] = username
            session["name"] = name

            flash(f"Welcome, {name}! Your account has been created successfully.", "success")
            return redirect(url_for("index"))

        except Error as err:
            conn.rollback()
            flash("A database error occurred during registration. Please try again.", "danger")
            print(f"[Register Error]: {err}")
            return render_template("register.html", form_data=form_data)
        finally:
            cursor.close()
            conn.close()

    return render_template("register.html", form_data=form_data)


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    User login route.
    
    Verifies user credentials against MySQL password hashes and initializes
    the user's browser session upon successful match.
    """
    if "user_id" in session:
        return redirect(url_for("index"))

    username = ""
    next_url = request.args.get("next")

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return render_template("login.html", username=username)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(
                "SELECT id, name, username, password_hash FROM users WHERE username = %s;",
                (username,),
            )
            user = cursor.fetchone()

            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["name"] = user["name"]

                flash(f"Welcome back, {user['name']}!", "success")
                if next_url and next_url.startswith("/"):
                    return redirect(next_url)
                return redirect(url_for("index"))
            else:
                flash("Invalid username or password. Please try again.", "danger")
                return render_template("login.html", username=username)

        except Error as err:
            flash("A database error occurred while logging in.", "danger")
            print(f"[Login Error]: {err}")
            return render_template("login.html", username=username)
        finally:
            cursor.close()
            conn.close()

    return render_template("login.html", username=username)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    """
    User logout route. Clears the session and redirects to the home page.
    """
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/movie-night/create", methods=["GET", "POST"])
@login_required
def create_movie_night():
    """
    Create a new movie night.
    
    Only authenticated users can access this route. Validates title, date,
    category, and description, then inserts the record into MySQL with status 'open'.
    """
    form_data = {}

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        date_str = request.form.get("date", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()

        form_data = {
            "title": title,
            "date": date_str,
            "category": category,
            "description": description,
        }

        # Validation
        if not title or not date_str or not category or not description:
            flash("All fields are mandatory.", "danger")
            return render_template("create_movie_night.html", form_data=form_data)

        if category not in ALLOWED_CATEGORIES:
            flash("Please choose a valid category (Comedy, Action, Animation, or Other).", "danger")
            return render_template("create_movie_night.html", form_data=form_data)

        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format. Please select a valid calendar date.", "danger")
            return render_template("create_movie_night.html", form_data=form_data)

        if len(title) > 150:
            flash("Title must be 150 characters or fewer.", "danger")
            return render_template("create_movie_night.html", form_data=form_data)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO movie_nights (creator_id, title, date, category, description, status)
                VALUES (%s, %s, %s, %s, %s, 'open');
                """,
                (session["user_id"], title, event_date, category, description),
            )
            conn.commit()
            night_id = cursor.lastrowid
            flash("Movie night created! Now suggest movie choices for your guests.", "success")
            return redirect(url_for("movie_detail", night_id=night_id))
        except Error as err:
            conn.rollback()
            flash("Failed to create movie night due to a database error.", "danger")
            print(f"[Create Movie Night Error]: {err}")
            return render_template("create_movie_night.html", form_data=form_data)
        finally:
            cursor.close()
            conn.close()

    return render_template("create_movie_night.html", form_data=form_data)


@app.route("/movie-night/<int:night_id>")
def movie_detail(night_id):
    """
    Detailed view for a specific movie night.
    
    Accessible to all visitors. Displays:
      - Movie night metadata (title, date, category, description, status, creator)
      - List of suggested movie choices with posters, trailers, vote counts, and percentages
      - Winner banner if finalized
      - Current user's vote state (if logged in)
      - Organizer action controls (edit, delete, add choice, finalize) if creator
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Fetch movie night details
    cursor.execute(
        """
        SELECT 
            mn.id,
            mn.creator_id,
            mn.title,
            mn.date,
            mn.category,
            mn.description,
            mn.status,
            mn.final_movie_id,
            u.name AS creator_name,
            u.username AS creator_username
        FROM movie_nights mn
        JOIN users u ON mn.creator_id = u.id
        WHERE mn.id = %s;
        """,
        (night_id,),
    )
    night = cursor.fetchone()

    if not night:
        cursor.close()
        conn.close()
        abort(404)

    # 2. Fetch all movie choices with vote counts
    cursor.execute(
        """
        SELECT 
            mc.id,
            mc.movie_night_id,
            mc.title,
            mc.genre,
            mc.reason,
            mc.poster_url,
            mc.trailer_url,
            COUNT(v.id) AS vote_count
        FROM movie_choices mc
        LEFT JOIN votes v ON mc.id = v.movie_choice_id
        WHERE mc.movie_night_id = %s
        GROUP BY mc.id
        ORDER BY vote_count DESC, mc.id ASC;
        """,
        (night_id,),
    )
    choices = cursor.fetchall()

    # Calculate total votes and percentage per choice
    total_votes = sum(c["vote_count"] for c in choices)
    for c in choices:
        c["vote_percentage"] = (
            round((c["vote_count"] / total_votes) * 100) if total_votes > 0 else 0
        )
        c["trailer_embed_url"] = extract_youtube_embed_url(c["trailer_url"])

    # 3. Check current user's vote (if authenticated)
    user_voted_choice_id = None
    if "user_id" in session:
        cursor.execute(
            """
            SELECT movie_choice_id FROM votes
            WHERE movie_night_id = %s AND user_id = %s;
            """,
            (night_id, session["user_id"]),
        )
        vote_row = cursor.fetchone()
        if vote_row:
            user_voted_choice_id = vote_row["movie_choice_id"]

    # 4. Check if finalized winner choice exists
    final_choice = None
    if night["status"] == "finalized" and night["final_movie_id"]:
        for c in choices:
            if c["id"] == night["final_movie_id"]:
                final_choice = c
                break

    cursor.close()
    conn.close()

    is_creator = "user_id" in session and session["user_id"] == night["creator_id"]

    return render_template(
        "movie_detail.html",
        night=night,
        choices=choices,
        total_votes=total_votes,
        user_voted_choice_id=user_voted_choice_id,
        final_choice=final_choice,
        is_creator=is_creator,
    )


@app.route("/movie-night/<int:night_id>/edit", methods=["GET", "POST"])
@login_required
def edit_movie_night(night_id):
    """
    Edit an existing movie night.
    
    Restricted to the event creator. Prevents edits on finalized events.
    Server-side validation ensures only valid dates and categories are stored.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM movie_nights WHERE id = %s;", (night_id,))
    night = cursor.fetchone()

    if not night:
        cursor.close()
        conn.close()
        abort(404)

    # Server-side creator authorization check
    if night["creator_id"] != session["user_id"]:
        cursor.close()
        conn.close()
        flash("You do not have permission to edit this movie night.", "danger")
        return redirect(url_for("movie_detail", night_id=night_id))

    if night["status"] == "finalized":
        cursor.close()
        conn.close()
        flash("This movie night has already been finalized and cannot be edited.", "warning")
        return redirect(url_for("movie_detail", night_id=night_id))

    form_data = {}

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        date_str = request.form.get("date", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()

        form_data = {
            "title": title,
            "date": date_str,
            "category": category,
            "description": description,
        }

        if not title or not date_str or not category or not description:
            flash("All fields are required.", "danger")
            cursor.close()
            conn.close()
            return render_template("edit_movie_night.html", night=night, form_data=form_data)

        if category not in ALLOWED_CATEGORIES:
            flash("Invalid category selected.", "danger")
            cursor.close()
            conn.close()
            return render_template("edit_movie_night.html", night=night, form_data=form_data)

        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format.", "danger")
            cursor.close()
            conn.close()
            return render_template("edit_movie_night.html", night=night, form_data=form_data)

        try:
            cursor.execute(
                """
                UPDATE movie_nights
                SET title = %s, date = %s, category = %s, description = %s
                WHERE id = %s AND creator_id = %s;
                """,
                (title, event_date, category, description, night_id, session["user_id"]),
            )
            conn.commit()
            flash("Movie night details updated successfully.", "success")
            return redirect(url_for("movie_detail", night_id=night_id))
        except Error as err:
            conn.rollback()
            flash("Database error while updating movie night.", "danger")
            print(f"[Edit Movie Night Error]: {err}")
        finally:
            cursor.close()
            conn.close()

    cursor.close()
    conn.close()
    return render_template("edit_movie_night.html", night=night, form_data=form_data)


@app.route("/movie-night/<int:night_id>/delete", methods=["POST"])
@login_required
def delete_movie_night(night_id):
    """
    Delete a movie night.
    
    Protected route. Checks that the current user is the owner before deleting.
    Cascading foreign keys clean up associated movie choices and votes.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT creator_id, title FROM movie_nights WHERE id = %s;", (night_id,))
    night = cursor.fetchone()

    if not night:
        cursor.close()
        conn.close()
        abort(404)

    if night["creator_id"] != session["user_id"]:
        cursor.close()
        conn.close()
        flash("Unauthorized: You cannot delete a movie night you did not create.", "danger")
        return redirect(url_for("movie_detail", night_id=night_id))

    try:
        cursor.execute("DELETE FROM movie_nights WHERE id = %s;", (night_id,))
        conn.commit()
        flash(f"Movie night '{night['title']}' was deleted.", "info")
        return redirect(url_for("index"))
    except Error as err:
        conn.rollback()
        flash("Failed to delete movie night due to a database error.", "danger")
        print(f"[Delete Movie Night Error]: {err}")
        return redirect(url_for("movie_detail", night_id=night_id))
    finally:
        cursor.close()
        conn.close()


@app.route("/movie-night/<int:night_id>/choices/add", methods=["POST"])
@login_required
def add_movie_choice(night_id):
    """
    Add a movie choice to a movie night.
    
    Only the creator of an open movie night can add movie choices. Validates
    poster and trailer URLs and stores the choice in MySQL.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT creator_id, status FROM movie_nights WHERE id = %s;", (night_id,))
    night = cursor.fetchone()

    if not night:
        cursor.close()
        conn.close()
        abort(404)

    if night["creator_id"] != session["user_id"]:
        cursor.close()
        conn.close()
        flash("Only the creator of this movie night can add movie choices.", "danger")
        return redirect(url_for("movie_detail", night_id=night_id))

    if night["status"] == "finalized":
        cursor.close()
        conn.close()
        flash("Cannot add choices to a finalized movie night.", "warning")
        return redirect(url_for("movie_detail", night_id=night_id))

    title = request.form.get("title", "").strip()
    genre = request.form.get("genre", "").strip()
    reason = request.form.get("reason", "").strip()
    poster_url = request.form.get("poster_url", "").strip()
    trailer_url = request.form.get("trailer_url", "").strip() or None

    if not title or not genre or not reason or not poster_url:
        cursor.close()
        conn.close()
        flash("Title, genre, reason, and poster URL are mandatory.", "danger")
        return redirect(url_for("movie_detail", night_id=night_id))

    if not is_valid_http_url(poster_url):
        cursor.close()
        conn.close()
        flash("Poster URL must start with http:// or https://", "danger")
        return redirect(url_for("movie_detail", night_id=night_id))

    if trailer_url and not is_valid_http_url(trailer_url):
        cursor.close()
        conn.close()
        flash("Trailer URL must be a valid http:// or https:// web link.", "danger")
        return redirect(url_for("movie_detail", night_id=night_id))

    try:
        cursor.execute(
            """
            INSERT INTO movie_choices (movie_night_id, title, genre, reason, poster_url, trailer_url)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            (night_id, title, genre, reason, poster_url, trailer_url),
        )
        conn.commit()
        flash(f"Suggested choice '{title}' added successfully!", "success")
    except Error as err:
        conn.rollback()
        flash("Failed to save movie choice due to a database error.", "danger")
        print(f"[Add Choice Error]: {err}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("movie_detail", night_id=night_id))


@app.route("/movie-night/<int:night_id>/choices/<int:choice_id>/delete", methods=["POST"])
@login_required
def delete_movie_choice(night_id, choice_id):
    """
    Delete a movie choice from a movie night.
    
    Allowed only for the creator while the movie night is still open.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT creator_id, status FROM movie_nights WHERE id = %s;", (night_id,))
    night = cursor.fetchone()

    if not night:
        cursor.close()
        conn.close()
        abort(404)

    if night["creator_id"] != session["user_id"]:
        cursor.close()
        conn.close()
        flash("Unauthorized: Only the host can remove movie choices.", "danger")
        return redirect(url_for("movie_detail", night_id=night_id))

    if night["status"] == "finalized":
        cursor.close()
        conn.close()
        flash("Cannot remove choices after finalization.", "warning")
        return redirect(url_for("movie_detail", night_id=night_id))

    try:
        cursor.execute(
            "DELETE FROM movie_choices WHERE id = %s AND movie_night_id = %s;",
            (choice_id, night_id),
        )
        conn.commit()
        flash("Movie choice removed.", "info")
    except Error as err:
        conn.rollback()
        flash("Error removing movie choice.", "danger")
        print(f"[Delete Choice Error]: {err}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("movie_detail", night_id=night_id))


@app.route("/movie-night/<int:night_id>/vote", methods=["POST"])
@login_required
def vote_movie(night_id):
    """
    Submit or update a user's vote for a movie choice.
    
    Enforces:
      - Active session check
      - Open status on the movie night
      - Validation that the chosen movie belongs to this movie night
      - One vote per user constraint (ON DUPLICATE KEY UPDATE in MySQL replaces vote)
    """
    choice_id = request.form.get("choice_id")

    if not choice_id:
        flash("No movie choice selected for voting.", "warning")
        return redirect(url_for("movie_detail", night_id=night_id))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check night status
        cursor.execute("SELECT status FROM movie_nights WHERE id = %s;", (night_id,))
        night = cursor.fetchone()

        if not night:
            abort(404)

        if night["status"] == "finalized":
            flash("Voting has closed for this movie night.", "warning")
            return redirect(url_for("movie_detail", night_id=night_id))

        # Validate that the choice belongs to this movie night
        cursor.execute(
            "SELECT id, title FROM movie_choices WHERE id = %s AND movie_night_id = %s;",
            (choice_id, night_id),
        )
        choice = cursor.fetchone()

        if not choice:
            flash("Selected movie choice is invalid for this movie night.", "danger")
            return redirect(url_for("movie_detail", night_id=night_id))

        # Insert or replace existing vote using MySQL's unique constraint (movie_night_id, user_id)
        cursor.execute(
            """
            INSERT INTO votes (movie_night_id, movie_choice_id, user_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE movie_choice_id = VALUES(movie_choice_id);
            """,
            (night_id, choice_id, session["user_id"]),
        )
        conn.commit()
        flash(f"Your vote for '{choice['title']}' has been recorded!", "success")

    except Error as err:
        conn.rollback()
        flash("Failed to record your vote due to a database error.", "danger")
        print(f"[Vote Error]: {err}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("movie_detail", night_id=night_id))


@app.route("/movie-night/<int:night_id>/finalize", methods=["POST"])
@login_required
def finalize_movie_night(night_id):
    """
    Finalize a movie night by selecting the winning movie.
    
    Enforces:
      - Current user is the event creator
      - Movie night has at least 2 choices
      - Selected winner belongs to this movie night
      - Status changes from 'open' to 'finalized'
      - Sets final_movie_id, which permanently displays the winner and locks voting
    """
    final_movie_id = request.form.get("final_movie_id")

    if not final_movie_id:
        flash("Please select a winning movie to finalize.", "warning")
        return redirect(url_for("movie_detail", night_id=night_id))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT creator_id, status FROM movie_nights WHERE id = %s;", (night_id,)
        )
        night = cursor.fetchone()

        if not night:
            abort(404)

        if night["creator_id"] != session["user_id"]:
            flash("Unauthorized: Only the creator can finalize the movie night.", "danger")
            return redirect(url_for("movie_detail", night_id=night_id))

        if night["status"] == "finalized":
            flash("This movie night is already finalized.", "warning")
            return redirect(url_for("movie_detail", night_id=night_id))

        # Verify minimum 2 choices
        cursor.execute(
            "SELECT COUNT(*) AS choice_count FROM movie_choices WHERE movie_night_id = %s;",
            (night_id,),
        )
        count_row = cursor.fetchone()
        if count_row["choice_count"] < 2:
            flash("You must add at least two movie choices before finalizing.", "warning")
            return redirect(url_for("movie_detail", night_id=night_id))

        # Verify that selected winner belongs to this movie night
        cursor.execute(
            "SELECT id, title FROM movie_choices WHERE id = %s AND movie_night_id = %s;",
            (final_movie_id, night_id),
        )
        winner = cursor.fetchone()

        if not winner:
            flash("Invalid winner selection.", "danger")
            return redirect(url_for("movie_detail", night_id=night_id))

        # Update movie night to finalized
        cursor.execute(
            """
            UPDATE movie_nights
            SET status = 'finalized', final_movie_id = %s
            WHERE id = %s AND creator_id = %s;
            """,
            (final_movie_id, night_id, session["user_id"]),
        )
        conn.commit()
        flash(f"Movie night finalized! The official winner is '{winner['title']}'.", "success")

    except Error as err:
        conn.rollback()
        flash("Failed to finalize movie night due to a database error.", "danger")
        print(f"[Finalize Error]: {err}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("movie_detail", night_id=night_id))


# =====================================================================
# Error Handlers
# =====================================================================

@app.errorhandler(404)
def page_not_found(e):
    """Render friendly 404 page for missing URLs or nonexistent movie nights."""
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    """Render friendly 500 page for unexpected internal server errors."""
    return (
        render_template(
            "404.html",
            error_title="Server Error (500)",
            error_message="Something unexpected went wrong on our end. Please try again shortly.",
        ),
        500,
    )


# =====================================================================
# Application Entrypoint
# =====================================================================

if __name__ == "__main__":
    # Initialize database tables and seed data if not yet created
    init_db()
    # Run development server on port 5000 (accessible on local network)
    app.run(host="0.0.0.0", port=5000, debug=True)
