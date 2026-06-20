# BengaluruOps Command — Full Implementation Plan
### Event-Driven Congestion Intelligence System (Hackathon Theme 2)

This document is written to be handed directly to an AI coding agent (Antigravity) as a build spec. It covers data prep, ML model training, backend API, frontend, and integration — in execution order.

---

## 0. Project Summary

**What we're building:** A traffic command center web app that takes the `Astram_event_data` dataset (8,173 Bengaluru traffic events, 46 columns) and:
1. Visualizes all events live on a map
2. Predicts the impact (priority + road closure) of a new/incoming event using a trained ML model
3. Predicts how long an event will take to resolve
4. Recommends officer deployment, barricades, and tow trucks
5. Suggests diversion routes for blocked corridors
6. Shows historical analytics for post-event learning

**Tech stack decision:**
- Backend: **Python + FastAPI** (fast to build, native ML integration, async-ready)
- ML: **scikit-learn (RandomForest/XGBoost)** for classifier + regressor — NOT deep learning. Reason: only 8,173 rows. A simple, explainable, fast-training model will outperform and out-demo a deep model on this data size, and it trains in seconds, not hours, which matters for a hackathon timeline.
- Frontend: **React + Vite + Tailwind CSS** + **Leaflet.js** (free, no API key needed, OpenStreetMap-based) for the map
- Database: **SQLite** for hackathon scope (zero setup) — swappable to PostgreSQL later
- Explainability: **SHAP** for the classifier
- Deployment: Docker Compose (one command to run everything)

