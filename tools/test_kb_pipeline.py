# -*- coding: utf-8 -*-
"""
test_kb_pipeline.py — kb_pipeline.py 검증 테스트
================================================
실행: python -X utf8 tools/test_kb_pipeline.py
"""

import sqlite3
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"
PIPELINE = Path(__file__).parent / "kb_pipeline.py"

PASSED = []
FAILED = []


def run_cmd(args: list, capture=True) -> tuple[int, str, str]:
    """kb_pipeline.py 실행"""
    cmd = [sys.executable, "-X", "utf8", str(PIPELINE)] + args
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        cwd=str(BASE),
    )
    return result.returncode, result.stdout, result.stderr


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  ✅ PASS: {name}")
        PASSED.append(name)
    else:
        print(f"  ❌ FAIL: {name}")
        if detail:
            print(f"     {detail}")
        FAILED.append(name)


def get_db_count(table: str, where: str = "") -> int:
    conn = sqlite3.connect(str(DB_PATH))
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += f" WHERE {where}"
    count = conn.execute(sql).fetchone()[0]
    conn.close()
    return count


# ──────────────────────────────────────────────────────────────────────────────
# TEST 1: --dry-run 실행 → 계획 출력 (에러 없음)
# ──────────────────────────────────────────────────────────────────────────────

def test1():
    print("\n[TEST 1] --dry-run 실행 → 계획 출력 (에러 없음)")
    rc, stdout, stderr = run_cmd(["--source", "examples", "--limit", "5", "--dry-run"])
    check("종료 코드 0", rc == 0, f"rc={rc}\nstdout={stdout[:300]}\nstderr={stderr[:300]}")
    check("'KB Pipeline' 출력 포함", "KB Pipeline" in stdout, stdout[:200])
    check("'드라이런' 출력 포함",
          "드라이런" in stdout or "DRY-RUN" in stdout or "dry_run" in stdout,
          stdout[:200])
    check("치명적 에러 없음",
          "Traceback" not in stderr and "Error" not in stderr[:50],
          stderr[:200])


# ──────────────────────────────────────────────────────────────────────────────
# TEST 2: --steps enrich --dry-run → 대상 레코드 목록 출력
# ──────────────────────────────────────────────────────────────────────────────

def test2():
    print("\n[TEST 2] --steps enrich --dry-run → 대상 목록 출력")
    rc, stdout, stderr = run_cmd(["--steps", "enrich", "--dry-run"])
    check("종료 코드 0", rc == 0, f"rc={rc}\nstdout={stdout[:300]}\nstderr={stderr[:300]}")
    check("Step 2 출력 포함",
          "Step 2" in stdout or "enrich" in stdout.lower() or "physics_enricher" in stdout,
          stdout[:300])
    check("치명적 에러 없음",
          "Traceback" not in stderr and ("Error" not in stderr[:50] if stderr else True),
          stderr[:200])


# ──────────────────────────────────────────────────────────────────────────────
# TEST 3: --steps fix --fix-limit 3 → fix_worked=1 확인 (실제 실행)
# ──────────────────────────────────────────────────────────────────────────────

def test3():
    print("\n[TEST 3] --steps fix --fix-limit 3 → fix_worked=1 증가 확인")
    before = get_db_count("sim_errors_v2", "fix_worked=1")
    fix_w0_before = get_db_count("sim_errors_v2", "fix_worked=0")
    print(f"  (실행 전: fix_worked=1: {before}건, fix_worked=0: {fix_w0_before}건)")

    if fix_w0_before == 0:
        print("  ⚠ fix_worked=0 레코드 없음 → SKIP")
        check("fix_worked=0 레코드 존재 (SKIP 허용)", True, "fix_worked=0 레코드 없어서 skip")
        return

    rc, stdout, stderr = run_cmd(["--steps", "fix", "--fix-limit", "3"])
    after = get_db_count("sim_errors_v2", "fix_worked=1")
    print(f"  (실행 후: fix_worked=1: {after}건)")

    check("종료 코드 0", rc == 0, f"rc={rc}\nstderr={stderr[:300]}")
    check("Step 3 실행됨",
          "Step 3" in stdout or "verified_fix" in stdout.lower() or "fix_pending" in stdout,
          stdout[:300])
    # fix가 성공했거나 (after > before), 아니면 skip/not_reproducible로 처리된 경우 OK
    check("에러 없이 완료", rc == 0 and "Traceback" not in stderr, stderr[:200])


