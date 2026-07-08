import atexit
import logging
import re

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from config import Config
from models import Subscriber, db
from scheduler import start_scheduler
from services import aurora_service, weather_service
from services.locations import VIEWING_LOCATIONS

logging.basicConfig(level=logging.INFO)

PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")


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

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.route("/")
    def index():
        kp_data = aurora_service.get_current_kp()
        kp_history = aurora_service.get_recent_kp_history()
        weather = weather_service.get_current_conditions(
            app.config["BANFF_LAT"], app.config["BANFF_LON"], app.config["TIMEZONE"]
        )
        sparkline_points = _build_sparkline(kp_history)
        return render_template(
            "index.html",
            kp_data=kp_data,
            kp_history=kp_history,
            weather=weather,
            locations=VIEWING_LOCATIONS,
            sparkline_points=sparkline_points,
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
        phone_number = request.form.get("phone_number", "").strip()
        carrier_domain = request.form.get("carrier_domain", "").strip() or None
        kp_threshold = request.form.get("kp_threshold", 4, type=float)
        cloud_threshold = request.form.get("cloud_threshold", 50, type=int)
        cloud_change_threshold = request.form.get(
            "cloud_change_threshold", 25, type=int
        )

        if not PHONE_RE.match(phone_number):
            flash(
                "Please enter a valid phone number in international format, "
                "e.g. +14035551234.",
                "error",
            )
            return redirect(url_for("index") + "#subscribe")

        existing = Subscriber.query.filter_by(phone_number=phone_number).first()
        if existing:
            existing.kp_threshold = kp_threshold
            existing.cloud_threshold = cloud_threshold
            existing.cloud_change_threshold = cloud_change_threshold
            existing.carrier_domain = carrier_domain
            existing.active = True
            db.session.commit()
            flash("Your alert preferences have been updated.", "success")
        else:
            sub = Subscriber(
                phone_number=phone_number,
                carrier_domain=carrier_domain,
                kp_threshold=kp_threshold,
                cloud_threshold=cloud_threshold,
                cloud_change_threshold=cloud_change_threshold,
            )
            db.session.add(sub)
            db.session.commit()
            flash("You're subscribed! We'll text you when conditions look good.", "success")

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

