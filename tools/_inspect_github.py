import sqlite3
conn = sqlite3.connect("db/knowledge.db")

# sim_errors 컬럼 확인
cols = [r[1] for r in conn.execute("PRAGMA table_info(sim_errors)").fetchall()]
print("sim_errors 컬럼:", cols)

# github_issue 샘플
rows = conn.execute("""SELECT id, error_type, error_message, LENGTH(original_code) FROM sim_errors 
    WHERE source='github_issue' LIMIT 5""").fetchall()
for r in rows:
    print(f"id={r[0]}, error_type={r[1]}, code_len={r[3]}, msg={str(r[2])[:80]}")

# sim_errors_v2 컬럼
cols2 = [r[1] for r in conn.execute("PRAGMA table_info(sim_errors_v2)").fetchall()]
print("\nsim_errors_v2 컬럼:", cols2[:12])

# github_issue 코드 포함 여부
r = conn.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE original_code IS NOT NULL AND LENGTH(original_code) > 50").fetchone()
print(f"\nsim_errors_v2 코드 있는 것: {r[0]}건")

conn.close()
