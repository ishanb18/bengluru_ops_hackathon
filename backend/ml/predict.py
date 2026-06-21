"""
predict.py — BengaluruOps Command
Shared inference helpers used by the FastAPI endpoints.
Loads all models once at startup and exposes prediction functions.
"""

import joblib
import json
import numpy as np
import pandas as pd
from pathlib import Path
from functools import lru_cache
import sys
from sklearn.pipeline import Pipeline

# ── Dynamic Model Registration for Uvicorn ──────────────────────────────────────
# Fixes joblib unpickling error since model was trained in __main__ context
class XGBLabelEncoderPipeline(Pipeline):
    def __init__(self, steps, le=None, *, memory=None, verbose=False):
        super().__init__(steps, memory=memory, verbose=verbose)
        self.le = le
    def predict(self, X, **predict_params):
        return self.le.inverse_transform(super().predict(X, **predict_params))
    def predict_proba(self, X, **predict_proba_params):
        return super().predict_proba(X, **predict_proba_params)
    @property
    def classes_(self):
        return self.le.classes_

sys.modules["__main__"].XGBLabelEncoderPipeline = XGBLabelEncoderPipeline

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "data" / "models"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

CATEGORICAL_FEATURES = ["event_cause", "corridor", "veh_type", "weekday_name", "event_type"]
NUMERIC_FEATURES = ["hour", "month", "is_peak_hour", "weekday",
                    "has_cargo_data", "has_junction"]
ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def _unwrap(obj):
    """
    Safely extract a ready-to-use sklearn Pipeline/estimator from joblib output.

    Priority order:
      1. If already a Pipeline/estimator (not a dict) → return as-is
      2. If dict → look for a value with named_steps (full sklearn Pipeline)
      3. If dict → reconstruct Pipeline from preprocessor + classifier parts
      4. If dict → return any value that has predict_proba / predict
    """
    if not isinstance(obj, dict):
        return obj

    # Priority 1: find a full sklearn Pipeline (has named_steps attribute)
    for v in obj.values():
        if hasattr(v, "named_steps"):
            return v

    # Priority 2: reconstruct Pipeline from separate preprocessor + classifier
    preprocessor = obj.get("preprocessor")
    label_encoder = obj.get("label_encoder")
    for key in ("pipeline", "model", "classifier", "clf", "estimator", "regressor"):
        if key in obj and (hasattr(obj[key], "predict_proba") or hasattr(obj[key], "predict")):
            clf = obj[key]
            if preprocessor is not None and hasattr(preprocessor, "transform"):
                if label_encoder is not None:
                    return XGBLabelEncoderPipeline([("preprocessor", preprocessor), ("classifier", clf)], le=label_encoder)
                from sklearn.pipeline import Pipeline as SKPipeline
                return SKPipeline([("preprocessor", preprocessor), ("classifier", clf)])
            return clf

    # Priority 3: any estimator in the dict values
    for v in obj.values():
        if hasattr(v, "predict_proba") or hasattr(v, "predict"):
            return v

    raise ValueError(f"Cannot extract estimator from dict keys: {list(obj.keys())}")


# ── Model Loading (cached — only loaded once at startup) ──────────────────────

@lru_cache(maxsize=None)
def load_priority_model():
    path = MODELS_DIR / "priority_model.pkl"
    if not path.exists():
        raise RuntimeError(f"priority_model.pkl not found at {path}. Run train_classifier.py first!")
    return _unwrap(joblib.load(path))



@lru_cache(maxsize=None)
def load_closure_model():
    path = MODELS_DIR / "closure_model.pkl"
    if not path.exists():
        raise RuntimeError(f"closure_model.pkl not found at {path}. Run train_classifier.py first!")
    return _unwrap(joblib.load(path))


@lru_cache(maxsize=None)
def load_duration_bucket_model():
    path = MODELS_DIR / "duration_bucket_model.pkl"
    if not path.exists():
        raise RuntimeError(f"duration_bucket_model.pkl not found at {path}. Run train_duration.py first!")
    return _unwrap(joblib.load(path))


@lru_cache(maxsize=None)
def load_duration_regression_model():
    path = MODELS_DIR / "duration_regression_model.pkl"
    if not path.exists():
        raise RuntimeError(f"duration_regression_model.pkl not found at {path}. Run train_duration.py first!")
    return _unwrap(joblib.load(path))


@lru_cache(maxsize=None)
def load_feature_names() -> list:
    path = MODELS_DIR / "classifier_feature_names.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f).get("features", [])


@lru_cache(maxsize=None)
def load_corridor_risk() -> dict:
    path = PROCESSED_DIR / "corridor_risk_scores.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


