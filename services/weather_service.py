"""
Fetches cloud cover data for the Banff area from Open-Meteo, a free
weather API that requires no API key: https://open-meteo.com/
"""

import logging
import time
from datetime import datetime

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WTTR_URL = "https://wttr.in"

logger = logging.getLogger(__name__)

# Simple in-memory cache to avoid rate limiting
_weather_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 600  # 10 minutes


def _get_from_wttr(lat, lon):
    """
    Fallback to wttr.in API when Open-Meteo is rate limited.
    Returns data in the same format as Open-Meteo.
    """
    try:
        # wttr.in uses a different format, we'll parse the JSON response
        params = {
            "format": "j1",
        }
        resp = requests.get(f"{WTTR_URL}/{lat},{lon}", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        current = data.get("current_condition", [{}])[0]
        weather = data.get("weather", [{}])[0]
        hourly = weather.get("hourly", [])

        # Build a simple forecast from hourly data
        night_forecast = []
        for h in hourly[:12]:  # Take first 12 hours
            time_str = h.get("time", "")
            cloud = int(h.get("cloudcover", 0))
            night_forecast.append({"time": time_str, "cloud_cover": cloud})

        return {
            "cloud_cover": int(current.get("cloudcover", 0)),
            "temperature_c": float(current.get("temp_C", 0)),
            "observed_at": current.get("observation_time", ""),
            "night_forecast": night_forecast[:12],
        }
    except Exception as exc:
        logger.warning("Fallback to wttr.in also failed: %s", exc)
        return None


def _get_from_groq(lat, lon, api_key):
    """
    Fallback to Groq AI when all weather APIs fail.
    Uses AI to estimate current weather conditions for the location.
    """
    if not api_key:
        logger.warning("Groq API key not provided, skipping AI fallback")
        return None

    try:
        from datetime import datetime, timedelta
        today = datetime.now()
        dates = [(today + timedelta(days=i)).strftime("%A, %B %d") for i in range(4)]

        prompt = f"""You are a weather assistant. Provide current weather conditions and 4-day forecast for Banff, Alberta (latitude {lat}, longitude {lon}).
Return ONLY a JSON object with these exact keys:
- cloud_cover: integer 0-100 (percentage of cloud cover)
- temperature_c: float (temperature in Celsius)
- observed_at: string (current time in ISO format)
- night_forecast: array of objects with "time" and "cloud_cover" keys for tonight (8pm-6am)
- daily_forecast: array of 4 objects with "date", "cloud_cover", "temp_max", "temp_min" keys

Dates to use for daily_forecast: {', '.join(dates)}

Example format:
{{
  "cloud_cover": 45,
  "temperature_c": 18.5,
  "observed_at": "2026-07-08T12:00:00",
  "night_forecast": [
    {{"time": "20:00", "cloud_cover": 50}},
    {{"time": "21:00", "cloud_cover": 55}},
    {{"time": "22:00", "cloud_cover": 60}},
    {{"time": "23:00", "cloud_cover": 65}},
    {{"time": "00:00", "cloud_cover": 70}},
    {{"time": "01:00", "cloud_cover": 65}},
    {{"time": "02:00", "cloud_cover": 60}},
    {{"time": "03:00", "cloud_cover": 55}},
    {{"time": "04:00", "cloud_cover": 50}},
    {{"time": "05:00", "cloud_cover": 45}},
    {{"time": "06:00", "cloud_cover": 40}}
  ],
  "daily_forecast": [
    {{"date": "{dates[0]}", "cloud_cover": 45, "temp_max": 20, "temp_min": 12}},
    {{"date": "{dates[1]}", "cloud_cover": 50, "temp_max": 18, "temp_min": 10}},
    {{"date": "{dates[2]}", "cloud_cover": 30, "temp_max": 22, "temp_min": 14}},
    {{"date": "{dates[3]}", "cloud_cover": 40, "temp_max": 19, "temp_min": 11}}
  ]
}}

Respond with ONLY the JSON, no other text."""

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 500
        }

        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=15)
        resp.raise_for_status()
        result = resp.json()

        content = result["choices"][0]["message"]["content"]

        # Parse the JSON response
        import json
        weather_data = json.loads(content)

        # Validate required fields
        if not all(key in weather_data for key in ["cloud_cover", "temperature_c", "observed_at", "night_forecast", "daily_forecast"]):
            logger.warning("Groq response missing required fields")
            return None

        logger.info("Successfully retrieved weather data from Groq AI")
        return weather_data

    except Exception as exc:
        logger.warning("Groq AI fallback failed: %s", exc)
        return None


