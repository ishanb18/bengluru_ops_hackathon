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

# ── Static police station lookup ───────────────────────────────────────────────
# Precomputed station associations per corridor (from historical data patterns)
CORRIDOR_STATIONS = {
    "Tumkur Road":     ["Peenya PS", "Yeshwanthpura PS", "Jalahalli PS", "Malleshwaram PS"],
    "Mysore Road":     ["Kengeri PS", "Rajarajeshwari Nagar PS", "Uttarahalli PS"],
    "Bellary Road 1":  ["Hebbal PS", "Sadashivanagar PS", "Yelahanka PS"],
    "Bellary Road 2":  ["Hebbal PS", "Yelahanka PS", "Bagalagunte PS"],
    "Hosur Road":      ["Electronic City PS", "BTM Layout PS", "Koramangala PS"],
    "ORR East 1":      ["Marathahalli PS", "KR Puram PS", "Whitefield PS"],
    "ORR East 2":      ["Marathahalli PS", "Bellandur PS"],
    "ORR North 1":     ["Hebbal PS", "Yelahanka PS"],
    "ORR North 2":     ["Bagalagunte PS", "Peenya PS"],
    "Old Madras Road": ["KR Puram PS", "Banaswadi PS"],
    "Magadi Road":     ["Magadi Road PS", "Vijayanagar PS"],
    "Bannerghata Road": ["JP Nagar PS", "Gottigere PS"],
}
DEFAULT_STATIONS = ["Central PS", "Traffic Control PS"]

# Simulated response times (minutes) — in real system, compute haversine distance
STATION_RESPONSE_TIMES = {
    "Peenya PS": 7,
    "Yeshwanthpura PS": 12,
    "Jalahalli PS": 18,
    "Malleshwaram PS": 24,
    "Kengeri PS": 10,
    "Rajarajeshwari Nagar PS": 15,
    "Hebbal PS": 8,
    "Sadashivanagar PS": 14,
    "Yelahanka PS": 20,
    "Electronic City PS": 11,
    "BTM Layout PS": 16,
    "Koramangala PS": 19,
    "Marathahalli PS": 9,
    "KR Puram PS": 13,
    "Whitefield PS": 22,
    "JP Nagar PS": 17,
    "Central PS": 25,
    "Traffic Control PS": 30,
}

BADGE_BY_INDEX = ["Primary", "Secondary", "Backup", "Far"]


def build_station_list(corridor: str) -> list[StationInfo]:
    stations = CORRIDOR_STATIONS.get(corridor, DEFAULT_STATIONS)[:4]
    result = []
    for i, name in enumerate(stations):
        eta = STATION_RESPONSE_TIMES.get(name, 20 + i * 5)
        dist_label = f"~{round(eta * 0.7, 1)} km"  # rough estimate: 0.7 km/min avg city speed
        result.append(StationInfo(
            name=name,
            distance_label=dist_label,
            estimated_response_min=eta,
            badge=BADGE_BY_INDEX[i] if i < len(BADGE_BY_INDEX) else "Far",
        ))
    return result


@router.post("", response_model=ManpowerResponse)
def recommend_manpower(request: ManpowerRequest):
    """
    Return AI-calculated deployment: officer count, barricades, tow truck,
    and nearest police station recommendations.
    """
    data = request.dict()
    rec = get_manpower_recommendation(
        priority=data["priority"],
        requires_closure=data["requires_closure"],
        corridor=data["corridor"],
        duration_bucket=data["duration_bucket"],
        veh_type=data["veh_type"],
    )

    stations = build_station_list(data["corridor"])

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
