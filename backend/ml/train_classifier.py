"""
train_classifier.py — BengaluruOps Command
Trains RandomForest and XGBoost classifiers, picks the best:
  1. Priority classifier      → priority_high (1=High, 0=Low) (No corridor feature!)
  2. Road closure classifier  → requires_road_closure (1=True, 0=False) (Uses SMOTE)
"""

import pandas as pd
import numpy as np
import joblib
import json
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
# Use imblearn pipeline to support SMOTE
from imblearn.pipeline import Pipeline
from imblearn.over_sampling import SMOTE
from sklearn.metrics import (
    classification_report, f1_score, confusion_matrix, accuracy_score
)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_CSV = BASE_DIR / "data" / "processed" / "events_clean.csv"
MODELS_DIR = BASE_DIR / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Feature Configuration ──────────────────────────────────────────────────────
# Priority includes 'corridor' per user request
PRIORITY_CATEGORICAL = ["event_cause", "corridor", "veh_type", "weekday_name", "event_type"]
CLOSURE_CATEGORICAL = ["event_cause", "corridor", "veh_type", "weekday_name", "event_type"]
NUMERIC_FEATURES = ["hour", "month", "is_peak_hour", "weekday", "has_cargo_data", "has_junction"]

PRIORITY_FEATURES = PRIORITY_CATEGORICAL + NUMERIC_FEATURES
CLOSURE_FEATURES = CLOSURE_CATEGORICAL + NUMERIC_FEATURES

TARGET_PRIORITY = "priority_high"
TARGET_CLOSURE = "requires_road_closure"

def build_preprocessor(cat_features) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_features),
            ("num", "passthrough", NUMERIC_FEATURES),
        ],
        remainder="drop",
    )

def train_and_evaluate_both(X_train, y_train, X_test, y_test, cat_features, use_smote=False, scale_weight=1.0):
    preprocessor = build_preprocessor(cat_features)
    
    # 1. RF Pipeline
    rf_steps = [("preprocessor", preprocessor)]
    if use_smote:
        rf_steps.append(("smote", SMOTE(random_state=42)))
    rf_steps.append(("classifier", RandomForestClassifier(random_state=42, n_jobs=-1, class_weight="balanced" if scale_weight > 1.5 and not use_smote else None)))
    rf_pipeline = Pipeline(rf_steps)
    
    rf_param_grid = {
        "classifier__n_estimators": [100, 200, 300],
        "classifier__max_depth": [5, 10, 14, None],
    }
    
    print("\nTraining RandomForest...")
    rf_search = RandomizedSearchCV(rf_pipeline, rf_param_grid, n_iter=5, cv=3, scoring="f1_macro", n_jobs=-1, random_state=42)
    rf_search.fit(X_train, y_train)
    rf_best = rf_search.best_estimator_
    rf_pred = rf_best.predict(X_test)
    rf_f1 = f1_score(y_test, rf_pred, average="macro")
    print(f"RandomForest Macro F1: {rf_f1:.4f}")

    # 2. XGB Pipeline
    xgb_steps = [("preprocessor", preprocessor)]
    if use_smote:
        xgb_steps.append(("smote", SMOTE(random_state=42)))
    xgb_steps.append(("classifier", XGBClassifier(use_label_encoder=False, eval_metric="logloss", random_state=42, n_jobs=-1, scale_pos_weight=scale_weight if not use_smote else 1.0)))
    xgb_pipeline = Pipeline(xgb_steps)
    
    xgb_param_grid = {
        "classifier__n_estimators": [100, 200, 300],
        "classifier__max_depth": [3, 5, 7],
        "classifier__learning_rate": [0.05, 0.1],
    }
    
    print("Training XGBoost...")
    xgb_search = RandomizedSearchCV(xgb_pipeline, xgb_param_grid, n_iter=5, cv=3, scoring="f1_macro", n_jobs=-1, random_state=42)
    xgb_search.fit(X_train, y_train)
    xgb_best = xgb_search.best_estimator_
    xgb_pred = xgb_best.predict(X_test)
    xgb_f1 = f1_score(y_test, xgb_pred, average="macro")
    print(f"XGBoost Macro F1: {xgb_f1:.4f}")

    # Pick winner
    if rf_f1 >= xgb_f1:
        print("Winner: RandomForest!")
        return rf_best, rf_f1, "RandomForest"
    else:
        print("Winner: XGBoost!")
        return xgb_best, xgb_f1, "XGBoost"

