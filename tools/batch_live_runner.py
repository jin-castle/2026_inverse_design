# -*- coding: utf-8 -*-
"""
batch_live_runner.py — Phase 3: 배치 실행기
============================================
audit_report.json을 기반으로 examples/github_issues/sim_errors를
배치 실행하고 결과를 DB에 저장.

실행:
  python tools/batch_live_runner.py --source examples --limit 20 --dry-run
  python tools/batch_live_runner.py --source examples --limit 50 --timeout 120
"""
import argparse, json, sqlite3, sys, time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
sys.path.insert(0, str(Path(__file__).parent))

from live_runner import run_code
from error_collector import collect, migrate_db

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"
TOOLS_DIR = Path(__file__).parent
REPORT_PATH = TOOLS_DIR / "audit_report.json"
CHECKPOINT_PATH = TOOLS_DIR / "batch_checkpoint.json"


# ──────────────────────────────────────────────────────────────────────────────
# audit_report.json 로드 (없으면 data_auditor 자동 실행)
# ──────────────────────────────────────────────────────────────────────────────

def load_audit_report() -> dict:
    if REPORT_PATH.exists():
        return json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    print("⚠️  audit_report.json 없음 → data_auditor 자동 실행...")
    import data_auditor
    return data_auditor.run_audit()


# ──────────────────────────────────────────────────────────────────────────────
# 체크포인트
# ──────────────────────────────────────────────────────────────────────────────

def load_checkpoint() -> set:
    if CHECKPOINT_PATH.exists():
        data = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        return set(data.get("completed_refs", []))
    return set()


def save_checkpoint(completed_refs: set, stats: dict) -> None:
    data = {
        "updated_at": datetime.now().isoformat(),
        "completed_refs": sorted(completed_refs),
        "stats": stats,
    }
    CHECKPOINT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 소스별 아이템 로딩
# ──────────────────────────────────────────────────────────────────────────────

def load_items_examples(report: dict, limit: int) -> list[dict]:
    """examples의 독립 실행 가능 코드"""
    items = report.get("examples", {}).get("runnable_items", [])
    # DB에서 실제 코드 가져오기
    conn = sqlite3.connect(str(DB_PATH))
    result = []
    for item in items[:limit * 2]:  # 여유분 확보
        if len(result) >= limit:
            break
        row = conn.execute(
            "SELECT id, title, code FROM examples WHERE id = ?", (item["id"],)
        ).fetchone()
        if row and row[2]:
            result.append({
                "source_ref": f"ex_{row[0]}",
                "title": row[1] or f"example_{row[0]}",
                "code": row[2],
                "db_id": row[0],
            })
    conn.close()
    return result[:limit]


def load_items_github_issues(report: dict, limit: int) -> list[dict]:
    """sim_errors의 github_issue 소스에서 코드 있는 것"""
    items = report.get("sim_errors", {}).get("runnable_items", [])
    # github_issue 소스만 필터
    github_items = [x for x in items if x.get("source") == "github_issue"]

    conn = sqlite3.connect(str(DB_PATH))
    result = []
    for item in github_items[:limit * 2]:
        if len(result) >= limit:
            break
        row = conn.execute(
            "SELECT id, error_type, original_code, context FROM sim_errors WHERE id = ?",
            (item["id"],)
        ).fetchone()
        if row:
            code = row[2] or row[3] or ""
            if code:
                result.append({
                    "source_ref": f"se_{row[0]}",
                    "title": f"github_issue_{row[0]} ({row[1] or 'Unknown'})",
                    "code": code,
                    "db_id": row[0],
                })
    conn.close()
    return result[:limit]


def load_items_sim_errors_unverified(report: dict, limit: int) -> list[dict]:
    """sim_errors의 미검증 소스 (github_structured 포함)에서 코드 있는 것"""
    items = report.get("sim_errors", {}).get("runnable_items", [])

    conn = sqlite3.connect(str(DB_PATH))
    result = []
    for item in items[:limit * 2]:
        if len(result) >= limit:
            break
        row = conn.execute(
            "SELECT id, error_type, original_code, context, source FROM sim_errors WHERE id = ?",
            (item["id"],)
        ).fetchone()
        if row:
            code = row[2] or row[3] or ""
            if code:
                result.append({
                    "source_ref": f"se_{row[0]}",
                    "title": f"{row[4]}_{row[0]} ({row[1] or 'Unknown'})",
                    "code": code,
                    "db_id": row[0],
                    "source": row[4],
                })
    conn.close()
    return result[:limit]


SOURCE_LOADERS = {
    "examples": ("examples", load_items_examples),
    "github_issues": ("github_issues", load_items_github_issues),
    "sim_errors_unverified": ("sim_errors_unverified", load_items_sim_errors_unverified),
}


