import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from models import Subscriber, db
from services import aurora_service, sms_service, weather_service

logger = logging.getLogger(__name__)


def _minutes_since(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 60


def check_conditions_and_notify(app):
    """
    One run of the checker: fetch current aurora + cloud data, then decide
    per-subscriber whether an SMS should go out. Designed to be safe to run
    even if an external API is temporarily down.
    """
    with app.app_context():
        kp_data = aurora_service.get_current_kp()
        weather = weather_service.get_current_conditions(
            app.config["BANFF_LAT"], app.config["BANFF_LON"], app.config["TIMEZONE"]
        )

        if kp_data is None or weather is None or weather.get("cloud_cover") is None:
            logger.info("Skipping notification check - upstream data unavailable.")
            return

        kp = kp_data["kp"]
        cloud_cover = weather["cloud_cover"]

        subscribers = Subscriber.query.filter_by(active=True).all()
        aurora_cooldown = app.config["AURORA_ALERT_COOLDOWN_MINUTES"]
        cloud_cooldown = app.config["CLOUD_ALERT_COOLDOWN_MINUTES"]

        for sub in subscribers:
            _maybe_send_aurora_alert(app, sub, kp, kp_data, cloud_cover, aurora_cooldown)
            _maybe_send_cloud_alert(app, sub, cloud_cover, cloud_cooldown)

        db.session.commit()


def _maybe_send_aurora_alert(app, sub, kp, kp_data, cloud_cover, cooldown_minutes):
    conditions_met = kp >= sub.kp_threshold and cloud_cover <= sub.cloud_threshold
    if not conditions_met:
        return

    minutes_since_last = _minutes_since(sub.last_aurora_alert_at)
    if minutes_since_last is not None and minutes_since_last < cooldown_minutes:
        return

    body = (
        f"Aurora Banff Alert: Kp {kp:.1f} ({kp_data['label']}) and only "
        f"{cloud_cover:.0f}% cloud cover near Banff right now. Good conditions "
        f"to head out and look north. Reply STOP to unsubscribe."
    )

    sent = False
    # Try email-to-SMS if subscriber has carrier domain set
    if sub.carrier_domain:
        sent = sms_service.send_sms_via_email(
            app.config["SMTP_SERVER"],
            app.config["SMTP_PORT"],
            app.config["SMTP_EMAIL"],
            app.config["SMTP_PASSWORD"],
            sub.phone_number,
            sub.carrier_domain,
            body,
        )
    # Fall back to Twilio if email-to-SMS wasn't used or failed
    if not sent:
        sent = sms_service.send_sms(
            app.config["TWILIO_ACCOUNT_SID"],
            app.config["TWILIO_AUTH_TOKEN"],
            app.config["TWILIO_FROM_NUMBER"],
            sub.phone_number,
            body,
        )
    if sent:
        sub.last_aurora_alert_at = datetime.now(timezone.utc)


def _maybe_send_cloud_alert(app, sub, cloud_cover, cooldown_minutes):
    if sub.last_cloud_cover is None:
        sub.last_cloud_cover = cloud_cover
        return

    change = abs(cloud_cover - sub.last_cloud_cover)
    if change < sub.cloud_change_threshold:
        return

    minutes_since_last = _minutes_since(sub.last_cloud_alert_at)
    if minutes_since_last is not None and minutes_since_last < cooldown_minutes:
        sub.last_cloud_cover = cloud_cover
        return

    direction = "cleared up" if cloud_cover < sub.last_cloud_cover else "clouded over"
    body = (
        f"Aurora Banff sky update: cloud cover has {direction} - now "
        f"{cloud_cover:.0f}% (was {sub.last_cloud_cover:.0f}%). Reply STOP to unsubscribe."
    )

    sent = False
    # Try email-to-SMS if subscriber has carrier domain set
    if sub.carrier_domain:
        sent = sms_service.send_sms_via_email(
            app.config["SMTP_SERVER"],
            app.config["SMTP_PORT"],
            app.config["SMTP_EMAIL"],
            app.config["SMTP_PASSWORD"],
            sub.phone_number,
            sub.carrier_domain,
            body,
        )
    # Fall back to Twilio if email-to-SMS wasn't used or failed
    if not sent:
        sent = sms_service.send_sms(
            app.config["TWILIO_ACCOUNT_SID"],
            app.config["TWILIO_AUTH_TOKEN"],
            app.config["TWILIO_FROM_NUMBER"],
            sub.phone_number,
            body,
        )
    if sent:
        sub.last_cloud_alert_at = datetime.now(timezone.utc)
    sub.last_cloud_cover = cloud_cover


def start_scheduler(app):
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        func=lambda: check_conditions_and_notify(app),
        trigger="interval",
        minutes=app.config["CHECK_INTERVAL_MINUTES"],
        id="condition_check",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=10),
    )
    scheduler.start()
    return scheduler
