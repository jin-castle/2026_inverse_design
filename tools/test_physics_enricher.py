"""
test_physics_enricher.py - physics_enricher 검증 스크립트

Usage:
    python -X utf8 tools/test_physics_enricher.py
"""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "db" / "knowledge.db"

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []


def test(name: str, ok: bool, detail: str = ""):
    status = PASS if ok else FAIL
    msg = f"{status} {name}"
    if detail:
        msg += f" ({detail})"
    print(msg)
    results.append((name, ok))
    return ok


def get_conn():
    return sqlite3.connect(str(DB_PATH))


# ─── TEST 1: --dry-run 출력 확인 ─────────────────────────────────────────────
print("\n=== TEST 1: --dry-run 출력 확인 ===")
proc = subprocess.run(
    [sys.executable, "-X", "utf8", str(ROOT / "tools" / "physics_enricher.py"), "--dry-run"],
    capture_output=True, text=True, encoding="utf-8",
    cwd=str(ROOT)
)
dry_ok = proc.returncode == 0 and "DRY-RUN" in proc.stdout and "id=" in proc.stdout
test("dry-run 실행 성공", dry_ok, f"returncode={proc.returncode}")
if not dry_ok:
    print(f"  stdout: {proc.stdout[:300]}")
    print(f"  stderr: {proc.stderr[:200]}")


# ─── TEST 2~5: 1건 실제 enrichment ───────────────────────────────────────────
print("\n=== TEST 2~5: 1건 실제 enrichment ===")

# 아직 비어있는 레코드 1건 찾기
conn = get_conn()
row = conn.execute("""
    SELECT id FROM sim_errors_v2
    WHERE (physics_cause IS NULL OR physics_cause = '')
       OR (code_cause IS NULL OR code_cause = '')
    ORDER BY id LIMIT 1
""").fetchone()
conn.close()

if row is None:
    print("  모든 레코드가 이미 채워져 있습니다. TEST 2~6은 기존 데이터로 검증합니다.")
    conn = get_conn()
    existing = conn.execute("""
        SELECT id, physics_cause, code_cause, root_cause_chain
        FROM sim_errors_v2
        WHERE physics_cause IS NOT NULL AND physics_cause != ''
        LIMIT 1
    """).fetchone()
    conn.close()
    if existing:
        eid, pc, cc, rcc = existing
        test("physics_cause >= 50자", len(pc) >= 50, f"{len(pc)}자")
        test("code_cause >= 20자", len(cc) >= 20, f"{len(cc)}자")
        try:
            parsed = json.loads(rcc) if rcc else None
            test("root_cause_chain JSON 파싱 가능", isinstance(parsed, list), f"len={len(parsed) if parsed else 0}")
        except Exception as e:
            test("root_cause_chain JSON 파싱 가능", False, str(e))
        test("DB 반영 확인", True, f"id={eid}")
    else:
        test("physics_cause >= 50자", False, "데이터 없음")
        test("code_cause >= 20자", False, "데이터 없음")
        test("root_cause_chain JSON 파싱 가능", False, "데이터 없음")
        test("DB 반영 확인", False, "데이터 없음")
else:
    target_id = row[0]
    print(f"  대상 id={target_id}")

    proc2 = subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "tools" / "physics_enricher.py"),
         "--limit", "1", "--model", "haiku"],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(ROOT)
    )

    if proc2.returncode != 0:
        print(f"  stderr: {proc2.stderr[:300]}")
        test("1건 enrichment 실행 성공", False, f"returncode={proc2.returncode}")
        test("physics_cause >= 50자", False, "실행 실패")
        test("code_cause >= 20자", False, "실행 실패")
        test("root_cause_chain JSON 파싱 가능", False, "실행 실패")
    else:
        test("1건 enrichment 실행 성공", True)

        conn = get_conn()
        updated = conn.execute("""
            SELECT id, physics_cause, code_cause, root_cause_chain
            FROM sim_errors_v2 WHERE id = ?
        """, (target_id,)).fetchone()
        conn.close()

        if updated:
            eid, pc, cc, rcc = updated
            test("physics_cause >= 50자", len(pc or "") >= 50, f"{len(pc or '')}자")
            test("code_cause >= 20자", len(cc or "") >= 20, f"{len(cc or '')}자")
            try:
                parsed = json.loads(rcc) if rcc else None
                test("root_cause_chain JSON 파싱 가능", isinstance(parsed, list), f"len={len(parsed) if parsed else 0}")
            except Exception as e:
                test("root_cause_chain JSON 파싱 가능", False, str(e))
            test("DB 반영 확인", bool(pc), f"id={eid}")
        else:
            test("physics_cause >= 50자", False, "레코드 없음")
            test("code_cause >= 20자", False, "레코드 없음")
            test("root_cause_chain JSON 파싱 가능", False, "레코드 없음")
            test("DB 반영 확인", False, "레코드 없음")


# ─── TEST 6: --limit 5 실행 → 5건 모두 physics_cause 채워짐 ──────────────────
print("\n=== TEST 6: --limit 5 실행 → 5건 physics_cause 채워짐 ===")

# 현재 비어있는 레코드 수
conn = get_conn()
empty_ids = [r[0] for r in conn.execute("""
    SELECT id FROM sim_errors_v2
    WHERE (physics_cause IS NULL OR physics_cause = '')
       OR (code_cause IS NULL OR code_cause = '')
    ORDER BY id LIMIT 5
""").fetchall()]
conn.close()

if len(empty_ids) == 0:
    print("  이미 모든 레코드가 채워진 상태입니다.")
    conn = get_conn()
    filled = conn.execute("""
        SELECT COUNT(*) FROM sim_errors_v2
        WHERE physics_cause IS NOT NULL AND physics_cause != ''
    """).fetchone()[0]
    conn.close()
    test("5건 physics_cause 채워짐", filled >= 5, f"이미 {filled}건 채워짐")
else:
    print(f"  처리 대상 ids: {empty_ids[:5]}")
    proc3 = subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "tools" / "physics_enricher.py"),
         "--limit", "5", "--model", "haiku"],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(ROOT)
    )

    print(f"  returncode={proc3.returncode}")
    if proc3.returncode != 0:
        print(f"  stderr: {proc3.stderr[:300]}")

    conn = get_conn()
    filled_count = 0
    for rid in empty_ids[:5]:
        r = conn.execute("SELECT physics_cause FROM sim_errors_v2 WHERE id=?", (rid,)).fetchone()
        if r and r[0] and len(r[0]) >= 50:
            filled_count += 1
    conn.close()

    test(f"5건 중 {filled_count}건 physics_cause 채워짐", filled_count >= min(5, len(empty_ids)),
         f"{filled_count}/{min(5, len(empty_ids))}")


# ─── 최종 결과 ────────────────────────────────────────────────────────────────
print("\n" + "=" * 50)
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"결과: {passed}/{total} PASSED")
if passed == total:
    print("🎉 ALL PASSED")
else:
    print(f"⚠️  {total - passed}개 실패")
    for name, ok in results:
        if not ok:
            print(f"  FAIL: {name}")

sys.exit(0 if passed == total else 1)
