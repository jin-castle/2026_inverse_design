# -*- coding: utf-8 -*-
"""
kb_pipeline.py — MEEP KB 자동 오케스트레이터
=============================================
새 데이터가 들어오면 자동으로:
  Step 1: batch_live_runner  → 코드 실행 → live_runs + sim_errors_v2 저장
  Step 2: physics_enricher   → physics_cause/code_cause 채우기
  Step 3: verified_fix_v2    → LLM 수정 → Docker 검증

실행:
  python -X utf8 tools/kb_pipeline.py --source examples --limit 20
  python -X utf8 tools/kb_pipeline.py --steps enrich,fix --fix-limit 10
  python -X utf8 tools/kb_pipeline.py --steps fix --fix-limit 20
  python -X utf8 tools/kb_pipeline.py --source examples --limit 5 --dry-run
"""

import argparse
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"

# 경로 등록
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(BASE / "api"))

# .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(str(BASE / ".env"))
except ImportError:
    pass


# ──────────────────────────────────────────────────────────────────────────────
# 마크다운 클렌저
# ──────────────────────────────────────────────────────────────────────────────

def clean_code(code: str) -> str:
    """마크다운/노트북 텍스트에서 순수 Python 코드만 추출"""
    if not code:
        return code

    # 1. ```python ... ``` 블록 추출 (있으면 블록 내용만 사용)
    blocks = re.findall(r"```python\s*(.*?)```", code, re.DOTALL)
    if blocks:
        code = "\n\n".join(b.strip() for b in blocks)
        # 마지막에 import meep 포함 확인
        if "import meep" in code or "import meep as mp" in code:
            return _cleanup_lines(code)
        # import meep 없어도 블록 있으면 반환
        return _cleanup_lines(code)

    # 2. ``` 블록만 있는 경우 (language 없음)
    blocks = re.findall(r"```\s*(.*?)```", code, re.DOTALL)
    if blocks:
        merged = "\n\n".join(b.strip() for b in blocks)
        if "import meep" in merged or "import meep as mp" in merged:
            return _cleanup_lines(merged)

    # 3. Jupyter 노트북 셀 형식 제거
    lines = code.split("\n")
    cleaned = []
    skip_next = False
    for line in lines:
        # In [N]: / Out[N]: 제거
        if re.match(r"^(In|Out)\s*\[\s*\d*\s*\]:", line):
            skip_next = False
            continue
        # ## 헤더 제거
        if re.match(r"^#{1,6}\s+", line):
            continue
        cleaned.append(line)

    result = "\n".join(cleaned)
    return _cleanup_lines(result)


def _cleanup_lines(code: str) -> str:
    """연속 빈줄 정리"""
    # 3개 이상 연속 빈줄 → 2개로
    code = re.sub(r"\n{3,}", "\n\n", code)
    return code.strip()


def is_markdown_mixed(code: str) -> bool:
    """코드에 마크다운이 혼재하는지 판별"""
    if not code:
        return False
    lines = code.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            return True
        if re.match(r"^(In|Out)\s*\[\s*\d*\s*\]:", stripped):
            return True
        if re.match(r"^#{1,6}\s+\S", stripped):
            return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# DB 현황 쿼리
# ──────────────────────────────────────────────────────────────────────────────

