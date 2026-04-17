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
# collect_v2: 5계층 구조 저장
# ──────────────────────────────────────────────────────────────────────────────

import json as _json
import re as _re


def _extract_physics_context(code: str) -> dict:
    """코드에서 물리 파라미터 자동 추출"""
    ctx = {
        "resolution": None,
        "pml_thickness": None,
        "wavelength_um": None,
        "dim": None,
        "uses_adjoint": 0,
        "uses_symmetry": 0,
        "cell_size": None,
        "device_type": "general",
        "run_mode": "forward",
    }

    # resolution
    m = _re.search(r'resolution\s*=\s*(\d+)', code)
    if m:
        ctx["resolution"] = int(m.group(1))

    # pml_thickness (PML 두께)
    m = _re.search(r'PML\s*\(\s*([\d.]+)', code)
    if m:
        ctx["pml_thickness"] = float(m.group(1))
    else:
        m = _re.search(r'dpml\s*=\s*([\d.]+)', code)
        if m:
            ctx["pml_thickness"] = float(m.group(1))

    # wavelength (fcen → wavelength_um = 1/fcen)
    m = _re.search(r'fcen\s*=\s*([\d.]+)', code)
    if m:
        fcen = float(m.group(1))
        if fcen > 0:
            ctx["wavelength_um"] = round(1.0 / fcen, 4)

    # dim (dimensions)
    m = _re.search(r'dimensions\s*=\s*(\d)', code)
    if m:
        ctx["dim"] = int(m.group(1))
    elif 'mp.CYLINDRICAL' in code:
        ctx["dim"] = -2
    elif 'mp.Vector3(0' in code or 'sz=0' in code or 'z=0' in code.lower():
        ctx["dim"] = 2

    # uses_adjoint / uses_symmetry
    if 'adjoint' in code.lower() or 'OptimizationProblem' in code:
        ctx["uses_adjoint"] = 1
    if 'symmetries' in code or 'mp.Mirror' in code or 'mp.Rotate' in code:
        ctx["uses_symmetry"] = 1

    # cell_size: mp.Vector3(x, y, z) 파싱
    m = _re.search(r'cell(?:_size)?\s*=\s*mp\.Vector3\s*\(\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)', code)
    if m:
        x, y = float(m.group(1)), float(m.group(2))
        z = float(m.group(3)) if m.group(3) else 0.0
        ctx["cell_size"] = _json.dumps({"x": x, "y": y, "z": z})

    # device_type 추론
    if 'DiffractedPlanewave' in code or 'grating' in code.lower():
        ctx["device_type"] = "grating"
    elif 'EigenmodeSource' in code and 'taper' in code.lower():
        ctx["device_type"] = "waveguide"
    elif 'ring' in code.lower() or 'resonator' in code.lower():
        ctx["device_type"] = "ring_resonator"
    elif 'OptimizationProblem' in code:
        ctx["device_type"] = "beamsplitter"
    elif 'EigenmodeSource' in code:
        ctx["device_type"] = "waveguide"

    # run_mode 추론
    if 'adjoint' in code.lower() or 'OptimizationProblem' in code:
        ctx["run_mode"] = "adjoint"
    elif 'Harminv' in code or 'harminv' in code:
        ctx["run_mode"] = "harminv"
    elif 'normalization' in code or 'norm_run' in code:
        ctx["run_mode"] = "normalization"
    elif 'get_eigenmode' in code or 'EigenmodeSource' in code:
        ctx["run_mode"] = "forward"
    else:
        ctx["run_mode"] = "forward"

    return ctx


def _classify_error_class(run_result: "RunResult", output: str) -> str:
    """run_result 기반 error_class 자동 분류"""
    stdout = run_result.stdout or ""
    stderr = run_result.stderr or ""
    combined = output + " " + stdout + " " + stderr

    if "NaN" in combined or "Inf" in combined or "diverged" in combined.lower():
        return "numerical_error"
    if run_result.status == "error":
        err_msg = run_result.error_message or ""
        # Python traceback 있으면 code_error
        if "Traceback" in (stderr + stdout) or "Error:" in err_msg:
            # monitor/PML/source 관련이면 config_error
            if any(kw in combined for kw in ["monitor", "PML", "source", "add_flux", "add_mode_monitor"]):
                return "config_error"
            return "code_error"
        return "code_error"
    # success인데 T 이상
    T = run_result.T_value
    if T is not None and (T > 1.05 or T < -0.01):
        return "physics_error"
    return "code_error"


def _extract_symptom(run_result: "RunResult") -> str:
    """symptom 추출"""
    stdout = run_result.stdout or ""
    stderr = run_result.stderr or ""
    combined = stdout + " " + stderr

    T = run_result.T_value
    if T is not None and T > 1.0:
        return "T>100%"
    if T is not None and T == 0.0:
        return "T=0"
    if "NaN" in combined or "Inf" in combined:
        return "NaN"
    if "diverged" in combined.lower():
        return "diverged"
    return ""


