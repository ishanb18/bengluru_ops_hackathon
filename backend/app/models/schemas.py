"""
schemas.py — BengaluruOps Command
Pydantic request/response schemas for all API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ── Shared / Base ──────────────────────────────────────────────────────────────

class EventBase(BaseModel):
    id: int
    status: str
    event_type: str
    event_cause: str
    corridor: str
    zone: str
    veh_type: str
    junction: Optional[str]
    police_station: Optional[str]
    latitude: float
    longitude: float
    address: Optional[str]
    priority: str
    priority_high: int
    requires_road_closure: int
    duration_minutes: Optional[float]
    duration_bucket: Optional[str]
    hour: Optional[int]
    weekday: Optional[int]
    month: Optional[int]
    is_peak_hour: Optional[bool]
    authenticated: bool
    start_datetime: Optional[str]
    closed_datetime: Optional[str]

    class Config:
        from_attributes = True


class EventListItem(BaseModel):
    id: int
    latitude: float
    longitude: float
    event_cause: str
    corridor: str
    zone: str
    priority: str
    requires_road_closure: int
    status: str
    duration_bucket: Optional[str]
    hour: Optional[int]
    authenticated: bool
    start_datetime: Optional[str]
    address: Optional[str]

    class Config:
        from_attributes = True


class PaginatedEvents(BaseModel):
    total: int
    page: int
    page_size: int
    events: List[EventListItem]


# ── Classify Request/Response ──────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    event_cause: str = Field(..., example="vehicle_breakdown")
    corridor: str = Field(default="Non-corridor", example="Tumkur Road")
    zone: str = Field(default="Unknown", example="North Zone 1")
    veh_type: str = Field(default="N/A", example="heavy_vehicle")
    hour: int = Field(default=9, ge=0, le=23, example=18)
    weekday: int = Field(default=1, ge=0, le=6, example=2)
    month: int = Field(default=6, ge=1, le=12, example=3)
    event_type: str = Field(default="unplanned", example="unplanned")
    has_cargo_data: int = Field(default=0, ge=0, le=1)
    has_junction: int = Field(default=0, ge=0, le=1)


class ShapFeature(BaseModel):
    feature: str
    value: float
    direction: str


class ClassifyResponse(BaseModel):
    priority: str
    priority_high: int
    confidence: float
    probabilities: Dict[str, float]
    requires_closure: bool
    closure_confidence: float
    shap_explanation: List[ShapFeature]
    recommended_action: str
    llm_verification: Optional[Dict[str, Any]] = None


# ── Duration Request/Response ──────────────────────────────────────────────────

class DurationRequest(BaseModel):
    event_cause: str = Field(..., example="vehicle_breakdown")
    corridor: str = Field(default="Non-corridor", example="Tumkur Road")
    zone: str = Field(default="Unknown")
    veh_type: str = Field(default="N/A")
    hour: int = Field(default=9, ge=0, le=23)
    weekday: int = Field(default=1, ge=0, le=6)
    month: int = Field(default=6, ge=1, le=12)
    event_type: str = Field(default="unplanned")
    priority_high: int = Field(default=0, ge=0, le=1)
    has_cargo_data: int = Field(default=0, ge=0, le=1)


class DurationResponse(BaseModel):
    bucket: str
    bucket_label: str
    confidence: float
    estimated_minutes: float
    estimated_hours: float
    bucket_probabilities: Dict[str, float]


# ── Manpower Request/Response ──────────────────────────────────────────────────

class ManpowerRequest(BaseModel):
    priority: str = Field(..., example="High")
    requires_closure: bool = Field(default=False)
    corridor: str = Field(default="Non-corridor")
    duration_bucket: str = Field(default="Medium", example="Medium")
    veh_type: str = Field(default="N/A")
    latitude: float = Field(default=12.9716)
    longitude: float = Field(default=77.5946)


class StationInfo(BaseModel):
    name: str
    distance_label: str
    estimated_response_min: int
    badge: str


class ManpowerResponse(BaseModel):
    officer_count: int
    barricade_count: int
    tow_truck_needed: bool
    bbmp_escalation: bool
    corridor_risk_score: float
    deployment_priority: str
    notes: List[str]
    nearest_stations: List[StationInfo]


# ── Diversion Response ────────────────────────────────────────────────────────

class AlternateRoute(BaseModel):
    name: str
    stress_score: float
    stress_level: str
    extra_minutes: int
    notes: str


class DiversionResponse(BaseModel):
    blocked_corridor: str
    alternates: List[AlternateRoute]
    message: str


# ── Analytics ─────────────────────────────────────────────────────────────────

class CorridorRiskItem(BaseModel):
    rank: int
    corridor: str
    risk_score: float
    risk_tier: str
    incident_count: int
    pct_high_priority: float
    pct_road_closures: float
    event_cause_top: str


class MonthlyTrend(BaseModel):
    month: str
    incident_count: int


class JunctionCount(BaseModel):
    junction: str
    incident_count: int


class ZonePeakHour(BaseModel):
    zone: str
    peak_hour: int
    peak_hour_label: str
    incident_count: int


class SummaryStats(BaseModel):
    total_incidents: int
    active_incidents: int
    high_priority_active: int
    road_closures_active: int
    avg_resolution_hours: Optional[float]


class CauseBreakdown(BaseModel):
    event_cause: str
    incident_count: int
    avg_duration_min: Optional[float] = None
    pct_high_priority: Optional[float] = None
