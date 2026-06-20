"""
diversion.py — GET /api/diversion/{corridor_name}
Fetches live alternate routes dynamically using the TomTom Routing API.
"""

from fastapi import APIRouter, Depends, HTTPException
import httpx
import sys, os, logging

logger = logging.getLogger(__name__)

# Ensure config is available
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from app.core.config import settings

router = APIRouter(prefix="/diversion", tags=["Diversion"])

# No hardcoded routes. Everything is dynamically generated from live GPS.


def _is_major_road(name: str) -> bool:
    """Heuristic: identify major/named roads vs tiny local streets."""
    if not name or len(name) < 6:
        return False
    major_keywords = [
        "tumkur", "mysore", "hosur", "bellary", "magadi", "nice road",
        "bannerghatta", "old madras", "outer ring", "orr", "nh ", "sh ",
        "100 feet", "80 ft", "60 feet", "subedar", "ramaiah", "hmt",
        "pipeline", "chord", "airport", "expressway", "flyover", "highway",
        "ring road", "shankar nagar", "ms ramaiah", "yeshwanthpur",
    ]
    name_lower = name.lower()
    return any(kw in name_lower for kw in major_keywords)


def _extract_route_name(route: dict, idx: int) -> str:
    """
    Parse TomTom guidance.instructions to build a human-readable route name.
    Prioritises major/named Bengaluru roads. Falls back gracefully.
    """
    try:
        instructions = route.get("guidance", {}).get("instructions", [])
        seen: list[str] = []
        skip_types = {"DEPART", "ARRIVE"}

        for inst in instructions:
            if inst.get("maneuver", "") in skip_types:
                continue  # skip origin/destination — always a local street
            street = (inst.get("street") or "").strip()
            if street and street not in seen and len(street) > 5:
                seen.append(street)

        # Priority 1: actual major/named roads
        major = [r for r in seen if _is_major_road(r)][:3]

        # Priority 2: longest road names tend to be more significant
        if not major:
            major = sorted([r for r in seen if len(r) > 8], key=len, reverse=True)[:3]

        # Priority 3: any road longer than 5 chars
        if not major:
            major = [r for r in seen if len(r) > 5][:3]

        if major:
            return "Via " + " > ".join(major)
    except Exception as e:
        logger.warning(f"Route name extraction failed: {e}")

    return f"Alternate Route {idx + 1}"



