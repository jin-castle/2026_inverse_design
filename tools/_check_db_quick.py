import sqlite3
conn = sqlite3.connect('C:/Users/user/projects/meep-kb/db/knowledge.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print('Tables:', [t[0] for t in tables])
cur.execute('PRAGMA table_info(sim_errors)')
print('sim_errors cols:', [(r[1], r[2]) for r in cur.fetchall()])
cur.execute("SELECT source, COUNT(*) FROM sim_errors GROUP BY source")
print('sim_errors by source:', cur.fetchall())
# Check sim_errors_v2
try:
    cur.execute('PRAGMA table_info(sim_errors_v2)')
    cols = cur.fetchall()
    print('sim_errors_v2 cols:', [(r[1], r[2]) for r in cols])
    cur.execute('SELECT COUNT(*) FROM sim_errors_v2')
    print('sim_errors_v2 count:', cur.fetchone())
except Exception as e:
    print('sim_errors_v2 error:', e)
# Sample github_issue rows with code
cur.execute("SELECT id, error_type, error_message FROM sim_errors WHERE source='github_issue' LIMIT 3")
print('github_issue samples:', cur.fetchall())
cur.execute("SELECT id, error_type, error_message FROM sim_errors WHERE source='github_structured' LIMIT 3")
print('github_structured samples:', cur.fetchall())
conn.close()