# ── Helper: build input DataFrame from request dict ───────────────────────────

def build_input_df(data: dict | list) -> pd.DataFrame:
    """
    Convert API request dict (or list of dicts) to a DataFrame suitable for model inference.
    Handles hour → weekday, is_peak_hour derivation.
    """
    if isinstance(data, dict):
        data = [data]
        
    PEAK_HOURS = {5, 6, 7, 8, 9, 10, 11, 17, 18, 19, 20, 21}
    WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    cause_mapping = {
        "Jam": "congestion",
        "Stationary Traffic": "congestion",
        "Queueing Traffic": "congestion",
        "abandoned_vehicle": "vehicle_breakdown",
        "oil_spill": "accident",
        "pedestrian_incident": "accident",
        "road_closed": "construction", # proxy for closure
        "lane_closed": "construction",
        "pot_holes": "pot_holes"
    }

    rows = []
    for d in data:
        hour = int(d.get("hour", 9))
        weekday = int(d.get("weekday", 1))  # 0=Mon
        cause = d.get("event_cause", "vehicle_breakdown")
        mapped_cause = cause_mapping.get(cause, cause)

        rows.append({
            "event_cause": mapped_cause,
            "corridor": d.get("corridor", "Non-corridor"),
            "zone": d.get("zone", "Unknown"),
            "veh_type": d.get("veh_type", "N/A"),
            "weekday_name": WEEKDAY_NAMES[weekday % 7],
            "event_type": d.get("event_type", "unplanned"),
            "hour": hour,
            "month": int(d.get("month", 6)),
            "is_peak_hour": int(hour in PEAK_HOURS),
            "weekday": weekday,
            "has_cargo_data": int(d.get("has_cargo_data", 0)),
            "priority_high": int(d.get("priority_high", 0)),
            "has_junction": int(d.get("has_junction", 0)),
        })
        
    return pd.DataFrame(rows)

# ── Prediction Functions ───────────────────────────────────────────────────────

def predict_priority(data: dict) -> dict:
    """Return priority prediction with confidence."""
    pipeline = load_priority_model()
    X = build_input_df(data)
    proba = pipeline.predict_proba(X)[0]
    classes = pipeline.classes_
    pred_class = classes[np.argmax(proba)]
    confidence = float(np.max(proba))
    
    # Soften extreme confidences for presentation
    confidence = min(0.97, confidence) if confidence > 0.97 else confidence

    return {
        "priority": "High" if pred_class == 1 else "Low",
        "priority_high": int(pred_class),
        "confidence": round(confidence, 3),
        "probabilities": {
            "Low": round(float(proba[0]), 3),
            "High": round(float(proba[1]), 3),
        },
    }

def predict_priority_batch(data_list: list) -> list[dict]:
    """Batch predict priority to prevent timeouts on large datasets."""
    if not data_list: return []
    pipeline = load_priority_model()
    X = build_input_df(data_list)
    proba_batch = pipeline.predict_proba(X)
    classes = pipeline.classes_
    
    results = []
    for proba in proba_batch:
        pred_class = classes[np.argmax(proba)]
        confidence = float(np.max(proba))
        confidence = min(0.97, confidence) if confidence > 0.97 else confidence
        results.append({
            "priority": "High" if pred_class == 1 else "Low",
            "priority_high": int(pred_class),
            "confidence": round(confidence, 3),
            "probabilities": {
                "Low": round(float(proba[0]), 3),
                "High": round(float(proba[1]), 3),
            },
        })
    return results


def predict_closure(data: dict) -> dict:
    """Return road closure prediction with confidence using ML blended with domain rules."""
    pipeline = load_closure_model()
    X = build_input_df(data)
    proba = pipeline.predict_proba(X)[0]
    
    # ML Prediction (0.50 threshold since we used class_weight='balanced')
    pred_class = 1 if proba[1] >= 0.50 else 0
    confidence = float(proba[1]) if pred_class == 1 else float(proba[0])

    # Domain Knowledge Overrides (Safety Net for extreme events)
    raw_cause = data.get("event_cause", "")
    veh_type = data.get("veh_type", "")
    
    if raw_cause in ["road_closed", "lane_closed", "tree_fall", "water_logging"]:
        pred_class = 1
        confidence = max(0.95, confidence)
    elif raw_cause == "accident" and veh_type in ["heavy_vehicle", "bus"]:
        pred_class = 1
        confidence = max(0.85, confidence)

    return {
        "requires_closure": bool(pred_class),
        "confidence": round(confidence, 3),
        "probabilities": {
            "No": round(float(proba[0]), 3),
            "Yes": round(float(proba[1]), 3),
        },
    }

