"""
train_duration.py — BengaluruOps Command
Trains two duration models by racing RandomForest vs XGBoost:
  1. Duration Bucket Classifier  → Fast / Medium / Slow
  2. Duration Regressor          → log1p(duration_minutes)

Run data_prep.py first!
"""

import pandas as pd
import numpy as np
import joblib
import json
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from xgboost import XGBClassifier, XGBRegressor
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.preprocessing import OneHotEncoder, LabelEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    classification_report, f1_score, accuracy_score,
    mean_absolute_error, r2_score
)

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

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_CSV = BASE_DIR / "data" / "processed" / "events_clean.csv"
MODELS_DIR = BASE_DIR / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Feature Configuration ──────────────────────────────────────────────────────
CATEGORICAL_FEATURES = ["event_cause", "corridor", "veh_type", "weekday_name", "event_type"]
NUMERIC_FEATURES = ["hour", "month", "is_peak_hour", "weekday", "has_cargo_data"]

ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET_BUCKET = "duration_bucket"
TARGET_MINUTES = "duration_minutes"

BUCKET_ORDER = ["Fast", "Medium", "Slow"]


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
            ("num", "passthrough", NUMERIC_FEATURES),
        ],
        remainder="drop",
    )

def train_bucket_classifier(df: pd.DataFrame) -> tuple:
    """Train 3-class duration bucket classifier (Race RF vs XGB)."""
    print("\n" + "=" * 60)
    print("Training Model 3: Duration Bucket Classifier (Fast/Medium/Slow)")
    print("=" * 60)

    model_df = df[ALL_FEATURES + [TARGET_BUCKET]].dropna(subset=ALL_FEATURES + [TARGET_BUCKET])
    X = model_df[ALL_FEATURES]
    y = model_df[TARGET_BUCKET]

    class_counts = y.value_counts()
    rare_classes = class_counts[class_counts < 2].index.tolist()
    if rare_classes:
        y = y.replace({cls: 'Medium' for cls in rare_classes})

    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    
    X_train, X_test, y_train, y_test = train_test_split(X, y_enc, test_size=0.20, stratify=y_enc, random_state=42)

    preprocessor = build_preprocessor()

    # 1. RandomForest
    rf_pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", RandomForestClassifier(random_state=42, n_jobs=-1, class_weight="balanced"))
    ])
    rf_param_grid = {
        "classifier__n_estimators": [100, 200, 300],
        "classifier__max_depth": [5, 10, 14, None],
    }
    print("Training RandomForest Bucket Classifier...")
    rf_search = RandomizedSearchCV(rf_pipeline, rf_param_grid, n_iter=5, cv=3, scoring="f1_weighted", n_jobs=-1, random_state=42)
    rf_search.fit(X_train, y_train)
    rf_f1 = f1_score(y_test, rf_search.best_estimator_.predict(X_test), average="weighted")
    print(f"RandomForest Weighted F1: {rf_f1:.4f}")

    # 2. XGBoost
    xgb_pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", XGBClassifier(use_label_encoder=False, eval_metric="mlogloss", random_state=42, n_jobs=-1))
    ])
    xgb_param_grid = {
        "classifier__n_estimators": [100, 200, 300],
        "classifier__max_depth": [3, 5, 7],
        "classifier__learning_rate": [0.01, 0.05, 0.1],
    }
    print("Training XGBoost Bucket Classifier...")
    xgb_search = RandomizedSearchCV(xgb_pipeline, xgb_param_grid, n_iter=5, cv=3, scoring="f1_weighted", n_jobs=-1, random_state=42)
    xgb_search.fit(X_train, y_train)
    xgb_f1 = f1_score(y_test, xgb_search.best_estimator_.predict(X_test), average="weighted")
    print(f"XGBoost Weighted F1: {xgb_f1:.4f}")

    if rf_f1 >= xgb_f1:
        print("Winner: RandomForest!")
        best_pipeline = rf_search.best_estimator_
        model_type = "RandomForest"
    else:
        print("Winner: XGBoost!")
        best_pipeline = xgb_search.best_estimator_
        model_type = "XGBoost"

    final_pipeline = XGBLabelEncoderPipeline(best_pipeline.steps, le=le)
    y_test_labels = le.inverse_transform(y_test)
    y_pred_metrics = final_pipeline.predict(X_test)
    
    f1 = f1_score(y_test_labels, y_pred_metrics, average="weighted")
    acc = accuracy_score(y_test_labels, y_pred_metrics)
    print(f"\nAccuracy: {acc:.4f}  |  F1 (weighted): {f1:.4f}")
    print(classification_report(y_test_labels, y_pred_metrics))

    metrics = {
        "target": "Duration Bucket",
        "accuracy": round(acc, 4),
        "f1_weighted": round(f1, 4),
        "bucket_distribution_train": pd.Series(y_train).value_counts().to_dict(),
        "classification_report": classification_report(y_test_labels, y_pred_metrics, output_dict=True),
    }
    return final_pipeline, metrics, model_type


