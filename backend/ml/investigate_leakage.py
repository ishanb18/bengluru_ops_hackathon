import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import f1_score, accuracy_score

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
df = pd.read_csv(BASE_DIR / 'data/processed/events_clean.csv')

CAT = ['event_cause', 'corridor', 'zone', 'veh_type', 'weekday_name', 'event_type']
NUM = ['hour', 'month', 'is_peak_hour', 'weekday', 'has_cargo_data', 'has_junction']
FEAT = CAT + NUM

model_df = df[FEAT + ['priority_high']].dropna(subset=FEAT + ['priority_high'])
print(f'Training rows: {len(model_df)}')

X = model_df[FEAT]
y = model_df['priority_high']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

ct = ColumnTransformer([
    ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CAT),
    ('num', 'passthrough', NUM),
])
clf = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42, n_jobs=-1)
pipe = Pipeline([('pre', ct), ('clf', clf)])
pipe.fit(X_train, y_train)
y_pred = pipe.predict(X_test)

acc = accuracy_score(y_test, y_pred)
f1w = f1_score(y_test, y_pred, average='weighted')
print(f'Accuracy: {acc:.4f}, F1 weighted: {f1w:.4f}')

# Top feature importances
fnames = ct.named_transformers_['cat'].get_feature_names_out(CAT).tolist() + NUM
importances = clf.feature_importances_
top_idx = np.argsort(importances)[::-1][:15]
print('Top 15 feature importances:')
for i in top_idx:
    if i < len(fnames):
        print(f'  {fnames[i]}: {importances[i]:.4f}')

# Also check: maybe police_station is the issue — check correlation
print()
print('police_station unique values:', df['police_station'].nunique())
print('Rows where police_station is not null:', df['police_station'].notna().sum())
print()
# Check if police_station column correlates perfectly
ps_prio = df[df['police_station'].notna()].groupby('police_station')['priority_high'].mean()
print('Police stations with 100% High:', (ps_prio == 1.0).sum())
print('Police stations with 0% High:', (ps_prio == 0.0).sum())
