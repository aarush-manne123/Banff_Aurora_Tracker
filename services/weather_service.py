"""
Fetches cloud cover data for the Banff area from Open-Meteo, a free
weather API that requires no API key: https://open-meteo.com/
"""

import logging
from datetime import datetime

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

logger = logging.getLogger(__name__)


def get_current_conditions(lat, lon, timezone):
    """
    Returns current cloud cover, temperature and a short night-hours cloud
    forecast for the given coordinates, or None on failure.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "cloud_cover,temperature_2m,weather_code",
        "hourly": "cloud_cover",
        "forecast_days": 2,
        "timezone": timezone,
    }
    try:
        resp = requests.get(FORECAST_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        current = data.get("current", {})
        hourly_time = data.get("hourly", {}).get("time", [])
        hourly_cloud = data.get("hourly", {}).get("cloud_cover", [])

        # Build a simple forecast for the coming night hours (8pm - 6am)
        night_forecast = []
        for t, cloud in zip(hourly_time, hourly_cloud):
            hour = datetime.fromisoformat(t).hour
            if hour >= 20 or hour <= 6:
                night_forecast.append({"time": t, "cloud_cover": cloud})

        return {
            "cloud_cover": current.get("cloud_cover"),
            "temperature_c": current.get("temperature_2m"),
            "observed_at": current.get("time"),
            "night_forecast": night_forecast[:12],
        }
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.warning("Could not fetch weather conditions: %s", exc)
        return None
