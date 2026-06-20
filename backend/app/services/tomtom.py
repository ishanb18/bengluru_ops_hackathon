import os
import sys
import httpx
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import random

# Ensure ml module is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.models.db import Event
from ml.predict import predict_priority, predict_closure, predict_duration

logger = logging.getLogger(__name__)

from app.core.config import settings

TOMTOM_API_KEY = settings.TOMTOM_API_KEY
# Bengaluru bounding box
BBOX = "77.45,12.85,77.75,13.15"

# Map TomTom iconCategory to our event causes
CAUSE_MAP = {
    1: "accident",
    6: "others",  # Jam
    8: "construction", # Road closed usually construction or others
    9: "construction",
    11: "water_logging",
    14: "vehicle_breakdown"
}

# Known corridors to map to (for realistic analytics rendering)
KNOWN_CORRIDORS = [
    "Tumkur Road", "Mysore Road", "Bellary Road 1", "Hosur Road", "ORR East 1", "Old Madras Road"
]

def _assign_corridor(tomtom_desc: str) -> str:
    """Fuzzy mapping of TomTom descriptions to our known corridors, otherwise Non-corridor."""
    desc = str(tomtom_desc).lower()
    if "tumkur" in desc: return "Tumkur Road"
    if "mysore" in desc: return "Mysore Road"
    if "bellary" in desc or "hebbal" in desc: return "Bellary Road 1"
    if "hosur" in desc or "electronic city" in desc: return "Hosur Road"
    if "orr" in desc or "outer ring" in desc or "marathahalli" in desc: return "ORR East 1"
    if "old madras" in desc or "kr puram" in desc: return "Old Madras Road"
    return "Non-corridor"

def sync_tomtom_incidents(db: Session):
    """
    Fetches live incidents from TomTom API, processes them through our ML pipeline
    for priority/duration, and updates the active DB records.
    """
    if not TOMTOM_API_KEY:
        logger.warning("[TomTom Sync] Skipped — TOMTOM_API_KEY not configured")
        return

    url = f"https://api.tomtom.com/traffic/services/5/incidentDetails?bbox={BBOX}&fields={{incidents{{type,geometry{{type,coordinates}},properties{{id,iconCategory,magnitudeOfDelay,events{{description,code}},startTime,endTime,from,to,length,delay}}}}}}&language=en-GB&timeValidityFilter=present&key={TOMTOM_API_KEY}"
    
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.error(f"[TomTom Sync] Failed to fetch API: {e}")
        return

    incidents = data.get("incidents", [])
    if not incidents:
        logger.info("[TomTom Sync] No live incidents found right now.")
        return

    logger.info(f"[TomTom Sync] Fetched {len(incidents)} live incidents. Processing via ML pipeline...")

    # Clear old active TomTom incidents — use synchronize_session=False for a fast
    # direct SQL DELETE that doesn't load rows into memory first (prevents DB lock)
    try:
        db.query(Event).filter(
            Event.status == "active", Event.authenticated == False
        ).delete(synchronize_session=False)
        db.commit()   # release the write lock immediately before inserting
    except Exception as e:
        logger.error(f"[TomTom Sync] Delete failed: {e}")
        db.rollback()
        return


    current_hour = datetime.now(timezone.utc).hour
    weekday = datetime.now(timezone.utc).weekday()
    month = datetime.now(timezone.utc).month

    for inc in incidents:
        props = inc.get("properties", {})
        geom = inc.get("geometry", {})
        
        # Get coordinates (use first coordinate of LineString, or Point)
        coords = geom.get("coordinates", [[0,0]])
        if isinstance(coords[0], list):
            lon, lat = coords[0][0], coords[0][1]
        else:
            lon, lat = coords[0], coords[1]

        # Map cause
        icon_category = props.get("iconCategory", 0)
        event_cause = CAUSE_MAP.get(icon_category, "others")
        
        # Determine corridor and address
        desc = props.get("events", [{}])[0].get("description", "Unknown Event")
        from_loc = props.get("from", "")
        address = f"[LIVE] {desc} near {from_loc}" if from_loc else f"[LIVE] {desc}"
        corridor = _assign_corridor(address)

        # ML Inputs
        veh_type = "heavy_vehicle" if "truck" in desc.lower() else "N/A"
        
        input_data = {
            "event_cause": event_cause,
            "corridor": corridor,
            "zone": "Unknown",
            "veh_type": veh_type,
            "hour": current_hour,
            "weekday": weekday,
            "month": month,
            "event_type": "unplanned",
            "weekday_name": datetime.now(timezone.utc).strftime("%A"),
            "is_peak_hour": 1 if (8<=current_hour<=10 or 17<=current_hour<=20) else 0,
            "has_cargo_data": 0,
            "has_junction": 0
        }
        
        # 1. Predict Priority & Closure using our ML Model
        try:
            p_res = predict_priority(input_data)
            priority = p_res["priority"]
            priority_high = p_res["priority_high"]
            
            c_res = predict_closure(input_data)
            requires_closure = int(c_res["requires_closure"])
        except Exception as e:
            logger.warning(f"ML classification failed for {address}: {e}")
            priority, priority_high, requires_closure = "Medium", 0, 0

        # 2. Predict Duration using our ML Model
        try:
            input_data["priority_high"] = priority_high
            dur_res = predict_duration(input_data)
            dur_minutes = dur_res["estimated_minutes"]
            dur_bucket = dur_res["bucket"]
        except Exception as e:
            logger.warning(f"ML duration failed for {address}: {e}")
            dur_minutes, dur_bucket = 60.0, "Medium"

        new_event = Event(
            status="active",
            event_type="unplanned",
            event_cause=event_cause,
            corridor=corridor,
            zone="Unknown",
            veh_type=veh_type,
            latitude=lat,
            longitude=lon,
            address=address,
            priority=priority,
            priority_high=priority_high,
            requires_road_closure=requires_closure,
            duration_minutes=dur_minutes,
            duration_bucket=dur_bucket,
            hour=current_hour,
            weekday=weekday,
            month=month,
            is_peak_hour=1 if (8<=current_hour<=10 or 17<=current_hour<=20) else 0,
            authenticated=0,
            start_datetime=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(new_event)

    db.commit()
    logger.info("[TomTom Sync] Successfully updated live map with real-time Bengaluru anomalies.")
