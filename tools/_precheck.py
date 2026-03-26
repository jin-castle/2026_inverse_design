import sqlite3
conn = sqlite3.connect("db/knowledge.db")

# concepts 상태
r = conn.execute("SELECT result_status, COUNT(*) FROM concepts GROUP BY result_status").fetchall()
print("concepts 상태:", dict(r))

# sim_errors github 현황
try:
    r2 = conn.execute("SELECT source, COUNT(*) FROM sim_errors GROUP BY source").fetchall()
    print("sim_errors 소스:", dict(r2))
except Exception as e:
    print("sim_errors:", e)

# sim_errors_v2 소스별
try:
    r3 = conn.execute("SELECT error_class, COUNT(*) FROM sim_errors_v2 GROUP BY error_class").fetchall()
    print("sim_errors_v2 error_class:", dict(r3))
except Exception as e:
    print("sim_errors_v2:", e)

conn.close()
