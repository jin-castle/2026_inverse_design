import sqlite3

# Docker DB (WAL 없는 버전 - 현재 로컬 DB 기준)
db = sqlite3.connect('db/knowledge.db')

# MARL 저장 예제
rows = db.execute(
    "SELECT title, result_status, created_at FROM examples WHERE source_repo LIKE '%marl%' OR title LIKE '%MARL%' ORDER BY id DESC LIMIT 10"
).fetchall()
print(f'MARL 저장 예제: {len(rows)}개')
for r in rows:
    print(f'  {r[2][:16]} | {r[1]} | {r[0][:60]}')

# sim_errors 소스별
print()
rows2 = db.execute(
    "SELECT source, COUNT(*) FROM sim_errors GROUP BY source ORDER BY COUNT(*) DESC"
).fetchall()
total = db.execute("SELECT COUNT(*) FROM sim_errors").fetchone()[0]
verified = db.execute("SELECT COUNT(*) FROM sim_errors WHERE fix_worked=1").fetchone()[0]
print(f'sim_errors 총 {total}개 (verified: {verified}개)')
for r in rows2:
    print(f'  {r[0]}: {r[1]}개')

# errors 테이블 - MARL 저장된 것
rows3 = db.execute(
    "SELECT error_msg, source_type, created_at FROM errors WHERE source_type IN ('marl_auto','marl_fixed') ORDER BY id DESC LIMIT 5"
).fetchall()
print(f'\nMARL errors 저장: {len(rows3)}개')
for r in rows3:
    print(f'  [{r[1]}] {r[0][:60]}')

db.close()
