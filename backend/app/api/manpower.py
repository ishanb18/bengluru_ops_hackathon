"""
manpower.py — POST /api/manpower
Rule-based manpower + resource recommendation engine.
"""

from fastapi import APIRouter
from ..models.schemas import ManpowerRequest, ManpowerResponse, StationInfo
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from ml.predict import get_manpower_recommendation, load_corridor_risk

router = APIRouter(prefix="/manpower", tags=["Manpower"])

import httpx
from app.core.config import settings

BADGE_BY_INDEX = ["Primary", "Secondary", "Backup", "Far"]

def get_nearest_police_stations(lat: float, lon: float) -> list[StationInfo]:
    """
    Dynamically finds the nearest police stations using TomTom POI Search API
    based on the exact latitude and longitude of the incident, removing hardcoded maps.
    """
    api_key = settings.TOMTOM_API_KEY
    if not api_key:
        return [
            StationInfo(name="Central PS", distance_label="~5.0 km", estimated_response_min=15, badge="Primary"),
            StationInfo(name="Traffic Control", distance_label="~8.0 km", estimated_response_min=25, badge="Backup")
        ]
        
    url = f"https://api.tomtom.com/search/2/categorySearch/police.json?lat={lat}&lon={lon}&radius=15000&limit=4&key={api_key}"
    
    try:
        try:
            response = httpx.get(url, timeout=5.0)
            response.raise_for_status()
            results = response.json().get("results", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [403, 429] and settings.TOMTOM_API_KEY_FALLBACK:
                import logging
                logging.getLogger(__name__).warning(f"TomTom POI search primary key failed ({e.response.status_code}). Switching to Fallback...")
                fallback_url = url.replace(api_key, settings.TOMTOM_API_KEY_FALLBACK)
                try:
                    response = httpx.get(fallback_url, timeout=5.0)
                    response.raise_for_status()
                    results = response.json().get("results", [])
                except Exception as e2:
                    logging.getLogger(__name__).warning(f"TomTom POI search fallback failed: {e2}")
                    raise e2
            else:
                raise e
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"TomTom POI search failed: {e}")
            raise e
            
        stations = []
        for i, res in enumerate(results):
            name = res.get("poi", {}).get("name", f"Station {i+1}")
            # Ensure it actually sounds like a station name to keep UI clean
            if "Police" not in name and "Station" not in name:
                name += " Police Station"
                
            dist_meters = res.get("dist", 0)
            dist_km = round(dist_meters / 1000.0, 1)
            
            # Assume 30 km/h avg city speed for police: 30 km / 60 min = 0.5 km/min
            # So ETA = distance in km / 0.5 = dist * 2 minutes + 3 min dispatch delay
            eta_min = int(dist_km * 2) + 3
            
            stations.append(StationInfo(
                name=name,
                distance_label=f"~{dist_km} km",
                estimated_response_min=eta_min,
                badge=BADGE_BY_INDEX[i] if i < len(BADGE_BY_INDEX) else "Far",
            ))
            
        if not stations:
            raise ValueError("No stations found in radius")
            
        return stations
            
    except Exception as e:
        # Fallback returned from the nested exception or if completely failed
        return [
            StationInfo(name="Ulsoor Traffic PS (Fallback)", distance_label="~3.5 km", estimated_response_min=12, badge="Primary"),
            StationInfo(name="Cubbon Park Traffic PS", distance_label="~7.0 km", estimated_response_min=22, badge="Backup"),
        ]


@router.post("", response_model=ManpowerResponse)
def recommend_manpower(request: ManpowerRequest):
    """
    Return AI-calculated deployment: officer count, barricades, tow truck,
    and nearest police station recommendations.
    """
    data = request.model_dump()
    rec = get_manpower_recommendation(
        priority=data["priority"],
        requires_closure=data["requires_closure"],
        corridor=data["corridor"],
        duration_bucket=data["duration_bucket"],
        veh_type=data["veh_type"],
    )

    stations = get_nearest_police_stations(data.get("latitude", 12.9716), data.get("longitude", 77.5946))

    return ManpowerResponse(
        officer_count=rec["officer_count"],
        barricade_count=rec["barricade_count"],
        tow_truck_needed=rec["tow_truck_needed"],
        bbmp_escalation=rec["bbmp_escalation"],
        corridor_risk_score=rec["corridor_risk_score"],
        deployment_priority=rec["deployment_priority"],
        notes=rec["notes"],
        nearest_stations=stations,
    )
