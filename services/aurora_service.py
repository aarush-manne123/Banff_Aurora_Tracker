"""
Fetches real-time geomagnetic activity (the Kp index) from NOAA's Space
Weather Prediction Center and turns it into a plain-language aurora
probability for the Banff area.

NOAA data is free and requires no API key:
https://services.swpc.noaa.gov/
"""

import logging

import requests

KP_INDEX_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
FORECAST_URL = "https://services.swpc.noaa.gov/text/3-day-forecast.txt"

logger = logging.getLogger(__name__)

# Banff sits at a magnetic latitude where the aurora is regularly visible
# even during moderate activity. This table maps the planetary Kp index to
# a plain-language chance of seeing the aurora from the Banff area,
# assuming clear, dark skies.
KP_GUIDANCE = [
    (0, "Very low", "Unlikely, even in a dark sky."),
    (2, "Low", "A faint glow may be visible low on the northern horizon."),
    (3, "Fair", "Worth a look — a band of light may appear to the north."),
    (4, "Good", "Good chance of visible aurora over the northern horizon."),
    (5, "Great", "Aurora likely, may extend well overhead."),
    (6, "Excellent", "Strong display likely, colour may be visible to the eye."),
    (7, "Exceptional", "Major storm — aurora likely overhead across most of the sky."),
    (9, "Extreme", "Severe storm — vivid aurora possible across the entire sky."),
]


def _guidance_for_kp(kp):
    label, detail = KP_GUIDANCE[0][1], KP_GUIDANCE[0][2]
    for threshold, lbl, det in KP_GUIDANCE:
        if kp >= threshold:
            label, detail = lbl, det
    return label, detail


def get_current_kp():
    """
    Returns the most recent planetary Kp index reading as a dict:
    {"kp": float, "time_tag": str, "label": str, "detail": str}
    or None if the data could not be fetched.
    """
    try:
        resp = requests.get(KP_INDEX_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # API now returns an array of objects directly, no header row
        if not data:
            return None

        latest = data[-1]
        time_tag, kp_raw = latest["time_tag"], latest["Kp"]
        kp = float(kp_raw)
        label, detail = _guidance_for_kp(kp)

        return {"kp": kp, "time_tag": time_tag, "label": label, "detail": detail}
    except (requests.RequestException, ValueError, IndexError, KeyError) as exc:
        logger.warning("Could not fetch Kp index: %s", exc)
        return None


def get_recent_kp_history(limit=8):
    """
    Returns the last `limit` Kp readings (oldest first) for a small sparkline,
    as a list of {"time_tag": str, "kp": float}.
    """
    try:
        resp = requests.get(KP_INDEX_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # API now returns an array of objects directly, no header row
        recent = data[-limit:]
        return [{"time_tag": r["time_tag"], "kp": float(r["Kp"])} for r in recent]
    except (requests.RequestException, ValueError, IndexError, KeyError) as exc:
        logger.warning("Could not fetch Kp history: %s", exc)
        return []
