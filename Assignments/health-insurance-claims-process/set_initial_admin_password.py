"""Set or reset the password for an existing administrator account.

Use this only when no administrator can log in yet. Normal password changes
should be performed from the administrator's user-management screen.
"""
from getpass import getpass

from werkzeug.security import generate_password_hash
from app import app, db, User


def main():
    username = input("Existing administrator username: ").strip()
    password = getpass("New password (minimum 8 characters): ")
    confirmation = getpass("Confirm new password: ")

    if len(password) < 8:
        print("Password must contain at least 8 characters.")
        return
    if password != confirmation:
        print("Passwords do not match.")
        return

    with app.app_context():
        user = User.query.filter_by(username=username, role="admin").first()
        if user is None:
            print("No administrator account with that username was found.")
            return
        user.password_hash = generate_password_hash(password)
        db.session.commit()
        print(f"Password hash updated for administrator '{username}'.")


if __name__ == "__main__":
    main()