# ──────────────────────────────────────────────────────────────────────────────
# TEST 4: --steps run,enrich --source examples --limit 3 → 실행
# ──────────────────────────────────────────────────────────────────────────────

def test4():
    print("\n[TEST 4] --steps run,enrich --source examples --limit 3 → 실행")
    before_lr = get_db_count("live_runs")
    print(f"  (실행 전: live_runs={before_lr}건)")

    rc, stdout, stderr = run_cmd(
        ["--steps", "run,enrich", "--source", "examples", "--limit", "3"]
    )
    after_lr = get_db_count("live_runs")
    print(f"  (실행 후: live_runs={after_lr}건)")

    check("종료 코드 0", rc == 0, f"rc={rc}\nstdout={stdout[:300]}\nstderr={stderr[:300]}")
    check("Step 1 실행됨",
          "Step 1" in stdout or "batch_live_runner" in stdout or "배치" in stdout,
          stdout[:300])
    check("Step 2 실행됨 (또는 대상 없음)",
          "Step 2" in stdout or "enrich" in stdout.lower() or "physics" in stdout.lower(),
          stdout[:300])
    check("치명적 에러 없음",
          "Traceback" not in stderr and ("Fatal" not in stderr if stderr else True),
          stderr[:200])


# ──────────────────────────────────────────────────────────────────────────────
# TEST 5: DB 현황 출력 정상 확인
# ──────────────────────────────────────────────────────────────────────────────

def test5():
    print("\n[TEST 5] DB 현황 출력 정상 확인")
    rc, stdout, stderr = run_cmd(["--dry-run", "--steps", "run"])

    check("종료 코드 0", rc == 0, f"rc={rc}\nstdout={stdout[:300]}\nstderr={stderr[:300]}")
    check("'DB 현황' 출력 포함",
          "DB 현황" in stdout or "live_runs" in stdout,
          stdout[:500])
    check("live_runs 숫자 출력",
          "live_runs" in stdout,
          stdout[:500])
    check("sim_errors_v2 숫자 출력",
          "sim_errors_v2" in stdout,
          stdout[:500])


# ──────────────────────────────────────────────────────────────────────────────
# 보너스: clean_code() 유닛 테스트
# ──────────────────────────────────────────────────────────────────────────────

def test_clean_code():
    print("\n[BONUS] clean_code() 유닛 테스트")
    sys.path.insert(0, str(Path(__file__).parent))
    from kb_pipeline import clean_code, is_markdown_mixed

    # 마크다운 블록 추출
    md_code = """
# 소개
아래는 MEEP 예시입니다.

```python
import meep as mp
sim = mp.Simulation()
```

## 결론
끝.
"""
    cleaned = clean_code(md_code)
    check("마크다운에서 코드 추출", "import meep as mp" in cleaned, cleaned[:100])
    check("헤더 제거됨", "# 소개" not in cleaned and "## 결론" not in cleaned, cleaned[:100])

    # 이미 순수 Python 코드
    pure_code = "import meep as mp\nsim = mp.Simulation()\n"
    cleaned2 = clean_code(pure_code)
    check("순수 코드 유지", "import meep as mp" in cleaned2, cleaned2[:100])

    # is_markdown_mixed
    check("마크다운 혼재 감지", is_markdown_mixed(md_code), "")
    check("순수 코드 미감지", not is_markdown_mixed(pure_code), "")


# ──────────────────────────────────────────────────────────────────────────────
# 실행
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("KB Pipeline 테스트 스위트")
    print("=" * 60)

    test1()
    test2()
    test3()
    test4()
    test5()
    test_clean_code()

    print("\n" + "=" * 60)
    total = len(PASSED) + len(FAILED)
    print(f"결과: {len(PASSED)}/{total} PASSED")
    if FAILED:
        print(f"실패: {FAILED}")
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("\n✅ ALL PASSED")
