# -*- coding: utf-8 -*-
import sqlite3, re, sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"

def has_markdown(code):
    if not code: return True
    markers = ["```", "## ", "**", "---\n", ">>> ", "In [", "Out[", "# %%"]
    for m in markers:
        if m in code: return True
    if "import meep" not in code and "import mp " not in code:
        return True
    return False

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT id, error_type, original_code FROM sim_errors_v2
    WHERE fix_worked=0
      AND error_type NOT IN ('Timeout','MPIDeadlockRisk','Unknown','')
      AND original_code IS NOT NULL AND original_code != ''
    ORDER BY id LIMIT 20
""").fetchall()

print(f"fix_worked=0 대상 ({len(rows)}건):")
runnable_ids = []
for r in rows:
    md = has_markdown(r["original_code"] or "")
    code_len = len(r["original_code"] or "")
    flag = "SKIP(md)" if md else "OK"
    print(f"  id={r['id']:3d} [{r['error_type']:20s}] {flag} len={code_len}")
    if not md:
        runnable_ids.append(r["id"])

print(f"\n실행 가능: {len(runnable_ids)}건 / ids: {runnable_ids[:10]}")

# fix_worked 현황
fw = conn.execute("SELECT fix_worked, COUNT(*) FROM sim_errors_v2 GROUP BY fix_worked").fetchall()
print("\nfix_worked 현황:")
for f, c in fw:
    print(f"  fix_worked={f}: {c}건")
conn.close()