**Repository structure:**
```
bengaluru-traffic-ops/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── incidents.py
│   │   │   ├── classify.py
│   │   │   ├── duration.py
│   │   │   ├── manpower.py
│   │   │   ├── diversion.py
│   │   │   └── analytics.py
│   │   ├── models/
│   │   │   ├── schemas.py        # Pydantic models
│   │   │   └── db.py             # SQLAlchemy models
│   │   ├── ml/
│   │   │   ├── train_classifier.py
│   │   │   ├── train_duration.py
│   │   │   ├── predict.py
│   │   │   └── shap_explainer.py
│   │   ├── data/
│   │   │   ├── raw/Astram_event_data_anonymized.csv
│   │   │   ├── processed/events_clean.csv
│   │   │   └── models/           # saved .pkl files
│   │   └── core/config.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Monitor.jsx
│   │   │   ├── Classifier.jsx
│   │   │   ├── Manpower.jsx
│   │   │   ├── Diversion.jsx
│   │   │   └── Analytics.jsx
│   │   ├── components/
│   │   ├── api/client.js
│   │   └── App.jsx
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 1. Data Preparation Phase

**Goal:** Turn the raw 46-column CSV into a clean, ML-ready dataset.

### Step 1.1 — Load and audit
- Load `Astram_event_data_anonymized.csv` with pandas
- Confirm 8,173 rows, 46 columns
- Print null counts per column, store as a data quality report

### Step 1.2 — Parse datetimes
Columns to parse with `pd.to_datetime(..., format='mixed', utc=True, errors='coerce')`:
- `start_datetime`, `end_datetime`, `created_date`, `modified_datetime`, `closed_datetime`, `resolved_datetime`

Derive new columns:
- `hour` (0–23) from `start_datetime`
- `weekday` (Monday–Sunday) from `start_datetime`
- `month` from `start_datetime`
- `duration_minutes` = `(closed_datetime - start_datetime).total_seconds() / 60`
- `is_peak_hour` = boolean, True if hour in [4,5,6,9,10,11,17,18,19,20]

### Step 1.3 — Clean categorical fields
- `event_type`: planned / unplanned — keep as-is, 2 classes
- `event_cause`: 17 categories — keep top 12, bucket rare ones (<20 occurrences) into "other"
- `priority`: High / Low — this is one ML target, encode as binary (1=High, 0=Low)
- `requires_road_closure`: True/False — this is the second ML target, encode as binary
- `corridor`: 22 unique values — keep as categorical, one-hot or target-encode
- `zone`: 10 unique values — keep as categorical
- `veh_type`: keep top categories, bucket rare into "other"
- `police_station`: 54 unique values — keep as categorical for the manpower module (not the ML model directly — too high cardinality, use corridor/zone instead for ML, use police_station only for the lookup/recommendation logic)

### Step 1.4 — Handle missing values
- For `cargo_material`, `reason_breakdown`, `age_of_truck`: these are only populated for vehicle breakdown events. Keep null for non-breakdown rows — do not impute. Use `.notna()` as a feature flag instead (`has_cargo_data`).
- For `junction`: fill missing with `"unmapped"` string, do not drop rows.
- Drop rows only if `latitude`/`longitude`/`event_cause`/`start_datetime` are missing (these are core fields).

### Step 1.5 — Build the corridor adjacency lookup table
Hardcode this as a Python dict (used by the Diversion module, not ML):
```python
CORRIDOR_DIVERSIONS = {
    "Mysore Road": ["Magadi Road", "NICE Expressway"],
    "Bellary Road 1": ["Bellary Road 2", "Hebbal Flyover"],
    "Tumkur Road": ["Magadi Road"],
    "ORR East 1": ["ORR East 2"],
    "Hosur Road": ["Bannerghatta Road"],
    "Old Madras Road": ["KR Pura alternate"]
}
```
Verify these corridor names match exactly what's in the `corridor` column — adjust spelling if needed after inspecting `df['corridor'].unique()`.

### Step 1.6 — Save processed dataset
Save to `backend/app/data/processed/events_clean.csv`. This is the single source of truth used by both ML training and the analytics API.

**Deliverable of this phase:** `events_clean.csv` + a `data_quality_report.md` documenting null %, row counts before/after cleaning, and class balance for `priority` and `requires_road_closure`.

---

## 2. Machine Learning Phase

### 2.1 — Model 1: Event Impact Classifier (multi-output)

**Goal:** Given event features, predict `priority` (High/Low) and `requires_road_closure` (True/False).

**Features (input X):**
| Feature | Type | Source |
|---|---|---|
| `event_cause` | categorical | direct column |
| `corridor` | categorical | direct column |
| `zone` | categorical | direct column |
| `veh_type` | categorical | direct column |
| `hour` | numeric | derived |
| `weekday` | categorical | derived |
| `month` | numeric | derived |
| `is_peak_hour` | boolean | derived |
| `event_type` | categorical | direct column (planned/unplanned) |

**Targets (Y):** two separate binary classifiers (simpler and more explainable than a single multi-label model):
- `priority_high` (1/0)
- `requires_road_closure` (1/0)

**Pipeline:**
1. `train_test_split` 80/20, stratified on `priority_high`
2. Preprocessing: `OneHotEncoder` for categoricals (handle_unknown='ignore'), passthrough for numeric — wrap in `sklearn.compose.ColumnTransformer`
3. Model: `RandomForestClassifier(n_estimators=300, max_depth=12, class_weight='balanced', random_state=42)` — start here. If time permits, also try `XGBClassifier` and compare F1 score; use whichever performs better.
4. Train two separate pipelines: one for `priority_high`, one for `requires_road_closure`
5. Evaluate: accuracy, precision, recall, F1, confusion matrix — for both targets
6. Save both pipelines with `joblib.dump()` to `backend/app/data/models/priority_model.pkl` and `closure_model.pkl`

**Explainability:**
- Use `shap.TreeExplainer` on the trained RandomForest
- For each prediction, compute SHAP values and return the top 4 contributing features with their direction (+/-) and magnitude — this feeds the "Why this prediction?" panel in the frontend
- Save a SHAP summary plot image during training for the README/demo

**Acceptance criteria:** F1 score ≥ 0.75 on both targets. If class imbalance hurts recall (priority_high is likely the minority class — verify with `value_counts()`), use `class_weight='balanced'` and/or SMOTE oversampling from `imbalanced-learn`.

### 2.2 — Model 2: Event Duration Predictor

**Goal:** Predict `duration_minutes` given event features.

**Important data note:** Duration has extreme outliers (potholes can be 4.5+ days = 6480+ minutes, while accidents are ~44 minutes). Do not train a raw regression on this — it will be dominated by outliers. Instead:

**Approach — classification into buckets (more robust + more useful for the UI):**
1. Create `duration_bucket` from `duration_minutes`:
   - `Fast`: ≤ 90 minutes
   - `Medium`: 90 minutes – 24 hours
   - `Slow`: > 24 hours
2. Train a `RandomForestClassifier` on the same feature set as Model 1, predicting `duration_bucket` (3 classes)
3. Additionally train a `RandomForestRegressor` on `log1p(duration_minutes)` for cases where a more precise number is needed (apply `np.expm1()` to get back to actual minutes) — only train this on the subset with `duration_minutes < 10000` (drop extreme pothole outliers from regression training, but keep them in the classifier)
4. Save both: `duration_bucket_model.pkl` and `duration_regression_model.pkl`

**Acceptance criteria:** Bucket classifier F1 ≥ 0.70. Regression model: report MAE in minutes, expect higher error due to inherent unpredictability — this is fine, the bucket prediction is the primary UX feature.

### 2.3 — Synthetic data augmentation (stretch goal, optional)

If time and judges' expectations call for showing "AI depth":
- Use `CTGAN` from the `sdv` (Synthetic Data Vault) library to generate 20,000–40,000 synthetic rows matching the real data's statistical distribution
- Retrain Model 1 and Model 2 on real + synthetic combined data
- Compare F1/accuracy before vs after — only keep this approach if it measurably improves metrics. Do NOT use synthetic data if it doesn't help; report it honestly either way. This is a "nice to have" that shows technical sophistication, but the core models must already work well on real data alone — don't make this a dependency for the demo.

### 2.4 — Repeat/chronic risk corridor scorer (rule-based, no training needed)

Not ML — a deterministic scoring formula, computed once and cached:
```
corridor_risk_score = (
    0.4 * normalized(incident_count_per_corridor) +
    0.3 * normalized(pct_high_priority_per_corridor) +
    0.2 * normalized(pct_road_closures_per_corridor) +
    0.1 * normalized(avg_duration_per_corridor)
)
```
Compute this once from `events_clean.csv`, save as `corridor_risk_scores.json`, served directly by the analytics API. This powers the "Corridor Risk Ranking" feature — recompute nightly or on-demand, not part of the ML training pipeline.

### 2.5 — Truck breakdown risk profiler (rule-based + simple model)

For the ~276 vehicle breakdown rows with `cargo_material`, `reason_breakdown`, `age_of_truck` populated:
- Compute average `age_of_truck` by `reason_breakdown` — store as a lookup table
- Train a small `RandomForestClassifier` to predict `reason_breakdown` (top 5 reasons) from `age_of_truck` + `veh_type` + `cargo_material` — used to pre-emptively flag high-risk truck profiles
- This is a small, secondary model — don't over-invest time here, 1-2 hours max

### 2.6 — Citizen report authenticity scorer (rule-based, no ML)

For rows where `authenticated == False`:
- Score 0–100 based on: is `event_cause` plausible for this `corridor`'s historical pattern? Is the `hour` consistent with this cause's typical occurrence time? Compute as a weighted similarity score against historical authenticated reports of the same `event_cause` on the same `corridor`.
- Keep this simple — a cosine similarity or simple rule-based score against historical patterns is sufficient. This is a differentiator feature, not the core ML deliverable — timebox to 2-3 hours.

---

## 3. Backend API Phase (FastAPI)

### 3.1 — Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn pandas scikit-learn xgboost shap joblib sqlalchemy python-multipart
pip freeze > requirements.txt
```

