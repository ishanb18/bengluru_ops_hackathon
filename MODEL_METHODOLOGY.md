# Model Training Methodology — Reference for Antigravity

This document explains **what was used and why**, separate from the runnable script (`train_models_v2.py`). Read this before changing, retraining, or extending the models — it captures the reasoning, not just the code, so the same decisions can be made correctly on new data.

---

## 1. The 3 models, in one table

| # | Model | Predicts | Algorithm used | Why | Macro F1 |
|---|---|---|---|---|---|
| 1 | Priority Classifier | `High` / `Low` | **XGBoost** | Beat RandomForest (0.821 vs 0.789) | **0.821** |
| 2 | Road Closure Classifier | `True` / `False` | **RandomForest** | Beat XGBoost (0.690 vs 0.661) | **0.690** |
| 3 | Duration Bucket Classifier | `Fast` / `Medium` / `Slow` | **XGBoost** | Beat RandomForest (0.548 vs 0.542) | **0.547** |

**Important: we don't hardcode one algorithm.** Every model is trained with *both* RandomForest and XGBoost, and whichever scores higher macro F1 on the held-out test set is the one that gets saved. This is a deliberate pattern — see Section 4.

---

## 2. Why tree-based models, not deep learning

The dataset has **8,173 rows total**, and the Duration model only has **3,127 usable rows** (rows with both a start and close timestamp). At this size:

- A neural network has too few examples per parameter to learn anything reliable — it will overfit and underperform a tree ensemble, while taking far longer to train and being harder to explain.
- RandomForest and XGBoost handle mixed categorical + numeric features natively, train in seconds on this row count, and produce feature importances for free.
- Both are SHAP-compatible, which matters for the "why did the model predict this" explainability layer in the product.

**Rule for Antigravity:** unless the training set exceeds roughly 50,000–100,000 rows, default to RandomForest/XGBoost comparison, not a neural net. If the dataset later grows past that, deep learning becomes worth revisiting.

---

## 3. Why each model uses different algorithms — don't force one winner

This is the most important methodological point: **we do not pick "RandomForest" or "XGBoost" up front and use it everywhere.** Each target has different characteristics (class balance, feature relationships, noise level), and the better algorithm differs per target. The training script always runs both and keeps the winner. If you retrain on new data and the winner flips, that's expected and fine — let the data decide, don't force consistency for its own sake.

---

## 4. Features used — and the validation each one passed

**Do not add a feature because it seems plausible.** Every feature below was tested against the actual target column *before* being included, using two checks:

1. **Signal check** — does it actually correlate with or separate the target classes?
2. **Leakage check** — does it correlate so strongly (>90% purity) that it's just encoding the answer, not predicting it?

### 4.1 — Final feature set

| Feature | Type | Used in | Validation result |
|---|---|---|---|
| `event_cause` | categorical | All 3 models | Core signal, casing-normalized (see 4.3) |
| `corridor` | categorical | Closure, Duration **only** | 99.9% purity for Priority → **excluded from Priority model** |
| `zone` | categorical | All 3 | 58% null, filled `"unknown"`, not missing-at-random (see 4.4) |
| `veh_type` | categorical | All 3 | Rare categories (<20 occurrences) bucketed to `"other"` |
| `weekday` | categorical | All 3 | Derived from `start_datetime` |
| `event_type` (planned/unplanned) | categorical | All 3 | Direct column |
| `hour_bin` | categorical | All 3 | Engineered — see 4.2 |
| `geo_cluster` | categorical | All 3 | Engineered — see 4.2. **Single biggest driver of the Priority model's accuracy gain.** |
| `police_station` | categorical | Closure, Duration **only** | 0% null, 77% median purity → safe. Excluded from Priority (leak risk similar to corridor) |
| `hour` | numeric (0-23) | All 3 | Derived from `start_datetime` |
| `month` | numeric (1-12) | All 3 | Derived |
| `is_peak_hour` | numeric (0/1) | All 3 | Flag for hour in [4,5,6,9,10,11,17,18,19,20] |
| `dist_from_center_km` | numeric | All 3 | Engineered — see 4.2 |

