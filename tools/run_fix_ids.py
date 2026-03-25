# -*- coding: utf-8 -*-
"""
fix_worked=0 실행 가능 레코드 단건씩 처리.
"""
import sys, sqlite3, time
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "tools"))
sys.path.insert(0, str(BASE / "api"))

DB_PATH = BASE / "db" / "knowledge.db"
TARGET_IDS = [4, 11, 30, 38, 43, 49, 52, 58, 65, 80, 93]

import importlib.util, os
from dotenv import load_dotenv
load_dotenv(str(BASE / ".env"))
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

spec = importlib.util.spec_from_file_location("vfv2", str(BASE / "tools" / "verified_fix_v2.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

print(f"처리 대상: {len(TARGET_IDS)}건 — IDs: {TARGET_IDS}")
print()

success = 0
fail = 0

for i, vid in enumerate(TARGET_IDS):
    print(f"[{i+1}/{len(TARGET_IDS)}] id={vid} ...", flush=True)

    # 이미 fix_worked=1이면 skip
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT fix_worked, error_type, original_code FROM sim_errors_v2 WHERE id=?",
        (vid,)
    ).fetchone()
    conn.close()

    if not row:
        print(f"  not found, skip")
        continue
    if row["fix_worked"] == 1:
        print(f"  already fix_worked=1, skip")
        success += 1
        continue

    try:
        conn2 = sqlite3.connect(str(DB_PATH))
        conn2.row_factory = sqlite3.Row
        full_row = conn2.execute("SELECT * FROM sim_errors_v2 WHERE id=?", (vid,)).fetchone()
        record = dict(full_row) if full_row else {}
        conn2.close()

        result = mod.process_record(record, API_KEY)
        if result and result.get("success"):
            print(f"  SUCCESS fix_worked=1", flush=True)
            success += 1
        else:
            reason = result.get("reason", "unknown") if result else "None"
            print(f"  FAIL: {reason}", flush=True)
            fail += 1
    except Exception as e:
        print(f"  ERROR: {e}", flush=True)
        fail += 1

    time.sleep(1)

print()
print("=" * 50)
conn = sqlite3.connect(str(DB_PATH))
fw = conn.execute(
    "SELECT fix_worked, COUNT(*) FROM sim_errors_v2 GROUP BY fix_worked"
).fetchall()
conn.close()
print("최종 fix_worked 현황:")
for f, c in fw:
    print(f"  fix_worked={f}: {c}건")
print(f"이번 실행: success={success}, fail={fail}")
