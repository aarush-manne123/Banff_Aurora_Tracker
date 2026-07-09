import secrets
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _now():
    return datetime.now(timezone.utc)


class Subscriber(db.Model):
    __tablename__ = "subscribers"

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    carrier_domain = db.Column(db.String(50), nullable=True)  # For email-to-SMS gateway

    # Alert when Kp index reaches this value or higher
    kp_threshold = db.Column(db.Float, default=4.0, nullable=False)

    # Alert when cloud cover is at or below this percentage (clear enough to see something)
    cloud_threshold = db.Column(db.Integer, default=50, nullable=False)

    # Alert whenever cloud cover changes by at least this many percentage points
    cloud_change_threshold = db.Column(db.Integer, default=25, nullable=False)

    active = db.Column(db.Boolean, default=True, nullable=False)
    unsubscribe_token = db.Column(
        db.String(32), unique=True, default=lambda: secrets.token_hex(16)
    )

    last_cloud_cover = db.Column(db.Integer, nullable=True)
    last_aurora_alert_at = db.Column(db.DateTime, nullable=True)
    last_cloud_alert_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=_now)

    @property
    def contact_display(self):
        if self.email and self.phone_number:
            return f"{self.email} / {self.phone_number}"
        return self.email or self.phone_number or "unknown"

    def __repr__(self):
        return f"<Subscriber {self.contact_display}>"
