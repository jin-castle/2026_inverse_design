# -*- coding: utf-8 -*-
# migrate_v2.py — sim_errors_v2 테이블 생성 (5계층 스키마)
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"

CREATE_V2 = """
CREATE TABLE IF NOT EXISTS sim_errors_v2 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  -- Layer 1: 실행 컨텍스트
  run_mode       TEXT,   -- forward | adjoint | normalization | eigenmode_solve | harminv
  run_stage      TEXT,   -- setup | running | post_process | optimization_loop
  iteration      INT,
  mpi_np         INT DEFAULT 1,

  -- Layer 2: 물리 파라미터
  device_type    TEXT,   -- waveguide | beamsplitter | grating | ring_resonator | general
  wavelength_um  REAL,
  resolution     INT,
  pml_thickness  REAL,
  cell_size      TEXT,   -- JSON: {"x": 10, "y": 5, "z": 0}
  dim            INT,
  uses_adjoint   INT DEFAULT 0,
  uses_symmetry  INT DEFAULT 0,

  -- Layer 3: 에러 분류
  error_class    TEXT,   -- code_error | physics_error | numerical_error | config_error
  error_type     TEXT,   -- Divergence | EigenMode | PML | MPIError | ...
  error_message  TEXT,
  traceback_full TEXT,
  symptom        TEXT,   -- T>100% | NaN | T=0 | diverged | wrong_mode

  -- Layer 4: 원인 체인
  trigger_code      TEXT,   -- 에러 직접 유발 코드 스니펫 (3~5줄)
  trigger_line      TEXT,   -- 파일:라인
  physics_cause     TEXT,   -- 물리적 원인 (자연어, 상세)
  code_cause        TEXT,   -- 코드 레벨 원인 (자연어)
  root_cause_chain  TEXT,   -- JSON array: [{level, cause}, ...]

  -- Layer 5: 수정 처방
  fix_type          TEXT,   -- code_only | physics_understanding | parameter_tune | structural
  fix_description   TEXT,   -- 수정 방법 (물리 이유 포함)
  original_code     TEXT,
  fixed_code        TEXT,
  code_diff         TEXT,   -- unified diff
  fix_worked        INT DEFAULT 0,

  -- 메타
  source         TEXT,   -- live_run | verified_fix | error_injector | github_issue
  meep_version   TEXT DEFAULT '1.31.0',
  run_time_sec   REAL,
  code_length    INT,
  code_hash      TEXT,
  created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_v2_error_class ON sim_errors_v2(error_class);
CREATE INDEX IF NOT EXISTS idx_v2_error_type ON sim_errors_v2(error_type);
CREATE INDEX IF NOT EXISTS idx_v2_run_mode ON sim_errors_v2(run_mode);
CREATE INDEX IF NOT EXISTS idx_v2_fix_worked ON sim_errors_v2(fix_worked);
CREATE INDEX IF NOT EXISTS idx_v2_source ON sim_errors_v2(source);
CREATE INDEX IF NOT EXISTS idx_v2_code_hash ON sim_errors_v2(code_hash);
"""

conn = sqlite3.connect(str(DB_PATH))
conn.executescript(CREATE_V2)
conn.commit()
count = conn.execute("SELECT COUNT(*) FROM sim_errors_v2").fetchone()[0]
print(f"sim_errors_v2 생성 완료: {count}건")

# 인덱스 확인
indexes = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='sim_errors_v2'"
).fetchall()
print(f"인덱스 {len(indexes)}개: {[r[0] for r in indexes]}")
conn.close()
