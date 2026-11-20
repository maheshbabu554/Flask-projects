
"""
Create the initial administrator account for HireWise AI.

Run:
    python scripts/create_admin.py
"""

import sys
from pathlib import Path
from getpass import getpass

# Add project root to Python path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from extensions import db
from models import User
from services.auth_service import hash_password


def create_admin():
    """Create the first administrator account."""

    app = create_app()

    with app.app_context():

        existing_admin = db.session.query(User).filter_by(
            role="admin"
        ).first()

        if existing_admin:
            print("An administrator account already exists.")
            return

        print("\n===== HireWise AI - Create Administrator =====\n")

        full_name = input("Administrator name: ").strip()
        email = input("Administrator email: ").strip().lower()
        password = getpass("Administrator password: ")
        confirm_password = getpass("Confirm password: ")

        if not full_name or not email or not password:
            print("All fields are required.")
            return

        if len(full_name) > 100 or len(email) > 120:
            print("Name or email exceeds the allowed length.")
            return

        if "@" not in email or "." not in email.split("@")[-1]:
            print("Enter a valid email address.")
            return

        if password != confirm_password:
            print("Passwords do not match.")
            return

        if len(password) < 8:
            print("Password must contain at least 8 characters.")
            return

        existing_user = db.session.query(User).filter_by(
            email=email
        ).first()

        if existing_user:
            print("An account with this email already exists.")
            return

        try:
            admin = User(
                full_name=full_name,
                email=email,
                password_hash=hash_password(password),
                role="admin",
                status="active",
            )

            db.session.add(admin)
            db.session.commit()

            print("\nAdministrator account created successfully.")
            print("You can now log in to HireWise AI.")

        except Exception:
            db.session.rollback()
            print("\nUnable to create administrator account.")
            raise


if __name__ == "__main__":
    create_admin()
