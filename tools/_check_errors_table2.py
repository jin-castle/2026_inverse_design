import sqlite3

db = sqlite3.connect('db/knowledge.db')
cur = db.cursor()

# errors 테이블 카테고리 분포 (category 컬럼)
cur.execute("SELECT category, COUNT(*) FROM errors GROUP BY category ORDER BY COUNT(*) DESC LIMIT 15")
print('에러 카테고리 분포:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}개')

# solution 있는 것 vs 없는 것
cur.execute("SELECT COUNT(*) FROM errors WHERE solution IS NOT NULL AND solution != ''")
print('\nsolution 있는 것:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM errors WHERE solution IS NULL OR solution = ''")
print('solution 없는 것:', cur.fetchone()[0])

# diagnose_engine이 왜 못 찾는지 직접 테스트
test_error = "AttributeError: 'NoneType' object has no attribute 'eps_func'"
cur.execute("""
    SELECT id, error_msg, category, solution
    FROM errors
    WHERE error_msg LIKE ? OR cause LIKE ?
    LIMIT 5
""", (f'%{test_error[:30]}%', f'%{test_error[:30]}%'))
rows = cur.fetchall()
print(f'\n테스트 검색 "{test_error[:30]}" → {len(rows)}건')

# FTS 검색 테스트
try:
    cur.execute("""
        SELECT e.id, e.error_msg, e.category
        FROM errors_fts ft
        JOIN errors e ON e.id = ft.rowid
        WHERE errors_fts MATCH ?
        LIMIT 5
    """, ('AttributeError',))
    rows = cur.fetchall()
    print(f'FTS "AttributeError" → {len(rows)}건')
    for r in rows:
        print(f'  [{r[1][:60]}] ({r[2]})')
except Exception as e:
    print('FTS 오류:', e)

db.close()
