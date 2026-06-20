"""
incidents.py — GET /api/incidents  &  GET /api/incidents/{id}
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional
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