def get_feature_names(pipeline, cat_features) -> list:
    ct = pipeline.named_steps["preprocessor"]
    ohe = ct.named_transformers_["cat"]
    ohe_names = ohe.get_feature_names_out(cat_features).tolist()
    return ohe_names + NUMERIC_FEATURES

def train_priority_model(df: pd.DataFrame) -> tuple:
    print("\n" + "=" * 60)
    print("Training Model 1: Priority Classifier (No corridor leak!)")
    print("=" * 60)

    model_df = df[PRIORITY_FEATURES + [TARGET_PRIORITY]].dropna()
    X = model_df[PRIORITY_FEATURES]
    y = model_df[TARGET_PRIORITY]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, stratify=y, random_state=42)

    neg_count = (y_train == 0).sum()
    pos_count = (y_train == 1).sum()
    scale_weight = neg_count / pos_count if pos_count > 0 else 1.0

    best_pipeline, best_f1, model_type = train_and_evaluate_both(X_train, y_train, X_test, y_test, PRIORITY_CATEGORICAL, use_smote=False, scale_weight=scale_weight)

    y_pred = best_pipeline.predict(X_test)
    print("\nPriority Test Results:")
    print(classification_report(y_test, y_pred))
    
    feature_names = get_feature_names(best_pipeline, PRIORITY_CATEGORICAL)
    return best_pipeline, feature_names, model_type

def train_closure_model(df: pd.DataFrame) -> tuple:
    print("\n" + "=" * 60)
    print("Training Model 2: Road Closure Classifier (With SMOTE)")
    print("=" * 60)

    model_df = df[CLOSURE_FEATURES + [TARGET_CLOSURE]].dropna()
    X = model_df[CLOSURE_FEATURES]
    y = model_df[TARGET_CLOSURE]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, stratify=y, random_state=42)

    neg_count = (y_train == 0).sum()
    pos_count = (y_train == 1).sum()
    scale_weight = (neg_count / pos_count) if pos_count > 0 else 1.0

    best_pipeline, best_f1, model_type = train_and_evaluate_both(X_train, y_train, X_test, y_test, CLOSURE_CATEGORICAL, use_smote=False, scale_weight=scale_weight)

    y_pred = best_pipeline.predict(X_test)
    print("\nClosure Test Results:")
    print(classification_report(y_test, y_pred))
    
    feature_names = get_feature_names(best_pipeline, CLOSURE_CATEGORICAL)
    return best_pipeline, feature_names, model_type

def compute_shap_values(pipeline, X_sample: pd.DataFrame, feature_names: list) -> list:
    try:
        import shap
        preprocessor = pipeline.named_steps["preprocessor"]
        clf = pipeline.named_steps["classifier"]
        X_enc = preprocessor.transform(X_sample)
        explainer = shap.TreeExplainer(clf)
        shap_values = explainer.shap_values(X_enc)
        if isinstance(shap_values, list):
            sv = shap_values[1]
        elif shap_values.ndim == 3:
            sv = shap_values[:, :, 1]
        else:
            sv = shap_values
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
        return top_features
    except Exception as e:
        print(f"[WARN] SHAP skipped: {e}")
        return []

def main():
    print("=" * 60)
    print("BengaluruOps — Classifier Training Pipeline")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"ERROR: {CLEAN_CSV} not found. Run data_prep.py first!")
        return

    df = pd.read_csv(CLEAN_CSV)
    priority_pipeline, priority_features, p_type = train_priority_model(df)
    closure_pipeline, closure_features, c_type = train_closure_model(df)

    # Save format required by predict.py (dict with preprocessor and model)
    joblib.dump({"preprocessor": priority_pipeline.named_steps["preprocessor"], "model": priority_pipeline.named_steps["classifier"], "model_type": p_type}, MODELS_DIR / "priority_model.pkl")
    joblib.dump({"preprocessor": closure_pipeline.named_steps["preprocessor"], "model": closure_pipeline.named_steps["classifier"], "model_type": c_type}, MODELS_DIR / "closure_model.pkl")
    
    print(f"\n✅ Saved priority_model.pkl ({p_type})")
    print(f"✅ Saved closure_model.pkl ({c_type})")

if __name__ == "__main__":
    main()