# ──────────────────────────────────────────────────────────────────────────────
# 배치 실행
# ──────────────────────────────────────────────────────────────────────────────

def run_batch(
    source: str = "examples",
    limit: int = 20,
    dry_run: bool = False,
    timeout: int = 120,
    skip_checkpoint: bool = False,
) -> dict:
    """배치 실행 메인 함수"""

    if source not in SOURCE_LOADERS:
        print(f"❌ 알 수 없는 source: {source}. 선택: {list(SOURCE_LOADERS.keys())}")
        return {}

    # DB 마이그레이션
    if not dry_run:
        migrate_db()

    # audit report 로드
    report = load_audit_report()

    # 아이템 로딩
    source_name, loader_fn = SOURCE_LOADERS[source]
    items = loader_fn(report, limit)

    print(f"\n{'=' * 60}")
    print(f"배치 실행: source={source}, limit={limit}, dry_run={dry_run}")
    print(f"대상 아이템: {len(items)}건")
    print(f"{'=' * 60}")

    if not items:
        print("⚠️  실행 가능한 아이템이 없습니다.")
        return {"total": 0}

    # 체크포인트 로드
    completed_refs = load_checkpoint() if not skip_checkpoint else set()

    # 통계
    stats = {
        "total": len(items),
        "success": 0,
        "error": 0,
        "timeout": 0,
        "mpi_deadlock_risk": 0,
        "blocked": 0,
        "skipped": 0,
        "started_at": datetime.now().isoformat(),
    }

    for i, item in enumerate(items, 1):
        ref = item["source_ref"]
        title = item["title"][:60]

        print(f"\n[{i}/{len(items)}] {ref}: {title}")

        # dry-run: 목록만 출력
        if dry_run:
            code_preview = item["code"][:80].replace("\n", " ")
            print(f"  [DRY-RUN] 코드 길이: {len(item['code'])}자")
            print(f"  코드 미리보기: {code_preview}...")
            continue

        # 체크포인트 스킵
        if ref in completed_refs:
            print(f"  ⏭️  이미 완료됨 (체크포인트 스킵)")
            stats["skipped"] += 1
            continue

        # 실행
        try:
            result = run_code(item["code"], timeout=timeout)
            stats[result.status] = stats.get(result.status, 0) + 1

            status_emoji = {
                "success": "✅",
                "error": "❌",
                "timeout": "⏱️",
                "mpi_deadlock_risk": "⚠️",
                "blocked": "🚫",
            }.get(result.status, "?")

            print(f"  {status_emoji} status={result.status}, time={result.run_time_sec}s")

            if result.error_type:
                print(f"     error_type: {result.error_type}")
            if result.T_value is not None:
                print(f"     T = {result.T_value:.4f}")

            # DB 저장
            lr_id = collect(
                code=item["code"],
                run_result=result,
                source=source_name,
                source_ref=ref,
            )
            print(f"     live_runs.id = {lr_id}")

            completed_refs.add(ref)
            save_checkpoint(completed_refs, stats)

        except Exception as e:
            print(f"  ❌ 예외 발생: {e}")
            stats["error"] = stats.get("error", 0) + 1

        # 컨테이너 과부하 방지
        time.sleep(0.5)

    # 최종 리포트
    stats["finished_at"] = datetime.now().isoformat()
    print(f"\n{'=' * 60}")
    print("📊 배치 실행 통계")
    print(f"{'=' * 60}")
    for k, v in stats.items():
        if k not in ("started_at", "finished_at"):
            print(f"  {k}: {v}")
    print(f"  시작: {stats['started_at']}")
    print(f"  종료: {stats['finished_at']}")

    return stats


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MEEP KB 배치 실행기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python batch_live_runner.py --source examples --limit 20 --dry-run
  python batch_live_runner.py --source examples --limit 50
  python batch_live_runner.py --source github_issues --limit 10
  python batch_live_runner.py --source sim_errors_unverified --limit 30
        """,
    )
    parser.add_argument(
        "--source",
        choices=["examples", "github_issues", "sim_errors_unverified"],
        default="examples",
        help="실행할 데이터 소스",
    )
    parser.add_argument("--limit", type=int, default=20, help="최대 실행 건수")
    parser.add_argument("--dry-run", action="store_true", help="실행 없이 목록만 출력")
    parser.add_argument("--timeout", type=int, default=120, help="코드 실행 타임아웃(초)")
    parser.add_argument("--no-checkpoint", action="store_true", help="체크포인트 무시")
    args = parser.parse_args()

    run_batch(
        source=args.source,
        limit=args.limit,
        dry_run=args.dry_run,
        timeout=args.timeout,
        skip_checkpoint=args.no_checkpoint,
    )
