# -*- coding: utf-8 -*-
"""sim_errors_v2 데이터가 /api/diagnose 응답에 실제로 포함되는지 확인"""
import urllib.request, json

BASE = "http://localhost:8765"

def post(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body,
                                  headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=30)
    return json.loads(r.read())

# EigenMode 에러 쿼리
r = post("/api/diagnose", {
    "code": "src = mp.EigenmodeSource(mp.GaussianSource(1.0, fwidth=0.2), eig_band=0)",
    "error": "meep: EigenmodeSource: cannot find mode 0",
    "n": 5
})

print(f"top_score: {r['top_score']}")
print(f"db_sufficient: {r['db_sufficient']}")
print(f"suggestions 수: {len(r['suggestions'])}")
print()

for i, s in enumerate(r["suggestions"][:3]):
    print(f"[{i+1}] type={s.get('type','')} score={s.get('score',0):.2f}")
    print(f"  title:         {s.get('title','')[:60]}")
    print(f"  cause:         {s.get('cause','')[:80]}")
    print(f"  solution:      {s.get('solution','')[:80]}")
    print(f"  physics_cause: {str(s.get('physics_cause',''))[:80]}")
    print(f"  fix_type:      {s.get('fix_type','')}")
    print(f"  root_cause:    {str(s.get('root_cause_chain',''))[:60]}")
    print(f"  symptom:       {s.get('symptom','')}")
    print()

# fix_worked=1 v2 레코드 수 확인
import sqlite3
conn = sqlite3.connect("C:/Users/user/projects/meep-kb/db/knowledge.db")
v2_fixed = conn.execute(
    "SELECT error_type, COUNT(*) FROM sim_errors_v2 WHERE fix_worked=1 GROUP BY error_type ORDER BY COUNT(*) DESC"
).fetchall()
print("sim_errors_v2 fix_worked=1 분포:")
for t, c in v2_fixed:
    print(f"  {t}: {c}")
conn.close()