def train_duration_regressor(df: pd.DataFrame) -> tuple:
    """Train regression on log1p(duration_minutes) (Race RF vs XGB)."""
    print("\n" + "=" * 60)
    print("Training Model 4: Duration Regressor (log-scale minutes)")
    print("=" * 60)

    reg_df = df[ALL_FEATURES + [TARGET_MINUTES, TARGET_BUCKET]].dropna(subset=ALL_FEATURES + [TARGET_MINUTES])
    reg_df = reg_df[reg_df[TARGET_MINUTES] < 10000]
    
    X = reg_df[ALL_FEATURES]
    y_raw = reg_df[TARGET_MINUTES]
    y = np.log1p(y_raw)  # log-transform for better regression

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)
    preprocessor = build_preprocessor()

    # 1. RandomForest
    rf_pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", RandomForestRegressor(random_state=42, n_jobs=-1))
    ])
    rf_param_grid = {
        "regressor__n_estimators": [100, 200, 300],
        "regressor__max_depth": [5, 10, 14, None],
    }
    print("Training RandomForest Regressor...")
    rf_search = RandomizedSearchCV(rf_pipeline, rf_param_grid, n_iter=5, cv=3, scoring="neg_mean_absolute_error", n_jobs=-1, random_state=42)
    rf_search.fit(X_train, y_train)
    rf_mae = mean_absolute_error(np.expm1(y_test), np.expm1(rf_search.best_estimator_.predict(X_test)))
    print(f"RandomForest MAE (minutes): {rf_mae:.2f}")

    # 2. XGBoost
    xgb_pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", XGBRegressor(random_state=42, n_jobs=-1))
    ])
    xgb_param_grid = {
        "regressor__n_estimators": [100, 200, 300],
        "regressor__max_depth": [3, 5, 7],
        "regressor__learning_rate": [0.01, 0.05, 0.1],
    }
    print("Training XGBoost Regressor...")
    xgb_search = RandomizedSearchCV(xgb_pipeline, xgb_param_grid, n_iter=5, cv=3, scoring="neg_mean_absolute_error", n_jobs=-1, random_state=42)
    xgb_search.fit(X_train, y_train)
    xgb_mae = mean_absolute_error(np.expm1(y_test), np.expm1(xgb_search.best_estimator_.predict(X_test)))
    print(f"XGBoost MAE (minutes): {xgb_mae:.2f}")

    if rf_mae <= xgb_mae:
        print("Winner: RandomForest!")
        best_reg_pipeline = rf_search.best_estimator_
        model_type = "RandomForest"
    else:
        print("Winner: XGBoost!")
        best_reg_pipeline = xgb_search.best_estimator_
        model_type = "XGBoost"

    y_pred_log = best_reg_pipeline.predict(X_test)
    y_pred_min = np.expm1(y_pred_log)
    y_test_min = np.expm1(y_test)

    mae = mean_absolute_error(y_test_min, y_pred_min)
    r2 = r2_score(y_test, y_pred_log)

    print(f"\nFinal Test MAE: {mae:.2f} minutes")
    print(f"Final Test R2 (log scale): {r2:.4f}")

    metrics = {
        "target": "Duration Minutes",
        "mae_minutes": round(mae, 2),
        "r2_score_log": round(r2, 4),
    }
    return best_reg_pipeline, metrics, model_type


def main():
    print("=" * 60)
    print("BengaluruOps — Duration Training Pipeline")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"ERROR: {CLEAN_CSV} not found. Run data_prep.py first!")
        return

    df = pd.read_csv(CLEAN_CSV)
    print(f"Loaded clean dataset: {df.shape}")

    bucket_pipeline, bucket_metrics, b_type = train_bucket_classifier(df)
    reg_pipeline, reg_metrics, r_type = train_duration_regressor(df)

    # Save
    joblib.dump({
        "preprocessor": bucket_pipeline.named_steps["preprocessor"],
        "model": bucket_pipeline.named_steps["classifier"],
        "label_encoder": bucket_pipeline.le,
        "model_type": b_type
    }, MODELS_DIR / "duration_bucket_model.pkl")

    joblib.dump({
        "preprocessor": reg_pipeline.named_steps["preprocessor"],
        "model": reg_pipeline.named_steps["regressor"],
        "model_type": r_type
    }, MODELS_DIR / "duration_regressor.pkl")

    print(f"\n✅ Saved duration_bucket_model.pkl ({b_type})")
    print(f"✅ Saved duration_regressor.pkl ({r_type})")

if __name__ == "__main__":
    main()
