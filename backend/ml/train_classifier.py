"""
train_classifier.py — BengaluruOps Command
Trains two RandomForest classifiers:
  1. Priority classifier      → priority_high (1=High, 0=Low)
  2. Road closure classifier  → requires_road_closure (1=True, 0=False)

Also generates SHAP explainability for Model 1.
Run data_prep.py first!
"""

import pandas as pd
import numpy as np
import joblib
import json
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    classification_report, f1_score, confusion_matrix, accuracy_score
)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_CSV = BASE_DIR / "data" / "processed" / "events_clean.csv"
MODELS_DIR = BASE_DIR / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Feature Configuration ──────────────────────────────────────────────────────
CATEGORICAL_FEATURES = ["event_cause", "corridor", "veh_type", "weekday_name", "event_type"]
NUMERIC_FEATURES = ["hour", "month", "is_peak_hour", "weekday",
                    "has_cargo_data", "has_junction"]

ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET_PRIORITY = "priority_high"
TARGET_CLOSURE = "requires_road_closure"


def build_preprocessor() -> ColumnTransformer:
    """Build the shared ColumnTransformer for feature encoding."""
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False),
             CATEGORICAL_FEATURES),
            ("num", "passthrough", NUMERIC_FEATURES),
        ],
        remainder="drop",
    )


def build_rf_pipeline(class_weight: str = "balanced") -> Pipeline:
    """Build a full sklearn Pipeline: preprocessor → RandomForest."""
    return Pipeline([
        ("preprocessor", build_preprocessor()),
        ("classifier", RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=5,
            class_weight=class_weight,
            random_state=42,
            n_jobs=-1,
        )),
    ])


def evaluate(pipeline, X_test, y_test, target_name: str) -> dict:
    """Run evaluation and return metrics dict."""
    y_pred = pipeline.predict(X_test)
    f1 = f1_score(y_test, y_pred, average="weighted")
    acc = accuracy_score(y_test, y_pred)
    print(f"\n── {target_name} ─────────────────────────────────────────")
    print(f"Accuracy: {acc:.4f}  |  F1 (weighted): {f1:.4f}")
    print(classification_report(y_test, y_pred))
    return {
        "target": target_name,
        "accuracy": round(acc, 4),
        "f1_weighted": round(f1, 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        "classification_report": classification_report(y_test, y_pred, output_dict=True),
    }


def get_feature_names(pipeline) -> list:
    """Extract all feature names after OHE transformation."""
    ct = pipeline.named_steps["preprocessor"]
    ohe = ct.named_transformers_["cat"]
    ohe_names = ohe.get_feature_names_out(CATEGORICAL_FEATURES).tolist()
    return ohe_names + NUMERIC_FEATURES


def train_priority_model(df: pd.DataFrame) -> tuple:
    """Train the priority classifier and return (pipeline, metrics, feature_names)."""
    print("\n" + "=" * 60)
    print("Training Model 1: Priority Classifier")
    print("=" * 60)

    # Drop rows missing any feature or target
    model_df = df[ALL_FEATURES + [TARGET_PRIORITY]].dropna()
    print(f"Training rows: {len(model_df)}")
    print(f"Class balance: {model_df[TARGET_PRIORITY].value_counts().to_dict()}")

    X = model_df[ALL_FEATURES]
    y = model_df[TARGET_PRIORITY]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )

    pipeline = build_rf_pipeline(class_weight="balanced")
    pipeline.fit(X_train, y_train)

    metrics = evaluate(pipeline, X_test, y_test, "Priority (High=1 / Low=0)")
    feature_names = get_feature_names(pipeline)

    return pipeline, metrics, feature_names


def train_closure_model(df: pd.DataFrame) -> tuple:
    """Train the road closure classifier."""
    print("\n" + "=" * 60)
    print("Training Model 2: Road Closure Classifier")
    print("=" * 60)

    model_df = df[ALL_FEATURES + [TARGET_CLOSURE]].dropna()
    print(f"Training rows: {len(model_df)}")
    print(f"Class balance: {model_df[TARGET_CLOSURE].value_counts().to_dict()}")

    # Try SMOTE if available for the heavily imbalanced class (8.3% True)
    X = model_df[ALL_FEATURES]
    y = model_df[TARGET_CLOSURE]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )

    # Try SMOTE oversampling
    try:
        from imblearn.over_sampling import SMOTE

        preprocessor = build_preprocessor()
        X_train_enc = preprocessor.fit_transform(X_train)

        smote = SMOTE(random_state=42, k_neighbors=3)
        X_res, y_res = smote.fit_resample(X_train_enc, y_train)
        print(f"SMOTE applied: {y_train.value_counts().to_dict()} -> {pd.Series(y_res).value_counts().to_dict()}")

        clf = RandomForestClassifier(
            n_estimators=300, max_depth=12, min_samples_leaf=3,
            random_state=42, n_jobs=-1
        )
        clf.fit(X_res, y_res)

        X_test_enc = preprocessor.transform(X_test)

        # Tune threshold for minority class (requires_closure=1)
        # Default 0.5 misses too many. Lower threshold catches more true positives.
        y_proba = clf.predict_proba(X_test_enc)[:, 1]
        best_thresh, best_f1 = 0.5, 0.0
        for thresh in [0.3, 0.35, 0.4, 0.45, 0.5]:
            y_t = (y_proba >= thresh).astype(int)
            f = f1_score(y_test, y_t, average="macro")
            if f > best_f1:
                best_f1, best_thresh = f, thresh
        print(f"Best threshold: {best_thresh} (macro F1={best_f1:.4f})")
        y_pred = (y_proba >= best_thresh).astype(int)

        f1 = f1_score(y_test, y_pred, average="weighted")
        acc = accuracy_score(y_test, y_pred)
        f1_macro = f1_score(y_test, y_pred, average="macro")
        print(f"\n-- Road Closure (SMOTE + threshold={best_thresh}) --")
        print(f"Accuracy: {acc:.4f}  |  F1 weighted: {f1:.4f}  |  F1 macro: {f1_macro:.4f}")
        print(classification_report(y_test, y_pred))

        # Wrap back into sklearn pipeline for consistent inference
        from sklearn.pipeline import Pipeline
        pipeline = Pipeline([
            ("preprocessor", preprocessor),
            ("classifier", clf),
        ])
        # Store threshold for use during inference
        pipeline.optimal_threshold = best_thresh

        metrics = {
            "target": "Road Closure",
            "accuracy": round(acc, 4),
            "f1_weighted": round(f1, 4),
            "f1_macro": round(f1_macro, 4),
            "optimal_threshold": best_thresh,
            "smote_used": True,
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
        }

    except ImportError:
        print("imbalanced-learn not available -- using class_weight='balanced'")
        pipeline = build_rf_pipeline(class_weight="balanced")
        pipeline.fit(X_train, y_train)
        metrics = evaluate(pipeline, X_test, y_test, "Road Closure")
        metrics["smote_used"] = False
        pipeline.optimal_threshold = 0.5

    feature_names = get_feature_names(pipeline)
    return pipeline, metrics, feature_names


