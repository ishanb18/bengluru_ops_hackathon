"""
weather_collector.py — BengaluruOps 2.0
Fetches Bengaluru current weather from OpenWeather API and stores in WeatherRecord table.
Runs every 15 minutes via background scheduler in main.py.
"""

import httpx
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.db import WeatherRecord
from app.core.config import settings

logger = logging.getLogger(__name__)

BENGALURU_LAT = 12.9716
BENGALURU_LON = 77.5946
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


def sync_weather(db: Session) -> dict | None:
    """
    Fetch latest Bengaluru weather from OpenWeather and persist to DB.
    Returns the weather dict for use by the traffic collector (attaching context).
    """
    api_key = settings.OPENWEATHER_API_KEY
    if not api_key:
        logger.warning("[Weather] OPENWEATHER_API_KEY not configured — skipping.")
        return None

    try:
        response = httpx.get(
            OPENWEATHER_URL,
            params={
                "lat": BENGALURU_LAT,
                "lon": BENGALURU_LON,
                "appid": api_key,
                "units": "metric",
            },
            timeout=8.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.error(f"[Weather] API fetch failed: {e}")
        return None

    main = data.get("main", {})
    wind = data.get("wind", {})
    weather_arr = data.get("weather", [{}])
    condition = weather_arr[0].get("main", "Clear")         # e.g. "Rain"
    condition_detail = weather_arr[0].get("description", "") # e.g. "light rain"
    rainfall_mm = data.get("rain", {}).get("1h", 0.0)
    visibility_m = data.get("visibility", 10000)
    wind_speed_kmh = round((wind.get("speed", 0)) * 3.6, 1)  # m/s → km/h

    record = WeatherRecord(
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        temperature_c=main.get("temp"),
        feels_like_c=main.get("feels_like"),
        humidity_pct=main.get("humidity"),
        rainfall_mm=rainfall_mm,
        visibility_m=visibility_m,
        wind_speed_kmh=wind_speed_kmh,
        condition=condition,
        condition_detail=condition_detail,
    )

    try:
        db.add(record)
        db.commit()
        logger.info(
            f"[Weather] Stored: {condition} {temperature_safe(main)} °C, "
            f"rain={rainfall_mm}mm, vis={visibility_m}m"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"[Weather] DB write failed: {e}")

    return {
        "condition": condition,
        "rainfall_mm": rainfall_mm,
        "visibility_m": visibility_m,
        "wind_speed_kmh": wind_speed_kmh,
        "temperature_c": main.get("temp"),
    }


def temperature_safe(main: dict) -> str:
    t = main.get("temp")
    return f"{t:.1f}" if t is not None else "?"


def get_latest_weather(db: Session) -> dict:
    """Return the most recent weather record as a dict. Used by traffic API."""
    record = (
        db.query(WeatherRecord)
        .order_by(WeatherRecord.timestamp.desc())
        .first()
    )
    if not record:
        return {
            "condition": "Unknown",
            "temperature_c": None,
            "rainfall_mm": 0.0,
            "visibility_m": 10000,
            "wind_speed_kmh": 0.0,
            "humidity_pct": None,
            "timestamp": None,
        }
    return {
        "condition": record.condition,
        "condition_detail": record.condition_detail,
        "temperature_c": record.temperature_c,
        "feels_like_c": record.feels_like_c,
        "humidity_pct": record.humidity_pct,
        "rainfall_mm": record.rainfall_mm,
        "visibility_m": record.visibility_m,
        "wind_speed_kmh": record.wind_speed_kmh,
        "timestamp": record.timestamp.isoformat() if record.timestamp else None,
    }