def _extract_trigger_code(code: str, run_result: "RunResult") -> tuple:
    """trigger_code + trigger_line 추출"""
    stderr = run_result.stderr or ""
    stdout = run_result.stdout or ""
    combined_err = stderr + "\n" + stdout

    # traceback에서 마지막 File "..." line N 추출
    file_matches = list(_re.finditer(r'File "([^"]+)", line (\d+)', combined_err))
    if file_matches:
        last_match = file_matches[-1]
        trigger_line = f"{last_match.group(1)}:{last_match.group(2)}"
        line_no = int(last_match.group(2))

        # 코드에서 해당 줄 ±2줄 추출 (코드가 직접 실행된 경우)
        lines = code.split("\n")
        if 1 <= line_no <= len(lines):
            start = max(0, line_no - 3)
            end = min(len(lines), line_no + 2)
            trigger_code = "\n".join(lines[start:end])
            return trigger_code, trigger_line

        return "", trigger_line

    # fallback: error_message 첫 줄
    err_msg = run_result.error_message or ""
    return err_msg.split("\n")[0][:200], ""


def _build_root_cause_chain(symptom: str, error_message: str, error_class: str, error_type: str) -> str:
    """root_cause_chain JSON 빌드"""
    chain = [
        {"level": 1, "cause": symptom or error_message[:100] if error_message else "unknown"},
        {"level": 2, "cause": (error_message or "")[:200]},
        {"level": 3, "cause": f"{error_class} in {error_type}"},
    ]
    return _json.dumps(chain, ensure_ascii=False)


def _infer_fix_type(error_class: str) -> str:
    """error_class 기반 fix_type 추론"""
    return {
        "code_error": "code_only",
        "physics_error": "physics_understanding",
        "numerical_error": "parameter_tune",
        "config_error": "physics_understanding",
    }.get(error_class, "code_only")


def collect_v2(
    code: str,
    run_result: "RunResult",
    source: str,
    source_ref: str,
    db_path: str = None,
    mpi_np: int = 1,
) -> int:
    """
    sim_errors_v2 테이블에 5계층 구조로 저장.
    물리 파라미터 자동 추출 + error_class 자동 분류 포함.
    정상 실행(success + T 정상)이면 v2에는 저장 안 함.

    Returns:
        삽입된 sim_errors_v2.id (저장 안 한 경우 0, 실패 -1)
    """
    path = db_path or str(DB_PATH)
    code_hash = compute_hash(code)

    # combined output
    stdout = run_result.stdout or ""
    stderr = run_result.stderr or ""
    output = stdout + "\n" + stderr

    # error_class 분류
    error_class = _classify_error_class(run_result, output)

    # 정상 실행 (no error, T 정상) → v2 저장 안 함
    T = run_result.T_value
    is_normal = (
        run_result.status == "success"
        and error_class == "code_error"  # 분류 실패한 경우도 여기 걸림
        and (T is None or (0.0 <= T <= 1.05))
        and "NaN" not in output
        and "diverged" not in output.lower()
    )
    # 실제로 에러도 없고 physics_error도 아닌 경우만 skip
    if run_result.status == "success" and error_class not in ("physics_error", "numerical_error"):
        if "NaN" not in output and "diverged" not in output.lower():
            return 0  # v2 저장 불필요

    # 물리 파라미터 추출
    phys = _extract_physics_context(code)
    run_mode = phys["run_mode"]

    # error_type (기존 classify_error 활용)
    error_type = classify_error(code, run_result)

    # symptom
    symptom = _extract_symptom(run_result)

    # trigger_code / trigger_line
    trigger_code, trigger_line = _extract_trigger_code(code, run_result)

    # error_message
    error_message = run_result.error_message or ""
    if not error_message and run_result.status == "error":
        # stderr 마지막 의미있는 줄에서 추출
        err_lines = [l.strip() for l in stderr.split("\n") if l.strip()]
        for line in reversed(err_lines):
            if not line.startswith("File ") and not line.startswith("Traceback"):
                error_message = line[:500]
                break

    # traceback
    traceback_full = stderr[:3000] if stderr else ""

    # root_cause_chain
    root_cause_chain = _build_root_cause_chain(symptom, error_message, error_class, error_type)

    # fix_type
    fix_type = _infer_fix_type(error_class)

    conn = sqlite3.connect(path)
    try:
        # 중복 확인 (같은 code_hash + error_class)
        existing = conn.execute(
            "SELECT id FROM sim_errors_v2 WHERE code_hash = ? AND error_class = ?",
            (code_hash, error_class)
        ).fetchone()
        if existing:
            return existing[0]

        cursor = conn.execute("""
            INSERT INTO sim_errors_v2 (
                run_mode, run_stage, mpi_np,
                device_type, wavelength_um, resolution, pml_thickness,
                cell_size, dim, uses_adjoint, uses_symmetry,
                error_class, error_type, error_message, traceback_full, symptom,
                trigger_code, trigger_line, root_cause_chain,
                fix_type,
                original_code,
                source, meep_version, run_time_sec, code_length, code_hash
            ) VALUES (
                ?, 'running', ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?,
                ?,
                ?, '1.31.0', ?, ?, ?
            )
        """, (
            run_mode, mpi_np,
            phys["device_type"], phys["wavelength_um"], phys["resolution"], phys["pml_thickness"],
            phys["cell_size"], phys["dim"], phys["uses_adjoint"], phys["uses_symmetry"],
            error_class, error_type, error_message[:500], traceback_full, symptom,
            trigger_code[:500], trigger_line[:200], root_cause_chain,
            fix_type,
            code[:5000],
            source,
            run_result.run_time_sec, len(code), code_hash,
        ))
        v2_id = cursor.lastrowid
        conn.commit()
        return v2_id

    except Exception as e:
        print(f"  ❌ collect_v2 오류: {e}")
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
