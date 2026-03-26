import sqlite3
conn = sqlite3.connect('C:/Users/user/projects/meep-kb/db/knowledge.db')
cur = conn.cursor()

# Check how many have original_code
cur.execute("SELECT COUNT(*) FROM sim_errors WHERE source IN ('github_issue','github_structured') AND original_code IS NOT NULL AND original_code != ''")
print('has original_code:', cur.fetchone())

# Check context/root_cause fields for code
cur.execute("SELECT COUNT(*) FROM sim_errors WHERE source IN ('github_issue','github_structured') AND context LIKE '%```%'")
print('context has code blocks:', cur.fetchone())

# Sample rows with code
cur.execute("SELECT id, error_type, original_code, context FROM sim_errors WHERE source='github_issue' AND original_code IS NOT NULL AND original_code != '' LIMIT 3")
rows = cur.fetchall()
for r in rows:
    print(f"\n--- ID {r[0]}, type={r[1]} ---")
    print(f"original_code[:200]: {str(r[2])[:200]}")
    print(f"context[:200]: {str(r[3])[:200]}")

# Sample context with ```
cur.execute("SELECT id, error_type, context FROM sim_errors WHERE source='github_issue' AND context LIKE '%```python%' LIMIT 3")
rows = cur.fetchall()
for r in rows:
    print(f"\n--- ID {r[0]}, type={r[1]} (context has ```python) ---")
    print(f"context[:500]: {str(r[2])[:500]}")

conn.close()