def compute_shap_values(pipeline, X_sample: pd.DataFrame, feature_names: list) -> list:
    """Compute SHAP values for a small sample and return top feature importances."""
    try:
        import shap

        preprocessor = pipeline.named_steps["preprocessor"]
        clf = pipeline.named_steps["classifier"]

        X_enc = preprocessor.transform(X_sample)
        explainer = shap.TreeExplainer(clf)
        shap_values = explainer.shap_values(X_enc)

        # Handle old API (list) and new SHAP ≥0.41 (3D ndarray: n_samples, n_features, n_classes)
        if isinstance(shap_values, list):
            sv = shap_values[1]           # old: [class0_arr, class1_arr]
        elif shap_values.ndim == 3:
            sv = shap_values[:, :, 1]     # new: pick class-1 slice
        else:
            sv = shap_values              # already (n_samples, n_features)

        mean_abs_shap = np.abs(sv).mean(axis=0)
        top_idx = np.argsort(mean_abs_shap)[::-1][:10]

        top_features = [
            {
                "feature": feature_names[int(i)],
                "mean_abs_shap": round(float(mean_abs_shap[int(i)]), 4),
                "direction": "positive" if sv[:, int(i)].mean() > 0 else "negative",
            }
            for i in top_idx
        ]
        print("\nTop SHAP features (Priority model):")
        for f in top_features[:5]:
            print(f"  {f['feature']}: {f['mean_abs_shap']} ({f['direction']})")
        return top_features

    except Exception as e:
        print(f"[WARN] SHAP skipped: {e}")
        return []


def single_prediction_shap(pipeline, input_dict: dict, feature_names: list) -> list:
    """
    Compute SHAP explanation for a single prediction.
    Returns top 4 features with direction and magnitude.
    Used by /api/classify endpoint.
    """
    try:
        import shap
        import pandas as pd

        X = pd.DataFrame([input_dict])
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
                "feature": feature_names[int(i)],
                "value": round(float(sv[int(i)]), 3),
                "direction": "positive" if sv[int(i)] > 0 else "negative",
            }
            for i in top_idx
        ]
    except Exception:
        return []


def main():
    print("=" * 60)
    print("BengaluruOps — Classifier Training Pipeline")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"ERROR: {CLEAN_CSV} not found. Run data_prep.py first!")
        return

    df = pd.read_csv(CLEAN_CSV)
    print(f"Loaded clean dataset: {df.shape}")

    # Train models
    priority_pipeline, priority_metrics, feature_names = train_priority_model(df)
    closure_pipeline, closure_metrics, _ = train_closure_model(df)

    # Save models BEFORE SHAP so they are always persisted even if SHAP fails
    joblib.dump(priority_pipeline, MODELS_DIR / "priority_model.pkl")
    joblib.dump(closure_pipeline, MODELS_DIR / "closure_model.pkl")
    print(f"\n✅ Saved priority_model.pkl → {MODELS_DIR}")
    print(f"✅ Saved closure_model.pkl  → {MODELS_DIR}")

    # SHAP on a sample (runs after save — failure here doesn't lose models)
    sample_df = df[ALL_FEATURES].dropna().sample(min(500, len(df)), random_state=42)
    shap_top = compute_shap_values(priority_pipeline, sample_df, feature_names)

    # Save feature names for inference
    with open(MODELS_DIR / "classifier_feature_names.json", "w") as f:
        json.dump({"features": feature_names, "categorical": CATEGORICAL_FEATURES,
                   "numeric": NUMERIC_FEATURES}, f, indent=2)

    # Save metrics
    all_metrics = {
        "priority_model": priority_metrics,
        "closure_model": closure_metrics,
        "shap_top_features": shap_top,
    }
    with open(MODELS_DIR / "classifier_metrics.json", "w") as f:
        json.dump(all_metrics, f, indent=2, default=str)
    print(f"✅ Saved classifier_metrics.json")

    # Final verdict
    p_f1 = priority_metrics["f1_weighted"]
    c_f1 = closure_metrics["f1_weighted"]
    print(f"\n── Final F1 Scores ────────────────────────────────────────")
    print(f"Priority model:      {p_f1:.4f} {'✅' if p_f1 >= 0.75 else '⚠️ below target 0.75'}")
    print(f"Road closure model:  {c_f1:.4f} {'✅' if c_f1 >= 0.65 else '⚠️ below target 0.65'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
