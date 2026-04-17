"""meep-kb DB 전체 상태 감사"""
import sqlite3, json, re
from pathlib import Path

DB = Path(r"C:\Users\user\projects\meep-kb\db\knowledge.db")
conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 70)
print("meep-kb DB 전체 상태 감사")
print("=" * 70)

# 1. 테이블별 row 수
print("\n[1] 테이블별 데이터 수")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '%fts%' AND name NOT LIKE 'sqlite_%'")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    cnt = cur.fetchone()[0]
    print(f"  {t:<25} {cnt:>6}건")

# 2. examples 상태
print("\n[2] examples 테이블 상태")
cur.execute("SELECT COUNT(*) FROM examples WHERE code IS NULL OR LENGTH(code) < 100")
bad_code = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM examples WHERE tags LIKE '%cis%'")
cis_cnt = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM examples WHERE result_status IS NOT NULL")
has_result = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM examples WHERE result_images IS NOT NULL AND result_images != '[]'")
has_img = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM examples WHERE code IS NOT NULL AND LENGTH(code) > 100 AND LENGTH(code) < 500")
short_code = cur.fetchone()[0]
print(f"  코드 없거나 짧음(<100자): {bad_code}건")
print(f"  CIS 태그:                {cis_cnt}건")
print(f"  result_status 있음:      {has_result}건")
print(f"  result_images 있음:      {has_img}건")
print(f"  코드 100~500자 (스텁?):  {short_code}건")

# 스텁 코드 예시
cur.execute("""SELECT id, title, LENGTH(code) len, tags 
               FROM examples WHERE code IS NOT NULL AND LENGTH(code) < 500 
               ORDER BY len LIMIT 10""")
stubs = cur.fetchall()
if stubs:
    print("  스텁 코드 의심 항목:")
    for r in stubs:
        print(f"    [{r['id']}] {r['title'][:50]} ({r['len']}자) tags={r['tags'][:30]}")

# 3. CIS examples 상세
print("\n[3] CIS examples 상세 (ID 619~)")
cur.execute("""SELECT id, title, LENGTH(code) len, tags, result_status
               FROM examples WHERE tags LIKE '%cis%' ORDER BY id""")
for r in cur.fetchall():
    status = r['result_status'] or '없음'
    print(f"  [{r['id']}] {r['title'][:55]}")
    print(f"       코드:{r['len']}자 | tags:{r['tags'][:40]} | status:{status}")

# 4. patterns 상태
print("\n[4] patterns 테이블 상태")
cur.execute("SELECT COUNT(*) FROM patterns WHERE code_snippet IS NULL OR LENGTH(code_snippet) < 20")
bad_pat = cur.fetchone()[0]
cur.execute("SELECT pattern_name, LENGTH(code_snippet) len FROM patterns ORDER BY created_at DESC LIMIT 10")
pats = cur.fetchall()
print(f"  코드 없는 패턴: {bad_pat}건")
print("  최근 패턴:")
for p in pats:
    print(f"    {p['pattern_name']:<40} ({p['len']}자)")

# 5. concepts 상태
print("\n[5] concepts 상태")
cur.execute("SELECT id, name, name_ko, LENGTH(explanation) len, result_status FROM concepts ORDER BY id")
for r in cur.fetchall():
    print(f"  [{r['id']}] {r['name']:<30} ({r['len']}자) status={r['result_status'] or '없음'}")

# 6. errors 상태
print("\n[6] errors (오류 DB) 상태")
cur.execute("SELECT COUNT(*) FROM errors")
err_cnt = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM errors WHERE source_type='cis_repro_analysis'")
cis_err = cur.fetchone()[0]
cur.execute("SELECT category, COUNT(*) cnt FROM errors GROUP BY category ORDER BY cnt DESC LIMIT 8")
cats = cur.fetchall()
print(f"  전체: {err_cnt}건 | CIS 분석: {cis_err}건")
print("  카테고리별:")
for c in cats:
    print(f"    {c['category']:<35} {c['cnt']}건")

# 7. docs 상태
print("\n[7] docs 상태")
cur.execute("SELECT id, section, url, LENGTH(content) len FROM docs ORDER BY id DESC LIMIT 10")
for r in cur.fetchall():
    print(f"  [{r['id']}] {r['section'][:45]:<45} ({r['len']}자) url={r['url']}")

# 8. sim_errors_v2 상태
print("\n[8] sim_errors_v2 상태")
cur.execute("SELECT COUNT(*) FROM sim_errors_v2")
sv2 = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=1")
fixed = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=0")
unfixed = cur.fetchone()[0]
print(f"  전체: {sv2}건 | 수정 성공: {fixed}건 | 미해결: {unfixed}건")

# 9. FTS 인덱스 상태 확인
print("\n[9] FTS 인덱스 동기화 확인")
for t in ['examples', 'errors', 'concepts']:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {t}_fts")
        fts_cnt = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        real_cnt = cur.fetchone()[0]
        sync = "OK" if fts_cnt == real_cnt else f"MISMATCH! fts={fts_cnt} real={real_cnt}"
        print(f"  {t}_fts: {sync}")
    except Exception as e:
        print(f"  {t}_fts: 오류 - {e}")

# 10. notebooks 상태
print("\n[10] notebooks 상태")
cur.execute("SELECT COUNT(*) FROM notebooks")
nb_cnt = cur.fetchone()[0]
cur.execute("SELECT id, title, filename, cell_count FROM notebooks")
for r in cur.fetchall():
    print(f"  [{r['id']}] {r['title'][:50]} | {r['filename']} | {r['cell_count']}셀")

conn.close()
print("\n" + "=" * 70)
print("감사 완료")
print("=" * 70)
