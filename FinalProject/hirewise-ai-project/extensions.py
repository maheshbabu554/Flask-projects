
"""
Initialize Flask extensions used throughout HireWise AI.

Extensions are created here and connected to the Flask application
inside the application factory in app.py.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate


# Database ORM
db = SQLAlchemy()

# User authentication and session management
login_manager = LoginManager()

# Database migration management
migrate = Migrate()
