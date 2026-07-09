import atexit
import logging
import re

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from config import Config
from models import Subscriber, db
from scheduler import start_scheduler
from services import aurora_service, sms_service, weather_service
from services.locations import VIEWING_LOCATIONS

logging.basicConfig(level=logging.INFO)

PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _build_sparkline(history, width=280, height=60, pad=6):
    """Turns a list of {"kp": float} readings into an SVG polyline points string."""
    if not history:
        return ""
    values = [h["kp"] for h in history]
    lo, hi = 0, 9  # Kp index always runs 0-9
    span = hi - lo or 1
    step = (width - 2 * pad) / max(len(values) - 1, 1)

    points = []
    for i, v in enumerate(values):
        x = pad + i * step
        y = height - pad - ((v - lo) / span) * (height - 2 * pad)
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Configure application root for subpath deployment
    if app.config.get("APPLICATION_ROOT"):
        app.config["APPLICATION_ROOT"] = app.config["APPLICATION_ROOT"]

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.route("/")
    def index():
        kp_data = aurora_service.get_current_kp()
        kp_history = aurora_service.get_recent_kp_history()
        kp_forecast = aurora_service.get_kp_forecast(days=4)
        weather = weather_service.get_current_conditions(
            app.config["BANFF_LAT"],
            app.config["BANFF_LON"],
            app.config["TIMEZONE"],
            app.config.get("GROQ_API_KEY"),
        )
        sparkline_points = _build_sparkline(kp_history)
        daily_forecast = weather.get("daily_forecast", []) if weather else []

        # Merge aurora forecast with weather forecast
        for i, day in enumerate(daily_forecast):
            if i < len(kp_forecast):
                day["aurora_kp_max"] = kp_forecast[i]["kp_max"]
                day["aurora_label"] = kp_forecast[i]["label"]
            else:
                day["aurora_kp_max"] = None
                day["aurora_label"] = "Unknown"

        return render_template(
            "index.html",
            kp_data=kp_data,
            kp_history=kp_history,
            weather=weather,
            locations=VIEWING_LOCATIONS,
            sparkline_points=sparkline_points,
            daily_forecast=daily_forecast,
        )


    @app.route("/api/status")
    def api_status():
        kp_data = aurora_service.get_current_kp()
        weather = weather_service.get_current_conditions(
            app.config["BANFF_LAT"], app.config["BANFF_LON"], app.config["TIMEZONE"]
        )
        return jsonify({"kp": kp_data, "weather": weather})

    @app.route("/subscribe", methods=["POST"])
    def subscribe():
        contact_method = request.form.get("contact_method", "email").strip()
        email = request.form.get("email", "").strip() or None
        phone_number = request.form.get("phone_number", "").strip() or None
        carrier_domain = request.form.get("carrier_domain", "").strip() or None
        kp_threshold = request.form.get("kp_threshold", 4, type=float)
        cloud_threshold = request.form.get("cloud_threshold", 50, type=int)
        cloud_change_threshold = request.form.get(
            "cloud_change_threshold", 25, type=int
        )

        # Validate based on chosen contact method
        if contact_method == "email":
            if not email or not EMAIL_RE.match(email):
                flash("Please enter a valid email address.", "error")
                return redirect(url_for("index") + "#subscribe")
            phone_number = None
            carrier_domain = None
        else:
            if not phone_number or not PHONE_RE.match(phone_number):
                flash(
                    "Please enter a valid phone number in international format, "
                    "e.g. +14035551234.",
                    "error",
                )
                return redirect(url_for("index") + "#subscribe")
            email = None

        # Look up existing subscriber by email or phone
        existing = None
        if email:
            existing = Subscriber.query.filter_by(email=email).first()
        if not existing and phone_number:
            existing = Subscriber.query.filter_by(phone_number=phone_number).first()

        is_new = existing is None

        if existing:
            existing.email = email or existing.email
            existing.phone_number = phone_number or existing.phone_number
            existing.kp_threshold = kp_threshold
            existing.cloud_threshold = cloud_threshold
            existing.cloud_change_threshold = cloud_change_threshold
            existing.carrier_domain = carrier_domain
            existing.active = True
            db.session.commit()
            flash("Your alert preferences have been updated.", "success")
        else:
            existing = Subscriber(
                email=email,
                phone_number=phone_number,
                carrier_domain=carrier_domain,
                kp_threshold=kp_threshold,
                cloud_threshold=cloud_threshold,
                cloud_change_threshold=cloud_change_threshold,
            )
            db.session.add(existing)
            db.session.commit()
            flash(
                "You're subscribed! We'll notify you when conditions look good.",
                "success",
            )

        # Send confirmation email for email subscribers
        if email and is_new:
            unsubscribe_url = url_for(
                "unsubscribe", token=existing.unsubscribe_token, _external=True
            )
            sms_service.send_confirmation_email(
                app.config["SMTP_SERVER"],
                app.config["SMTP_PORT"],
                app.config["SMTP_EMAIL"],
                app.config["SMTP_PASSWORD"],
                email,
                unsubscribe_url,
            )

        return redirect(url_for("index") + "#subscribe")

    @app.route("/unsubscribe/<token>")
    def unsubscribe(token):
        sub = Subscriber.query.filter_by(unsubscribe_token=token).first()
        if sub:
            sub.active = False
            db.session.commit()
            flash("You've been unsubscribed from aurora alerts.", "success")
        else:
            flash("That unsubscribe link is invalid or has already been used.", "error")
        return redirect(url_for("index"))

    return app


app = create_app()


if __name__ == "__main__":
    # Convenience for local development only: runs the scheduler in the same
    # process as the dev server. In production, run the scheduler as its own
    # separate process instead - see scheduler_runner.py and the README.
    _dev_scheduler = start_scheduler(app)
    atexit.register(lambda: _dev_scheduler.shutdown(wait=False))
    app.run(debug=True, host="0.0.0.0", port=1324)

