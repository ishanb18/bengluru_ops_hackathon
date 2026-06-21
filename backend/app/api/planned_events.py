"""
planned_events.py — GET/POST /api/planned-events
Manages scheduled/planned traffic events: VIP movements, festivals, road works, etc.
Stores in-memory for demo; easily extensible to DB.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/planned-events", tags=["Planned Events"])

# Pre-seeded real upcoming Bengaluru events (June–August 2026)
_PLANNED_EVENTS = [
    {
        "id": 1,
        "title": "Kempegowda Jayanti Procession",
        "event_type": "Festival",
        "corridor": "CBD 1",
        "date": "2026-06-27",
        "time": "09:00",
        "duration_hours": 5,
        "impact": "High",
        "manpower_needed": 55,
        "description": "Annual Kempegowda Jayanti celebrations. Large procession from Town Hall to Lal Bagh. Full closure of KG Road, Majestic area. Diversions via Mysore Road and Magadi Road.",
        "status": "upcoming",
    },
    {
        "id": 2,
        "title": "ISKCON Rath Yatra — Rajajinagar",
        "event_type": "Festival",
        "corridor": "Magadi Road",
        "date": "2026-06-28",
        "time": "07:00",
        "duration_hours": 6,
        "impact": "Medium",
        "manpower_needed": 30,
        "description": "ISKCON Rath Yatra chariot procession from Rajajinagar to Majestic. Partial closure on West of Chord Road and Magadi Road. Heavy devotee footfall near Majestic junction.",
        "status": "upcoming",
    },
    {
        "id": 3,
        "title": "Silk Board Flyover Night Maintenance",
        "event_type": "Road Work",
        "corridor": "Hosur Road",
        "date": "2026-07-04",
        "time": "23:00",
        "duration_hours": 7,
        "impact": "High",
        "manpower_needed": 14,
        "description": "NHAI structural maintenance on Silk Board flyover. Full closure of Hosur Road northbound from Electronic City to Silk Board. Diversion via Bannerghatta Road. All heavy vehicles banned.",
        "status": "upcoming",
    },
    {
        "id": 4,
        "title": "VIP Movement — Governor's Convoy",
        "event_type": "VIP Movement",
        "corridor": "Bellary Road 1",
        "date": "2026-07-08",
        "time": "10:30",
        "duration_hours": 1,
        "impact": "Medium",
        "manpower_needed": 28,
        "description": "Governor's convoy from Raj Bhavan to Vidhana Soudha for assembly session inauguration. Temporary 15-min corridor hold on Bellary Road and MG Road.",
        "status": "upcoming",
    },
    {
        "id": 5,
        "title": "Varamahalakshmi Procession — Old Madras Road",
        "event_type": "Festival",
        "corridor": "Old Madras Road",
        "date": "2026-08-07",
        "time": "08:00",
        "duration_hours": 4,
        "impact": "Medium",
        "manpower_needed": 22,
        "description": "Varamahalakshmi Vratam processions across East Bengaluru. Temporary road blocks near Indiranagar, Kalyan Nagar, and Banaswadi areas. Expected crowd of 50,000+.",
        "status": "upcoming",
    },
    {
        "id": 6,
        "title": "Independence Day Parade — Rajpath",
        "event_type": "Public Event",
        "corridor": "Bellary Road 1",
        "date": "2026-08-15",
        "time": "08:00",
        "duration_hours": 4,
        "impact": "High",
        "manpower_needed": 80,
        "description": "Karnataka Independence Day parade at Field Marshal Manekshaw Parade Ground. Full closure of Bellary Road, MG Road, and Vidhana Soudha area from 5 AM. Metro recommended for public.",
        "status": "upcoming",
    },
]

_next_id = 7


class PlannedEventRequest(BaseModel):
    title: str
    event_type: str
    corridor: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    duration_hours: float
    impact: str  # Low / Medium / High
    description: str = ""
    manpower_needed: Optional[int] = None


@router.get("")
def list_planned_events():
    """Return all planned events sorted by date."""
    sorted_events = sorted(_PLANNED_EVENTS, key=lambda x: (x["date"], x["time"]))
    return {"events": sorted_events, "total": len(sorted_events)}


@router.post("")
def create_planned_event(request: PlannedEventRequest):
    """Schedule a new planned event."""
    global _next_id

    # Auto-estimate manpower if not provided
    manpower = request.manpower_needed
    if manpower is None:
        base = {"Low": 5, "Medium": 15, "High": 35}.get(request.impact, 10)
        manpower = base + int(request.duration_hours * 2)

    event = {
        "id": _next_id,
        "title": request.title,
        "event_type": request.event_type,
        "corridor": request.corridor,
        "date": request.date,
        "time": request.time,
        "duration_hours": request.duration_hours,
        "impact": request.impact,
        "manpower_needed": manpower,
        "description": request.description,
        "status": "upcoming",
    }
    _PLANNED_EVENTS.append(event)
    _next_id += 1
    return {"success": True, "event": event}


@router.delete("/{event_id}")
def delete_planned_event(event_id: int):
    """Remove a planned event."""
    global _PLANNED_EVENTS
    before = len(_PLANNED_EVENTS)
    _PLANNED_EVENTS = [e for e in _PLANNED_EVENTS if e["id"] != event_id]
    if len(_PLANNED_EVENTS) == before:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Event not found")
    return {"success": True}
