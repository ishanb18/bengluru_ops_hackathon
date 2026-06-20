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

def _rule_parse_incident(desc: str, address_context: str, icon_category: int = 0) -> tuple[str, str, str]:
    """Uses robust keyword matching and TomTom iconCategory to classify event_cause, corridor, and veh_type."""
    desc_lower = desc.lower()
    address_lower = address_context.lower()
    combined = desc_lower + " " + address_lower

    # 1. Event Cause from keyword rules (high priority for specific text)
    event_cause = "others"
    if "accident" in combined or "crash" in combined or "collision" in combined:
        event_cause = "accident"
    elif "breakdown" in combined or "broken down" in combined:
        event_cause = "vehicle_breakdown"
    elif "water" in combined or "flood" in combined or "logging" in combined:
        event_cause = "water_logging"
    elif "tree" in combined and "fall" in combined:
        event_cause = "tree_fall"
    elif "construction" in combined or "roadwork" in combined or "maintenance" in combined:
        event_cause = "construction"
    elif "vip" in combined or "movement" in combined:
        event_cause = "vip_movement"
    elif "event" in combined or "procession" in combined or "rally" in combined:
        event_cause = "public_event"
    elif "pot hole" in combined or "pothole" in combined:
        event_cause = "pot_holes"
    elif "abandoned" in combined:
        event_cause = "abandoned_vehicle"
    elif "oil" in combined and "spill" in combined:
        event_cause = "oil_spill"
    elif "pedestrian" in combined:
        event_cause = "pedestrian_incident"

    # 2. If no specific keyword matched, fallback to TomTom's iconCategory
    if event_cause == "others":
        icon_mapping = {
            1: "accident",
            6: "Jam",
            7: "lane_closed",
            8: "road_closed",
            9: "construction",
            11: "water_logging",
            14: "vehicle_breakdown"
        }
        if icon_category in icon_mapping:
            event_cause = icon_mapping[icon_category]
        else:
            # Fallback to generic traffic words if icon is generic/unknown
            if "queue" in combined:
                event_cause = "Queueing Traffic"
            elif "jam" in combined:
                event_cause = "Jam"
            elif "stationary" in combined or "slow" in combined:
                event_cause = "Stationary Traffic"

    # 2. Corridor
    corridor = "Non-corridor"
    major_corridors = [
        "Tumkur Road", "Mysore Road", "Bellary Road", "Hosur Road", 
        "ORR East", "ORR West", "ORR North", "Old Madras Road", 
        "Magadi Road", "Bannerghata Road", "West of Chord Road", "Outer Ring Road"
    ]
    for c in major_corridors:
        if c.lower() in combined:
            corridor = c
            break

    # 3. Vehicle Type
    veh_type = "N/A"
    if "heavy" in combined or "truck" in combined or "hgv" in combined or "lorry" in combined or "bus" in combined:
        veh_type = "heavy_vehicle"
    elif "car" in combined or "suv" in combined:
        veh_type = "private_car"
    elif "bike" in combined or "two wheeler" in combined or "motorcycle" in combined:
        veh_type = "two_wheeler"
    elif "lcv" in combined or "van" in combined:
        veh_type = "lcv"

    return event_cause, corridor, veh_type

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
    except httpx.HTTPStatusError as e:
        if e.response.status_code in [403, 429] and settings.TOMTOM_API_KEY_FALLBACK:
            logger.warning(f"[TomTom Sync] Primary key failed ({e.response.status_code}). Switching to Fallback Key...")
            fallback_url = url.replace(TOMTOM_API_KEY, settings.TOMTOM_API_KEY_FALLBACK)
            try:
                response = httpx.get(fallback_url, timeout=10.0)
                response.raise_for_status()
                data = response.json()
            except Exception as e2:
                logger.error(f"[TomTom Sync] Fallback key also failed: {e2}")
                return
        else:
            logger.error(f"[TomTom Sync] Failed to fetch API: {e}")
            return
    except Exception as e:
        logger.error(f"[TomTom Sync] Failed to fetch API: {e}")
        return

    incidents = data.get("incidents", [])
    if not incidents:
        logger.info("[TomTom Sync] No live incidents found right now.")
        return

    logger.info(f"[TomTom Sync] Fetched {len(incidents)} live incidents. Processing via ML pipeline...")

    current_hour = datetime.now(timezone.utc).hour
    weekday = datetime.now(timezone.utc).weekday()
    month = datetime.now(timezone.utc).month

    # Process all incidents in parallel with LLM
    import concurrent.futures
    
    def process_incident(inc):
        props = inc.get("properties", {})
        geom = inc.get("geometry", {})

        coords = geom.get("coordinates", [[0, 0]])
        if isinstance(coords[0], list):
            lon, lat = coords[0][0], coords[0][1]
        else:
            lon, lat = coords[0], coords[1]

        # Extract advanced telemetry safely (prevent NoneType errors)
        magnitude = props.get("magnitudeOfDelay") or 0
        delay_sec = props.get("delay") or 0
        length_m = props.get("length") or 0
        
        events_list = props.get("events", [{}])
        desc = events_list[0].get("description", "Unknown Event") if events_list else "Unknown"
        # tmc (Traffic Message Channel) gives specific lane closure codes
        tmc_codes = []
        for e in events_list:
            if "tmc" in e and "code" in e["tmc"]:
                tmc_codes.append(str(e["tmc"]["code"]))
        tmc_str = ",".join(tmc_codes) if tmc_codes else ""

        from_loc = props.get("from", "")
        address = f"[LIVE] {desc} near {from_loc}" if from_loc else f"[LIVE] {desc}"
        
        # Add advanced telemetry to notes
        if delay_sec > 0 or length_m > 0:
            address += f" | {round(length_m)}m affected, {round(delay_sec/60)}m delay (Severity: {magnitude})"

        # Extract real start time
        start_time_str = props.get("startTime")
        if start_time_str:
            try:
                # TomTom returns ISO8601 strings like "2024-12-08T03:25:30Z"
                incident_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                incident_time = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            incident_time = datetime.now(timezone.utc).replace(tzinfo=None)
            
        icon_category = props.get("iconCategory", 0)

        # Parse with rules
        event_cause, corridor, veh_type = _rule_parse_incident(desc, address, icon_category)

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
            "is_peak_hour": 1 if (8 <= current_hour <= 10 or 17 <= current_hour <= 20) else 0,
            "has_cargo_data": 0,
            "has_junction": 0,
            "magnitudeOfDelay": magnitude,
            "delay": delay_sec,
            "length": length_m,
            "tmc": tmc_str
        }

        try:
            p_res = predict_priority(input_data)
            priority = p_res["priority"]
            priority_high = p_res["priority_high"]
            c_res = predict_closure(input_data)
            requires_closure = int(c_res["requires_closure"])
        except Exception as e:
            logger.warning(f"ML classification failed for {address}: {e}")
            priority, priority_high, requires_closure = "Medium", 0, 0

        try:
            input_data["priority_high"] = priority_high
            dur_res = predict_duration(input_data)
            dur_minutes = dur_res["estimated_minutes"]
            dur_bucket = dur_res["bucket"]
        except Exception as e:
            logger.warning(f"ML duration failed for {address}: {e}")
            dur_minutes, dur_bucket = 60.0, "Medium"

        return Event(
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
            is_peak_hour=1 if (8 <= current_hour <= 10 or 17 <= current_hour <= 20) else 0,
            authenticated=0,
            start_datetime=incident_time,
        )

    # Use ThreadPoolExecutor to speed up LLM inference
    new_events = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_incident, incidents))
        new_events = [r for r in results if r is not None]

    # Now do a smart UPSERT to preserve historical data
    try:
        from sqlalchemy import text
        # 1. Get all current unauthenticated active incidents
        current_active = db.query(Event).filter(Event.status == 'active', Event.authenticated == 0).all()
        
        # 2. Map existing by coordinate signature
        existing_map = {f"{round(e.latitude, 3)}_{round(e.longitude, 3)}": e for e in current_active}
        
        # 3. Process new events
        for ne in new_events:
            sig = f"{round(ne.latitude, 3)}_{round(ne.longitude, 3)}"
            if sig in existing_map:
                # Update existing (keep its original start time and DB ID)
                ex = existing_map[sig]
                ex.address = ne.address
                ex.event_cause = ne.event_cause
                ex.duration_minutes = ne.duration_minutes
                ex.duration_bucket = ne.duration_bucket
                ex.priority = ne.priority
                ex.priority_high = ne.priority_high
                ex.requires_road_closure = ne.requires_road_closure
                del existing_map[sig]
            else:
                # Insert new
                db.add(ne)
                
        # 4. Any remaining in existing_map are no longer active, mark resolved
        for ex in existing_map.values():
            ex.status = "resolved"
            ex.closed_datetime = datetime.now(timezone.utc).replace(tzinfo=None)
            
        db.commit()
        logger.info("[TomTom Sync] Successfully updated live map with real-time Bengaluru anomalies (Upsert).")
    except Exception as e:
        logger.error(f"[TomTom Sync] DB write failed: {e}")
        db.rollback()
