import sqlite3

# 컨테이너 UTC 기준 → KST 16:00~17:00 = UTC 07:00~08:00
# 컨테이너 현재시각: UTC 09:59 → KST 18:59

conn = sqlite3.connect('/app/db/knowledge.db')
c = conn.cursor()

print("=== patterns 최근 10개 ===")
c.execute("SELECT id, pattern_name, created_at FROM patterns ORDER BY created_at DESC LIMIT 10")
for r in c.fetchall():
    print(r)

print()
print("=== 오늘(2026-03-03) UTC 기준 전체 업데이트 ===")
for tbl in ['errors', 'examples', 'patterns', 'docs']:
    c.execute(f"SELECT COUNT(*) FROM {tbl} WHERE created_at >= '2026-03-03'")
    cnt = c.fetchone()[0]
    print(f"  {tbl}: 오늘 {cnt}개")

print()
print("=== KST 16:00~17:00 = UTC 07:00~08:00 패턴 ===")
for tbl in ['errors', 'examples', 'patterns', 'docs']:
    c.execute(f"SELECT COUNT(*) FROM {tbl} WHERE created_at >= '2026-03-03 07:00:00' AND created_at < '2026-03-03 08:00:00'")
    cnt = c.fetchone()[0]
    if cnt > 0:
        print(f"  {tbl}: {cnt}개")

print()
print("=== sim_runs 전체 ===")
c.execute("SELECT * FROM sim_runs ORDER BY created_at DESC")
for r in c.fetchall():
    print(dict(zip([d[0] for d in c.description], r)))

print()
print("=== sim_errors 전체 ===")
c.execute("SELECT id, error_type, created_at, SUBSTR(error_message, 1, 80) FROM sim_errors ORDER BY created_at DESC")
for r in c.fetchall():
    print(r)

print()
print("=== patterns 오늘 전체 (UTC 03:00 이후) ===")
c.execute("SELECT id, pattern_name, use_case, created_at FROM patterns WHERE created_at >= '2026-03-03 03:00:00' ORDER BY created_at")
for r in c.fetchall():
    print(r)

conn.close()
