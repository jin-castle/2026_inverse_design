#!/usr/bin/env python3
"""
sim_tracker.py - 시뮬레이션 실행 이력 추적 모듈
meep-kb FastAPI 서버와 통신하는 클라이언트 + 로컬 SQLite 직접 쓰기 지원

사용법 (시뮬레이션 코드에 삽입):
    from sim_tracker import SimTracker
    tracker = SimTracker(project_id="PROJ-GRATING-001")

    run_id = tracker.start_run(script="grating_adjoint.py", meep_version="1.31.0",
                                mpi_procs=4, resolution=32, n_params=175,
                                optimizer="nlopt_mma", beta_schedule=[4,8,16,32,64,128,256],
                                n_iter=500)

    tracker.log_error(run_id, error_type="adjoint_chunk_mismatch",
                      error_message="...", root_cause="...", fix_applied="...")

    tracker.finish_run(run_id, best_fom=0.84, final_fom=0.79,
                       runtime_sec=3600, adjoint_working=True, status="success")
"""

import sqlite3
import json
import os
import time
import uuid
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# DB 경로 (환경변수 또는 기본값)
DB_PATH = os.environ.get("SIM_KB_DB", str(Path(__file__).parent.parent / "db/knowledge.db"))
API_BASE = os.environ.get("SIM_KB_API", "http://localhost:8765")


def _get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn):
    """테이블 없으면 생성 (마이그레이션 safe)"""
    ddl = """
    CREATE TABLE IF NOT EXISTS sim_runs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id          TEXT UNIQUE NOT NULL,
        project_id      TEXT NOT NULL,
        script_name     TEXT,
        meep_version    TEXT,
        mpi_procs       INTEGER DEFAULT 1,
        resolution      INTEGER,
        n_params        INTEGER,
        optimizer       TEXT,
        beta_schedule   TEXT,
        n_iter          INTEGER,
        use_adjoint     INTEGER DEFAULT 1,
        adjoint_working INTEGER DEFAULT 0,
        best_fom        REAL,
        final_fom       REAL,
        runtime_sec     REAL,
        status          TEXT DEFAULT 'running',
        notes           TEXT,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sim_errors (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id          TEXT,
        project_id      TEXT,
        error_type      TEXT NOT NULL,
        error_message   TEXT NOT NULL,
        meep_version    TEXT,
        context         TEXT,
        root_cause      TEXT,
        fix_applied     TEXT,
        fix_worked      INTEGER DEFAULT 0,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sim_patterns (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern_name    TEXT UNIQUE NOT NULL,
        category        TEXT NOT NULL,
        meep_version    TEXT,
        description     TEXT,
        code_snippet    TEXT NOT NULL,
        do_this         TEXT,
        not_this        TEXT,
        verified        INTEGER DEFAULT 0,
        source_run_id   TEXT,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sim_params (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id          TEXT,
        param_name      TEXT NOT NULL,
        param_value     TEXT NOT NULL,
        param_type      TEXT,
        effect          TEXT,
        recommended     INTEGER DEFAULT 0,
        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_sim_runs_project ON sim_runs(project_id);
    CREATE INDEX IF NOT EXISTS idx_sim_errors_type  ON sim_errors(error_type);
    CREATE INDEX IF NOT EXISTS idx_sim_patterns_cat ON sim_patterns(category);
    """
    for stmt in ddl.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()


