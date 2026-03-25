# -*- coding: utf-8 -*-
"""
error_collector.py — Phase 2: 실행 결과 DB 저장
================================================
live_runner 결과를 DB에 저장하고 중복을 방지.
live_runs 테이블 + sim_errors 컬럼 마이그레이션 수행.

사용:
  from tools.error_collector import collect, migrate_db
  collect(code, run_result, source="examples", source_ref="ex_id_42")
"""
import hashlib, sqlite3, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
from diagnose_engine import parse_error

# live_runner는 같은 패키지에서 임포트
sys.path.insert(0, str(Path(__file__).parent))
from live_runner import RunResult

BASE = Path(__file__).parent.parent
DB_PATH = BASE / "db" / "knowledge.db"


# ──────────────────────────────────────────────────────────────────────────────
# DB 마이그레이션
# ──────────────────────────────────────────────────────────────────────────────

MIGRATION_SQL = """
-- sim_errors 추가 컬럼 (없으면 추가)
-- SQLite는 IF NOT EXISTS 미지원이므로 try/except 처리

CREATE TABLE IF NOT EXISTS live_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code_hash TEXT UNIQUE,
    source TEXT,
    source_ref TEXT,
    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT,
    error_type TEXT,
    run_time_sec REAL,
    mpi_np INT DEFAULT 1,
    T_value REAL,
    R_value REAL,
    sim_error_id INT
);
"""

COLUMN_MIGRATIONS = [
    ("sim_errors", "run_time_sec", "REAL"),
    ("sim_errors", "code_length", "INT"),
    ("sim_errors", "mpi_np", "INT"),
]


def migrate_db(db_path: str = None) -> None:
    """DB 스키마 마이그레이션 실행"""
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    try:
        # live_runs 테이블 생성
        conn.executescript(MIGRATION_SQL)

        # sim_errors 컬럼 추가 (없는 경우만)
        existing_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(sim_errors)").fetchall()
        }
        for table, col, col_type in COLUMN_MIGRATIONS:
            if col not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                    print(f"  ✅ {table}.{col} 컬럼 추가됨")
                except sqlite3.OperationalError as e:
                    print(f"  ⚠️ {table}.{col} 추가 실패: {e}")

        conn.commit()
        print("  DB 마이그레이션 완료")
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# 코드 해시
# ──────────────────────────────────────────────────────────────────────────────

def compute_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# 에러 타입 분류
# ──────────────────────────────────────────────────────────────────────────────

def classify_error(code: str, run_result: RunResult) -> str:
    """RunResult에서 에러 타입 결정 (diagnose_engine.parse_error 재활용)"""
    if run_result.error_type:
        return run_result.error_type

    # status 기반 fallback
    status_map = {
        "success": "",
        "timeout": "Timeout",
        "mpi_deadlock_risk": "MPIDeadlockRisk",
        "blocked": "SecurityBlock",
    }
    if run_result.status in status_map:
        return status_map[run_result.status]

    # stderr/stdout 파싱
    combined_err = (run_result.stderr or "") + "\n" + (run_result.stdout or "")
    if combined_err.strip():
        info = parse_error(code, combined_err)
        return info.get("primary_type", "Unknown")

    return "Unknown"


# ──────────────────────────────────────────────────────────────────────────────
# 메인 수집 함수
# ──────────────────────────────────────────────────────────────────────────────

def collect(
    code: str,
    run_result: RunResult,
    source: str,
    source_ref: str,
    db_path: str = None,
    mpi_np: int = 1,
) -> int:
    """
    실행 결과를 live_runs 테이블에 저장.

    Args:
        code: 실행된 코드
        run_result: RunResult dataclass
        source: 데이터 출처 ('examples', 'github_issues', 'sim_errors_unverified', 'live_run')
        source_ref: 출처 참조 ID (예: 'ex_42', 'se_123')
        db_path: DB 경로 (None이면 기본 경로 사용)
        mpi_np: MPI 프로세스 수

    Returns:
        삽입된 live_runs.id (중복이면 기존 id 반환, -1이면 실패)
    """
    path = db_path or str(DB_PATH)
    code_hash = compute_hash(code)
    error_type = classify_error(code, run_result)

    conn = sqlite3.connect(path)
    try:
        # 중복 확인
        existing = conn.execute(
            "SELECT id FROM live_runs WHERE code_hash = ?", (code_hash,)
        ).fetchone()
        if existing:
            return existing[0]

        # live_runs 삽입
        cursor = conn.execute("""
            INSERT INTO live_runs
              (code_hash, source, source_ref, run_at, status,
               error_type, run_time_sec, mpi_np, T_value, R_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            code_hash,
            source,
            str(source_ref),
            datetime.now().isoformat(),
            run_result.status,
            error_type,
            run_result.run_time_sec,
            mpi_np,
            run_result.T_value,
            run_result.R_value,
        ))
        live_run_id = cursor.lastrowid

        # 에러인 경우 sim_errors에도 저장
        sim_error_id = None
        if run_result.status == "error" and run_result.error_message:
            err_cursor = conn.execute("""
                INSERT INTO sim_errors
                  (run_id, project_id, error_type, error_message, meep_version,
                   context, root_cause, fix_applied, fix_worked,
                   fix_description, fix_keywords, pattern_name, source,
                   original_code, fixed_code, created_at,
                   run_time_sec, code_length)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"live_{live_run_id}",
                source_ref,
                error_type,
                (run_result.error_message or "")[:500],
                "",  # meep_version (컨테이너에서 1.31.0)
                (run_result.stderr or "")[:500],
                "",  # root_cause (미정)
                "",  # fix_applied
                0,   # fix_worked
                "",  # fix_description
                "",  # fix_keywords
                f"live_run_{source}",
                "live_run",
                code[:5000],
                "",  # fixed_code
                datetime.now().isoformat(),
                run_result.run_time_sec,
                len(code),
            ))
            sim_error_id = err_cursor.lastrowid

            # live_runs.sim_error_id 업데이트
            conn.execute(
                "UPDATE live_runs SET sim_error_id = ? WHERE id = ?",
                (sim_error_id, live_run_id)
            )

        conn.commit()
        return live_run_id

    except Exception as e:
        print(f"  ❌ collect 오류: {e}")
        return -1
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("DB 마이그레이션 실행 중...")
    migrate_db()
    print("완료!")

    # 현황 확인
    conn = sqlite3.connect(str(DB_PATH))
    live_count = conn.execute("SELECT COUNT(*) FROM live_runs").fetchone()[0]
    sim_cols = [row[1] for row in conn.execute("PRAGMA table_info(sim_errors)").fetchall()]
    conn.close()

    print(f"\nlive_runs: {live_count}건")
    print(f"sim_errors 컬럼: {sim_cols}")
