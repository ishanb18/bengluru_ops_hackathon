import sqlite3
conn = sqlite3.connect('backend/data/bengaluru_ops.db')
cursor = conn.cursor()
cursor.execute("SELECT event_cause, COUNT(*) FROM events WHERE status='active' GROUP BY event_cause")
print(cursor.fetchall())
conn.close()
