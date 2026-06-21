"""
incidents.py — GET /api/incidents  &  GET /api/incidents/{id}
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional
from pydantic import BaseModel
import math

from ..models.db import get_db, Event
from ..models.schemas import EventBase, EventListItem, PaginatedEvents

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("", response_model=PaginatedEvents)
def list_incidents(
    status: Optional[str] = Query(None, description="active|closed|resolved"),
    priority: Optional[str] = Query(None, description="High|Low"),
    corridor: Optional[str] = Query(None),
    zone: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """Return paginated list of incidents with geo + key fields for map rendering."""
    filters = []

    if status:
        filters.append(Event.status == status)
    if priority:
        filters.append(Event.priority == priority)
    if corridor:
        filters.append(Event.corridor == corridor)
    if zone:
        filters.append(Event.zone == zone)
    if date_from:
        filters.append(Event.start_datetime >= date_from)
    if date_to:
        filters.append(Event.start_datetime <= date_to + " 23:59:59")

    query = db.query(Event)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    offset = (page - 1) * page_size
    events = query.order_by(Event.priority_high.desc(), Event.start_datetime.desc()) \
                  .offset(offset).limit(page_size).all()

    items = []
    for e in events:
        items.append(EventListItem(
            id=e.id,
            latitude=e.latitude,
            longitude=e.longitude,
            event_cause=e.event_cause or "",
            corridor=e.corridor or "Non-corridor",
            zone=e.zone or "Unknown",
            priority=e.priority or "Low",
            requires_road_closure=e.requires_road_closure or 0,
            status=e.status or "unknown",
            duration_bucket=e.duration_bucket,
            hour=e.hour,
            authenticated=e.authenticated or False,
            start_datetime=str(e.start_datetime) if e.start_datetime else None,
            address=e.address,
        ))

    return PaginatedEvents(
        total=total,
        page=page,
        page_size=page_size,
        events=items,
    )


@router.get("/timeline")
def get_incident_timeline(
    hours: int = Query(8, ge=1, le=24, description="Hours back to query: 8 or 24"),
    zone: Optional[str] = Query(None, description="Filter by zone"),
    corridor: Optional[str] = Query(None, description="Filter by corridor"),
    db: Session = Depends(get_db),
):
    """
    Return a chronological activity log of incidents from the last N hours.
    Used by the Shift Report / Incident Timeline screen.
    When the DB has no start_datetime data for 'active' events (historical seed),
    we fall back to sampling recent historical events to give a realistic demo.
    """
    from datetime import datetime, timedelta
    from sqlalchemy import func as sql_func

    cutoff = datetime.now() - timedelta(hours=hours)

    filters = [Event.start_datetime >= cutoff]
    if zone:
        filters.append(Event.zone == zone)
    if corridor:
        filters.append(Event.corridor == corridor)

    events = (
        db.query(Event)
        .filter(and_(*filters))
        .order_by(Event.start_datetime.desc())
        .limit(200)
        .all()
    )

    # Fallback: if no events in the time window (historical data has old dates),
    # return a representative sample of recent historical events for demo purposes.
    if not events:
        q = db.query(Event).filter(Event.start_datetime.isnot(None))
        if zone:
            q = q.filter(Event.zone == zone)
        if corridor:
            q = q.filter(Event.corridor == corridor)
        events = q.order_by(Event.start_datetime.desc()).limit(50).all()

    items = []
    for e in events:
        # Compute elapsed label
        elapsed_label = "Unknown"
        if e.start_datetime:
            try:
                delta = datetime.now() - e.start_datetime
                total_min = int(delta.total_seconds() / 60)
                if total_min < 60:
                    elapsed_label = f"{total_min}m ago"
                elif total_min < 1440:
                    elapsed_label = f"{total_min // 60}h {total_min % 60}m ago"
                else:
                    elapsed_label = f"{total_min // 1440}d ago"
            except Exception:
                elapsed_label = "—"

        items.append({
            "id": e.id,
            "event_cause": (e.event_cause or "unknown").replace("_", " ").title(),
            "corridor": e.corridor or "Non-corridor",
            "zone": e.zone or "Unknown",
            "priority": e.priority or "Low",
            "status": e.status or "unknown",
            "requires_road_closure": bool(e.requires_road_closure),
            "duration_bucket": e.duration_bucket,
            "duration_minutes": e.duration_minutes,
            "address": e.address or "",
            "is_peak_hour": bool(e.is_peak_hour),
            "authenticated": bool(e.authenticated),
            "start_datetime": str(e.start_datetime) if e.start_datetime else None,
            "elapsed_label": elapsed_label,
            "hour": e.hour,
            "police_station": e.police_station or "",
        })

    # Summary counts for the shift report header
    total = len(items)
    high_count = sum(1 for i in items if i["priority"] == "High")
    closure_count = sum(1 for i in items if i["requires_road_closure"])
    resolved_count = sum(1 for i in items if i["status"] == "closed")

    return {
        "hours": hours,
        "zone_filter": zone,
        "corridor_filter": corridor,
        "total_events": total,
        "high_priority_count": high_count,
        "closure_count": closure_count,
        "resolved_count": resolved_count,
        "events": items,
    }


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """Return high-level KPI stats for the dashboard top bar."""
    total = db.query(Event).count()
    active = db.query(Event).filter(Event.status == "active").count()
    high_priority_active = db.query(Event).filter(
        Event.status == "active", Event.priority == "High"
    ).count()
    road_closures_active = db.query(Event).filter(
        Event.status == "active", Event.requires_road_closure == 1
    ).count()
    closed_count = db.query(Event).filter(Event.status == "closed").count()

    # Avg resolution for closed events that have duration
    from sqlalchemy import func
    avg_dur = db.query(func.avg(Event.duration_minutes)).filter(
        Event.status == "closed", Event.duration_minutes.isnot(None)
    ).scalar()

    return {
        "total_incidents": total,
        "active_incidents": active,
        "high_priority_active": high_priority_active,
        "road_closures_active": road_closures_active,
        "closed_incidents": closed_count,
        "avg_resolution_hours": round(avg_dur / 60, 1) if avg_dur else None,
    }


@router.get("/{incident_id}", response_model=EventBase)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    """Return full detail of a single incident."""
    event = db.query(Event).filter(Event.id == incident_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

    return EventBase(
        id=event.id,
        status=event.status or "",
        event_type=event.event_type or "",
        event_cause=event.event_cause or "",
        corridor=event.corridor or "",
        zone=event.zone or "",
        veh_type=event.veh_type or "",
        junction=event.junction,
        police_station=event.police_station,
        latitude=event.latitude,
        longitude=event.longitude,
        address=event.address,
        priority=event.priority or "Low",
        priority_high=event.priority_high or 0,
        requires_road_closure=event.requires_road_closure or 0,
        duration_minutes=event.duration_minutes,
        duration_bucket=event.duration_bucket,
        hour=event.hour,
        weekday=event.weekday,
        month=event.month,
        is_peak_hour=bool(event.is_peak_hour),
        authenticated=event.authenticated or False,
        start_datetime=str(event.start_datetime) if event.start_datetime else None,
        closed_datetime=str(event.closed_datetime) if event.closed_datetime else None,
    )


class IncidentReportRequest(BaseModel):
    event_cause: str
    corridor: str
    veh_type: str = "N/A"
    description: str = ""
    address: str = ""
    latitude: float = 12.9716
    longitude: float = 77.5946
    reporter_name: str = "Field Officer"


@router.post("/report")
def report_incident(request: IncidentReportRequest, db: Session = Depends(get_db)):
    """
    Submit a new incident report from field officers or citizens.
    Auto-classifies priority based on event_cause and creates DB entry.
    """
    from datetime import datetime
    import random

    # Auto-priority rules
    high_priority_causes = ["accident", "vehicle_breakdown", "water_logging", "tree_fall", "oil_spill"]
    priority_high = 1 if request.event_cause in high_priority_causes else 0
    priority = "High" if priority_high else "Low"
    requires_closure = 1 if request.event_cause in ["accident", "tree_fall", "construction"] else 0

    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()
    month = now.month
    is_peak = 1 if (8 <= hour <= 10 or 17 <= hour <= 20) else 0

    new_event = Event(
        status="active",
        authenticated=False,
        latitude=request.latitude,
        longitude=request.longitude,
        address=request.address or f"Reported near {request.corridor}",
        event_type="unplanned",
        event_cause=request.event_cause,
        corridor=request.corridor,
        zone="Unknown",
        veh_type=request.veh_type,
        junction="unmapped",
        police_station="",
        start_datetime=now,
        hour=hour,
        weekday=weekday,
        month=month,
        is_peak_hour=is_peak,
        priority=priority,
        priority_high=priority_high,
        requires_road_closure=requires_closure,
        duration_bucket="Medium",
        has_cargo_data=0,
        has_truck_age=0,
        has_junction=0,
        is_authenticated=0,
    )

    try:
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save incident: {e}")

    return {
        "success": True,
        "incident_id": new_event.id,
        "priority": priority,
        "message": f"Incident reported successfully. Priority: {priority}. ID: {new_event.id}",
    }
