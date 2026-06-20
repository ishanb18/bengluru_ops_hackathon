"""
db.py — BengaluruOps Command
SQLAlchemy ORM models + SQLite engine setup.
"""

from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime, Text,
    create_engine, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "bengaluru_ops.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)

# Speed up SQLite with WAL mode
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA cache_size=-65536")  # 64MB cache
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(20), index=True, default="unknown")
    authenticated = Column(Integer, default=0)  # 0/1

    # Geo
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(Text, nullable=True)

    # Categorical features (also ML inputs)
    event_type = Column(String(20), index=True, default="unplanned")
    event_cause = Column(String(50), index=True, nullable=False)
    corridor = Column(String(100), index=True, default="Non-corridor")
    zone = Column(String(50), index=True, default="Unknown")
    veh_type = Column(String(50), default="N/A")
    junction = Column(String(100), default="unmapped")
    police_station = Column(String(100), nullable=True)

    # Time
    start_datetime = Column(DateTime, nullable=True, index=True)
    closed_datetime = Column(DateTime, nullable=True)
    hour = Column(Integer, nullable=True)
    weekday = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    is_peak_hour = Column(Integer, default=0)  # 0/1

    # Targets / labels
    priority = Column(String(10), index=True, default="Low")
    priority_high = Column(Integer, default=0)
    requires_road_closure = Column(Integer, default=0)

    # Duration
    duration_minutes = Column(Float, nullable=True)
    duration_bucket = Column(String(10), nullable=True)

    # Feature flags
    has_cargo_data = Column(Integer, default=0)
    has_truck_age = Column(Integer, default=0)
    has_junction = Column(Integer, default=0)
    is_authenticated = Column(Integer, default=0)

    # Truck breakdown specifics
    cargo_material = Column(String(100), nullable=True)
    reason_breakdown = Column(String(100), nullable=True)
    age_of_truck = Column(Float, nullable=True)


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
