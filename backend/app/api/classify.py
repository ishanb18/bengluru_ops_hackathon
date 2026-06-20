"""
classify.py — POST /api/classify
Event Impact Classifier: predicts priority + road closure + SHAP explanation
"""

from fastapi import APIRouter
from ..models.schemas import ClassifyRequest, ClassifyResponse, ShapFeature
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from ml.predict import (
    predict_priority,
    predict_closure,
    get_shap_explanation,
)

router = APIRouter(prefix="/classify", tags=["AI Classifier"])


def _build_recommended_action(priority: str, requires_closure: bool,
                               corridor: str, veh_type: str) -> str:
    """Generate a human-readable action recommendation string."""
    parts = []

    # Officer dispatch
    if priority == "High":
        parts.append("Dispatch 6+ officers immediately")
    else:
        parts.append("Dispatch 2 officers")

    # Road closure
    if requires_closure:
        parts.append(f"deploy barricades on {corridor}")

    # Tow truck
    if veh_type in ("heavy_vehicle", "truck", "private_bus"):
        parts.append("alert BBMP for tow truck")

    # Diversion
    CORRIDOR_DIVERSIONS = {
        "Mysore Road": "Magadi Road",
        "Bellary Road 1": "Bellary Road 2",
        "Tumkur Road": "Magadi Road",
        "ORR East 1": "ORR East 2",
        "Hosur Road": "Bannerghata Road",
        "Old Madras Road": "KR Pura alternate",
    }
    if corridor in CORRIDOR_DIVERSIONS and requires_closure:
        parts.append(f"activate {CORRIDOR_DIVERSIONS[corridor]} diversion")

    return " · ".join(parts) if parts else "Monitor situation"


@router.post("", response_model=ClassifyResponse)
def classify_incident(request: ClassifyRequest):
    """
    Classify an incoming traffic event.
    Returns: priority, road closure prediction, confidence, SHAP explanation, action recommendation.
    """
    data = request.dict()

    # Run predictions
    priority_result = predict_priority(data)
    closure_result = predict_closure(data)

    # SHAP explanation
    shap_raw = get_shap_explanation(data, model_type="priority")
    shap_features = [
        ShapFeature(
            feature=s["feature"],
            value=s["value"],
            direction=s["direction"],
        )
        for s in shap_raw
    ]

    # Recommended action
    action = _build_recommended_action(
        priority=priority_result["priority"],
        requires_closure=closure_result["requires_closure"],
        corridor=data.get("corridor", "Non-corridor"),
        veh_type=data.get("veh_type", "N/A"),
    )

    # Run LLM verification
    from app.services.llm_verifier import verify_incident_via_llm
    corridor_str = data.get("corridor", "Bengaluru")
    cause_str = data.get("event_cause", "traffic incident")
    llm_result = verify_incident_via_llm(cause_str, corridor_str)

    return ClassifyResponse(
        priority=priority_result["priority"],
        priority_high=priority_result["priority_high"],
        confidence=priority_result["confidence"],
        probabilities=priority_result["probabilities"],
        requires_closure=closure_result["requires_closure"],
        closure_confidence=closure_result["confidence"],
        shap_explanation=shap_features,
        recommended_action=action,
        llm_verification=llm_result
    )