@router.get("/{corridor_name}")
async def get_diversions(
    corridor_name: str,
    event_cause: str = "vehicle_breakdown",
    veh_type: str = "N/A",
    hour: int = 9,
    lat: float = None,
    lon: float = None
):
    if lat is None or lon is None:
        from app.models.db import SessionLocal, Event
        from sqlalchemy import func
        db = SessionLocal()
        base = corridor_name.split(" (")[0].lower().strip()
        row = db.query(
            func.avg(Event.latitude).label("lat"),
            func.avg(Event.longitude).label("lon")
        ).filter(Event.corridor.ilike(f"%{base}%")).first()
        db.close()
        
        if row and row.lat and row.lon:
            lat, lon = row.lat, row.lon
        else:
            lat, lon = 12.9716, 77.5946 # CBD fallback

    # Generate a dynamic endpoint ~5km away to bypass blockage
    end_lat = lat + 0.045
    end_lon = lon + 0.045
    coords = f"{lat},{lon}:{end_lat},{end_lon}"

    api_key = settings.TOMTOM_API_KEY
    if not api_key:
        return {
            "blocked_corridor": corridor_name,
            "alternates": [],
            "message": f"{corridor_name} is blocked. TomTom API Key missing, dynamic routing unavailable.",
        }

    url = f"https://api.tomtom.com/routing/1/calculateRoute/{coords}/json"
    params = {
        "key": api_key,
        "alternativeType": "anyRoute",
        "computeBestOrder": "false",
        "routeType": "fastest",
        "traffic": "true",
        "maxAlternatives": 2,
        "instructionsType": "text",         # enables guidance.instructions with street names
        "instructionAnnouncementPoints": "all",
    }

    # 1. Fetch TomTom Routing API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            if response.status_code in [403, 429] and settings.TOMTOM_API_KEY_FALLBACK:
                logger.warning(f"TomTom Routing API failed with {response.status_code}. Using fallback key.")
                params["key"] = settings.TOMTOM_API_KEY_FALLBACK
                response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.error(f"TomTom Routing API failed: {e}")
        return {
            "blocked_corridor": corridor_name,
            "alternates": [],
            "message": f"{corridor_name} is blocked. TomTom unavailable.",
        }

    routes = data.get("routes", [])
    if len(routes) <= 1:
        return {"blocked_corridor": corridor_name, "alternates": [], "message": f"{corridor_name} is blocked. No clear alternatives found."}

    # 2. Extract alternates and their mid-points for Flow analysis
    alternates_data = []
    for idx, r in enumerate(routes[1:]):
        summary = r.get("summary", {})
        length_km = summary.get("lengthInMeters", 0) / 1000.0
        traffic_delay = summary.get("trafficDelayInSeconds", 0)
        route_name = _extract_route_name(r, idx)

        # Get midpoint of the route to check real-time flow congestion
        instructions = r.get("guidance", {}).get("instructions", [])
        mid_lat, mid_lon = 12.9716, 77.5946
        if instructions:
            mid_idx = len(instructions) // 2
            point = instructions[mid_idx].get("point", {})
            if "latitude" in point:
                mid_lat = point["latitude"]
                mid_lon = point["longitude"]

        alternates_data.append({
            "idx": idx,
            "name": route_name,
            "length_km": length_km,
            "traffic_delay": traffic_delay,
            "mid_lat": mid_lat,
            "mid_lon": mid_lon
        })

    # 3. Query TomTom Flow API for LIVE Real-Time Congestion
    async def get_live_stress(lat, lon):
        flow_url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(flow_url, params={"key": api_key, "point": f"{lat},{lon}", "unit": "KMPH"}, timeout=5.0)
                if res.status_code == 200:
                    fsd = res.json().get("flowSegmentData", {})
                    cs = fsd.get("currentSpeed")
                    ff = fsd.get("freeFlowSpeed")
                    if cs is not None and ff and ff > 0:
                        return max(0.0, min(100.0, ((ff - cs) / ff) * 100))
        except Exception:
            pass
        return 0.0

    import asyncio
    stress_results = await asyncio.gather(*[get_live_stress(alt["mid_lat"], alt["mid_lon"]) for alt in alternates_data])

    # 4. Use trained ML Model to predict Incident Duration Impact
    from ml.predict import predict_duration
    from datetime import datetime
    ml_input = {
        "event_cause": event_cause,
        "veh_type": veh_type,
        "corridor": corridor_name,
        "hour": hour,
        "month": datetime.now().month,
        "weekday": datetime.now().weekday()
    }
    try:
        duration_pred = predict_duration(ml_input)
        ml_estimated_minutes = duration_pred.get("estimated_minutes", 60.0)
    except Exception as e:
        logger.warning(f"ML Duration Prediction failed: {e}")
        ml_estimated_minutes = 60.0

    # Spillover ratio: every hour of blockage adds a base +10% stress projection to surrounding alternates
    ml_spillover_projection = (ml_estimated_minutes / 60.0) * 10.0

    # 5. Build final response (Hybrid: ML Projection + Live API Data)
    final_alternates = []
    for alt, live_stress in zip(alternates_data, stress_results):
        extra_minutes = round(alt["traffic_delay"] / 60.0)
        
        # True Hybrid Score: Live Congestion + ML Spillover Projection
        stress_score = min(100.0, live_stress + ml_spillover_projection)
        stress_score = round(stress_score, 1)

        # Ensure delay minutes reflect the stress score visually
        if stress_score > 30 and extra_minutes < 10:
            extra_minutes += round(stress_score / 4.0)

        if stress_score < 35:
            stress_level = "Low"
        elif stress_score < 70:
            stress_level = "Medium"
        else:
            stress_level = "High"

        final_alternates.append({
            "name": alt["name"],
            "stress_score": stress_score,
            "stress_level": stress_level,
            "extra_minutes": extra_minutes,
            "notes": f"{round(alt['length_km'], 1)} km live path. {round(live_stress)}% live congestion + {round(ml_spillover_projection)}% ML projected spillover ({round(ml_estimated_minutes)}min blockage)."
        })

    return {
        "blocked_corridor": corridor_name,
        "alternates": final_alternates,
        "message": f"{corridor_name} is blocked. Hybrid ML + Live API analysis generated for {len(final_alternates)} routes."
    }

