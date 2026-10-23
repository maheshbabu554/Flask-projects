# WeatherApp (Flask + MySQL + Open-Meteo)

Features: register / login / logout, dashboard, city search, 5-day forecast,
My Cities (add / remove), search history, settings.

Weather data comes from **Open-Meteo** (https://open-meteo.com) - it is free
and needs **no API key**.

## Setup (Windows)

1. Create the database in MySQL Workbench (see below).
2. Open the `.env` file and set `DB_PASSWORD` to your MySQL root password.
   (If `.env` is missing, copy `.env.example` to `.env`.)
3. In the project folder run:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

4. Open http://127.0.0.1:5000 , click **Sign Up**, create an account, then log in.

## Create the database in MySQL Workbench

1. Open MySQL Workbench and connect to your local server.
2. File > Open SQL Script... > choose `database.sql`
   (or paste its SQL into a new query tab).
3. Click the lightning bolt (Execute).
4. Refresh the Schemas panel: you should see `weather_app` with the tables
   `users`, `saved_cities`, `search_history`.

## Where to change things

| I want to change...         | Open this file                       |
|-----------------------------|--------------------------------------|
| Colors, card sizes, layout  | static/css/style.css (see :root)     |
| Sidebar menu                | templates/base.html                  |
| Weather card / forecast     | templates/_weather.html              |
| Pages and buttons           | templates/*.html                     |
| Routes and SQL queries      | app.py                               |
| Weather icons / descriptions| app.py (WEATHER_CODES)               |
| Database tables / fields    | database.sql (+ queries in app.py)   |
| Default city                | config.py                            |
| MySQL password              | .env                                 |

## Troubleshooting

- "Database error": MySQL is not running, or DB_PASSWORD in `.env` is wrong,
  or you did not run `database.sql` yet.
- "Could not reach the weather service": check your internet connection.
