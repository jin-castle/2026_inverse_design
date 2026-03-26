import sqlite3
conn = sqlite3.connect('db/knowledge.db')
print('live_runs:', conn.execute('SELECT COUNT(*) FROM live_runs').fetchone()[0])
print('sim_errors_v2:', conn.execute('SELECT COUNT(*) FROM sim_errors_v2').fetchone()[0])
print('fix_worked=1:', conn.execute('SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=1').fetchone()[0])
print('fix_worked=0:', conn.execute('SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=0').fetchone()[0])
q = "SELECT COUNT(*) FROM sim_errors_v2 WHERE physics_cause IS NULL OR physics_cause=''"
print('physics_null:', conn.execute(q).fetchone()[0])
conn.close()
