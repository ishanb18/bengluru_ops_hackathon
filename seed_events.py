import pandas as pd
import sqlite3
import random
from datetime import datetime, timezone, timedelta

df = pd.read_csv('backend/data/processed/events_clean.csv')
sample = df[df['priority_high'] == 1].sample(15)

conn = sqlite3.connect('backend/data/bengaluru_ops.db')
cursor = conn.cursor()

for _, row in sample.iterrows():
    address = f"[SIMULATED] Historical: {row['event_cause']} on {row['corridor']}"
    start_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=random.randint(10, 120))
    
    cursor.execute('''
        INSERT INTO events (
            status, event_type, event_cause, corridor, zone, veh_type,
            latitude, longitude, address, priority, priority_high, 
            requires_road_closure, duration_minutes, duration_bucket,
            hour, weekday, month, is_peak_hour, authenticated,
            start_datetime
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'active', row.get('event_type', 'unplanned'), row['event_cause'], 
        row['corridor'], row.get('zone', 'Unknown'), row['veh_type'], 
        row['latitude'], row['longitude'], address, 'High', 1, 
        row.get('requires_road_closure', 0), row.get('duration_minutes', 60), 
        row.get('duration_bucket', 'Medium'), row['hour'], row['weekday'], 
        row['month'], row['is_peak_hour'], 1, start_time.strftime('%Y-%m-%d %H:%M:%S.%f')
    ))

conn.commit()
conn.close()
print('Simulated events inserted successfully!')
