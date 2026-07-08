import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'aurora.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")

    # Email-to-SMS gateway settings (alternative to Twilio)
    SMTP_SERVER = os.environ.get("SMTP_SERVER", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

    # Groq AI API key for fallback weather data
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

    CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", 10))
    AURORA_ALERT_COOLDOWN_MINUTES = int(
        os.environ.get("AURORA_ALERT_COOLDOWN_MINUTES", 120)
    )
    CLOUD_ALERT_COOLDOWN_MINUTES = int(
        os.environ.get("CLOUD_ALERT_COOLDOWN_MINUTES", 30)
    )

    # Banff townsite coordinates - used as the reference point for forecasts
    BANFF_LAT = 51.1784
    BANFF_LON = -115.5708
    TIMEZONE = "America/Edmonton"

    # Application root path for subpath deployment (e.g., "/aurora-tracker")
    APPLICATION_ROOT = os.environ.get("APPLICATION_ROOT", "")
