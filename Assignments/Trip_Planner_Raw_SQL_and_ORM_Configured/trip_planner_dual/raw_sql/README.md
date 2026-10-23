# Trip Planner — Raw SQL version

This version uses `mysql.connector` and parameterized SQL. It uses the shared database `trip_planner_raw_sql_orm`, but its tables are unprefixed and separate from the ORM version.

1. Copy `.env.example` to `.env`. Set your MySQL password and a strong `SECRET_KEY`; keep `DB_NAME=trip_planner_raw_sql_orm`.
2. Create the database in MySQL Workbench if it does not exist: `CREATE DATABASE IF NOT EXISTS trip_planner_raw_sql_orm;`
3. In this folder, run `py -m venv .venv`, then `.venv\Scripts\activate`, then `py -m pip install -r requirements.txt`.
4. Run `py app.py` and open `http://127.0.0.1:5000`.

Tables used by this project: `users`, `trips`, `activities`, and `place_suggestions`. Do not run it simultaneously with the ORM app on the same port.