### 4.2 — Engineered features, and the test that justified each one

**`dist_from_center_km`** — haversine distance from every event's lat/lon to Bengaluru city center (MG Road / Trinity Circle, 12.9716, 77.6033).
*Test performed:* Pearson correlation against the priority target.
*Result:* r = -0.176 — weak but real. Kept.

**`geo_cluster`** — K-Means with k=15 fit on `[latitude, longitude]`, output saved as a categorical ID.
*Test performed:* grouped by cluster, computed `value_counts(normalize=True).max()` per cluster for the priority target, averaged across clusters.
*Result:* mean purity 73% (Priority), 93% (Closure) — informative without being a shortcut (compare to corridor's 99.9%, which WAS a shortcut). Kept. This is exactly what the leakage check is for: a feature can be highly correlated AND legitimate if it's not just relabeling the target.

**`hour_bin`** — 6 buckets (`late_night`, `morning_rush`, `midday`, `afternoon`, `evening_rush`, `night`) instead of raw hour alone.
*Test performed:* grouped closure rate by bucket.
*Result:* swings from 6.7% (evening_rush) to 27.4% (midday) — a 4x range that raw `hour` as a single numeric feature doesn't expose as cleanly to a tree's first few splits. Kept alongside raw `hour` (redundancy is cheap for tree models — they'll use whichever split is more useful and ignore the rest).

### 4.3 — A real bug found and fixed during validation

`event_cause` had **"Debris" and "debris" as two separate categories** purely from inconsistent casing in the source data — silently splitting that signal across two one-hot columns instead of one. Fixed by lowercasing and stripping all categorical text fields before bucketing rare categories. **If you add new categorical features from raw text, always check `df[col].unique()` for casing/whitespace duplicates before training — this class of bug is invisible in aggregate metrics and only shows up if you print the raw unique values.**

### 4.4 — `zone`: handled as "missing, not at random"

`zone` is null in 58% of rows. The naive fix (drop rows with null zone) was tried first and produced a *worse*, misleading model — it was disproportionately removing a non-random subset of the data, and on the remaining subset, `corridor` became artificially predictive (see 4.5 leakage notes below). The correct fix: keep all rows, fill null `zone` as the literal string `"unknown"`, and let the model learn from that as its own category rather than discarding data.

**Rule for Antigravity:** before dropping any rows for a null column, always check `df['col'].isna()` against the target distribution. If the null rate correlates with anything in the target or other features, the rows are not missing-at-random and dropping them will bias the model — fill instead of drop.

### 4.5 — Features that were tested and REJECTED

| Feature | Why rejected |
|---|---|
| `corridor` (for Priority model only) | 99.9% purity — confirmed business-rule artifact, not learnable signal. Every named corridor is tagged ~100% "High" priority and "Non-corridor" is ~100% "Low" by the data-entry process itself, not by event characteristics. Including it gives a fake near-100% accuracy that fails to generalize. |
| `police_station` (for Priority model only) | Same leak pattern as corridor, smaller magnitude (a handful of stations near-pure for priority) |
| `is_weekend` | Zero signal — 61.57% High-rate on weekends vs 61.54% on weekdays. Statistical noise, not a real pattern. |
| `age_of_truck` as a raw numeric ML feature | Only 276/8,173 rows (3.4%) populated, AND the column has data corruption (max value = 2026, almost certainly a year typo rather than an age in years). Reserved for a separate rule-based truck-risk profiler instead of the core 3 models — do not feed it into RandomForest/XGBoost as-is. |
| `cargo_material` | Same 3.4% population issue, plus messy free-text values ("Goods", "goods", "Goods carried" — inconsistent casing/phrasing, would need its own normalization pass before being usable) |

**Rule for Antigravity:** "we have this column" is not a reason to use it as a feature. Every candidate feature needs the same two-question test as above: does it have real population/coverage, and does it correlate with the target for a *causal* reason rather than a *data-pipeline* reason?

---

## 5. How the 3 targets were chosen (and 2 were rejected)

| Candidate label | Verdict | Why |
|---|---|---|
| `priority` (High/Low) | **Used** | 5,030 High / 3,141 Low (62/38) — healthy balance, only 2 nulls in 8,173 rows |
| `requires_road_closure` (True/False) | **Used** | 676 True / 7,497 False (8/92) — real imbalance, handled with SMOTE (Section 6) |
| `duration_bucket` (derived: Fast ≤90min / Medium ≤24hr / Slow >24hr) | **Used, with caveat** | Only computable on 3,127/8,173 rows (38%) that have both `start_datetime` and `closed_datetime`. Trained on that subset only — be upfront that it's a smaller sample. |
| `status` (active/closed/resolved) | **Rejected** | This reflects data-pipeline processing state, not a property of the event itself. Predicting it teaches the model nothing useful about traffic impact. |

**Rule for Antigravity:** a column is a viable ML target only if it describes something about the *event itself*, not something about *how the record was processed*. If you're unsure, ask: "would a traffic commander want this predicted in advance of the event being fully logged?" `status` fails this test; `priority` and `requires_road_closure` pass it.

---

## 6. Handling class imbalance — SMOTE, only where it's needed

`requires_road_closure` is 92/8 imbalanced. Without correction, a classifier can score 92% accuracy by always predicting "False" — useless, but a deceptively good-looking number.

**What we tested, with real before/after numbers on this data:**

| Approach | Closure-class F1 |
|---|---|
| Baseline (no correction) | 0.291 |
| `class_weight='balanced'` (reweighting only) | ~0.31 (tested in an earlier pass, see project history) |
| **SMOTE oversampling (train split only)** | **0.423** |

SMOTE generates synthetic minority-class examples by interpolating between real minority-class neighbors in feature space — applied **only to the training split, never the test split**, so the reported metrics reflect performance on real, un-augmented data.

**Rule for Antigravity:**
- Only apply SMOTE to a target that's actually imbalanced (we did NOT apply it to `priority`, which is already 62/38 — augmenting an already-balanced target adds noise, not signal).
- Always fit SMOTE after the train/test split, never before — fitting before the split lets synthetic points leak information into the test set and inflates your reported metrics dishonestly.
- Always report the baseline (no augmentation) number alongside the augmented number so the improvement is verifiable, not just claimed.

**Full synthetic dataset generation (CTGAN, etc.) was deliberately NOT used.** Reasoning, fully spelled out: the dataset has 219 unique `(event_cause, corridor)` combinations, and 89 of them have fewer than 5 real examples (median is 7). A generative model trained on data this sparse mostly interpolates between existing patterns rather than learning a genuine underlying distribution — for combinations with 1-2 real examples, there's nothing for it to learn the true shape from. SMOTE's interpolation between real *nearest neighbors* in already-encoded feature space is a much smaller, more defensible leap than a generative model fabricating entirely new rows. If you're tempted to add CTGAN/SDV-style augmentation, re-run the sparsity check first (`df.groupby([cat_col_1, cat_col_2]).size()`) and treat a high count of low-population combinations as a reason not to.

---

## 7. The leakage check — run this every time you retrain

This is the single most important habit in this pipeline, and it's baked into the script so it can't be silently skipped. Before training any model, the script computes, for every candidate categorical feature:

```python
purity = df.groupby(feature)[target].apply(lambda s: s.value_counts(normalize=True).max())
mean_purity = purity.mean()
```

If `mean_purity > 0.90`, the feature is flagged as a likely leak and should be excluded from that specific target's model (it may still be fine for a *different* target — `corridor` leaks for `priority` but not for `requires_road_closure`).

**A 99%+ accuracy or F1 score is not a win — it's a signal to go check for leakage first.** That's exactly what happened in this project: the first version of the Priority model scored 99.9% accuracy, which led directly to discovering the corridor leak. Don't celebrate a suspiciously perfect score; investigate it.

---

## 8. Train/test methodology

- **Split:** 80/20, `stratify=y` on every model so the class balance is preserved in both splits.
- **Random state:** fixed at `42` everywhere for reproducibility — if you change this, expect metrics to shift slightly; that's normal variance, not a regression.
- **Preprocessing:** `OneHotEncoder(handle_unknown="ignore")` for all categoricals, wrapped in a `ColumnTransformer` with `remainder="passthrough"` for numeric features. `handle_unknown="ignore"` matters specifically because production traffic events may contain a `corridor` or `event_cause` value not seen during training — without this flag, the pipeline would crash on unseen categories instead of degrading gracefully.
- **Evaluation metric:** macro F1 is the primary metric used to compare RandomForest vs XGBoost and to judge model quality — not accuracy. Macro F1 averages performance across classes equally, so it doesn't let a model hide poor minority-class performance behind a high majority-class accuracy (this is exactly why the Closure model's 92% accuracy is NOT the headline number — its macro F1 of 0.690 is the honest one).

---

## 9. Hyperparameters used (and why these, not others)

```python
# RandomForest
RandomForestClassifier(
    n_estimators=400,    # enough trees to stabilize predictions at this data size; diminishing returns past ~500 for 8K rows
    max_depth=14,         # capped to prevent overfitting on a dataset this size — unbounded depth memorizes noise
    random_state=42,
    n_jobs=-1,             # use all available cores, training is fast either way at this row count
)

# XGBoost
XGBClassifier(
    n_estimators=400,
    max_depth=6,           # XGBoost trees should be shallower than RF trees — boosting compounds many weak learners, RF averages many independent ones
    learning_rate=0.08,    # conservative rate appropriate for 400 rounds; higher would risk overfitting faster than the ensemble can correct
    random_state=42,
)
```

These were not exhaustively tuned via grid search — for an 8K-row dataset, the gains from hyperparameter search are marginal compared to the gains from correct feature engineering and leakage removal (which is exactly what the v1→v2 jump shows: feature work moved Priority macro F1 from 0.588 to 0.821, a 23-point gain, with no hyperparameter tuning at all). **If retraining on a substantially larger dataset (50K+ rows), grid search or Optuna-based tuning becomes worth the time investment; on this data size, it is not the best use of hackathon hours.**

---

## 10. If you're adding a 4th model — the checklist

1. Pick a target column. Run the "would a commander want this predicted in advance" test (Section 5).
2. Check class balance with `.value_counts(normalize=True)`. If imbalanced beyond roughly 80/20, plan for SMOTE.
3. Check null rate on the target and on every candidate feature. If null rate is high, check whether it's missing-at-random before deciding to drop or fill (Section 4.4).
4. For every candidate feature: run the leakage check (Section 7) against this new target specifically — leakage is target-specific, not feature-specific. A feature safe for one target may leak for another.
5. Check for casing/whitespace duplicates in any text categorical (Section 4.3).
6. Train both RandomForest and XGBoost, keep the winner by macro F1 — don't assume which will win.
7. Report macro F1, not accuracy, as the headline metric, especially if the target is imbalanced.
8. Save the model bundle as `{"preprocessor": ..., "model": ..., "model_type": ...}` via `joblib.dump()`, matching the pattern used for the existing 3 models, so the backend's `predict.py` can load all 4 the same way.

---

## 11. Quick numbers reference

```
Priority Classifier      — XGBoost      — Macro F1: 0.821 — Accuracy: 0.833
Road Closure Classifier  — RandomForest — Macro F1: 0.690 — Accuracy: 0.920
Duration Bucket          — XGBoost      — Macro F1: 0.547 — Accuracy: 0.716

RF vs XGB comparison (macro F1):
  Priority:  RF=0.789  XGB=0.821  -> XGB wins
  Closure:   RF=0.690  XGB=0.661  -> RF wins
  Duration:  RF=0.542  XGB=0.548  -> XGB wins (marginal)

SMOTE impact on Closure model (minority class F1):
  Before: 0.291
  After:  0.423
  Delta:  +0.132

Feature engineering impact (v1 -> v2, same algorithm family):
  Priority macro F1: 0.588 -> 0.821  (+0.233, geo_cluster was the main driver)
  Closure macro F1:  0.674 -> 0.690  (+0.016, modest — ceiling is class imbalance, not features)
  Duration macro F1: 0.547 -> 0.547  (~flat — ceiling is data volume: only 3,127 usable rows)
```
