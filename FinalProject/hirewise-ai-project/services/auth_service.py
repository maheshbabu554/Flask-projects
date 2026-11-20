
"""
Authentication service for HireWise AI.

Handles password hashing, password verification,
and secure password changes.
"""

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)


def hash_password(password):
    """
    Hash a password before storing it in the database.
    """

    if not isinstance(password, str) or not password:
        raise ValueError("Password is required.")

    if len(password) < 8:
        raise ValueError(
            "Password must contain at least 8 characters."
        )

    return generate_password_hash(password)


def verify_password(stored_hash, entered_password):
    """
    Verify an entered password against its stored hash.
    """

    if not stored_hash or not entered_password:
        return False

    return check_password_hash(
        stored_hash,
        entered_password,
    )


def change_user_password(user, current_password, new_password):
    """
    Verify the current password and update the user's password hash.

    The calling route is responsible for committing the transaction.
    """

    if not verify_password(
        user.password_hash,
        current_password,
    ):
        raise ValueError("Current password is incorrect.")

    user.password_hash = hash_password(new_password)
