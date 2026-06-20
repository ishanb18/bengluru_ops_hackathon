"""
data_prep.py — BengaluruOps Command
Cleans the raw Astram event CSV and produces events_clean.csv
Run this FIRST before training any models.
"""

import pandas as pd
import numpy as np
import os
import json
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_CSV = BASE_DIR / "data" / "raw" / "Astram_event_data_anonymized.csv"
OUT_CSV = BASE_DIR / "data" / "processed" / "events_clean.csv"
QUALITY_REPORT = BASE_DIR / "data" / "processed" / "data_quality_report.json"

# Also support running from hackathon root (looks for the original filename)
ORIGINAL_CSV = BASE_DIR.parent / "Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv"


def load_raw() -> pd.DataFrame:
    if RAW_CSV.exists():
        print(f"Loading from {RAW_CSV}")
        return pd.read_csv(RAW_CSV)
    elif ORIGINAL_CSV.exists():
        print(f"Loading from original location: {ORIGINAL_CSV}")
        return pd.read_csv(ORIGINAL_CSV)
    else:
        raise FileNotFoundError(
            f"Could not find raw CSV at {RAW_CSV} or {ORIGINAL_CSV}.\n"
            "Copy the CSV to backend/data/raw/Astram_event_data_anonymized.csv"
        )


def parse_datetimes(df: pd.DataFrame) -> pd.DataFrame:
    """Parse all datetime columns with mixed formats."""
    dt_cols = ["start_datetime", "end_datetime", "created_date",
               "modified_datetime", "closed_datetime", "resolved_datetime"]
    for col in dt_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format="mixed", utc=True, errors="coerce")
    return df


def derive_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive hour, weekday, month, is_peak_hour from start_datetime."""
    df["hour"] = df["start_datetime"].dt.hour
    df["weekday"] = df["start_datetime"].dt.dayofweek      # 0=Mon … 6=Sun
    df["weekday_name"] = df["start_datetime"].dt.day_name()
    df["month"] = df["start_datetime"].dt.month
    df["month_name"] = df["start_datetime"].dt.month_name()

    # Bengaluru peak hours: early morning (5-7), morning rush (8-11), evening (17-21)
    PEAK_HOURS = {5, 6, 7, 8, 9, 10, 11, 17, 18, 19, 20, 21}
    df["is_peak_hour"] = df["hour"].isin(PEAK_HOURS).astype(int)
    return df


def compute_duration(df: pd.DataFrame) -> pd.DataFrame:
    """Compute duration_minutes from start → closed datetime."""
    df["duration_minutes"] = (
        (df["closed_datetime"] - df["start_datetime"])
        .dt.total_seconds()
        .div(60)
    )
    # Negative or zero durations are invalid — set to NaN
    df.loc[df["duration_minutes"] <= 0, "duration_minutes"] = np.nan

    # Create duration bucket (Fast / Medium / Slow)
    def bucket(mins):
        if pd.isna(mins):
            return np.nan
        if mins <= 90:
            return "Fast"
        elif mins <= 1440:   # 24 hours
            return "Medium"
        else:
            return "Slow"

    df["duration_bucket"] = df["duration_minutes"].apply(bucket)
    return df


def clean_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize and bucket rare categorical values."""

    # ── event_cause ─────────────────────────────────────────────────────────
    # Normalize casing / duplicates
    df["event_cause"] = df["event_cause"].str.lower().str.strip()
    # Merge Debris/debris, test_demo, Fog into 'other'
    CAUSE_REMAP = {
        "debris": "others",
        "test_demo": "others",
        "fog / low visibility": "others",
    }
    df["event_cause"] = df["event_cause"].replace(CAUSE_REMAP)
    # Keep top 12 causes, bucket the rest
    top_causes = df["event_cause"].value_counts().head(12).index.tolist()
    df["event_cause"] = df["event_cause"].where(df["event_cause"].isin(top_causes), "others")

    # ── priority ────────────────────────────────────────────────────────────
    df["priority_high"] = (df["priority"] == "High").astype(int)

    # ── requires_road_closure ───────────────────────────────────────────────
    df["requires_road_closure"] = df["requires_road_closure"].astype(bool).astype(int)

    # ── corridor ────────────────────────────────────────────────────────────
    df["corridor"] = df["corridor"].fillna("Non-corridor").str.strip()

    # ── zone ────────────────────────────────────────────────────────────────
    df["zone"] = df["zone"].fillna("Unknown").str.strip()

    # ── veh_type ────────────────────────────────────────────────────────────
    df["veh_type"] = df["veh_type"].fillna("N/A").str.strip()
    # Keep top 10, bucket rare
    top_veh = df["veh_type"].value_counts().head(10).index.tolist()
    df["veh_type"] = df["veh_type"].where(df["veh_type"].isin(top_veh), "others")

    # ── event_type ──────────────────────────────────────────────────────────
    df["event_type"] = df["event_type"].fillna("unplanned").str.lower().str.strip()

    # ── junction ────────────────────────────────────────────────────────────
    df["junction"] = df["junction"].fillna("unmapped").str.strip()

    # ── status ──────────────────────────────────────────────────────────────
    df["status"] = df["status"].fillna("unknown").str.lower().str.strip()

    # ── authenticated ───────────────────────────────────────────────────────
    df["authenticated"] = df["authenticated"].fillna(False).astype(bool)

    return df


