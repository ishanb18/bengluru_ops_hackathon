"""
traffic_collector.py — BengaluruOps 2.0
Fetches real-time speed and congestion for Bengaluru corridors from TomTom Flow API.
Stores TrafficSnapshot records every 10 minutes.
"""

import httpx
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.db import TrafficSnapshot, Event
from app.core.config import settings

logger = logging.getLogger(__name__)

TOMTOM_FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

# Mid-point coordinates for each monitored Bengaluru corridor
CORRIDOR_WAYPOINTS = {
    "Tumkur Road":      (13.032, 77.538),
    "Mysore Road":      (12.933, 77.510),
    "Bellary Road":     (13.033, 77.591),
    "Hosur Road":       (12.885, 77.645),
    "ORR East":         (12.939, 77.667),
    "ORR West":         (12.997, 77.535),
    "Old Madras Road":  (12.993, 77.660),
    "Hebbal":           (13.043, 77.596),
    "Electronic City":  (12.845, 77.665),
    "Silk Board":       (12.917, 77.623),
}


def _predict_risk(congestion: float, hour: int, rainfall_mm: float) -> tuple[str, str]:
    """
    Simple rule-based congestion risk forecast.
    Returns (risk_30min, risk_60min) as Low/Medium/High.
    TODO: Replace with trained ML model once enough TrafficSnapshot data is collected.
    """
    is_peak = 8 <= hour <= 10 or 17 <= hour <= 20
    rain_factor = 15 if rainfall_mm > 5 else (8 if rainfall_mm > 1 else 0)

    # 30-min: assume congestion slightly worsens during peak, slightly improves off-peak
    cong_30 = congestion + (8 if is_peak else -5) + rain_factor
    cong_60 = congestion + (12 if is_peak else -10) + rain_factor

    def bucket(c):
        c = max(0, min(100, c))
        if c < 35: return "Low"
        if c < 65: return "Medium"
        return "High"

    return bucket(cong_30), bucket(cong_60)


def _fetch_corridor_flow(corridor: str, lat: float, lon: float) -> dict | None:
    """Query TomTom Flow Segment Data API for a single corridor waypoint."""
    api_key = settings.TOMTOM_API_KEY
    if not api_key:
        return None

    try:
        response = httpx.get(
            TOMTOM_FLOW_URL,
            params={
                "key": api_key,
                "point": f"{lat},{lon}",
                "unit": "KMPH",
            },
            timeout=8.0,
        )
        response.raise_for_status()
        data = response.json()
        fsd = data.get("flowSegmentData", {})
        current_speed = fsd.get("currentSpeed")
        free_flow = fsd.get("freeFlowSpeed")
        confidence = fsd.get("confidence", 1.0)

        if current_speed is None or free_flow is None or free_flow == 0:
            return None

        congestion = max(0.0, round((1 - current_speed / free_flow) * 100, 1))
        return {
            "current_speed": round(float(current_speed), 1),
            "free_flow_speed": round(float(free_flow), 1),
            "congestion_percent": congestion,
            "confidence": round(float(confidence), 3),
        }
    except Exception as e:
        logger.warning(f"[Traffic] Flow API failed for {corridor}: {e}")
        return None


def _count_active_incidents(db: Session, corridor_name: str) -> int:
    """Count active incidents near this corridor from the events table."""
    # Match corridor names between CORRIDOR_WAYPOINTS and Event.corridor column
    # CORRIDOR_WAYPOINTS uses 'Bellary Road' while events use 'Bellary Road 1', 'Bellary Road 2', etc.
    base = corridor_name.split(" (")[0].lower().strip()
    rows = db.query(func.count(Event.id)).filter(
        Event.status == "active",
        Event.corridor.ilike(f"%{base}%")
    ).scalar()
    return rows or 0