### 3.2 — Database schema (SQLAlchemy + SQLite)
Table `events` mirrors the cleaned CSV — load once at startup via a seed script (`seed_db.py`) that reads `events_clean.csv` into SQLite. This lets the API query/filter without re-reading CSV on every request.

Key columns to include in the DB table: `id`, `event_type`, `latitude`, `longitude`, `event_cause`, `requires_road_closure`, `start_datetime`, `closed_datetime`, `status`, `priority`, `corridor`, `zone`, `police_station`, `junction`, `duration_minutes`, `authenticated`.

### 3.3 — API Endpoints

**`GET /api/incidents`**
- Query params: `status` (active/closed), `priority`, `corridor`, `zone`, `date_from`, `date_to`
- Returns: paginated list of incidents with lat/lon for map rendering
- Used by: Live Map screen

**`GET /api/incidents/{id}`**
- Returns full detail of a single incident (all fields)
- Used by: Map marker click → side panel

**`POST /api/classify`**
- Request body: `{event_cause, corridor, zone, veh_type, hour, weekday, month, event_type}`
- Loads `priority_model.pkl` and `closure_model.pkl`, runs prediction
- Returns: `{priority: "High"/"Low", confidence: 0.87, requires_closure: true, shap_explanation: [{feature, value, direction}]}`
- Used by: AI Classifier screen

