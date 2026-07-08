"""
Fetches real-time geomagnetic activity (the Kp index) from NOAA's Space
Weather Prediction Center and turns it into a plain-language aurora
probability for the Banff area.

NOAA data is free and requires no API key:
https://services.swpc.noaa.gov/
"""

import logging
import time

import requests

KP_INDEX_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
FORECAST_URL = "https://services.swpc.noaa.gov/text/3-day-forecast.txt"

logger = logging.getLogger(__name__)

# Simple in-memory cache to avoid rate limiting
_kp_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 300  # 5 minutes

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
    Uses a 5-minute cache to avoid rate limiting.
    """
    current_time = time.time()

    # Return cached data if still valid
    if _kp_cache["data"] and (current_time - _kp_cache["timestamp"] < CACHE_TTL):
        logger.debug("Using cached Kp data")
        return _kp_cache["data"]

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

        result = {"kp": kp, "time_tag": time_tag, "label": label, "detail": detail}

        # Cache the result
        _kp_cache["data"] = result
        _kp_cache["timestamp"] = current_time

        return result
    except (requests.RequestException, ValueError, IndexError, KeyError) as exc:
        logger.warning("Could not fetch Kp index: %s", exc)
        # Return cached data even if expired, as fallback
        if _kp_cache["data"]:
            logger.info("Using expired cached Kp data as fallback")
            return _kp_cache["data"]
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


def get_kp_forecast(days=4):
    """
    Parses NOAA's 3-day forecast text to extract predicted Kp values.
    Returns a list of {"date": str, "kp_max": float, "label": str} for each day.
    """
    try:
        resp = requests.get(FORECAST_URL, timeout=10)
        resp.raise_for_status()
        text = resp.text

        # Parse the forecast text
        lines = text.split('\n')
        forecast_days = []
        date_headers = None
        kp_columns = []

        for line in lines:
            # Look for the date header line (e.g., "             Jul 08       Jul 09       Jul 10")
            if 'Jul' in line or 'Aug' in line or 'Sep' in line or 'Oct' in line or 'Nov' in line or 'Dec' in line or 'Jan' in line or 'Feb' in line or 'Mar' in line or 'Apr' in line or 'May' in line or 'Jun' in line:
                parts = line.split()
                # Check if this looks like a date header (contains month abbreviations)
                months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                if any(month in parts for month in months):
                    date_headers = parts

            # Look for Kp forecast lines (e.g., "00-03UT       2.67         3.00         3.67")
            if 'UT' in line and date_headers:
                parts = line.split()
                if len(parts) > 1 and any(c.replace('.', '').isdigit() for c in parts):
                    # Extract numeric Kp values (they can be decimals like 2.67)
                    kp_values = []
                    for part in parts[1:]:  # Skip the time column
                        try:
                            kp_values.append(float(part))
                        except ValueError:
                            continue

                    if kp_values and date_headers:
                        # Initialize columns if needed
                        if not kp_columns:
                            kp_columns = [[] for _ in range(len(kp_values))]

                        # Add values to respective columns
                        for i, kp in enumerate(kp_values):
                            if i < len(kp_columns):
                                kp_columns[i].append(kp)

        # Calculate max Kp for each day from the columns
        if date_headers and kp_columns:
            from datetime import datetime
            current_year = datetime.now().year

            for i, date_str in enumerate(date_headers):
                if i < len(kp_columns) and kp_columns[i]:
                    kp_max = max(kp_columns[i])
                    label, _ = _guidance_for_kp(kp_max)

                    # Format date nicely
                    full_date = f"{current_year} {date_str}"
                    forecast_days.append({
                        "date": full_date,
                        "kp_max": kp_max,
                        "label": label
                    })

        return forecast_days[:days]
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Could not fetch Kp forecast: %s", exc)
        return []
