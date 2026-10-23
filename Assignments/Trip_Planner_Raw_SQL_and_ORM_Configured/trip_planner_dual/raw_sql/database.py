"""MySQL connection helpers and schema initialization for Trip Planner."""
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Return a new MySQL connection using values from .env."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "trip_planner"),
        autocommit=False,
    )


def initialize_database():
    """Create application tables if they do not already exist.

    Create the database itself once in MySQL Workbench before running the app.
    """
    statements = [
        """CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL,
            email VARCHAR(120) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS trips (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            destination VARCHAR(120) NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            budget DECIMAL(12,2) NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_trips_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_trips_user (user_id)
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS activities (
            id INT AUTO_INCREMENT PRIMARY KEY,
            trip_id INT NOT NULL,
            name VARCHAR(120) NOT NULL,
            activity_date DATE NOT NULL,
            activity_time TIME NULL,
            category VARCHAR(40) NOT NULL,
            place VARCHAR(160) NOT NULL,
            cost DECIMAL(12,2) NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_activities_trip FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE,
            INDEX idx_activities_trip_date (trip_id, activity_date)
        ) ENGINE=InnoDB""",
        """CREATE TABLE IF NOT EXISTS place_suggestions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            destination VARCHAR(120) NOT NULL,
            category VARCHAR(40) NOT NULL,
            description VARCHAR(500) NOT NULL,
            created_by INT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_suggestions_user FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
            INDEX idx_suggestions_destination (destination),
            INDEX idx_suggestions_category (category)
        ) ENGINE=InnoDB""",
    ]
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        for statement in statements:
            cursor.execute(statement)
        connection.commit()
    except Error:
        if connection:
            connection.rollback()
        raise
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
