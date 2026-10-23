# WeatherApp (Flask + Open-Meteo)

A simple weather website. No login, no API key, no database setup.

## How to run (Windows)

```bat
cd weather_app
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open  http://127.0.0.1:5000  in your browser.
(Mac/Linux: use `source venv/bin/activate` instead of the activate line.)

## Features
* Live dropdown: type "anan" and every matching city appears.
* "City fetched successfully" (green) or "City not found - incorrect city" (red) appears instantly.
* Pages: Home, Search, My Cities, History, Settings.
* Server-side validation for every value that reaches the API.
* Wrong city / wrong data returns 400 / 404 (never 200).

## Project structure
```
weather_app/
├── app.py              Flask routes (pages + JSON API)
├── config.py           All settings in one place
├── database.py         SQLite helper (tables are created automatically)
├── validators.py       Server-side validation rules
├── weather_service.py  Talks to Open-Meteo (geocoding + forecast)
├── requirements.txt
├── templates/          HTML pages (Jinja2)
└── static/
    ├── css/style.css
    ├── img/hero-bg.svg Home page background (replace with any photo)
    └── js/
        ├── main.js     Shared code: toast, dropdown, cards, icons
        ├── home.js  search.js  cities.js  history.js  settings.js
```

## API
| Method | Address | Purpose |
|---|---|---|
| GET | /api/suggest?q=anan | dropdown cities |
| GET | /api/weather?city=Hyderabad | weather by name |
| GET | /api/weather?lat=..&lon=..&name=.. | weather by dropdown choice |
| GET / POST / DELETE | /api/cities | My Cities |
| GET / DELETE | /api/history | History |
| POST | /api/settings | temperature unit |

## Status codes
200 OK · 201 created · 400 wrong data · 404 city not found · 409 already saved · 503 weather service down