def predict_closure_batch(data_list: list) -> list[dict]:
    if not data_list: return []
    pipeline = load_closure_model()
    X = build_input_df(data_list)
    proba_batch = pipeline.predict_proba(X)
    
    results = []
    for i, proba in enumerate(proba_batch):
        pred_class = 1 if proba[1] >= 0.50 else 0
        confidence = float(proba[1]) if pred_class == 1 else float(proba[0])
        
        raw_cause = data_list[i].get("event_cause", "")
        veh_type = data_list[i].get("veh_type", "")
        
        if raw_cause in ["road_closed", "lane_closed", "tree_fall", "water_logging"]:
            pred_class = 1
            confidence = max(0.95, confidence)
        elif raw_cause == "accident" and veh_type in ["heavy_vehicle", "bus"]:
            pred_class = 1
            confidence = max(0.85, confidence)

        results.append({
            "requires_closure": bool(pred_class),
            "confidence": round(confidence, 3),
            "probabilities": {
                "No": round(float(proba[0]), 3),
                "Yes": round(float(proba[1]), 3),
            },
        })
    return results


def predict_duration(data: dict) -> dict:
    """Return duration bucket + estimated minutes."""
    bucket_model = load_duration_bucket_model()
    reg_model = load_duration_regression_model()

    X = build_input_df(data)

    # Bucket prediction
    bucket_proba = bucket_model.predict_proba(X)[0]
    bucket_classes = bucket_model.classes_
    pred_bucket = bucket_classes[np.argmax(bucket_proba)]
    bucket_confidence = float(np.max(bucket_proba))

    # Regression prediction (in original minutes)
    log_pred = reg_model.predict(X)[0]
    estimated_minutes = float(np.expm1(log_pred))
    estimated_minutes = max(1, round(estimated_minutes, 1))

    BUCKET_LABELS = {
        "Fast": "≤ 90 minutes",
        "Medium": "1.5 hours – 24 hours",
        "Slow": "> 24 hours",
    }

    return {
        "bucket": pred_bucket,
        "bucket_label": BUCKET_LABELS.get(pred_bucket, pred_bucket),
        "confidence": round(bucket_confidence, 3),
        "estimated_minutes": estimated_minutes,
        "estimated_hours": round(estimated_minutes / 60, 1),
        "bucket_probabilities": {
            cls: round(float(p), 3)
            for cls, p in zip(bucket_classes, bucket_proba)
        },
    }

def predict_duration_batch(data_list: list) -> list[dict]:
    if not data_list: return []
    bucket_model = load_duration_bucket_model()
    reg_model = load_duration_regression_model()

    X = build_input_df(data_list)

    bucket_proba_batch = bucket_model.predict_proba(X)
    bucket_classes = bucket_model.classes_
    
    log_pred_batch = reg_model.predict(X)
    
    BUCKET_LABELS = {
        "Fast": "≤ 90 minutes",
        "Medium": "1.5 hours – 24 hours",
        "Slow": "> 24 hours",
    }

    results = []
    for i, bucket_proba in enumerate(bucket_proba_batch):
        pred_bucket = bucket_classes[np.argmax(bucket_proba)]
        bucket_confidence = float(np.max(bucket_proba))
        
        log_pred = log_pred_batch[i]
        estimated_minutes = float(np.expm1(log_pred))
        estimated_minutes = max(1, round(estimated_minutes, 1))
        
        results.append({
            "bucket": pred_bucket,
            "bucket_label": BUCKET_LABELS.get(pred_bucket, pred_bucket),
            "confidence": round(bucket_confidence, 3),
            "estimated_minutes": estimated_minutes,
            "estimated_hours": round(estimated_minutes / 60, 1),
            "bucket_probabilities": {
                cls: round(float(p), 3)
                for cls, p in zip(bucket_classes, bucket_proba)
            },
        })
    return results


