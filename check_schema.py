import sqlite3
conn = sqlite3.connect('db/knowledge.db')
# Get live_runs schema
schema = conn.execute("PRAGMA table_info(live_runs)").fetchall()
print("live_runs columns:")
for col in schema:
    print(f"  {col}")

# Sample rows
rows = conn.execute('SELECT * FROM live_runs LIMIT 3').fetchall()
print("\nSample rows:")
for r in rows:
    print(f"  {r[:5]}")

conn.close()
