"""
traffic.py — BengaluruOps 2.0
GET /api/traffic/live       — Current congestion for all 10 monitored corridors
GET /api/traffic/weather    — Latest Bengaluru weather snapshot
GET /api/traffic/forecast   — Congestion risk prediction for all corridors
GET /api/traffic/history/{corridor} — Last 2-hour history for one corridor
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.models.db import get_db, TrafficSnapshot, WeatherRecord
from app.services.traffic_collector import get_latest_snapshots, _congestion_status
from app.services.weather_collector import get_latest_weather

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/traffic", tags=["Traffic 2.0"])

# In-memory cache to avoid hammering DB on every poll
_snapshot_cache: list[dict] = []
_snapshot_cache_time: datetime | None = None
CACHE_TTL_SECONDS = 60


@router.get("/live")
def get_live_traffic(db: Session = Depends(get_db)):
    """
    Returns real-time congestion for all 10 Bengaluru corridors.
    Data comes from the latest TrafficSnapshot records (refreshed every 10 min).
    """
    global _snapshot_cache, _snapshot_cache_time

    now = datetime.now(timezone.utc)
    if (
        _snapshot_cache
        and _snapshot_cache_time
        and (now - _snapshot_cache_time).total_seconds() < CACHE_TTL_SECONDS
    ):
        return {"corridors": _snapshot_cache, "cached": True}

    snapshots = get_latest_snapshots(db)
    if snapshots:
        _snapshot_cache = snapshots
        _snapshot_cache_time = now

    return {"corridors": snapshots, "cached": False}


@router.get("/weather")
def get_weather(db: Session = Depends(get_db)):
    """Returns the latest Bengaluru weather snapshot from WeatherRecord table."""
    return get_latest_weather(db)


@router.get("/forecast")
def get_forecast(db: Session = Depends(get_db)):
    """
    Returns current congestion + 30-min and 60-min predicted risk for all corridors.
    Sourced from the latest TrafficSnapshot records.
    """
    snapshots = get_latest_snapshots(db)
    weather = get_latest_weather(db)

    corridors = []
    for snap in snapshots:
        corridors.append({
            "corridor": snap["corridor"],
            "now_pct": snap["congestion_percent"],
            "now_status": snap["status"],
            "risk_30min": snap["risk_30min"],
            "risk_60min": snap["risk_60min"],
            "incident_count": snap["incident_count"],
        })

    return {
        "corridors": corridors,
        "weather": weather,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/history/{corridor_name}")
def get_corridor_history(corridor_name: str, db: Session = Depends(get_db)):
    """
    Returns the last 2 hours of TrafficSnapshot records for a specific corridor.
    Useful for trend charts.
    """
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)

    rows = (
        db.query(TrafficSnapshot)
        .filter(
            TrafficSnapshot.corridor == corridor_name,
            TrafficSnapshot.timestamp >= since,
        )
        .order_by(TrafficSnapshot.timestamp.asc())
        .all()
    )

    history = [
        {
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "current_speed": r.current_speed,
            "congestion_percent": r.congestion_percent,
            "incident_count": r.incident_count,
        }
        for r in rows
    ]

    return {"corridor": corridor_name, "history": history}
