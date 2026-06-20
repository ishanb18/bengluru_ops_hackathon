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

    query = db.query(
        Event.corridor,
        func.count(Event.id).label("incident_count"),
        func.sum(Event.priority_high).label("high_prio_count"),
        func.sum(Event.requires_road_closure).label("closure_count")
    ).filter(
        Event.status == "active",
        Event.corridor != "Non-corridor"
    ).group_by(Event.corridor).order_by(desc("incident_count")).limit(20)

    rows = query.all()
    if not rows:
        return []

    # Raw score per corridor
    raw_scores = []
    for row in rows:
        count = row.incident_count or 1
        score = (count * 1.0) + ((row.high_prio_count or 0) * 2.0) + ((row.closure_count or 0) * 3.0)
        raw_scores.append(score)

    max_score = max(raw_scores) if raw_scores else 1

    items = []
    for rank, (row, raw) in enumerate(zip(rows, raw_scores), 1):
        count = row.incident_count or 1
        # Normalize to 0–100
        score = round((raw / max_score) * 100, 1)
        pct_high = round(((row.high_prio_count or 0) / count) * 100, 1)
        pct_closure = round(((row.closure_count or 0) / count) * 100, 1)

        if score > 70: risk_tier = "High"
        elif score > 35: risk_tier = "Medium"
        else: risk_tier = "Low"

        items.append(CorridorRiskItem(
            rank=rank,
            corridor=row.corridor,
            risk_score=score,
            risk_tier=risk_tier,
            incident_count=count,
            pct_high_priority=pct_high,
            pct_road_closures=pct_closure,
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
    
    def format_hour(h: int | None) -> str:
        if h is None: return "Unknown"
        if h == 0: return "12 AM"
        if h < 12: return f"{h} AM"
        if h == 12: return "12 PM"
        return f"{h-12} PM"
    
    return [
        MonthlyTrend(
            month=format_hour(row.hour), 
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
    """Return the actual peak hour per corridor from historical data."""

    # For each corridor, find the hour with the most incidents (from full history)
    from sqlalchemy import text
    rows = db.execute(text("""
        SELECT corridor, hour, COUNT(*) as cnt
        FROM events
        WHERE corridor IS NOT NULL AND corridor != '' AND corridor != 'Non-corridor'
        GROUP BY corridor, hour
        ORDER BY corridor, cnt DESC
    """)).fetchall()

    # Keep only the top hour per corridor
    seen = {}
    for row in rows:
        if row[0] not in seen:
            seen[row[0]] = (row[1], row[2])  # (peak_hour, count)

    # Sort by count descending, take top 5
    top5 = sorted(seen.items(), key=lambda x: x[1][1], reverse=True)[:5]

    result = []
    for corridor, (hour, count) in top5:
        result.append(ZonePeakHour(
            zone=corridor,
            peak_hour=hour,
            peak_hour_label=f"{hour:02d}:00 – {(hour + 1) % 24:02d}:00",
            incident_count=count,
        ))
    return result


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
