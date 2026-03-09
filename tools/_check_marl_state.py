import sqlite3
db = sqlite3.connect('db/knowledge.db')
cur = db.cursor()

cur.execute("SELECT source_type, COUNT(*) FROM errors GROUP BY source_type")
print('errors 소스타입:', cur.fetchall())

cur.execute("SELECT source, COUNT(*) FROM sim_errors GROUP BY source")
print('sim_errors 소스:', cur.fetchall())

# MARL에서 저장한 데이터 확인
cur.execute("SELECT error_msg, solution FROM errors WHERE source_type='marl_auto' LIMIT 3")
for r in cur.fetchall():
    print(f'MARL 에러: [{r[0][:60]}] | 해결: [{r[1][:60]}]')

# GitHub issues 중 solution이 토론 텍스트인 것 샘플
cur.execute("""
    SELECT error_msg, solution FROM errors 
    WHERE source_type='github_issue' AND solution NOT LIKE '%```%' 
    AND LENGTH(solution) > 200
    LIMIT 3
""")
print('\nGitHub issue (코드없는 긴 solution):')
for r in cur.fetchall():
    print(f'  에러: {r[0][:60]}')
    print(f'  해결: {r[1][:120]}')
    print()
db.close()