def drop_critical_nulls(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows missing core fields: lat/lon, event_cause, start_datetime."""
    before = len(df)
    df = df.dropna(subset=["latitude", "longitude", "event_cause", "start_datetime"])
    after = len(df)
    print(f"Dropped {before - after} rows with critical nulls. Remaining: {after}")
    return df


def add_feature_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add binary flags for presence of optional data."""
    df["has_cargo_data"] = df["cargo_material"].notna().astype(int)
    df["has_truck_age"] = df["age_of_truck"].notna().astype(int)
    df["has_junction"] = (df["junction"] != "unmapped").astype(int)
    df["is_authenticated"] = df["authenticated"].astype(int)
    return df


def select_final_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the columns needed for ML + analytics."""
    keep = [
        # Identifiers
        "id", "status", "authenticated",
        # Geo
        "latitude", "longitude",
        # Categorical features (ML)
        "event_type", "event_cause", "corridor", "zone", "veh_type",
        # Time features (ML)
        "start_datetime", "hour", "weekday", "weekday_name", "month", "month_name",
        "is_peak_hour",
        # Targets (ML)
        "priority", "priority_high", "requires_road_closure",
        # Duration
        "closed_datetime", "duration_minutes", "duration_bucket",
        # Extra info
        "junction", "police_station",
        # Special feature flags
        "has_cargo_data", "has_truck_age", "has_junction", "is_authenticated",
        # Truck breakdown specifics
        "cargo_material", "reason_breakdown", "age_of_truck",
        # For display
        "address",
    ]
    # Only keep cols that exist
    keep = [c for c in keep if c in df.columns]
    return df[keep].reset_index(drop=True)


def build_quality_report(df_raw: pd.DataFrame, df_clean: pd.DataFrame) -> dict:
    """Build a data quality report to save alongside the clean CSV."""
    return {
        "raw_rows": len(df_raw),
        "clean_rows": len(df_clean),
        "rows_dropped": len(df_raw) - len(df_clean),
        "null_counts_before": df_raw.isnull().sum().to_dict(),
        "null_counts_after": df_clean.isnull().sum().to_dict(),
        "class_balance_priority": df_clean["priority"].value_counts().to_dict(),
        "class_balance_closure": df_clean["requires_road_closure"].value_counts().to_dict(),
        "duration_bucket_dist": df_clean["duration_bucket"].value_counts(dropna=False).to_dict(),
        "event_cause_dist": df_clean["event_cause"].value_counts().to_dict(),
        "corridor_dist": df_clean["corridor"].value_counts().head(15).to_dict(),
    }


def main():
    print("=" * 60)
    print("BengaluruOps - Data Preparation Pipeline")
    print("=" * 60)

    # Load
    df = load_raw()
    print(f"Loaded {len(df)} rows × {len(df.columns)} columns")
    df_raw = df.copy()

    # Pipeline
    df = parse_datetimes(df)
    df = derive_time_features(df)
    df = compute_duration(df)
    df = clean_categoricals(df)
    df = drop_critical_nulls(df)
    df = add_feature_flags(df)
    df = select_final_columns(df)

    # Save
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"\n[OK] Saved clean dataset -> {OUT_CSV}")
    print(f"     Final shape: {df.shape}")

    # Quality report
    report = build_quality_report(df_raw, df)
    with open(QUALITY_REPORT, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"[OK] Saved quality report -> {QUALITY_REPORT}")

    # Quick summary
    print("\n-- Class Balance -------------------------------------")
    print(f"Priority:       {df['priority'].value_counts().to_dict()}")
    print(f"Road Closure:   {df['requires_road_closure'].value_counts().to_dict()}")
    print(f"Duration Bucket:{df['duration_bucket'].value_counts(dropna=False).to_dict()}")
    print(f"Event Cause:    {df['event_cause'].value_counts().head(8).to_dict()}")
    print("=" * 60)

    return df


if __name__ == "__main__":
    main()
