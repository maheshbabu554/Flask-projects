TRIP PLANNER — RAW SQL + ORM IN ONE MYSQL DATABASE

This ZIP contains two independent Flask projects:
  raw_sql/  uses mysql.connector and SQL queries.
  orm/      uses Flask-SQLAlchemy (ORM).

Both projects use the same MySQL database: trip_planner_raw_sql_orm. Their tables and data are kept separate:
  Raw SQL: users, trips, activities, place_suggestions
  ORM:     orm_users, orm_trips, orm_activities, orm_place_suggestions

IMPORTANT: Do not put your real password into the ZIP or share your .env file.

SETUP (do the ORM project first)
1. Extract this ZIP. Open the trip_planner_dual/orm folder in VS Code.
2. In MySQL Workbench, run: CREATE DATABASE IF NOT EXISTS trip_planner_raw_sql_orm;
3. Copy orm/.env.example to orm/.env. Open .env and enter your own MySQL password and a strong SECRET_KEY. Keep DB_NAME=trip_planner_raw_sql_orm.
4. Open a terminal in the orm folder and run:
     py -m venv .venv
     .venv\Scripts\activate
     py -m pip install -r requirements.txt
     py app.py
5. Open http://127.0.0.1:5000. The ORM tables are created automatically when the app starts.
6. Verify in Workbench:
     USE trip_planner_raw_sql_orm;
     SHOW TABLES;
   Look for the four orm_ tables.

RAW SQL PROJECT (after ORM is working)
1. Open the raw_sql folder in a separate VS Code window.
2. Copy raw_sql/.env.example to raw_sql/.env and enter the same MySQL credentials. Keep the same DB_NAME.
3. In its terminal run:
     py -m venv .venv
     .venv\Scripts\activate
     py -m pip install -r requirements.txt
     py app.py
4. Its tables use the unprefixed names listed above.

Run only one project at a time because both default to port 5000. Each implementation stores users and trips in its own tables; accounts/data are not shared between implementations.

The apps do not intentionally drop tables or erase existing data. If the database already contains old tables, keep them; do not run DROP TABLE commands. The ORM now uses prefixed table names so it won't reuse the raw SQL tables.
