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

# Map Corridors to (Origin, Destination) coordinate strings "lat,lon:lat,lon"
CORRIDOR_COORDS = {
    "Tumkur Road": "13.024,77.552:13.040,77.525",
    "Mysore Road": "12.956,77.535:12.910,77.485",
    "Bellary Road 1": "13.013,77.585:13.048,77.592",
    "Hosur Road": "12.926,77.622:12.845,77.665",
    "ORR East 1": "12.923,77.637:12.956,77.698",
    "Old Madras Road": "12.983,77.638:13.003,77.682",
    "Magadi Road": "12.975,77.561:12.982,77.523",
    "Bellary Road 2": "13.048,77.592:13.100,77.595",
    "ORR North 1": "13.025,77.640:13.048,77.592",
    "Bannerghata Road": "12.926,77.600:12.875,77.595",
    "West of Chord Road": "12.981,77.545:13.010,77.548",
    "CBD 1": "12.971,77.594:12.980,77.605"
}

# Static fallback routes when TomTom API is unavailable (demo-safe)
STATIC_DIVERSIONS = {
    "Tumkur Road": [
        {"name": "Magadi Road via Vijayanagar", "stress_score": 35, "stress_level": "Medium", "extra_minutes": 12, "notes": "Parallel arterial — moderate congestion expected."},
        {"name": "NICE Road connector", "stress_score": 22, "stress_level": "Low", "extra_minutes": 8, "notes": "Toll road bypass — lower stress alternate."},
    ],
    "Mysore Road": [
        {"name": "Magadi Road", "stress_score": 40, "stress_level": "Medium", "extra_minutes": 15, "notes": "Standard diversion for Mysore Road blockages."},
        {"name": "NICE Road (Konanakunte)", "stress_score": 25, "stress_level": "Low", "extra_minutes": 10, "notes": "Longer but free-flowing bypass."},
    ],
    "Bellary Road 1": [
        {"name": "Bellary Road 2 via Hebbal", "stress_score": 45, "stress_level": "Medium", "extra_minutes": 14, "notes": "Inner ring alternate for Hebbal corridor."},
    ],
    "Hosur Road": [
        {"name": "Bannerghatta Road", "stress_score": 38, "stress_level": "Medium", "extra_minutes": 11, "notes": "South-east parallel route."},
    ],
    "ORR East 1": [
        {"name": "ORR East 2 via Bellandur", "stress_score": 42, "stress_level": "Medium", "extra_minutes": 13, "notes": "Outer ring continuation route."},
    ],
    "Old Madras Road": [
        {"name": "KR Puram alternate via Swami Vivekananda Road", "stress_score": 30, "stress_level": "Low", "extra_minutes": 9, "notes": "Eastern bypass for Old Madras block."},
    ],
}


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
async def get_diversions(corridor_name: str):
    coords = CORRIDOR_COORDS.get(corridor_name)
    if not coords:
        coords = "12.971,77.594:12.926,77.622"

    api_key = settings.TOMTOM_API_KEY
    if not api_key:
        alternates = STATIC_DIVERSIONS.get(corridor_name, STATIC_DIVERSIONS.get("Tumkur Road", []))
        return {
            "blocked_corridor": corridor_name,
            "alternates": alternates,
            "message": f"{corridor_name} is blocked. Showing pre-computed alternate routes (TomTom key not configured).",
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

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.error(f"TomTom Routing API failed: {e}")
        alternates = STATIC_DIVERSIONS.get(corridor_name, [])
        return {
            "blocked_corridor": corridor_name,
            "alternates": alternates,
            "message": f"{corridor_name} is blocked. TomTom unavailable — showing fallback routes.",
        }

    routes = data.get("routes", [])
    if len(routes) <= 1:
        return {"blocked_corridor": corridor_name, "alternates": [], "message": f"{corridor_name} is blocked. No clear alternatives found."}

    # The first route is the primary. The rest are alternatives.
    alternatives = []
    primary_summary = routes[0].get("summary", {})
    primary_travel_time = primary_summary.get("travelTimeInSeconds", 0)

    for idx, r in enumerate(routes[1:]):
        summary = r.get("summary", {})
        travel_time = summary.get("travelTimeInSeconds", 0)
        traffic_delay = summary.get("trafficDelayInSeconds", 0)
        length_km = summary.get("lengthInMeters", 0) / 1000.0

        # Extract real road names from guidance instructions
        route_name = _extract_route_name(r, idx)

        # Calculate extra minutes compared to a traffic-free primary route, or just absolute delay
        extra_minutes = round(traffic_delay / 60.0)
        stress_score = min(100, round(extra_minutes * 3.5, 1))

        if stress_score < 30:
            stress_level = "Low"
        elif stress_score < 65:
            stress_level = "Medium"
        else:
            stress_level = "High"

        alternatives.append({
            "name": route_name,
            "stress_score": stress_score,
            "stress_level": stress_level,
            "extra_minutes": extra_minutes,
            "notes": f"{round(length_km, 1)} km live-routed path. {extra_minutes} min traffic delay."
        })

    return {
        "blocked_corridor": corridor_name,
        "alternates": alternatives,
        "message": f"{corridor_name} is blocked. {len(alternatives)} live alternate route(s) generated via TomTom."
    }
