# WeatherApp — Flask + MySQL ORM

This project uses Flask, Flask-SQLAlchemy (ORM), MySQL, and Open-Meteo weather/geocoding APIs. Open-Meteo does not require an API key.

## Features
- No login or registration pages.
- Search city autocomplete dropdown using Open-Meteo geocoding.
- Current weather, today's highlights, and a five-day forecast.
- Saved cities and search history shared by visitors through a guest profile.
- Friendly error messages for invalid city names and weather/API/database problems.
- Success toast after a city weather search completes.
- All application database reads/writes use SQLAlchemy ORM. No raw SQL statements are used in `app.py`.

## Requirements
- Python 3.10+
- MySQL Server

## Setup (Windows)
1. Create a MySQL database (if it does not already exist):
   ```sql
   CREATE DATABASE weather_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
   This one-time database creation statement is for setup only; the application itself uses ORM.
2. Copy `.env.example` to `.env` and update `DB_USER`, `DB_PASSWORD`, and other settings.
3. Open a terminal in this project folder and create a virtual environment:
   ```powershell
   py -m venv venv
   .\\venv\\Scripts\\activate
   ```
4. Install packages:
   ```powershell
   pip install -r requirements.txt
   ```
5. Start the app:
   ```powershell
   python app.py
   ```
6. Open http://127.0.0.1:5000

## Database notes
The app uses the existing `weather_app` database by default. SQLAlchemy `db.create_all()` creates missing tables but does not migrate or repair existing tables. Back up your database before changing schemas. A shared guest user is used to keep the existing `user_id` relationships in the saved city/history tables.

## Project structure
```text
WeatherApp_ORM/
├── app.py
├── config.py
├── requirements.txt
├── .env.example
├── README.md
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── search.html
│   ├── weather.html
│   ├── cities.html
│   ├── history.html
│   ├── settings.html
│   └── error.html
└── static/
    ├── css/style.css
    └── js/script.js
```

## UI note
The included stylesheet recreates a clean weather dashboard because the original stylesheet was not attached in the request. If you want the exact original UI, replace `static/css/style.css` with your existing stylesheet. The HTML keeps the same overall weather-card and sidebar structure.
