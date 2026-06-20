"""
train_duration.py — BengaluruOps Command
Trains two duration models:
  1. Duration Bucket Classifier  → Fast / Medium / Slow (3-class RF)
  2. Duration Regressor          → log1p(duration_minutes) → RF Regressor

Run data_prep.py first!
"""

import pandas as pd
import numpy as np
import joblib
import json
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, LabelEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    classification_report, f1_score, accuracy_score,
    mean_absolute_error, r2_score
)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_CSV = BASE_DIR / "data" / "processed" / "events_clean.csv"
MODELS_DIR = BASE_DIR / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Feature Configuration ──────────────────────────────────────────────────────
CATEGORICAL_FEATURES = ["event_cause", "corridor", "veh_type", "weekday_name", "event_type"]
NUMERIC_FEATURES = ["hour", "month", "is_peak_hour", "weekday",
                    "has_cargo_data"]

ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET_BUCKET = "duration_bucket"
TARGET_MINUTES = "duration_minutes"

BUCKET_ORDER = ["Fast", "Medium", "Slow"]


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False),
             CATEGORICAL_FEATURES),
            ("num", "passthrough", NUMERIC_FEATURES),
        ],
        remainder="drop",
    )


def train_bucket_classifier(df: pd.DataFrame) -> tuple:
    """Train 3-class duration bucket classifier."""
    print("\n" + "=" * 60)
    print("Training Model 3: Duration Bucket Classifier (Fast/Medium/Slow)")
    print("=" * 60)

    # Only rows with valid duration_bucket
    model_df = df[ALL_FEATURES + [TARGET_BUCKET]].dropna(
        subset=ALL_FEATURES + [TARGET_BUCKET]
    )
    print(f"Training rows: {len(model_df)}")
    print(f"Bucket distribution: {model_df[TARGET_BUCKET].value_counts().to_dict()}")

    X = model_df[ALL_FEATURES]
    y = model_df[TARGET_BUCKET]

    # Check for very rare classes (need >=2 for stratify)
    class_counts = y.value_counts()
    print(f"Class counts before split: {class_counts.to_dict()}")
    rare_classes = class_counts[class_counts < 2].index.tolist()
    if rare_classes:
        print(f"Merging rare classes {rare_classes} into 'Medium' for stable split")
        y = y.replace({cls: 'Medium' for cls in rare_classes})

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )

    pipeline = Pipeline([
        ("preprocessor", build_preprocessor()),
        ("classifier", RandomForestClassifier(
            n_estimators=300,
            max_depth=15,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )),
    ])
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    f1 = f1_score(y_test, y_pred, average="weighted")
    acc = accuracy_score(y_test, y_pred)

    print(f"\nAccuracy: {acc:.4f}  |  F1 (weighted): {f1:.4f}")
    print(classification_report(y_test, y_pred))

    metrics = {
        "target": "Duration Bucket",
        "accuracy": round(acc, 4),
        "f1_weighted": round(f1, 4),
        "bucket_distribution_train": y_train.value_counts().to_dict(),
        "classification_report": classification_report(y_test, y_pred, output_dict=True),
    }
    return pipeline, metrics


def train_duration_regressor(df: pd.DataFrame) -> tuple:
    """Train regression on log1p(duration_minutes), excluding extreme outliers (>10000 min)."""
    print("\n" + "=" * 60)
    print("Training Model 4: Duration Regressor (log-scale minutes)")
    print("=" * 60)

    # Filter: must have valid duration and be < 10000 min (~7 days)
    reg_df = df[ALL_FEATURES + [TARGET_MINUTES, TARGET_BUCKET]].dropna(
        subset=ALL_FEATURES + [TARGET_MINUTES]
    )
    reg_df = reg_df[reg_df[TARGET_MINUTES] < 10000]
    print(f"Training rows (after outlier removal): {len(reg_df)}")
    print(f"Duration range: {reg_df[TARGET_MINUTES].min():.1f} – {reg_df[TARGET_MINUTES].max():.1f} min")
    print(f"Duration median: {reg_df[TARGET_MINUTES].median():.1f} min")

    X = reg_df[ALL_FEATURES]
    y_raw = reg_df[TARGET_MINUTES]
    y = np.log1p(y_raw)  # log-transform for better regression

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )

    pipeline = Pipeline([
        ("preprocessor", build_preprocessor()),
        ("regressor", RandomForestRegressor(
            n_estimators=300,
            max_depth=15,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )),
    ])
    pipeline.fit(X_train, y_train)

    y_pred_log = pipeline.predict(X_test)
    y_pred_min = np.expm1(y_pred_log)   # back to minutes
    y_test_min = np.expm1(y_test)       # back to minutes

    mae = mean_absolute_error(y_test_min, y_pred_min)
    r2 = r2_score(y_test, y_pred_log)

    print(f"\nMAE: {mae:.1f} minutes  |  R² (log-scale): {r2:.4f}")
    print(f"Example predictions (minutes): {y_pred_min[:5].round(1).tolist()}")
    print(f"Actual values (minutes):       {y_test_min[:5].round(1).tolist()}")

    metrics = {
        "target": "Duration Minutes",
        "mae_minutes": round(mae, 1),
        "r2_log_scale": round(r2, 4),
        "training_rows": len(reg_df),
        "note": "Trained on log1p(duration_minutes), apply np.expm1() to predictions",
    }
    return pipeline, metrics


def main():
    print("=" * 60)
    print("BengaluruOps — Duration Model Training Pipeline")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"ERROR: {CLEAN_CSV} not found. Run data_prep.py first!")
        return

    df = pd.read_csv(CLEAN_CSV)
    # Restore numeric types
    df["priority_high"] = pd.to_numeric(df["priority_high"], errors="coerce")
    df["is_peak_hour"] = pd.to_numeric(df["is_peak_hour"], errors="coerce")
    df["has_cargo_data"] = pd.to_numeric(df["has_cargo_data"], errors="coerce")
    print(f"Loaded clean dataset: {df.shape}")

    # Train
    bucket_pipeline, bucket_metrics = train_bucket_classifier(df)
    reg_pipeline, reg_metrics = train_duration_regressor(df)

    # Save models
    joblib.dump(bucket_pipeline, MODELS_DIR / "duration_bucket_model.pkl")
    joblib.dump(reg_pipeline, MODELS_DIR / "duration_regression_model.pkl")
    print(f"\n✅ Saved duration_bucket_model.pkl    → {MODELS_DIR}")
    print(f"✅ Saved duration_regression_model.pkl → {MODELS_DIR}")

    # Save metrics
    all_metrics = {
        "bucket_classifier": bucket_metrics,
        "regression_model": reg_metrics,
    }
    with open(MODELS_DIR / "duration_metrics.json", "w") as f:
        json.dump(all_metrics, f, indent=2, default=str)
    print(f"✅ Saved duration_metrics.json")

    # Final verdict
    b_f1 = bucket_metrics["f1_weighted"]
    print(f"\n── Final Scores ────────────────────────────────────────────")
    print(f"Bucket F1:   {b_f1:.4f} {'✅' if b_f1 >= 0.70 else '⚠️ below target 0.70'}")
    print(f"Regressor MAE: {reg_metrics['mae_minutes']:.1f} minutes")
    print("=" * 60)


if __name__ == "__main__":
    main()