def _get_mock_data():
    """
    Last resort: return mock data when all APIs fail.
    This ensures the UI doesn't show "unavailable" message.
    """
    logger.warning("All weather APIs failed, using mock data")
    return {
        "cloud_cover": 50,
        "temperature_c": 15,
        "observed_at": "Unknown (API unavailable)",
        "night_forecast": [
            {"time": f"{i:02d}:00", "cloud_cover": 50} for i in range(20, 24)
        ] + [
            {"time": f"{i:02d}:00", "cloud_cover": 50} for i in range(0, 6)
        ],
    }


def get_current_conditions(lat, lon, timezone, groq_api_key=None):
    """
    Returns current cloud cover, temperature and a short night-hours cloud
    forecast for the given coordinates, or None on failure.
    Uses a 10-minute cache to avoid rate limiting.
    Prioritizes Groq AI if API key is provided, as weather APIs may be inaccurate.
    """
    current_time = time.time()

    # Return cached data if still valid
    if _weather_cache["data"] and (current_time - _weather_cache["timestamp"] < CACHE_TTL):
        logger.debug("Using cached weather data")
        return _weather_cache["data"]

    # Try Groq AI first if API key is provided (more accurate than weather APIs)
    if groq_api_key:
        logger.info("Using Groq AI as primary weather source")
        groq_result = _get_from_groq(lat, lon, groq_api_key)
        if groq_result:
            _weather_cache["data"] = groq_result
            _weather_cache["timestamp"] = current_time
            return groq_result
        logger.warning("Groq AI failed, falling back to weather APIs")

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "cloud_cover,temperature_2m",
        "daily": "cloud_cover,temperature_2m_max,temperature_2m_min",
        "forecast_days": 4,
        "timezone": timezone,
    }

    # Retry with exponential backoff for rate limiting
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.get(FORECAST_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            current = data.get("current", {})
            daily = data.get("daily", {})

            # Parse daily forecast
            daily_forecast = []
            if daily:
                times = daily.get("time", [])
                cloud_covers = daily.get("cloud_cover", [])
                temp_maxs = daily.get("temperature_2m_max", [])
                temp_mins = daily.get("temperature_2m_min", [])

                for i, time_str in enumerate(times):
                    if i < len(cloud_covers) and i < len(temp_maxs) and i < len(temp_mins):
                        from datetime import datetime
                        date_obj = datetime.fromisoformat(time_str)
                        daily_forecast.append({
                            "date": date_obj.strftime("%A, %B %d"),
                            "cloud_cover": cloud_covers[i],
                            "temp_max": temp_maxs[i],
                            "temp_min": temp_mins[i],
                        })

            result = {
                "cloud_cover": current.get("cloud_cover"),
                "temperature_c": current.get("temperature_2m"),
                "observed_at": current.get("time"),
                "night_forecast": [],  # Simplified - no hourly data to avoid rate limiting
                "daily_forecast": daily_forecast,
            }

            # Cache the result
            _weather_cache["data"] = result
            _weather_cache["timestamp"] = current_time

            return result
        except requests.HTTPError as exc:
            if exc.response.status_code == 429 and attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1, 2, 4 seconds
                logger.warning("Rate limited, waiting %d seconds before retry %d/%d", wait_time, attempt + 1, max_retries)
                time.sleep(wait_time)
                continue
            # If we get rate limited after all retries, try fallback
            logger.warning("Open-Meteo rate limited, trying wttr.in fallback")
            fallback_result = _get_from_wttr(lat, lon)
            if fallback_result:
                _weather_cache["data"] = fallback_result
                _weather_cache["timestamp"] = current_time
                return fallback_result
            # Return cached data even if expired, as fallback
            if _weather_cache["data"]:
                logger.info("Using expired cached data as fallback")
                return _weather_cache["data"]
            # Last resort: use mock data
            return _get_mock_data()
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.warning("Could not fetch weather conditions: %s", exc)
            # Try fallback on other errors
            fallback_result = _get_from_wttr(lat, lon)
            if fallback_result:
                _weather_cache["data"] = fallback_result
                _weather_cache["timestamp"] = current_time
                return fallback_result
            # Return cached data even if expired, as fallback
            if _weather_cache["data"]:
                logger.info("Using expired cached data as fallback")
                return _weather_cache["data"]
            # Last resort: use mock data
            return _get_mock_data()
