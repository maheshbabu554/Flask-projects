# Triply — Flask Trip Planner

A beginner-friendly multi-page Flask app using MySQL Connector, Bootstrap 5, Jinja templates, CSS and a small amount of JavaScript. It uses plain parameterized SQL (no ORM).

## Features
- Register, login and logout; passwords are stored as Werkzeug password hashes.
- Users can view and manage only their own trips and activities.
- Create/edit/delete trips with destination, dates and budget.
- Add/edit/delete activities with date, optional time, category, place and estimated cost.
- Itinerary grouped by date, calculated total, budget remaining/over-budget indicator.
- Server-side validation for date ranges, non-negative money values and required fields.
- Trip dates cannot be changed if saved activities would fall outside the new range.
- Public Explore page with combined search and category filtering; signed-in users can submit place suggestions.
- Tables are created automatically when the app starts. The database itself must exist first.

## Folder structure
```text
trip_planner/
├── app.py
├── database.py
├── .env.example
├── requirements.txt
├── README.md
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── register.html
│   ├── login.html
│   ├── my_trips.html
│   ├── trip_form.html
│   ├── trip_detail.html
│   ├── activity_form.html
│   ├── explore.html
│   ├── suggest_place.html
│   ├── 404.html
│   └── 500.html
└── static/
    ├── css/style.css
    └── js/script.js
```

## Setup (Windows / VS Code)
1. Install Python 3.10+ and MySQL Server.
2. Open MySQL Workbench and run:
   ```sql
   CREATE DATABASE trip_planner CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
3. Copy `.env.example` to a file named `.env` in this folder. Update `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`, and replace `SECRET_KEY` with a long random value. Never share your real `.env` file.
4. Open a terminal in this folder and run:
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   py app.py
   ```
5. Open `http://127.0.0.1:5000` in your browser.

`database.py` creates the tables (`users`, `trips`, `activities`, `place_suggestions`) on startup. You do not need a separate SQL file. Bootstrap and Google Fonts are loaded from CDNs, so those design resources need an internet connection.

## Demo checklist
1. Register two separate accounts.
2. As account A, create a trip with two or more days and a budget.
3. Add one activity on each of two days. Check date grouping and the calculated total.
4. Edit an activity cost; confirm the total and budget difference update on the trip page.
5. Try an activity date outside the trip and a negative cost; server-side validation should reject each.
6. Try shortening the trip dates so an existing activity falls outside the trip; the edit should be rejected with an explanation.
7. Log in as account B and manually visit account A's trip URL; the app returns a not-found page.
8. Use Explore search and category filters together; reset to clear both.

## Notes
- For local development, the app uses Flask's built-in server. Do not deploy with debug mode enabled.
- Set `FLASK_DEBUG=true` in `.env` only while actively debugging; otherwise leave it unset/false.
- A zero budget is allowed and shown as “no budget set” unless activities have costs.
