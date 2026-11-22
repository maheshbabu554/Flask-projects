
"""
Main application file for HireWise AI.

Creates and configures the Flask application, initializes
extensions, configures authentication, and registers routes.
"""

import os
from pathlib import Path

import zcatalyst_sdk

from flask import Flask, redirect, url_for, request, g

from config import Config
from extensions import db, login_manager, migrate


def create_app():
    """Create and configure the HireWise AI application."""

    app = Flask(__name__)

    # -----------------------------------------------------
    # APPLICATION CONFIGURATION
    # -----------------------------------------------------

    app.config.from_object(Config)

    # Allow up to 20 resumes of 5 MB each in one request,
    # plus 1 MB for multipart request overhead.
    app.config["MAX_CONTENT_LENGTH"] = (
        20 * 5 * 1024 * 1024
    ) + (1 * 1024 * 1024)

    # -----------------------------------------------------
    # CATALYST SDK INITIALIZATION
    # -----------------------------------------------------

    @app.before_request
    def initialize_catalyst():
        """
        Initialize Catalyst SDK when running inside AppSail.

        Local development continues without Catalyst initialization.
        """

        if os.getenv("X_ZOHO_CATALYST_LISTEN_PORT"):
            g.catalyst_app = zcatalyst_sdk.initialize(req=request)

    # -----------------------------------------------------
    # INITIALIZE FLASK EXTENSIONS
    # -----------------------------------------------------

    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = (
        "Please log in to access this page."
    )
    login_manager.login_message_category = "warning"

    migrate.init_app(app, db)

    # -----------------------------------------------------
    # PRIVATE RESUME STORAGE
    # -----------------------------------------------------

    upload_folder = (
        Path(app.config["UPLOAD_FOLDER"]) / "resumes"
    )

    upload_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    app.config["RESUME_UPLOAD_FOLDER"] = str(upload_folder)

    # -----------------------------------------------------
    # PRIVATE CANDIDATE DOCUMENT STORAGE
    # -----------------------------------------------------

    private_document_folder = (
        Path(app.instance_path) / "private_documents"
    )

    private_document_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    app.config["PRIVATE_DOCUMENT_FOLDER"] = str(
        private_document_folder
    )

    # -----------------------------------------------------
    # USER SESSION LOADER
    # -----------------------------------------------------

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        """Load the authenticated user from the database."""

        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    # -----------------------------------------------------
    # IMPORT APPLICATION BLUEPRINTS
    # -----------------------------------------------------

    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.recruiter import recruiter_bp
    from routes.vacancies import vacancy_bp
    from routes.candidates import candidate_bp
    from routes.interviews import interview_bp
    from routes.followups import followup_bp
    from routes.ai import ai_bp
    from routes.offer_letters import offer_letters_bp
    from routes.document_upload import document_upload_bp

    # -----------------------------------------------------
    # REGISTER APPLICATION BLUEPRINTS
    # -----------------------------------------------------

    app.register_blueprint(auth_bp)

    app.register_blueprint(
        admin_bp,
        url_prefix="/admin",
    )

    app.register_blueprint(
        recruiter_bp,
        url_prefix="/recruiter",
    )

    app.register_blueprint(vacancy_bp)
    app.register_blueprint(candidate_bp)
    app.register_blueprint(interview_bp)
    app.register_blueprint(followup_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(offer_letters_bp)

    # Candidate one-time document upload portal
    app.register_blueprint(document_upload_bp)

    # -----------------------------------------------------
    # HOME ROUTE
    # -----------------------------------------------------

    @app.route("/")
    def index():
        """Redirect visitors to login or their dashboard."""

        from flask_login import current_user

        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))

        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))

        return redirect(url_for("recruiter.dashboard"))

    return app


# ---------------------------------------------------------
# APPLICATION INSTANCE
# ---------------------------------------------------------

app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
