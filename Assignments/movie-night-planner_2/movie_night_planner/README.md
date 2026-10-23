# Movie Night Planner — Flask & MySQL Web Application

A complete, multipage movie planning web application built with **Python 3**, **Flask**, **MySQL**, **Jinja2**, and **Bootstrap 5.3.8**.

Movie lovers can organize movie nights, propose movie choices with real high-resolution posters and YouTube trailer links, vote on their favorite movies, and empower the event creator to review the votes and finalize the winning title.

---

## 🍿 Features

- **Equal Registered Users**: Every registered user has the same capabilities (no special admin tiers or dashboards).
- **User Authentication**: Secure signup, login, and logout with password hashing via Werkzeug (`scrypt` / `pbkdf2`).
- **Session-Based State**: Safe HTTP-only session cookies and CSRF protection via Flask-WTF on every form submission.
- **Search & Category Filtering**: Filter movie nights simultaneously by search title and category (`Comedy`, `Action`, `Animation`, `Other`) via bookmarkable GET parameters.
- **Movie Choices with Real Media**: High-definition poster cards with local SVG fallback for broken links, plus responsive YouTube trailer modal player.
- **Fair Voting System**: Each user gets exactly 1 vote per movie night; changing a vote seamlessly updates the existing vote without duplicate records.
- **Creator Finalization**: Once at least 2 choices exist, the event organizer can finalize the winner. Voting is locked and the winning film is prominently showcased.
- **Server-Side Authorization**: Ownership checks are strictly verified on the server before edit, delete, add choice, or finalize actions.

---

## 📁 Project Folder Structure

```text
movie_night_planner/
├── app.py                      # Main Flask application with routes, database helpers & docstrings
├── requirements.txt            # Python dependencies
├── schema.sql                  # MySQL database initialization script
├── .env                        # Database credentials and secret key (never commit to git)
├── .env.example                # Example template for environment configuration
├── .gitignore                  # Git exclusions for Python and sensitive credentials
├── README.md                   # Full documentation & setup guide
├── templates/                  # Jinja2 HTML templates
│   ├── base.html               # Master layout with Bootstrap 5.3.8, navbar, alerts & trailer modal
│   ├── index.html              # Home page with search, category filtering & movie nights grid
│   ├── movie_detail.html       # Movie night details, suggested choices, voting & winner showcase
│   ├── register.html           # User registration page
│   ├── login.html              # User login page with demo account hints
│   ├── create_movie_night.html # Form to organize a new movie night
│   ├── edit_movie_night.html   # Form for creators to edit their movie night
│   └── 404.html                # Friendly 404 error page
└── static/
    ├── style.css               # Cinematic dark styling & responsive aspect ratios
    ├── app.js                  # Video modal controller & image fallbacks
    └── images/
        └── movie-placeholder.svg # Local SVG fallback poster
```

---

## 🚀 Windows Setup & Installation

### Step 1: Open PowerShell or Command Prompt
Navigate to your desired project directory:
```powershell
cd C:\Users\YourUsername\Projects
```

### Step 2: Extract or Clone the Project
Make sure you are in the `movie_night_planner` folder:
```powershell
cd movie_night_planner
```

### Step 3: Create a Python Virtual Environment
```powershell
python -m venv venv
```

### Step 4: Activate the Virtual Environment
On Windows PowerShell:
```powershell
.\venv\Scripts\Activate.ps1
```
*(If PowerShell shows an execution policy error, run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)*

On Command Prompt (`cmd.exe`):
```cmd
venv\Scripts\activate.bat
```

### Step 5: Install Project Dependencies
```powershell
pip install -r requirements.txt
```

---

## 🗄️ MySQL Database Setup

### Step 1: Start MySQL Server
Ensure MySQL is running (e.g., via MySQL Workbench, XAMPP, or Windows Services).

### Step 2: Create the Database
Open MySQL Command Line Client or terminal:
```sql
mysql -u root -p
```
Run:
```sql
CREATE DATABASE IF NOT EXISTS movie_night_planner CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

### Step 3: Configure `.env` File
Create or open the `.env` file in the `movie_night_planner/` directory:
```env
SECRET_KEY=dev_secret_key_change_in_production_7f8a9b2c3d4e5f6
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_actual_mysql_password
DB_NAME=movie_night_planner
```

---

## ▶️ Running the Application

With your virtual environment activated, run:
```powershell
python app.py
```

The database tables and sample initial movie nights will be created automatically on the first startup.

Open your browser and navigate to:
```text
http://127.0.0.1:5000
```

---

## 🔑 Demo Accounts for Testing

The application automatically seeds initial demo accounts on first run:

| Username | Password | Role / Description |
| :--- | :--- | :--- |
| `alex` | `password123` | Creator of "Friday Night Comedy Blast" |
| `jordan` | `password123` | Creator of "Studio Ghibli & Modern Anime Night" |
| `sam` | `password123` | Community Voter |

You can also register any new account on the `/register` page.

---

## 🧪 Feature Testing Checklist

- [ ] **Browse**: Visit `http://127.0.0.1:5000/` as a guest and view movie nights.
- [ ] **Search & Filter**: Search for "Comedy" or filter by "Action" / "Animation".
- [ ] **Register**: Create a new account with a unique username.
- [ ] **Login**: Sign in with `alex` / `password123`.
- [ ] **Create Event**: Click "Plan Movie Night" and create a new event.
- [ ] **Add Choices**: Suggest 2 or more movies with posters and YouTube links.
- [ ] **Watch Trailer**: Click "Watch Trailer" to open the YouTube trailer modal.
- [ ] **Voting**: Switch user to `jordan` or `sam` and vote for a film. Switch vote and verify count updates accurately without duplicating.
- [ ] **Finalize Winner**: Log back in as `alex`, click "Finalize Winner", pick the movie, and confirm. Verify that voting closes and the winner is highlighted with the trophy banner.

---

## 🎓 College Viva / Project Demonstration Notes

1. **How is password security handled?**
   - We use `werkzeug.security.generate_password_hash` which utilizes salted PBKDF2/scrypt. Passwords are never stored in plain text.
2. **How is SQL injection prevented?**
   - All queries use parameterized SQL placeholders (`%s`) handled by `mysql-connector-python`. User input is never concatenated into raw SQL strings.
3. **How does duplicate voting prevention work?**
   - The `votes` table has a composite unique constraint: `UNIQUE KEY uq_user_movie_night (movie_night_id, user_id)`. Our query uses `ON DUPLICATE KEY UPDATE movie_choice_id = VALUES(movie_choice_id)` so voting again cleanly switches the user's vote.
4. **How are ownership rules enforced?**
   - In `app.py`, route handlers verify `if night['creator_id'] != session['user_id']: abort(403)`. Client-side hiding of buttons is backed up by server-side verification.