class SimTracker:
    """시뮬레이션 실행 추적기. MPI 환경에서는 master만 DB 쓰기."""

    def __init__(self, project_id: str, db_path: str = None, master_only: bool = True):
        self.project_id = project_id
        self.db_path = db_path or DB_PATH
        self.master_only = master_only
        self._is_master = self._check_master()

    def _check_master(self) -> bool:
        try:
            import meep as mp
            return mp.am_master()
        except Exception:
            return True

    def _write(self, fn, *args, **kwargs):
        """master_only 모드면 master만 DB 쓰기 실행"""
        if self.master_only and not self._is_master:
            return None
        conn = _get_conn()
        _ensure_schema(conn)
        try:
            result = fn(conn, *args, **kwargs)
            conn.commit()
            return result
        except Exception as e:
            print(f"[SimTracker] DB 오류: {e}")
            return None
        finally:
            conn.close()

    def start_run(self,
                  script_name: str = "",
                  meep_version: str = "",
                  mpi_procs: int = 1,
                  resolution: int = 32,
                  n_params: int = 0,
                  optimizer: str = "adam",
                  beta_schedule: list = None,
                  n_iter: int = 0,
                  use_adjoint: bool = True,
                  notes: str = "") -> str:
        """새 시뮬레이션 실행 등록. run_id 반환."""
        run_id = f"{self.project_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

        def _insert(conn):
            conn.execute("""
                INSERT OR REPLACE INTO sim_runs
                (run_id, project_id, script_name, meep_version, mpi_procs,
                 resolution, n_params, optimizer, beta_schedule, n_iter,
                 use_adjoint, status, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (run_id, self.project_id, script_name, meep_version, mpi_procs,
                  resolution, n_params, optimizer,
                  json.dumps(beta_schedule or []),
                  n_iter, int(use_adjoint), "running", notes))
            return run_id

        result = self._write(_insert)
        if result:
            print(f"[SimTracker] ▶ 실행 시작: {run_id}")
        return run_id

    def finish_run(self, run_id: str, best_fom: float = None, final_fom: float = None,
                   runtime_sec: float = None, adjoint_working: bool = False,
                   status: str = "success", notes: str = ""):
        """실행 완료 업데이트."""
        def _update(conn):
            conn.execute("""
                UPDATE sim_runs SET
                    best_fom=?, final_fom=?, runtime_sec=?,
                    adjoint_working=?, status=?, notes=COALESCE(NULLIF(?,''), notes),
                    updated_at=CURRENT_TIMESTAMP
                WHERE run_id=?
            """, (best_fom, final_fom, runtime_sec,
                  int(adjoint_working), status, notes, run_id))
        self._write(_update)
        if self._is_master:
            print(f"[SimTracker] ✅ 완료: {run_id} | FOM={best_fom:.4f} | adjoint={'✅' if adjoint_working else '❌'}")

    def log_error(self, run_id: str, error_type: str, error_message: str,
                  meep_version: str = "", context: dict = None,
                  root_cause: str = "", fix_applied: str = "", fix_worked: bool = False):
        """오류 기록."""
        def _insert(conn):
            conn.execute("""
                INSERT INTO sim_errors
                (run_id, project_id, error_type, error_message, meep_version,
                 context, root_cause, fix_applied, fix_worked)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (run_id, self.project_id, error_type, error_message, meep_version,
                  json.dumps(context or {}), root_cause, fix_applied, int(fix_worked)))
        self._write(_insert)
        if self._is_master:
            status = "✅ 해결됨" if fix_worked else "⚠️ 미해결"
            print(f"[SimTracker] 오류 기록: [{error_type}] {status}")

    def log_pattern(self, pattern_name: str, category: str, description: str,
                    code_snippet: str, do_this: str = "", not_this: str = "",
                    meep_version: str = "", verified: bool = False, run_id: str = ""):
        """동작 확인된 코드 패턴 등록."""
        def _insert(conn):
            conn.execute("""
                INSERT OR REPLACE INTO sim_patterns
                (pattern_name, category, meep_version, description,
                 code_snippet, do_this, not_this, verified, source_run_id)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (pattern_name, category, meep_version, description,
                  code_snippet, do_this, not_this, int(verified), run_id))
        self._write(_insert)

    def log_param(self, run_id: str, param_name: str, param_value: Any,
                  effect: str = "", recommended: bool = False):
        """파라미터 효과 기록."""
        def _insert(conn):
            conn.execute("""
                INSERT INTO sim_params (run_id, param_name, param_value, param_type, effect, recommended)
                VALUES (?,?,?,?,?,?)
            """, (run_id, param_name, str(param_value), type(param_value).__name__,
                  effect, int(recommended)))
        self._write(_insert)

    def get_known_errors(self, error_type: str = None) -> List[Dict]:
        """알려진 오류 패턴 조회."""
        conn = _get_conn()
        _ensure_schema(conn)
        try:
            if error_type:
                rows = conn.execute(
                    "SELECT * FROM sim_errors WHERE error_type=? AND fix_worked=1 ORDER BY created_at DESC LIMIT 10",
                    (error_type,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sim_errors WHERE fix_worked=1 ORDER BY created_at DESC LIMIT 20"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_best_config(self, project_id: str = None) -> Optional[Dict]:
        """가장 높은 FOM을 달성한 설정 조회."""
        pid = project_id or self.project_id
        conn = _get_conn()
        _ensure_schema(conn)
        try:
            row = conn.execute("""
                SELECT * FROM sim_runs
                WHERE project_id=? AND adjoint_working=1 AND status='success'
                ORDER BY best_fom DESC LIMIT 1
            """, (pid,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def search_patterns(self, category: str = None, meep_version: str = None) -> List[Dict]:
        """코드 패턴 검색."""
        conn = _get_conn()
        _ensure_schema(conn)
        try:
            q = "SELECT * FROM sim_patterns WHERE verified=1"
            params = []
            if category:
                q += " AND category=?"; params.append(category)
            if meep_version:
                q += " AND meep_version=?"; params.append(meep_version)
            q += " ORDER BY created_at DESC"
            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# ────────────────────────────────────────────────────────────
# 시드 데이터: 이번 세션에서 발견한 지식 삽입
# ────────────────────────────────────────────────────────────
def seed_known_knowledge():
    """이번 세션에서 발견한 오류/패턴을 DB에 삽입."""
    tracker = SimTracker(project_id="SYSTEM")

    # ── 패턴 1: adjoint loop 올바른 패턴 ──
    tracker.log_pattern(
        pattern_name="adjoint_loop_correct_v131",
        category="adjoint",
        meep_version="1.31.0",
        description="MEEP 1.31에서 adjoint loop의 올바른 패턴. "
                    "opt()를 한 번만 호출, update_design/reset_meep 별도 불필요.",
        code_snippet="""
# ✅ 올바른 패턴 (MEEP 1.31.0)
for i in range(n_iter):
    x_mapped = mapping(x, beta)      # filter + projection
    f0, dJ_du = opt([x_mapped])      # ← 이것만. 내부에서 fwd+adj+reset
    x = x + lr * np.array(dJ_du).flatten()
    x = np.clip(x, 0, 1)
""",
        do_this="opt([x])만 호출. update_design, reset_meep 별도 호출 금지.",
        not_this="""
# ❌ 잘못된 패턴 - 매 iter 새 opt 생성
_, opt_new, _, _ = build_simulation(rho_proj)  # 매 iter 새로 생성
f0, dJ_du = opt_new([rho_proj])                # chunk 불일치 유발

# ❌ 잘못된 패턴 - update_design 따로 호출
opt.update_design([x])   # reset_meep 호출됨 → state 꼬임
f0, dJ_du = opt([x])
""",
        verified=False,  # v2 테스트 결과 후 True로 업데이트
    )

    # ── 패턴 2: DesignRegion API (MEEP 1.31) ──
    tracker.log_pattern(
        pattern_name="design_region_api_v131",
        category="adjoint",
        meep_version="1.31.0",
        description="MEEP 1.31에서 DesignRegion의 올바른 생성 방법. "
                    "design_parameters는 mp.MaterialGrid 객체여야 함 (list 아님).",
        code_snippet="""
# ✅ 올바른 방식
design_variables = mp.MaterialGrid(
    mp.Vector3(NX, NY),
    medium1=SiO2, medium2=Si,
    grid_type="U_MEAN"         # U_DEFAULT도 가능
)
design_region = mpa.DesignRegion(
    design_parameters=design_variables,   # mp.MaterialGrid 직접
    volume=mp.Volume(center=..., size=...)
)
geometry = [
    mp.Block(center=design_region.center, size=design_region.size,
             material=design_variables),   # geometry에도 같은 객체 참조
]
""",
        do_this="mp.MaterialGrid를 design_parameters로 직접 전달. geometry에서도 같은 객체 참조.",
        not_this="mpa.MaterialGrid는 MEEP 1.31에 없음. list[np.ndarray] 전달 불가.",
        verified=True,
    )

    # ── 패턴 3: mapping (filter + projection) ──
    tracker.log_pattern(
        pattern_name="mapping_filter_projection",
        category="filter",
        meep_version="1.31.0",
        description="conic filter + tanh projection 체인. "
                    "autograd 자동 chain rule로 gradient 연결됨.",
        code_snippet="""
import meep.adjoint as mpa
import autograd.numpy as npa

minimum_length = 0.09   # 최소 피처 크기 (um)
eta_e   = 0.55
eta_i   = 0.5
filter_radius = mpa.get_conic_radius_from_eta_e(minimum_length, eta_e)

def mapping(x, beta):
    x = mpa.conic_filter(
        x, filter_radius,
        design_width, design_height, design_resolution
    )
    x = x.flatten()
    x = mpa.tanh_projection(x, beta, eta_i)
    return x.flatten()

# 사용:
x_mapped = mapping(x_raw, beta)
f0, dJ_du = opt([x_mapped])
""",
        do_this="mpa.conic_filter → mpa.tanh_projection 순서. autograd.numpy 사용.",
        not_this="numpy tanh projection만 쓰면 chain rule 끊김. gradient 부정확.",
        verified=True,
    )

    # ── 패턴 4: objective_functions 형식 ──
    tracker.log_pattern(
        pattern_name="objective_function_format",
        category="adjoint",
        meep_version="1.31.0",
        description="OptimizationProblem의 objective_functions 형식.",
        code_snippet="""
# ✅ 단일 함수 (스칼라 반환)
def J(tran_coeff):
    return npa.abs(tran_coeff)**2

opt = mpa.OptimizationProblem(
    objective_functions=J,         # 리스트 아님
    objective_arguments=ob_list,   # 리스트
    ...
)

# 다중 objective (리스트):
opt = mpa.OptimizationProblem(
    objective_functions=[J1, J2],
    ...
)
""",
        do_this="단일 목적함수는 리스트 없이 함수 직접 전달.",
        not_this="[J] 형태로 리스트 감싸면 gradient 출력 차원이 달라짐.",
        verified=True,
    )

    # ── 오류 기록: mpa.MaterialGrid 없음 ──
    conn = _get_conn()
    _ensure_schema(conn)
    conn.execute("""
        INSERT OR IGNORE INTO sim_errors
        (run_id, project_id, error_type, error_message, meep_version,
         root_cause, fix_applied, fix_worked)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        "PROJ-GRATING-001-historical",
        "PROJ-GRATING-001",
        "mpa_materialgrid_not_found",
        "module 'meep.adjoint' has no attribute 'MaterialGrid'",
        "1.31.0",
        "MEEP 1.28 API: mpa.MaterialGrid. 1.31에서 mp.MaterialGrid로 이동됨.",
        "mp.MaterialGrid 사용, mpa.DesignRegion(design_parameters=mat_grid)로 변경",
        1
    ))

    # ── 오류 기록: adjoint chunks mismatch ──
    conn.execute("""
        INSERT OR IGNORE INTO sim_errors
        (run_id, project_id, error_type, error_message, meep_version,
         root_cause, fix_applied, fix_worked)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        "PROJ-GRATING-001-historical",
        "PROJ-GRATING-001",
        "adjoint_chunk_mismatch",
        "The number of adjoint chunks (3) is not equal to the number of forward chunks (0)",
        "1.31.0",
        "매 iter마다 build_simulation()으로 새 opt 생성. "
        "forward DFT monitor가 adjoint run 전에 clear됨 (forward_chunks=0).",
        "opt를 한 번만 생성, opt([x]) 반복 호출. update_design/reset_meep 별도 금지.",
        0   # v2 테스트 후 업데이트 필요
    ))
    conn.commit()
    conn.close()
    print("[seed] ✅ 지식 DB 시드 데이터 삽입 완료")


if __name__ == "__main__":
    seed_known_knowledge()
    # 조회 테스트
    tracker = SimTracker("TEST")
    patterns = tracker.search_patterns(category="adjoint")
    print(f"\n등록된 adjoint 패턴: {len(patterns)}개")
    for p in patterns:
        print(f"  - [{p['pattern_name']}] verified={p['verified']}")

    errors = tracker.get_known_errors()
    print(f"\n해결된 오류: {len(errors)}개")
    for e in errors:
        print(f"  - [{e['error_type']}] {e['fix_applied'][:50]}...")