**`POST /api/duration`**
- Request body: same as classify
- Loads `duration_bucket_model.pkl` and `duration_regression_model.pkl`
- Returns: `{bucket: "Medium", estimated_minutes: 72, confidence: 0.81}`
- Used by: Duration Predictor screen

**`POST /api/manpower`**
- Request body: `{priority, requires_closure, corridor, duration_bucket, veh_type}`
- Rule-based logic (no ML): calculates officer count via lookup table, e.g.:
  ```
  base_officers = 2
  if priority == "High": base_officers += 3
  if requires_closure: base_officers += 2
  if veh_type in ["Heavy vehicle", "Bus"]: base_officers += 1
  ```
- Looks up nearest police stations by haversine distance from incident lat/lon to all 54 station coordinates (precompute station lat/lon centroids from the data, or use a static lookup if station addresses are available)
- Returns: `{officer_count, barricade_count, tow_truck_needed, recommended_stations: [{name, distance_km, available_officers, eta_min}]}`
- Used by: Manpower screen

**`GET /api/diversion/{corridor_name}`**
- Looks up `CORRIDOR_DIVERSIONS` dict
- For each alternate route, computes a live "stress score" = recent incident count on that corridor / historical average (from DB query)
- Returns: `{blocked_corridor, alternates: [{name, stress_score, stress_level}]}`
- Used by: Diversion screen

**`GET /api/analytics/corridor-risk`**
- Returns precomputed `corridor_risk_scores.json`, sorted descending
- Used by: Analytics screen — Corridor Risk Ranking

**`GET /api/analytics/monthly-trend`**
- Groups DB by month, returns incident counts
- Used by: Analytics screen — Month over month chart

**`GET /api/analytics/top-junctions`**
- Groups DB by `junction`, returns top 10 by incident count
- Used by: Analytics screen — Top 10 worst junctions

**`GET /api/analytics/peak-hours`**
- Groups DB by `zone` + `hour`, returns the peak hour per zone
- Used by: Analytics screen — Peak hours by zone

**`GET /api/analytics/pothole-escalation`**
- Filters DB for `event_cause == "pothole"` and `status != "closed"`
- Returns count + avg duration, flagged for BBMP escalation
- Used by: Duration screen — Pothole escalation tracker

### 3.4 — CORS + serving
- Enable CORS for `localhost:5173` (Vite dev server) and the production frontend origin
- Serve via `uvicorn app.main:app --reload --port 8000` in dev

---

## 4. Frontend Phase (React + Vite + Tailwind + Leaflet)

### 4.1 — Setup
```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install leaflet react-leaflet axios react-router-dom recharts
```

Configure Tailwind with the light theme tokens used in the mockup:
```js
colors: {
  bg: { app: '#F3F5F8', panel: '#FFFFFF' },
  brand: { green: '#16A34A', greenBg: '#ECFDF3' },
  state: { red: '#DC2626', redBg: '#FEF1F1', amber: '#D97706', amberBg: '#FEF6E7', blue: '#2563EB', blueBg: '#EEF4FF' },
  text: { 1: '#111827', 2: '#6B7280', 3: '#9CA3AF' },
  border: { DEFAULT: '#E5E7EB' }
}
```

### 4.2 — Page-by-page build order

