# Trip Planner — ORM version

This version uses Flask-SQLAlchemy and the shared MySQL database `trip_planner_raw_sql_orm`. ORM tables have an `orm_` prefix to keep their data separate from the Raw SQL version.

1. Copy `.env.example` to `.env`.
2. Set your MySQL password and a strong `SECRET_KEY`; keep `DB_NAME=trip_planner_raw_sql_orm`.
3. Create the database in MySQL Workbench if it does not exist: `CREATE DATABASE IF NOT EXISTS trip_planner_raw_sql_orm;`
4. In this folder, run `py -m venv .venv`, then `.venv\Scripts\activate`, then `py -m pip install -r requirements.txt`.
5. Run `py app.py` and open `http://127.0.0.1:5000`.

Tables created by this project: `orm_users`, `orm_trips`, `orm_activities`, and `orm_place_suggestions`. `db.create_all()` creates missing tables; it does not drop existing tables.
