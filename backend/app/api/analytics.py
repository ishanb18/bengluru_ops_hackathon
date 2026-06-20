"""
analytics.py — GET /api/analytics/*
All analytics endpoints — powered by live DB queries (Real-Time City Insights).
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List

from ..models.db import get_db, Event
from ..models.schemas import (
    CorridorRiskItem, MonthlyTrend, JunctionCount,
    ZonePeakHour, SummaryStats, CauseBreakdown
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ── Live Corridor Risk Ranking ────────────────────────────────────────────────

@router.get("/corridor-risk", response_model=List[CorridorRiskItem])
def corridor_risk(db: Session = Depends(get_db)):
    """Return real-time corridor risk scores based on active incidents."""
    
    # Query live events per corridor
    query = db.query(
        Event.corridor,
        func.count(Event.id).label("incident_count"),
        func.sum(Event.priority_high).label("high_prio_count"),
        func.sum(Event.requires_road_closure).label("closure_count")
    ).filter(
        Event.status == "active",
        Event.corridor != "Non-corridor"
    ).group_by(Event.corridor).order_by(desc("incident_count")).limit(20)

    items = []
    for rank, row in enumerate(query.all(), 1):
        count = row.incident_count or 1
        pct_high = (row.high_prio_count / count) * 100
        pct_closure = (row.closure_count / count) * 100
        
        # Calculate live risk score (arbitrary weights: 1 base, 2 high prio, 3 closure)
        score = round((count * 1.0) + (row.high_prio_count * 2.0) + (row.closure_count * 3.0), 1)
        
        if score > 15: risk_tier = "High"
        elif score > 5: risk_tier = "Medium"
        else: risk_tier = "Low"

        items.append(CorridorRiskItem(
            rank=rank,
            corridor=row.corridor,
            risk_score=score,
            risk_tier=risk_tier,
            incident_count=count,
            pct_high_priority=round(pct_high, 1),
            pct_road_closures=round(pct_closure, 1),
            event_cause_top="Dynamic Live Causes" 
        ))
    
    return items


# ── Hourly Trend (Replacing Monthly) ──────────────────────────────────────────

@router.get("/monthly-trend", response_model=List[MonthlyTrend])
def hourly_trend(db: Session = Depends(get_db)):
    """Return live hour-by-hour incident counts (Mocking monthly trend schema for UI compatibility)."""
    
    query = db.query(
        Event.hour,
        func.count(Event.id).label("count")
    ).filter(Event.status == "active").group_by(Event.hour).order_by(Event.hour).all()
    
    # Map hour integer to string month name to satisfy the MonthlyTrend schema in the frontend
    hour_map = {0: "12 AM", 4: "4 AM", 8: "8 AM", 12: "12 PM", 16: "4 PM", 20: "8 PM"}
    
    return [
        MonthlyTrend(
            month=hour_map.get(row.hour, f"{row.hour}:00"), 
            incident_count=row.count
        )
        for row in query
    ]


# ── Top Junctions ─────────────────────────────────────────────────────────────

@router.get("/top-junctions", response_model=List[JunctionCount])
def top_junctions(db: Session = Depends(get_db)):
    """Return top 10 worst live junctions by incident count."""
    
    query = db.query(
        Event.address, # Use Address since TomTom doesn't map exact 'junction' strings
        func.count(Event.id).label("count")
    ).filter(
        Event.status == "active",
        Event.address != None
    ).group_by(Event.address).order_by(desc("count")).limit(10).all()

    return [
        JunctionCount(junction=str(row.address)[:30], incident_count=row.count)
        for row in query
    ]


# ── Peak Hours by Zone ────────────────────────────────────────────────────────

@router.get("/peak-hours", response_model=List[ZonePeakHour])
def peak_hours(db: Session = Depends(get_db)):
    """Return live zone stats."""
    
    query = db.query(
        Event.corridor,
        func.count(Event.id).label("count")
    ).filter(Event.status == "active").group_by(Event.corridor).order_by(desc("count")).limit(5).all()

    current_hour = datetime.now().hour
    return [
        ZonePeakHour(
            zone=row.corridor,
            peak_hour=current_hour,
            peak_hour_label=f"{current_hour:02d}:00 - {(current_hour + 1) % 24:02d}:00",
            incident_count=row.count,
        )
        for row in query
    ]


# ── Summary Stats ─────────────────────────────────────────────────────────────

@router.get("/summary", response_model=SummaryStats)
def summary_stats(db: Session = Depends(get_db)):
    """Global live metrics for the dashboard."""

    total = db.query(Event).filter(Event.status == "active").count()
    high_prio = db.query(Event).filter(Event.status == "active", Event.priority_high == 1).count()
    closures = db.query(Event).filter(Event.status == "active", Event.requires_road_closure == 1).count()

    avg_dur = db.query(func.avg(Event.duration_minutes)).filter(
        Event.status == "active", Event.duration_minutes.isnot(None)
    ).scalar()

    return SummaryStats(
        total_incidents=total,
        active_incidents=total,
        high_priority_active=high_prio,
        road_closures_active=closures,
        avg_resolution_hours=round(avg_dur / 60, 1) if avg_dur else None,
    )


@router.get("/cause-breakdown", response_model=List[CauseBreakdown])
def cause_breakdown(db: Session = Depends(get_db)):
    """Breakdown of active incidents by cause."""
    rows = db.query(
        Event.event_cause,
        func.count(Event.id).label("count"),
        func.avg(Event.duration_minutes).label("avg_dur"),
        func.avg(Event.priority_high).label("pct_high"),
    ).filter(Event.status == "active").group_by(Event.event_cause).order_by(desc("count")).all()

    return [
        CauseBreakdown(
            event_cause=(row.event_cause or "unknown").replace("_", " ").title(),
            incident_count=row.count,
            avg_duration_min=round(row.avg_dur, 1) if row.avg_dur else None,
            pct_high_priority=round((row.pct_high or 0) * 100, 1),
        )
        for row in rows
    ]


@router.get("/pothole-escalation")
def pothole_escalation(db: Session = Depends(get_db)):
    """Flag long-running pothole incidents that need BBMP escalation."""
    rows = db.query(Event).filter(
        Event.event_cause.in_(["pot_holes", "pothole", "pot_holes"]),
        Event.status == "active",
    ).all()

    escalations = []
    for e in rows:
        dur = e.duration_minutes or 0
        if dur > 1440 or (e.duration_bucket == "Slow"):
            escalations.append({
                "id": e.id,
                "address": e.address,
                "corridor": e.corridor,
                "duration_minutes": dur,
                "duration_days": round(dur / 1440, 1) if dur else None,
                "priority": e.priority,
                "action": "Escalate to BBMP maintenance",
            })

    return {
        "total_potholes_active": len(rows),
        "needs_escalation": len(escalations),
        "escalations": escalations[:20],
        "message": f"{len(escalations)} pothole(s) exceed traffic-police jurisdiction — BBMP escalation recommended.",
    }

@router.get("/metadata/corridors", response_model=List[str])
def get_corridors(db: Session = Depends(get_db)):
    """Fetch distinct live corridors from the database to populate dropdowns."""
    corridors = db.query(Event.corridor).filter(Event.corridor != None, Event.corridor != "").distinct().all()
    # corridors is a list of tuples like [('Tumkur Road',), ('Mysore Road',)]
    result = [c[0] for c in corridors]
    # Ensure Non-corridor is always an option
    if "Non-corridor" not in result:
        result.append("Non-corridor")
    return sorted(result)
