"""
Runs the aurora/cloud condition checker as its own standalone process.

This is intentionally separate from the web app (wsgi.py / app.py). If the
scheduler were started inside the Flask app itself, every gunicorn worker
process would run its own copy of it and every subscriber would get
duplicate text messages. Run exactly one instance of this process
alongside the web app - see deploy/aurora-tracker-scheduler.service.
"""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.blocking import BlockingScheduler

from app import create_app
from scheduler import check_conditions_and_notify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = create_app()


def run():
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        func=lambda: check_conditions_and_notify(app),
        trigger="interval",
        minutes=app.config["CHECK_INTERVAL_MINUTES"],
        id="condition_check",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=15),
    )
    logger.info(
        "Aurora Banff scheduler started - checking every %s minute(s).",
        app.config["CHECK_INTERVAL_MINUTES"],
    )
    scheduler.start()


if __name__ == "__main__":
    run()
