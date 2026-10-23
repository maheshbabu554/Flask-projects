
"""SQLAlchemy ORM models and database initialization."""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData

# Keep ORM tables separate from the Raw SQL tables.
db = SQLAlchemy(
    metadata=MetaData()
)


class User(db.Model):
    """Store registered users."""

    __tablename__ = "orm_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp()
    )

    trips = db.relationship(
        "Trip",
        back_populates="owner",
        cascade="all, delete-orphan"
    )


class Trip(db.Model):
    """Store trips owned by registered users."""

    __tablename__ = "orm_trips"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("orm_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    destination = db.Column(db.String(120), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    budget = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp()
    )

    owner = db.relationship(
        "User",
        back_populates="trips"
    )

    activities = db.relationship(
        "Activity",
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by=lambda: (
            Activity.activity_date,
            Activity.activity_time,
            Activity.id
        )
    )


class Activity(db.Model):
    """Store activities associated with a trip."""

    __tablename__ = "orm_activities"

    id = db.Column(db.Integer, primary_key=True)

    trip_id = db.Column(
        db.Integer,
        db.ForeignKey("orm_trips.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    name = db.Column(db.String(120), nullable=False)
    activity_date = db.Column(db.Date, nullable=False)
    activity_time = db.Column(db.Time, nullable=True)
    category = db.Column(db.String(40), nullable=False)
    place = db.Column(db.String(160), nullable=False)

    cost = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp()
    )

    trip = db.relationship(
        "Trip",
        back_populates="activities"
    )

    @property
    def display_time(self):
        """Return the activity time in 12-hour format."""
        if not self.activity_time:
            return ""
        return self.activity_time.strftime("%I:%M %p")

    @property
    def time_value(self):
        """Return the activity time for an HTML time input."""
        if not self.activity_time:
            return ""
        return self.activity_time.strftime("%H:%M")


class PlaceSuggestion(db.Model):
    """Store community-submitted travel suggestions."""

    __tablename__ = "orm_place_suggestions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    destination = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    description = db.Column(db.String(500), nullable=False)

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("orm_users.id", ondelete="SET NULL"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp()
    )


def init_db(app):
    """Initialize Flask-SQLAlchemy and create missing ORM tables."""
    db.init_app(app)

    with app.app_context():
        db.create_all()
