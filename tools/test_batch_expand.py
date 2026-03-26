# -*- coding: utf-8 -*-
"""
test_batch_expand.py — 배치 확장 실행 검증 스크립트
=====================================================
TEST 1: live_runs 총 건수 확인 (31건 이상)
TEST 2: sim_errors_v2 에러 유형별 분포 출력
TEST 3: 중복 실행 없음 확인 (code_hash UNIQUE 제약)
TEST 4: 성공률 계산 (success / total >= 50%)
TEST 5: 에러 건수 확인 (sim_errors_v2 WHERE source='live_run' COUNT >= 5)
"""
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"

def run_tests():
    conn = sqlite3.connect(str(DB_PATH))
    passed = 0
    failed = 0
    results = []

    # TEST 1: live_runs 총 건수 확인 (31건 이상)
    total = conn.execute("SELECT COUNT(*) FROM live_runs").fetchone()[0]
    if total >= 31:
        results.append(f"✅ TEST 1 PASSED: live_runs 총계 {total}건 (>= 31)")
        passed += 1
    else:
        results.append(f"❌ TEST 1 FAILED: live_runs 총계 {total}건 (< 31 목표)")
        failed += 1

    # TEST 2: sim_errors_v2 에러 유형별 분포 출력
    rows = conn.execute(
        "SELECT error_type, COUNT(*) FROM sim_errors_v2 GROUP BY error_type ORDER BY COUNT(*) DESC"
    ).fetchall()
    v2_total = conn.execute("SELECT COUNT(*) FROM sim_errors_v2").fetchone()[0]
    results.append(f"ℹ️  TEST 2 INFO: sim_errors_v2 에러 유형별 분포 (총 {v2_total}건):")
    if rows:
        for error_type, count in rows:
            results.append(f"     {error_type or 'None'}: {count}건")
        results.append(f"✅ TEST 2 PASSED: 에러 유형 분포 출력 완료")
        passed += 1
    else:
        results.append(f"⚠️  TEST 2 WARNING: sim_errors_v2 데이터 없음 (배치 실행 전일 수 있음)")
        passed += 1  # 배치 전에는 OK

    # TEST 3: 중복 실행 없음 확인 (code_hash UNIQUE 제약)
    try:
        dup_count = conn.execute(
            "SELECT COUNT(*) - COUNT(DISTINCT code_hash) FROM live_runs"
        ).fetchone()[0]
        if dup_count == 0:
            results.append(f"✅ TEST 3 PASSED: 중복 code_hash 없음 (UNIQUE 제약 정상)")
            passed += 1
        else:
            results.append(f"❌ TEST 3 FAILED: 중복 code_hash {dup_count}건 발견!")
            failed += 1
    except Exception as e:
        results.append(f"❌ TEST 3 ERROR: {e}")
        failed += 1

    # TEST 4: 성공률 계산 (success / total >= 50%)
    success_count = conn.execute(
        "SELECT COUNT(*) FROM live_runs WHERE status = 'success'"
    ).fetchone()[0]
    if total > 0:
        success_rate = success_count / total
        if success_rate >= 0.5:
            results.append(
                f"✅ TEST 4 PASSED: 성공률 {success_rate:.1%} ({success_count}/{total}) >= 50%"
            )
            passed += 1
        else:
            results.append(
                f"❌ TEST 4 FAILED: 성공률 {success_rate:.1%} ({success_count}/{total}) < 50%"
            )
            failed += 1
    else:
        results.append(f"❌ TEST 4 FAILED: live_runs 데이터 없음")
        failed += 1

    # TEST 5: 에러 건수 확인 (sim_errors_v2 WHERE source='live_run' COUNT >= 5)
    live_run_errors = conn.execute(
        "SELECT COUNT(*) FROM sim_errors_v2 WHERE source = 'live_run'"
    ).fetchone()[0]
    if live_run_errors >= 5:
        results.append(
            f"✅ TEST 5 PASSED: sim_errors_v2 (source='live_run') {live_run_errors}건 >= 5"
        )
        passed += 1
    else:
        results.append(
            f"❌ TEST 5 FAILED: sim_errors_v2 (source='live_run') {live_run_errors}건 < 5"
        )
        failed += 1

    conn.close()

    # 결과 출력
    print("\n" + "=" * 60)
    print("🧪 test_batch_expand.py 결과")
    print("=" * 60)
    for line in results:
        print(line)
    print("=" * 60)
    print(f"총 {passed + failed}개 테스트: {passed} PASSED, {failed} FAILED")
    if failed == 0:
        print("🎉 ALL PASSED!")
    else:
        print(f"⚠️  {failed}개 실패")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
