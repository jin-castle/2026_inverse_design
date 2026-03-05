import sqlite3
conn = sqlite3.connect('/app/db/knowledge.db')

print("=== DFT/Field 관련 패턴 ===")
rows = conn.execute(
    "SELECT id, pattern_name, description, use_case, length(code_snippet) FROM patterns WHERE id IN (5,6,7,8,9,56,57,44,47,48) ORDER BY id"
).fetchall()
for r in rows:
    print(f'[{r[0]}] {r[1]} | code:{r[4]}자')
    print(f'  desc: {str(r[2])[:120]}')
    print(f'  use_case: {str(r[3])[:80]}')
    print()

print("=== 패턴 author_repo 통계 ===")
rows2 = conn.execute(
    "SELECT author_repo, COUNT(*) FROM patterns GROUP BY author_repo ORDER BY COUNT(*) DESC"
).fetchall()
for r in rows2:
    print(f'  {r[0]}: {r[1]}건')
