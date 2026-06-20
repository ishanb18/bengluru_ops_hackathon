"""
corridor_risk.py — BengaluruOps Command
Computes a risk score for each Bengaluru corridor using a weighted formula.
No ML — pure analytics. Run once, save as JSON, serve from analytics API.

Formula:
  risk_score = 0.4 * norm(incident_count)
             + 0.3 * norm(pct_high_priority)
             + 0.2 * norm(pct_road_closures)
             + 0.1 * norm(avg_duration_hours)
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_CSV = BASE_DIR / "data" / "processed" / "events_clean.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "corridor_risk_scores.json"


def normalize(series: pd.Series) -> pd.Series:
    """Min-max normalize a series to [0, 1]. Handle zero range gracefully."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - mn) / (mx - mn)


def compute_corridor_risk(df: pd.DataFrame) -> pd.DataFrame:
    """Build per-corridor risk scores."""
    # Exclude 'Non-corridor' rows from ranking (keep for analytics but flag separately)
    corridor_df = df.copy()

    g = corridor_df.groupby("corridor")

    agg = pd.DataFrame({
        "incident_count": g["id"].count(),
        "pct_high_priority": g["priority_high"].mean() * 100,
        "pct_road_closures": g["requires_road_closure"].mean() * 100,
        "avg_duration_hours": g["duration_minutes"].mean() / 60,
        "event_cause_top": g["event_cause"].agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else "unknown"),
    }).reset_index()

    # Normalize each component
    agg["n_incidents"] = normalize(agg["incident_count"])
    agg["n_priority"] = normalize(agg["pct_high_priority"])
    agg["n_closure"] = normalize(agg["pct_road_closures"])
    agg["n_duration"] = normalize(agg["avg_duration_hours"].fillna(0))

    # Composite score
    agg["risk_score"] = (
        0.4 * agg["n_incidents"] +
        0.3 * agg["n_priority"] +
        0.2 * agg["n_closure"] +
        0.1 * agg["n_duration"]
    )
    # Scale to 0–100
    agg["risk_score"] = (agg["risk_score"] * 100).round(1)

    # Risk tier
    def risk_tier(score):
        if score >= 70:
            return "Critical"
        elif score >= 45:
            return "High"
        elif score >= 25:
            return "Medium"
        else:
            return "Low"

    agg["risk_tier"] = agg["risk_score"].apply(risk_tier)
    agg = agg.sort_values("risk_score", ascending=False).reset_index(drop=True)
    agg["rank"] = agg.index + 1

    return agg


def compute_peak_hours_by_zone(df: pd.DataFrame) -> dict:
    """Return the peak hour (highest incident count) per zone."""
    zone_hour = df.groupby(["zone", "hour"])["id"].count().reset_index()
    zone_hour.columns = ["zone", "hour", "count"]
    peak = zone_hour.loc[zone_hour.groupby("zone")["count"].idxmax()][["zone", "hour", "count"]]
    result = {}
    for _, row in peak.iterrows():
        h = int(row["hour"])
        result[row["zone"]] = {
            "peak_hour": h,
            "peak_hour_label": f"{h:02d}:00 – {(h+2)%24:02d}:00",
            "incident_count": int(row["count"]),
        }
    return result


def compute_top_junctions(df: pd.DataFrame, n: int = 10) -> list:
    """Return top N junctions by incident count (excluding 'unmapped')."""
    junc_df = df[df["junction"] != "unmapped"]
    counts = junc_df.groupby("junction")["id"].count().sort_values(ascending=False).head(n)
    return [{"junction": j, "incident_count": int(c)} for j, c in counts.items()]


def compute_monthly_trend(df: pd.DataFrame) -> list:
    """Return monthly incident counts."""
    df["year_month"] = pd.to_datetime(
        df["start_datetime"], format="mixed", utc=True, errors="coerce"
    ).dt.to_period("M").astype(str)
    monthly = df.groupby("year_month")["id"].count().sort_index()
    return [{"month": m, "incident_count": int(c)} for m, c in monthly.items()]


def compute_cause_breakdown(df: pd.DataFrame) -> list:
    """Return incident count by event_cause with avg duration."""
    g = df.groupby("event_cause").agg(
        incident_count=("id", "count"),
        avg_duration_min=("duration_minutes", "mean"),
        pct_high_priority=("priority_high", "mean"),
    ).reset_index()
    g["avg_duration_min"] = g["avg_duration_min"].round(1)
    g["pct_high_priority"] = (g["pct_high_priority"] * 100).round(1)
    g = g.sort_values("incident_count", ascending=False)
    return g.to_dict(orient="records")


def main():
    print("=" * 60)
    print("BengaluruOps — Corridor Risk Scorer")
    print("=" * 60)

    if not CLEAN_CSV.exists():
        print(f"ERROR: {CLEAN_CSV} not found. Run data_prep.py first!")
        return

    df = pd.read_csv(CLEAN_CSV)
    print(f"Loaded clean dataset: {df.shape}")

    # Compute all analytics
    corridor_risk = compute_corridor_risk(df)
    peak_hours = compute_peak_hours_by_zone(df)
    top_junctions = compute_top_junctions(df)
    monthly_trend = compute_monthly_trend(df)
    cause_breakdown = compute_cause_breakdown(df)

    # Corridor diversions lookup
    CORRIDOR_DIVERSIONS = {
        "Mysore Road": ["Magadi Road", "NICE Expressway"],
        "Bellary Road 1": ["Bellary Road 2", "Hebbal Flyover"],
        "Tumkur Road": ["Magadi Road", "NICE Expressway"],
        "ORR East 1": ["ORR East 2"],
        "Hosur Road": ["Bannerghata Road"],
        "Old Madras Road": ["KR Pura alternate"],
        "Magadi Road": ["Mysore Road", "Chord Road"],
        "Bellary Road 2": ["Bellary Road 1", "ORR North 1"],
        "ORR North 1": ["ORR North 2", "Bellary Road 2"],
        "ORR North 2": ["ORR North 1"],
        "Bannerghata Road": ["Hosur Road"],
        "West of Chord Road": ["Magadi Road"],
    }

    # Build comprehensive output
    output = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "total_incidents": len(df),
        "corridor_risk": corridor_risk[
            ["rank", "corridor", "risk_score", "risk_tier",
             "incident_count", "pct_high_priority", "pct_road_closures",
             "avg_duration_hours", "event_cause_top"]
        ].to_dict(orient="records"),
        "peak_hours_by_zone": peak_hours,
        "top_junctions": top_junctions,
        "monthly_trend": monthly_trend,
        "cause_breakdown": cause_breakdown,
        "corridor_diversions": CORRIDOR_DIVERSIONS,
    }

    # Save
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"✅ Saved corridor risk scores → {OUTPUT_FILE}")
    print(f"\nTop 5 riskiest corridors:")
    for row in output["corridor_risk"][:5]:
        print(f"  #{row['rank']} {row['corridor']}: {row['risk_score']} ({row['risk_tier']})")
    print("=" * 60)


if __name__ == "__main__":
    main()