1. **Layout shell** — sidebar nav + topbar, shared across all pages (`Layout.jsx`)
2. **Monitor (Live Map)** — Leaflet map centered on Bengaluru (12.9716° N, 77.5946° E), markers colored by priority, fetched from `GET /api/incidents`, click marker → side panel with detail from `GET /api/incidents/{id}`. Floating stats panel calls a lightweight aggregate endpoint (add `GET /api/analytics/summary` if not already covered) for the today/7-day/30-day tab counts.
3. **AI Classifier** — form with 4 dropdowns (event_cause, corridor, veh_type, time bucket), submit → `POST /api/classify`, render result card + SHAP bar chart (use `recharts` horizontal bar)
4. **Duration Predictor** — same form pattern, submit → `POST /api/duration`, render bucket cards + timeline visualization
5. **Manpower** — triggered from a classified incident (pass priority/closure/corridor as state), calls `POST /api/manpower`, renders deployment cards + station list with distance bars
6. **Diversion** — corridor dropdown, calls `GET /api/diversion/{corridor}`, renders the alternate route cards with stress pills
7. **Analytics** — dashboard of charts, each panel calls its respective analytics endpoint, render with `recharts` (bar charts for monthly trend, horizontal bars for corridor risk and top junctions)

### 4.3 — Component reuse
Build these as shared components used across pages, matching the existing mockup styling already approved:
- `StatCard.jsx` (metric grid cells)
- `Badge.jsx` (priority/severity pills)
- `IncidentMarker.jsx` (Leaflet custom icon)
- `SidePanel.jsx` (slide-in detail panel)
- `RiskBar.jsx` (horizontal bar with score)

### 4.4 — API client
Centralize all backend calls in `src/api/client.js` using `axios`, with base URL from `import.meta.env.VITE_API_URL` (set to `http://localhost:8000` in `.env`).

---

## 5. Integration & Testing Phase

1. **Backend smoke test:** start FastAPI, hit each endpoint with `curl` or Postman, verify response shapes match what frontend expects
2. **Seed data verification:** confirm DB has all 8,173 rows loaded correctly, spot-check 5 random records against the source CSV
3. **Model sanity check:** manually test the classifier with known historical patterns (e.g., "vehicle breakdown + Tumkur Road + evening" should return High priority — verify this matches the actual data pattern)
4. **End-to-end click-through:** open frontend, verify Monitor map loads incidents, click a marker, run a classification, run a duration prediction, check manpower recommendation, check diversion suggestion, check analytics charts all render
5. **Edge cases:** empty form submission, corridor with no diversion mapping, incident with missing junction name — make sure none of these crash the UI

---

## 6. Demo Preparation Checklist

- [ ] Seed the live map with a realistic "today" subset so it doesn't look empty
- [ ] Prepare 2-3 pre-set classifier examples that produce visually distinct results (one High+closure, one Low+no closure) to demo quickly without fumbling dropdowns live
- [ ] Have the SHAP explanation ready to talk through — this is your strongest "AI" proof point for judges
- [ ] Print/screenshot the corridor risk ranking and top junctions — useful as a backup slide if live demo has network issues
- [ ] Prepare the one-line answer for "how do you predict unplanned events": *"We don't predict when they occur — we predict their impact and duration once reported, and use historical patterns to pre-position resources on high-risk corridors during high-risk hours."*
- [ ] Time the full demo walkthrough — target under 4 minutes for the live portion

---

## 7. Suggested Build Order & Time Allocation (24-hour hackathon)

| Phase | Hours | Deliverable |
|---|---|---|
| Data cleaning + EDA | 0–2 | `events_clean.csv`, data quality report |
| ML Model 1 (classifier) | 2–5 | trained + saved priority/closure models, SHAP working |
| ML Model 2 (duration) | 5–7 | trained + saved duration bucket model |
| Backend API core | 7–11 | all endpoints working, tested with curl/Postman |
| Frontend shell + Monitor map | 11–15 | live map rendering real incidents |
| Frontend Classifier + Duration screens | 15–18 | both forms working end-to-end |
| Frontend Manpower + Diversion screens | 18–20 | both working end-to-end |
| Frontend Analytics dashboard | 20–22 | all charts rendering |
| Polish, bug fixes, demo prep | 22–24 | rehearsed demo, backup screenshots |

Stretch goals (CTGAN augmentation, authenticity scorer, truck profiler) should only be attempted if core deliverables are done with time to spare — do not let them block the critical path.
