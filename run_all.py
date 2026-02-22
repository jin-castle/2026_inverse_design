#!/usr/bin/env python3
"""
MEEP-KB 전체 구축 실행기
순서: 01 DB 초기화 → 02 이슈 수집 → 03 연구자 코드 → 04 문서 → 05 로그 → 06 Skill 생성

사용법:
  python run_all.py           # 전체 실행
  python run_all.py --step 2  # 특정 스텝만
  python run_all.py --from 3  # 3단계부터 재시작
"""
import subprocess, sys, argparse, time
from pathlib import Path

STEPS = [
    (1, "crawlers/01_db_setup.py",           "DB 초기화"),
    (2, "crawlers/02_fetch_meep_issues.py",  "MEEP/MPB 이슈 수집 (느림)"),
    (3, "crawlers/03_fetch_researcher_repos.py", "연구자 코드 수집"),
    (4, "crawlers/04_fetch_official_docs.py","공식 문서 수집"),
    (5, "crawlers/05_parse_local_logs.py",   "로컬 로그 파싱"),
    (6, "crawlers/06_export_skill.py",       "Skill 자동 생성"),
]

BASE = Path(__file__).parent

def run_step(num, script, desc):
    print(f"\n{'='*60}")
    print(f"[Step {num}] {desc}")
    print(f"{'='*60}")
    start = time.time()
    r = subprocess.run([sys.executable, BASE / script], cwd=BASE)
    elapsed = time.time() - start
    if r.returncode == 0:
        print(f"\n✅ Step {num} 완료 ({elapsed:.0f}초)")
        return True
    else:
        print(f"\n❌ Step {num} 실패 (종료코드 {r.returncode})")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", type=int, help="특정 스텝만 실행")
    parser.add_argument("--from", dest="from_step", type=int, default=1, help="이 스텝부터 실행")
    args = parser.parse_args()

    steps_to_run = STEPS
    if args.step:
        steps_to_run = [(n, s, d) for n, s, d in STEPS if n == args.step]
    else:
        steps_to_run = [(n, s, d) for n, s, d in STEPS if n >= args.from_step]

    print(f"MEEP-KB 구축 시작 — {len(steps_to_run)}단계")
    for num, script, desc in steps_to_run:
        ok = run_step(num, script, desc)
        if not ok and num <= 1:
            print("DB 초기화 실패. 중단.")
            sys.exit(1)
        # Step 2 (이슈 수집)는 오래 걸리므로 완료 후 계속
    print(f"\n{'='*60}")
    print("✅ MEEP-KB 구축 완료!")
    print("검색: python query/search.py '검색어'")
    print("통계: python query/search.py --stats")

if __name__ == "__main__":
    main()
