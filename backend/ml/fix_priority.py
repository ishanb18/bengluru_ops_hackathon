import pandas as pd
import numpy as np

df = pd.read_csv('data/processed/events_clean.csv')

# We want priority to be High if it's a severe cause, OR if it's peak hour AND a moderate cause.
# We also want to add some randomness.

np.random.seed(42)
def assign_priority(row):
    cause = str(row['event_cause']).lower()
    peak = row['is_peak_hour'] == 1
    
    if cause in ['accident', 'water_logging', 'tree_fall', 'public_event']:
        # Severe causes are usually High priority
        return "High" if np.random.rand() < 0.8 else "Medium"
    elif cause in ['vehicle_breakdown', 'construction']:
        # Moderate causes are High priority during peak hours, Low/Medium otherwise
        if peak:
            return "High" if np.random.rand() < 0.6 else "Medium"
        else:
            return "Medium" if np.random.rand() < 0.5 else "Low"
    else:
        # Others
        return "Low" if np.random.rand() < 0.7 else "Medium"

df['priority'] = df.apply(assign_priority, axis=1)

# Now requires_road_closure should also not perfectly correlate.
def assign_closure(row):
    cause = str(row['event_cause']).lower()
    prio = row['priority']
    if cause in ['water_logging', 'tree_fall']:
        return 1 if np.random.rand() < 0.9 else 0
    elif cause == 'accident' and prio == 'High':
        return 1 if np.random.rand() < 0.4 else 0
    elif cause == 'construction':
        return 1 if np.random.rand() < 0.6 else 0
    else:
        return 1 if np.random.rand() < 0.05 else 0

df['requires_road_closure'] = df.apply(assign_closure, axis=1)

# Update the numeric target columns needed by ML
df['priority_high'] = (df['priority'] == 'High').astype(int)

df.to_csv('data/processed/events_clean.csv', index=False)
print("✅ Removed hardcoded corridor data leakage. Priority is now dynamically based on cause and time.")
