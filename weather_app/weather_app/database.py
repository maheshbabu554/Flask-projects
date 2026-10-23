"""
database.py
-----------
Small helper for the SQLite database.

SQLite is built into Python, so you do NOT need to install or set up
anything. The file weather.db is created automatically.

Tables
~~~~~~
saved_cities   : cities shown on the "My Cities" page
search_history : every successful search (shown on "History")
settings       : key/value pairs, e.g. unit = C or F
"""
import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS saved_cities (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    region     TEXT,
    country    TEXT,
    latitude   REAL NOT NULL,
    longitude  REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (latitude, longitude)
);

CREATE TABLE IF NOT EXISTS search_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    region      TEXT,
    country     TEXT,
    latitude    REAL NOT NULL,
    longitude   REAL NOT NULL,
    searched_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def get_db():
    """Return the database connection for the current request.

    The connection is opened only once per request and stored in
    Flask's ``g`` object, then closed automatically by ``close_db``.
    """
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE_PATH"])
        g.db.row_factory = sqlite3.Row  # lets us read columns by name
    return g.db


def close_db(error=None):
    """Close the database connection at the end of each request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    """Connect the database helpers to the Flask app and create tables."""
    app.teardown_appcontext(close_db)
    with app.app_context():
        get_db().executescript(SCHEMA)


def get_setting(key, default=None):
    """Read one setting value (returns ``default`` if it does not exist)."""
    row = get_db().execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    """Create or update one setting value."""
    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    db.commit()
