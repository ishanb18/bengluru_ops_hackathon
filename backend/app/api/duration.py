"""
duration.py — POST /api/duration
Event Duration Predictor: returns Fast/Medium/Slow bucket + estimated minutes
"""

from fastapi import APIRouter
from ..models.schemas import DurationRequest, DurationResponse
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from ml.predict import predict_duration

router = APIRouter(prefix="/duration", tags=["Duration Predictor"])


@router.post("", response_model=DurationResponse)
def predict_event_duration(request: DurationRequest):
    """
    Predict how long an event will take to resolve.
    Returns duration bucket (Fast/Medium/Slow), estimated minutes, and confidence.
    """
    data = request.dict()
    result = predict_duration(data)
    return DurationResponse(**result)