def get_db_stats() -> dict:
    """DB 현황 통계 반환"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        live_runs = conn.execute("SELECT COUNT(*) FROM live_runs").fetchone()[0]
        sim_errors_v2 = conn.execute("SELECT COUNT(*) FROM sim_errors_v2").fetchone()[0]
        fix_worked_1 = conn.execute(
            "SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=1"
        ).fetchone()[0]
        fix_worked_0 = conn.execute(
            "SELECT COUNT(*) FROM sim_errors_v2 WHERE fix_worked=0"
        ).fetchone()[0]
        physics_null = conn.execute(
            "SELECT COUNT(*) FROM sim_errors_v2 WHERE physics_cause IS NULL OR physics_cause=''"
        ).fetchone()[0]
        conn.close()
        return {
            "live_runs": live_runs,
            "sim_errors_v2": sim_errors_v2,
            "fix_worked_1": fix_worked_1,
            "fix_worked_0": fix_worked_0,
            "physics_null": physics_null,
        }
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# 리포트 출력
# ──────────────────────────────────────────────────────────────────────────────

def print_report(
    steps: list,
    step1_stats: dict = None,
    step2_stats: dict = None,
    step3_stats: dict = None,
    db_before: dict = None,
    db_after: dict = None,
    source: str = "examples",
    limit: int = 20,
    enrich_model: str = "haiku",
    fix_limit: int = 10,
    dry_run: bool = False,
):
    """리포트 출력"""
    sep = "=" * 60
    print(f"\n{sep}")
    if dry_run:
        print("KB Pipeline 드라이런 결과")
    else:
        print("KB Pipeline 실행 결과")
    print(sep)

    if "run" in steps and step1_stats is not None:
        s = step1_stats
        print(f"\n[Step 1] batch_live_runner ({source}, limit={limit})")
        if dry_run:
            print(f"  [DRY-RUN] 실행 없이 계획만 출력")
            print(f"  대상: {s.get('total', 0)}건")
        else:
            print(f"  실행: {s.get('total', 0)}건 | "
                  f"성공: {s.get('success', 0)} | "
                  f"에러: {s.get('error', 0)} | "
                  f"timeout: {s.get('timeout', 0)} | "
                  f"MPI차단: {s.get('mpi_deadlock_risk', 0) + s.get('blocked', 0)}")

    if "enrich" in steps and step2_stats is not None:
        s = step2_stats
        print(f"\n[Step 2] physics_enricher ({enrich_model})")
        if dry_run:
            print(f"  [DRY-RUN] 대상: {s.get('total', 0)}건")
        else:
            print(f"  대상: {s.get('total', 0)}건 | "
                  f"완료: {s.get('success', 0)}건 | "
                  f"실패: {s.get('failed', 0)}건")

    if "fix" in steps and step3_stats is not None:
        s = step3_stats
        print(f"\n[Step 3] verified_fix_v2 (limit={fix_limit})")
        if dry_run:
            print(f"  [DRY-RUN] 대상: {s.get('total', 0)}건")
        else:
            print(f"  대상: {s.get('total', 0)}건 | "
                  f"fix_worked=1: {s.get('fixed', 0)}건 | "
                  f"실패: {s.get('failed', 0)}건 | "
                  f"skip: {s.get('skipped', 0)}건")

    # DB 현황
    db = db_after or db_before
    if db and "error" not in db:
        print(f"\nDB 현황:")
        print(f"  live_runs: {db.get('live_runs', '?')}건")
        v2 = db.get('sim_errors_v2', '?')
        fw1 = db.get('fix_worked_1', '?')
        print(f"  sim_errors_v2: {v2}건 (fix_worked=1: {fw1}건)")
        if db_before and db_after and "error" not in db_before:
            delta_lr = db_after.get('live_runs', 0) - db_before.get('live_runs', 0)
            delta_v2 = db_after.get('sim_errors_v2', 0) - db_before.get('sim_errors_v2', 0)
            delta_fw = db_after.get('fix_worked_1', 0) - db_before.get('fix_worked_1', 0)
            if delta_lr or delta_v2 or delta_fw:
                print(f"  증가: live_runs +{delta_lr} | sim_errors_v2 +{delta_v2} | fix_worked=1 +{delta_fw}")

    print(f"{sep}\n")


# ──────────────────────────────────────────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    source: str = "examples",
    limit: int = 20,
    timeout: int = 60,
    steps: list = None,
    fix_limit: int = 10,
    enrich_model: str = "haiku",
    dry_run: bool = False,
) -> dict:
    """
    KB 파이프라인 실행.
    반환: {step1, step2, step3, db_before, db_after}
    """
    if steps is None:
        steps = ["run", "enrich", "fix"]

    print(f"\n{'=' * 60}")
    print(f"KB Pipeline 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  steps: {steps}")
    print(f"  source: {source}, limit: {limit}")
    print(f"  enrich_model: {enrich_model}, fix_limit: {fix_limit}")
    print(f"  dry_run: {dry_run}")
    print(f"{'=' * 60}")

    db_before = get_db_stats()
    step1_stats = None
    step2_stats = None
    step3_stats = None

    # ── Step 1: batch_live_runner ──────────────────────────────────────────
    if "run" in steps:
        print(f"\n▶ Step 1: batch_live_runner 실행...")
        try:
            from batch_live_runner import run_batch
            step1_stats = run_batch(
                source=source,
                limit=limit,
                dry_run=dry_run,
                timeout=timeout,
                skip_checkpoint=False,
            )
        except Exception as e:
            print(f"  ❌ Step 1 실패: {e}")
            step1_stats = {"total": 0, "error": str(e)}

    # ── Step 2: physics_enricher ────────────────────────────────────────────
    if "enrich" in steps:
        print(f"\n▶ Step 2: physics_enricher 실행...")
        try:
            from physics_enricher import enrich_pending
            step2_stats = enrich_pending(limit=limit, model=enrich_model, dry_run=dry_run)
        except Exception as e:
            print(f"  ❌ Step 2 실패: {e}")
            step2_stats = {"total": 0, "success": 0, "failed": 0, "error": str(e)}

    # ── Step 3: verified_fix_v2 ─────────────────────────────────────────────
    if "fix" in steps:
        print(f"\n▶ Step 3: verified_fix_v2 실행...")
        if dry_run:
            # dry_run이면 대상 조회만
            try:
                from verified_fix_v2 import get_unfixed_records, is_markdown_mixed
                records = get_unfixed_records(limit=fix_limit)
                skip_md = sum(1 for r in records if is_markdown_mixed(r.get("original_code") or ""))
                step3_stats = {
                    "total": len(records),
                    "fixed": 0,
                    "failed": 0,
                    "skipped": skip_md,
                    "dry_run": True,
                }
                print(f"  [DRY-RUN] 대상: {len(records)}건 (마크다운 skip 예상: {skip_md}건)")
            except Exception as e:
                print(f"  ❌ Step 3 dry_run 조회 실패: {e}")
                step3_stats = {"total": 0, "fixed": 0, "failed": 0, "skipped": 0}
        else:
            try:
                from verified_fix_v2 import fix_pending
                step3_stats = fix_pending(limit=fix_limit, skip_markdown=True)
            except Exception as e:
                print(f"  ❌ Step 3 실패: {e}")
                step3_stats = {"total": 0, "fixed": 0, "failed": 0, "skipped": 0, "error": str(e)}

    db_after = get_db_stats() if not dry_run else db_before

    # 리포트 출력
    print_report(
        steps=steps,
        step1_stats=step1_stats,
        step2_stats=step2_stats,
        step3_stats=step3_stats,
        db_before=db_before,
        db_after=db_after,
        source=source,
        limit=limit,
        enrich_model=enrich_model,
        fix_limit=fix_limit,
        dry_run=dry_run,
    )

    return {
        "step1": step1_stats,
        "step2": step2_stats,
        "step3": step3_stats,
        "db_before": db_before,
        "db_after": db_after,
    }


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="KB Pipeline — MEEP KB 자동 오케스트레이터",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 전체 파이프라인
  python tools/kb_pipeline.py --source examples --limit 20

  # 특정 단계만
  python tools/kb_pipeline.py --steps enrich,fix --fix-limit 10
  python tools/kb_pipeline.py --steps fix --fix-limit 20

  # 드라이런
  python tools/kb_pipeline.py --source examples --limit 5 --dry-run
        """,
    )
    parser.add_argument(
        "--source",
        choices=["examples", "github_issues", "sim_errors_unverified"],
        default="examples",
        help="배치 실행 소스 (기본: examples)",
    )
    parser.add_argument("--limit", type=int, default=20, help="배치 실행 건수 (기본: 20)")
    parser.add_argument("--timeout", type=int, default=60, help="실행 timeout 초 (기본: 60)")
    parser.add_argument(
        "--steps",
        default="run,enrich,fix",
        help="실행할 단계 콤마 구분 (기본: run,enrich,fix)",
    )
    parser.add_argument("--fix-limit", type=int, default=10, help="verified_fix_v2 처리 건수 (기본: 10)")
    parser.add_argument(
        "--enrich-model",
        choices=["haiku", "sonnet"],
        default="haiku",
        help="physics_enricher LLM 모델 (기본: haiku)",
    )
    parser.add_argument("--dry-run", action="store_true", help="실행 없이 계획만 출력")
    args = parser.parse_args()

    # steps 파싱
    valid_steps = {"run", "enrich", "fix"}
    steps = [s.strip() for s in args.steps.split(",")]
    invalid = [s for s in steps if s not in valid_steps]
    if invalid:
        print(f"❌ 알 수 없는 steps: {invalid}. 선택: {valid_steps}", file=sys.stderr)
        sys.exit(1)

    run_pipeline(
        source=args.source,
        limit=args.limit,
        timeout=args.timeout,
        steps=steps,
        fix_limit=args.fix_limit,
        enrich_model=args.enrich_model,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
