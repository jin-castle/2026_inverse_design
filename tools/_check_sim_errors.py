import sqlite3
conn = sqlite3.connect('C:/Users/user/projects/meep-kb/db/knowledge.db')
c = conn.cursor()

# Check sim_errors_v2 coverage
print("=== sim_errors_v2 by error_type ===")
c.execute("""
    SELECT error_type, COUNT(*) as total, 
           SUM(CASE WHEN fix_worked=1 THEN 1 ELSE 0 END) as fixed
    FROM sim_errors_v2
    GROUP BY error_type
    ORDER BY total DESC
""")
for row in c.fetchall():
    print(f"  {row[0]}: total={row[1]}, fixed={row[2]}")

print("\n=== sim_errors by error_type ===")
c.execute("""
    SELECT error_type, COUNT(*) as total,
           SUM(CASE WHEN fix_worked=1 THEN 1 ELSE 0 END) as fixed
    FROM sim_errors
    GROUP BY error_type
    ORDER BY total DESC
    LIMIT 20
""")
for row in c.fetchall():
    print(f"  {row[0]}: total={row[1]}, fixed={row[2]}")

conn.close()
