import sqlite3, json

db = sqlite3.connect('db/knowledge.db')
cur = db.cursor()

# errors 테이블 구조
cur.execute("PRAGMA table_info(errors)")
cols = [r[1] for r in cur.fetchall()]
print('errors 컬럼:', cols)

# 샘플 데이터
cur.execute("SELECT * FROM errors LIMIT 3")
rows = cur.fetchall()
for row in rows:
    for c, v in zip(cols, row):
        print(f'  {c}: {str(v)[:150]}')
    print()

# 에러 카테고리 분포
cur.execute("SELECT error_type, COUNT(*) FROM errors GROUP BY error_type ORDER BY COUNT(*) DESC LIMIT 10")
print('에러 타입 분포:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}개')

# sim_errors 확인
cur.execute("PRAGMA table_info(sim_errors)")
cols2 = [r[1] for r in cur.fetchall()]
print('\nsim_errors 컬럼:', cols2)

db.close()
