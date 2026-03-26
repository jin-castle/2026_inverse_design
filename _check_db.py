import sqlite3
conn = sqlite3.connect('C:/Users/user/projects/meep-kb/db/knowledge.db')
c = conn.cursor()
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('Tables:', tables)

# sim_errors 현황
counts = c.execute("SELECT source, COUNT(*) FROM sim_errors GROUP BY source").fetchall()
print('sim_errors by source:', counts)

# sim_errors_v2 현황  
try:
    count_v2 = c.execute("SELECT COUNT(*) FROM sim_errors_v2").fetchone()[0]
    fix_worked_v2 = c.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=1").fetchone()[0]
    print(f'sim_errors_v2 total: {count_v2}, fix_worked=1: {fix_worked_v2}')
except Exception as e:
    print(f'sim_errors_v2: {e}')

# sim_errors columns
cols = [r[1] for r in c.execute("PRAGMA table_info(sim_errors)").fetchall()]
print('sim_errors columns:', cols)
conn.close()