def sync_traffic(db: Session, weather_context: dict | None = None) -> list[dict]:
    """
    Fetch traffic flow for all corridors and store TrafficSnapshot records.
    Returns list of corridor summary dicts for immediate API use.
    """
    api_key = settings.TOMTOM_API_KEY
    if not api_key:
        logger.warning("[Traffic] TOMTOM_API_KEY not configured — skipping.")
        return []

    now = datetime.now(timezone.utc)
    hour = now.hour
    weather = weather_context or {}
    rainfall = weather.get("rainfall_mm", 0.0)
    condition = weather.get("condition", "Clear")

    snapshots = []
    for corridor, (lat, lon) in CORRIDOR_WAYPOINTS.items():
        flow = _fetch_corridor_flow(corridor, lat, lon)
        incident_count = _count_active_incidents(db, corridor)

        if flow:
            risk_30, risk_60 = _predict_risk(flow["congestion_percent"], hour, rainfall)
            snap = TrafficSnapshot(
                timestamp=now.replace(tzinfo=None),
                corridor=corridor,
                current_speed=flow["current_speed"],
                free_flow_speed=flow["free_flow_speed"],
                congestion_percent=flow["congestion_percent"],
                confidence=flow["confidence"],
                weather_condition=condition,
                rainfall_mm=rainfall,
                incident_count=incident_count,
                risk_30min=risk_30,
                risk_60min=risk_60,
            )
            summary = {
                "corridor": corridor,
                "current_speed": flow["current_speed"],
                "free_flow_speed": flow["free_flow_speed"],
                "congestion_percent": flow["congestion_percent"],
                "status": _congestion_status(flow["congestion_percent"]),
                "incident_count": incident_count,
                "risk_30min": risk_30,
                "risk_60min": risk_60,
                "weather": condition,
                "rainfall_mm": rainfall,
                "confidence": flow["confidence"],
            }
        else:
            # API unavailable — store a null snapshot so we have a timestamp record
            snap = TrafficSnapshot(
                timestamp=now.replace(tzinfo=None),
                corridor=corridor,
                weather_condition=condition,
                rainfall_mm=rainfall,
                incident_count=incident_count,
            )
            summary = {
                "corridor": corridor,
                "current_speed": None,
                "free_flow_speed": None,
                "congestion_percent": None,
                "status": "Unknown",
                "incident_count": incident_count,
                "risk_30min": None,
                "risk_60min": None,
                "weather": condition,
                "rainfall_mm": rainfall,
                "confidence": None,
            }

        db.add(snap)
        snapshots.append(summary)

    try:
        db.commit()
        logger.info(f"[Traffic] Stored {len(CORRIDOR_WAYPOINTS)} corridor snapshots.")
    except Exception as e:
        db.rollback()
        logger.error(f"[Traffic] DB write failed: {e}")

    return snapshots


def _congestion_status(pct: float) -> str:
    if pct is None: return "Unknown"
    if pct < 35: return "Low"
    if pct < 65: return "Medium"
    return "High"


def get_latest_snapshots(db: Session) -> list[dict]:
    """
    Return the most recent TrafficSnapshot for each corridor.
    Used by GET /api/traffic/live.
    """
    from sqlalchemy import text
    rows = db.execute(text("""
        SELECT t.*
        FROM traffic_snapshots t
        INNER JOIN (
            SELECT corridor, MAX(timestamp) as max_ts
            FROM traffic_snapshots
            GROUP BY corridor
        ) latest ON t.corridor = latest.corridor AND t.timestamp = latest.max_ts
        ORDER BY t.congestion_percent DESC NULLS LAST
    """)).fetchall()

    result = []
    for row in rows:
        row_dict = dict(row._mapping)
        result.append({
            "corridor": row_dict.get("corridor"),
            "current_speed": row_dict.get("current_speed"),
            "free_flow_speed": row_dict.get("free_flow_speed"),
            "congestion_percent": row_dict.get("congestion_percent"),
            "status": _congestion_status(row_dict.get("congestion_percent") or 0),
            "incident_count": row_dict.get("incident_count", 0),
            "risk_30min": row_dict.get("risk_30min"),
            "risk_60min": row_dict.get("risk_60min"),
            "weather": row_dict.get("weather_condition"),
            "rainfall_mm": row_dict.get("rainfall_mm", 0.0),
            "timestamp": str(row_dict.get("timestamp", "")),
        })
    return result