def get_shap_explanation(data: dict, model_type: str = "priority") -> list:
    """
    Get SHAP values for a single prediction.
    Returns top 4 features with direction and magnitude.
    """
    try:
        import shap
        pipeline = load_priority_model() if model_type == "priority" else load_closure_model()
        feature_names = load_feature_names()
        if not feature_names:
            return []

        X = build_input_df(data)
        preprocessor = pipeline.named_steps["preprocessor"]
        clf = pipeline.named_steps["classifier"]

        X_enc = preprocessor.transform(X)
        explainer = shap.TreeExplainer(clf)
        shap_values = explainer.shap_values(X_enc)

        # Handle old API (list) and new SHAP ≥0.41 (3D ndarray: n_samples, n_features, n_classes)
        if isinstance(shap_values, list):
            sv = shap_values[1][0]        # old: class1 array, first sample
        elif shap_values.ndim == 3:
            sv = shap_values[0, :, 1]     # new: first sample, all features, class1
        else:
            sv = shap_values[0]           # already (n_samples, n_features)

        top_idx = np.argsort(np.abs(sv))[::-1][:4]
        return [
            {
                "feature": feature_names[int(i)] if int(i) < len(feature_names) else f"feature_{i}",
                "value": round(float(sv[int(i)]), 3),
                "direction": "+" if sv[int(i)] > 0 else "-",
            }
            for i in top_idx
        ]
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"SHAP failed: {e}")
        return [{"feature": "shap_unavailable", "value": 0.0, "direction": "+",
                 "error": str(e)}]


def get_manpower_recommendation(priority: str, requires_closure: bool,
                                 corridor: str, duration_bucket: str,
                                 veh_type: str) -> dict:
    """
    AI-driven manpower recommendation engine.
    Uses Llama-3 to dynamically compute deployment counts based on context.
    Falls back to basic rules if the LLM fails.
    """
    bbmp_escalation = False
    
    # Load precomputed risk data for station recommendations
    risk_data = load_corridor_risk()
    corridor_risk_list = risk_data.get("corridor_risk", [])
    corridor_rank = next(
        (r["risk_score"] for r in corridor_risk_list if r["corridor"] == corridor),
        50
    )

    try:
        from groq import Groq
        import os, json
        from app.core.config import settings
        
        use_openrouter = (
            settings.GROQ_API_KEY.startswith("sk-or-")
            or "openrouter" in (settings.GROQ_API_KEY or "").lower()
        )
        client = Groq(
            api_key=settings.GROQ_API_KEY,
            base_url="https://openrouter.ai/api/v1" if use_openrouter else None,
        )
        
        prompt = f"""
You are an expert AI Traffic Operations Dispatcher for the Bengaluru Police.
Analyze the following incident and recommend exact field resource allocations.
Context:
- Priority Level: {priority}
- Requires Road Closure: {requires_closure}
- Location: {corridor}
- Estimated Duration: {duration_bucket}
- Vehicle Involved: {veh_type}

Output your recommendation as a STRICT JSON object with these EXACT keys (no markdown blocks, no extra text):
{{
    "officer_count": (integer between 1 and 15),
    "barricade_count": (integer between 0 and 10),
    "tow_truck_needed": (boolean true or false),
    "notes": ["short note 1", "short note 2"]
}}
"""
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b" if use_openrouter else "llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=150,
            response_format={"type": "json_object"}
        )
        
        response_text = completion.choices[0].message.content
        result = json.loads(response_text)
        
        return {
            "officer_count": int(result.get("officer_count", 2)),
            "barricade_count": int(result.get("barricade_count", 1)),
            "tow_truck_needed": bool(result.get("tow_truck_needed", False)),
            "bbmp_escalation": False,
            "corridor_risk_score": corridor_rank,
            "deployment_priority": "Immediate" if priority == "High" else "Scheduled",
            "notes": result.get("notes", ["Dynamic LLM deployment triggered."]),
        }
    except Exception as e:
        print(f"LLM Manpower allocation failed, falling back to rules: {e}")
        # Rule-based fallback
        base_officers = 2
        if priority == "High": base_officers += 3
        if requires_closure: base_officers += 2
        if veh_type in ("heavy_vehicle", "truck", "private_bus", "bmtc_bus", "ksrtc_bus"): base_officers += 1
        if duration_bucket == "Slow": base_officers += 1

        barricades = 3 if requires_closure else (2 if priority == "High" else 1)
        tow_truck = veh_type in ("heavy_vehicle", "truck", "private_bus") or (veh_type == "bmtc_bus" and priority == "High")

        recommendation = {
            "officer_count": base_officers,
            "barricade_count": barricades,
            "tow_truck_needed": tow_truck,
            "bbmp_escalation": False,
            "corridor_risk_score": corridor_rank,
            "deployment_priority": "Immediate" if priority == "High" else "Scheduled",
            "notes": [],
        }

        if priority == "High" and requires_closure: recommendation["notes"].append("⚠️ High priority + road closure: deploy within 10 min")
        if tow_truck: recommendation["notes"].append("🚚 Heavy vehicle detected: coordinate with BBMP tow team")
        if duration_bucket == "Slow": recommendation["notes"].append("⏱ Long-duration event: arrange shift rotation")

        return recommendation
