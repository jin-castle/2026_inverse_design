import sqlite3
conn = sqlite3.connect('db/knowledge.db')
filled = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE physics_cause IS NOT NULL AND physics_cause != ''").fetchone()[0]
total = conn.execute('SELECT COUNT(*) FROM sim_errors_v2').fetchone()[0]
print(f'physics_cause 채움: {filled}/{total}')
conn.close()
