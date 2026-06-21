"""
main.py — BengaluruOps 2.0
FastAPI application entry point.
Startup: creates DB tables, seeds historical data, loads ML models,
and starts three background collectors (TomTom incidents, TomTom flow, OpenWeather).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os, sys, logging

# Add backend root to path for ml.predict imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.api import incidents, classify, duration, manpower, diversion, analytics, scan, planned_events
from app.api import traffic as traffic_router
from app.models.db import create_tables, SessionLocal
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bengaluru_ops")

# ── App Initialization ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "BengaluruOps 2.0 — Real-time traffic intelligence for Bengaluru. "
        "Live congestion monitoring, AI prediction, weather integration, and diversion routing."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(incidents.router, prefix="/api")
app.include_router(classify.router, prefix="/api")
app.include_router(duration.router, prefix="/api")
app.include_router(manpower.router, prefix="/api")
app.include_router(diversion.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(traffic_router.router, prefix="/api")  # 2.0: live traffic + weather
app.include_router(scan.router, prefix="/api")
app.include_router(planned_events.router, prefix="/api")

# Track background tasks so we can cancel them cleanly on shutdown
_background_tasks: list = []


# ── Startup ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    logger.info("BengaluruOps Command starting...")

    # 1. Hybrid Database: Initialize tables, seed historical data, and accept live TomTom stream.
    from app.models.db import create_tables
    create_tables()
    _seed_database()
    logger.info("[OK] SQLite Database Hybrid Architecture initialized.")

    # 2. Pre-load ML models into cache (warm up)
    try:
        from ml.predict import (
            load_priority_model, load_closure_model,
            load_duration_bucket_model, load_duration_regression_model,
            load_corridor_risk,
        )
        load_priority_model()
        load_closure_model()
        load_duration_bucket_model()
        load_duration_regression_model()
        load_corridor_risk()
        logger.info("[OK] ML models loaded and cached")
    except Exception as e:
        logger.warning(f"[WARN] ML models not loaded: {e}")
        logger.warning("Run train_classifier.py and train_duration.py first!")

    logger.info("API ready at http://localhost:8000")
    logger.info("Docs at http://localhost:8000/docs")

    # 3. Start background collector tasks (Weather + Traffic only; TomTom incidents are on-demand via /api/scan)
    import asyncio
    from app.services.weather_collector import sync_weather
    from app.services.traffic_collector import sync_traffic

    # Shared latest weather context (updated by weather poller, read by traffic poller)
    _weather_ctx: dict = {}

    async def weather_poller():
        """Polls OpenWeather API every 15 minutes. Runs immediately on startup."""
        while True:
            db = SessionLocal()
            try:
                result = await asyncio.to_thread(sync_weather, db)
                if result:
                    _weather_ctx.update(result)
                    logger.info(f"[Weather] Updated: {result.get('condition')} {result.get('temperature_c')}C")
            except Exception as e:
                logger.error(f"Weather polling error: {e}")
            finally:
                db.close()
            await asyncio.sleep(900)  # 15 minutes

    async def traffic_poller():
        """Polls TomTom Flow API for corridor speeds every 2 hours. Runs immediately on startup."""
        await asyncio.sleep(1)  # brief wait so weather runs first and populates _weather_ctx
        while True:
            db = SessionLocal()
            try:
                await asyncio.to_thread(sync_traffic, db, _weather_ctx or None)
                logger.info("[Traffic] Corridor congestion snapshots updated.")
            except Exception as e:
                logger.error(f"Traffic polling error: {e}")
            finally:
                db.close()
            await asyncio.sleep(7200)  # 2 hours

    _background_tasks.append(asyncio.create_task(weather_poller()))
    _background_tasks.append(asyncio.create_task(traffic_poller()))
    logger.info("[OK] Background collectors active: Weather (15min), Traffic Flow (5min). TomTom Incidents: on-demand via /api/scan")


@app.on_event("shutdown")
async def shutdown_event():
    """Cancel all background pollers cleanly to prevent exit-code-1 crashes."""
    import asyncio
    for task in _background_tasks:
        if not task.done():
            task.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)
    logger.info("[OK] BengaluruOps 2.0 background tasks stopped cleanly.")


def _seed_database():
    """
    Load events_clean.csv into SQLite using pandas to_sql.
    This is bulletproof for NaN/NaT — no manual type conversion needed.
    """
    import pandas as pd
    from pathlib import Path
    from sqlalchemy import create_engine, inspect

    BASE_DIR = Path(__file__).resolve().parent.parent
    CLEAN_CSV = BASE_DIR / "data" / "processed" / "events_clean.csv"
    DB_PATH = BASE_DIR / "data" / "bengaluru_ops.db"

    if not CLEAN_CSV.exists():
        logger.error(f"events_clean.csv not found. Run: python ml/data_prep.py")
        return

    # Check if already seeded
    db_engine = create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False}
    )
    insp = inspect(db_engine)
    if insp.has_table("events"):
        with db_engine.connect() as conn:
            count = conn.execute(__import__("sqlalchemy").text("SELECT COUNT(*) FROM events")).scalar()
            if count > 8000:
                logger.info(f"[OK] Database already seeded with historical data ({count} events)")
                return

    logger.info("Database empty — seeding from CSV...")
    df = pd.read_csv(CLEAN_CSV)
    logger.info(f"Loaded {len(df)} rows from CSV")

    # ── Integer PK (original id col is strings like 'FKID000000') ────────────
    if "id" in df.columns:
        df = df.drop(columns=["id"])
    df.insert(0, "id", range(1, len(df) + 1))

    # ── Datetime: parse → convert to naive (SQLite has no tz support) ─────────
    for col in ["start_datetime", "closed_datetime"]:
        if col in df.columns:
            dt = pd.to_datetime(df[col], format="mixed", utc=True, errors="coerce")
            df[col] = dt.dt.tz_convert(None)  # strip tz → naive datetime

    # ── Integer columns: fill NaN with 0 ─────────────────────────────────────
    int_cols = ["hour", "weekday", "month", "is_peak_hour",
                "priority_high", "requires_road_closure",
                "has_cargo_data", "has_truck_age", "has_junction", "is_authenticated"]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # ── String columns: fill NaN with sensible defaults ───────────────────────
    str_defaults = {
        "status": "unknown", "event_type": "unplanned", "event_cause": "others",
        "corridor": "Non-corridor", "zone": "Unknown", "veh_type": "N/A",
        "junction": "unmapped", "priority": "Low", "address": "",
        "police_station": "", "cargo_material": "", "reason_breakdown": "",
        "duration_bucket": "",
    }
    for col, default in str_defaults.items():
        if col in df.columns:
            df[col] = df[col].fillna(default).astype(str)
            df[col] = df[col].replace("nan", default).replace("None", default)

    # ── Select columns for the events table ───────────────────────────────────
    keep_cols = [
        "status", "authenticated", "latitude", "longitude", "address",
        "event_type", "event_cause", "corridor", "zone", "veh_type",
        "junction", "police_station", "start_datetime", "closed_datetime",
        "hour", "weekday", "month", "is_peak_hour", "priority",
        "priority_high", "requires_road_closure", "duration_minutes",
        "duration_bucket", "has_cargo_data", "has_truck_age",
        "has_junction", "is_authenticated", "cargo_material",
        "reason_breakdown", "age_of_truck",
    ]
    df_db = df[[c for c in keep_cols if c in df.columns]].copy()

    # ── Write to SQLite using the WAL-enabled SQLAlchemy engine ──────────────
    from app.models.db import engine as sa_engine
    with sa_engine.begin() as conn:
        df_db.to_sql("events", conn, if_exists="append", index=False, chunksize=500)
    logger.info(f"[OK] Database seeded with {len(df_db)} events")



# ── Health Check ───────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "endpoints": [
            "GET  /api/incidents",
            "GET  /api/incidents/{id}",
            "GET  /api/incidents/summary",
            "GET  /api/incidents/timeline",
            "POST /api/classify",
            "POST /api/duration",
            "POST /api/manpower",
            "GET  /api/diversion/{corridor}",
            "GET  /api/analytics/corridor-risk",
            "GET  /api/analytics/monthly-trend",
            "GET  /api/analytics/top-junctions",
            "GET  /api/analytics/peak-hours",
            "GET  /api/analytics/pothole-escalation",
            "POST /api/analytics/pothole-escalation/escalate",
            "GET  /api/analytics/cause-breakdown",
            "GET  /api/analytics/summary",
            "GET  /api/analytics/metadata/zones",
        ],
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}
