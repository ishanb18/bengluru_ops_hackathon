"""
scan.py — POST /api/scan
On-demand TomTom incident sync. Triggered by the "Refresh" button on the frontend.
Conserves free-tier API calls by only fetching when explicitly requested.
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.db import get_db
from app.services.tomtom import sync_tomtom_incidents
from app.services.traffic_collector import sync_traffic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scan", tags=["Live Scan"])


@router.post("")
def trigger_scan(db: Session = Depends(get_db)):
    """
    Manually trigger a TomTom incident sync and traffic flow sync.
    Returns the count of active incidents after the sync.
    """
    try:
        sync_tomtom_incidents(db)
        sync_traffic(db)

        from app.models.db import Event
        active_count = db.query(Event).filter(Event.status == "active").count()

        return {
            "status": "ok",
            "message": f"Live scan complete. {active_count} active incidents on map.",
            "active_incidents": active_count,
        }
    except Exception as e:
        logger.error(f"Manual scan failed: {e}")
        return {
            "status": "error",
            "message": f"Scan failed: {str(e)}",
            "active_incidents": 0,
        }
