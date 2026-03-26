import sqlite3, json
conn = sqlite3.connect('db/knowledge.db')
rows = conn.execute(
    "SELECT error_type, physics_cause, code_cause FROM sim_errors_v2 WHERE physics_cause IS NOT NULL AND physics_cause != '' LIMIT 3"
).fetchall()
for r in rows:
    print(f"[{r[0]}]")
    print(f"  physics: {r[1][:100]}")
    print(f"  code:    {r[2][:80]}")
    print()
# Count filled
total = conn.execute('SELECT COUNT(*) FROM sim_errors_v2').fetchone()[0]
filled = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE physics_cause IS NOT NULL AND physics_cause != ''").fetchone()[0]
print(f"Total: {total}, Filled: {filled}")
conn.close()
