import sqlite3
conn = sqlite3.connect('C:/Users/user/projects/meep-kb/db/knowledge.db')
cur = conn.cursor()

# Check context content distribution
cur.execute("""
SELECT 
  SUM(CASE WHEN context LIKE '%```python%' THEN 1 ELSE 0 END) as ctx_python,
  SUM(CASE WHEN context LIKE '%```%' THEN 1 ELSE 0 END) as ctx_any,
  SUM(CASE WHEN root_cause LIKE '%```%' THEN 1 ELSE 0 END) as rc_any,
  SUM(CASE WHEN fix_applied LIKE '%```%' THEN 1 ELSE 0 END) as fa_any,
  COUNT(*) as total
FROM sim_errors WHERE source IN ('github_issue', 'github_structured')
""")
print('code block distribution:', cur.fetchone())

# Sample one full context
cur.execute("""
SELECT id, error_type, context 
FROM sim_errors WHERE source='github_issue' AND context LIKE '%```python%' 
LIMIT 1
""")
row = cur.fetchone()
if row:
    print(f"\n--- Full context of ID {row[0]} ({row[1]}) ---")
    print(row[2][:2000])

conn.close()
