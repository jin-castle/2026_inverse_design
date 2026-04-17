#!/usr/bin/env python3
"""
sim_errors + sim_errors_v2 → sim_errors_unified 통합 마이그레이션

전략:
  - 새 테이블 sim_errors_unified: 양쪽 컬럼 전부 포함 (superset)
  - sim_errors_v2 우선 삽입 (더 풍부한 스키마)
  - sim_errors에서 중복 제거 후 나머지 삽입
  - 중복 기준: error_message 앞 120자 동일
  - 기존 두 테이블은 DROP하지 않고 보존 (아카이브)
  - search_executor.py 에서 sim_errors_unified 단일 쿼리로 변경
"""

import sqlite3, shutil, json, time
from pathlib import Path
from datetime import datetime

DB_PATH = Path("/mnt/c/Users/user/projects/meep-kb/db/knowledge.db")
BACKUP  = Path(f"/mnt/c/Users/user/projects/meep-kb/db/knowledge_backup_pre_unified_{datetime.now().strftime('%Y%m%d_%H%M')}.db")

# ── DDL: 통합 테이블 ──────────────────────────────────────────────────────────
CREATE_UNIFIED = """
CREATE TABLE IF NOT EXISTS sim_errors_unified (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,

  -- 출처 추적
  origin_table        TEXT,    -- 'sim_errors' | 'sim_errors_v2'
  origin_id           INTEGER, -- 원본 테이블의 id
  source              TEXT,    -- github_issue | live_run | error_injector | marl_auto ...

  -- 실행 컨텍스트 (v2 전용 → se는 NULL)
  run_mode            TEXT,    -- forward | adjoint | normalization | eigenmode_solve | harminv
  run_stage           TEXT,    -- setup | running | post_process | optimization_loop
  iteration           INT,
  mpi_np              INT,
  device_type         TEXT,    -- waveguide | grating | ring_resonator | general
  wavelength_um       REAL,
  resolution          INT,
  pml_thickness       REAL,
  cell_size           TEXT,    -- JSON
  dim                 INT,
  uses_adjoint        INT,
  uses_symmetry       INT,
  run_mode_meta       TEXT,    -- se.context JSON 보존

  -- 에러 분류
  error_class         TEXT,    -- code_error | physics_error | numerical_error | config_error
  error_type          TEXT NOT NULL,
  error_message       TEXT NOT NULL,
  traceback_full      TEXT,

  -- 증상 (3분할 — 양쪽 공통)
  symptom             TEXT,    -- v2 원본 symptom 필드
  symptom_numerical   TEXT,
  symptom_behavioral  TEXT,
  symptom_error_pattern TEXT,

  -- 원인 체인 (v2 풍부 / se 단순)
  physics_cause       TEXT,    -- v2: 물리 원인 / se: NULL
  code_cause          TEXT,    -- v2: 코드 원인 / se: NULL
  root_cause          TEXT,    -- se: root_cause / v2: physics+code 요약
  root_cause_chain    TEXT,    -- JSON array (v2 전용)
  trigger_code        TEXT,
  trigger_line        TEXT,

  -- 수정 처방
  fix_type            TEXT,
  fix_description     TEXT,
  fix_keywords        TEXT,    -- se 전용 JSON 배열
  fix_applied         TEXT,    -- se 전용
  original_code       TEXT,
  original_code_raw   TEXT,
  fixed_code          TEXT,
  code_diff           TEXT,    -- unified diff (v2 전용)
  fix_worked          INT DEFAULT 0,

  -- 검증 / 진단 (마이그레이션으로 생성)
  verification_criteria TEXT,
  diagnostic_snippet    TEXT,

  -- 메타
  pattern_name        TEXT,    -- se 전용
  project_id          TEXT,    -- se 전용
  run_id              TEXT,    -- se 전용
  code_hash           TEXT,
  code_length         INT,
  run_time_sec        REAL,
  meep_version        TEXT,
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_IDX = [
    "CREATE INDEX IF NOT EXISTS idx_seu_error_type      ON sim_errors_unified(error_type)",
    "CREATE INDEX IF NOT EXISTS idx_seu_fix_worked       ON sim_errors_unified(fix_worked)",
    "CREATE INDEX IF NOT EXISTS idx_seu_source           ON sim_errors_unified(source)",
    "CREATE INDEX IF NOT EXISTS idx_seu_symptom_num      ON sim_errors_unified(symptom_numerical)",
    "CREATE INDEX IF NOT EXISTS idx_seu_symptom_beh      ON sim_errors_unified(symptom_behavioral)",
    "CREATE INDEX IF NOT EXISTS idx_seu_error_pattern    ON sim_errors_unified(symptom_error_pattern)",
]

CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS sim_errors_unified_fts USING fts5(
    error_type, error_message, root_cause, fix_description,
    symptom_numerical, symptom_behavioral, symptom_error_pattern,
    physics_cause, code_cause,
    content='sim_errors_unified', content_rowid='id'
);
"""

# ── 헬퍼 ──────────────────────────────────────────────────────────────────────
def dedup_key(msg: str) -> str:
    return (msg or "")[:120].strip().lower()

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

# ── v2 → unified 변환 ─────────────────────────────────────────────────────────
def from_v2(row: dict) -> dict:
    # physics_cause + code_cause → root_cause 요약
    root = ""
    if row.get("physics_cause"):
        root += row["physics_cause"][:200]
    if row.get("code_cause"):
        root += (" / " if root else "") + row["code_cause"][:200]
    return {
        "origin_table": "sim_errors_v2",
        "origin_id":    row["id"],
        "source":       row.get("source") or "live_run",
        "run_mode":     row.get("run_mode"),
        "run_stage":    row.get("run_stage"),
        "iteration":    row.get("iteration"),
        "mpi_np":       row.get("mpi_np"),
        "device_type":  row.get("device_type"),
        "wavelength_um":row.get("wavelength_um"),
        "resolution":   row.get("resolution"),
        "pml_thickness":row.get("pml_thickness"),
        "cell_size":    row.get("cell_size"),
        "dim":          row.get("dim"),
        "uses_adjoint": row.get("uses_adjoint"),
        "uses_symmetry":row.get("uses_symmetry"),
        "run_mode_meta":None,
        "error_class":  row.get("error_class"),
        "error_type":   row.get("error_type") or "Unknown",
        "error_message":row.get("error_message") or "",
        "traceback_full":row.get("traceback_full"),
        "symptom":      row.get("symptom"),
        "symptom_numerical":   row.get("symptom_numerical"),
        "symptom_behavioral":  row.get("symptom_behavioral"),
        "symptom_error_pattern":row.get("symptom_error_pattern"),
        "physics_cause":row.get("physics_cause"),
        "code_cause":   row.get("code_cause"),
        "root_cause":   root or None,
        "root_cause_chain": row.get("root_cause_chain"),
        "trigger_code": row.get("trigger_code"),
        "trigger_line": row.get("trigger_line"),
        "fix_type":     row.get("fix_type"),
        "fix_description": row.get("fix_description"),
        "fix_keywords": None,
        "fix_applied":  None,
        "original_code":row.get("original_code"),
        "original_code_raw": row.get("original_code_raw"),
        "fixed_code":   row.get("fixed_code"),
        "code_diff":    row.get("code_diff"),
        "fix_worked":   row.get("fix_worked") or 0,
        "verification_criteria": row.get("verification_criteria"),
        "diagnostic_snippet":    row.get("diagnostic_snippet"),
        "pattern_name": None,
        "project_id":   None,
        "run_id":       None,
        "code_hash":    row.get("code_hash"),
        "code_length":  row.get("code_length"),
        "run_time_sec": row.get("run_time_sec"),
        "meep_version": row.get("meep_version"),
        "created_at":   row.get("created_at"),
    }

# ── se → unified 변환 ─────────────────────────────────────────────────────────
def from_se(row: dict) -> dict:
    return {
        "origin_table": "sim_errors",
        "origin_id":    row["id"],
        "source":       row.get("source") or "github_issue",
        "run_mode":     None,
        "run_stage":    None,
        "iteration":    None,
        "mpi_np":       row.get("mpi_np"),
        "device_type":  None,
        "wavelength_um":None,
        "resolution":   None,
        "pml_thickness":None,
        "cell_size":    None,
        "dim":          None,
        "uses_adjoint": None,
        "uses_symmetry":None,
        "run_mode_meta":row.get("context"),
        "error_class":  None,
        "error_type":   row.get("error_type") or "Unknown",
        "error_message":row.get("error_message") or "",
        "traceback_full":None,
        "symptom":      None,
        "symptom_numerical":    row.get("symptom_numerical"),
        "symptom_behavioral":   row.get("symptom_behavioral"),
        "symptom_error_pattern":row.get("symptom_error_pattern"),
        "physics_cause":None,
        "code_cause":   None,
        "root_cause":   row.get("root_cause"),
        "root_cause_chain": None,
        "trigger_code": None,
        "trigger_line": None,
        "fix_type":     None,
        "fix_description": row.get("fix_description"),
        "fix_keywords": row.get("fix_keywords"),
        "fix_applied":  row.get("fix_applied"),
        "original_code":row.get("original_code"),
        "original_code_raw": None,
        "fixed_code":   row.get("fixed_code"),
        "code_diff":    None,
        "fix_worked":   row.get("fix_worked") or 0,
        "verification_criteria": None,
        "diagnostic_snippet":    None,
        "pattern_name": row.get("pattern_name"),
        "project_id":   row.get("project_id"),
        "run_id":       row.get("run_id"),
        "code_hash":    None,
        "code_length":  row.get("code_length"),
        "run_time_sec": row.get("run_time_sec"),
        "meep_version": row.get("meep_version"),
        "created_at":   row.get("created_at"),
    }

# ── INSERT 헬퍼 ───────────────────────────────────────────────────────────────
FIELDS = [
    "origin_table","origin_id","source","run_mode","run_stage","iteration","mpi_np",
    "device_type","wavelength_um","resolution","pml_thickness","cell_size","dim",
    "uses_adjoint","uses_symmetry","run_mode_meta","error_class","error_type",
    "error_message","traceback_full","symptom","symptom_numerical","symptom_behavioral",
    "symptom_error_pattern","physics_cause","code_cause","root_cause","root_cause_chain",
    "trigger_code","trigger_line","fix_type","fix_description","fix_keywords","fix_applied",
    "original_code","original_code_raw","fixed_code","code_diff","fix_worked",
    "verification_criteria","diagnostic_snippet","pattern_name","project_id","run_id",
    "code_hash","code_length","run_time_sec","meep_version","created_at",
]

INSERT_SQL = f"""
INSERT INTO sim_errors_unified ({','.join(FIELDS)})
VALUES ({','.join('?' for _ in FIELDS)})
"""

def insert_row(conn, rec: dict):
    vals = [rec.get(f) for f in FIELDS]
    conn.execute(INSERT_SQL, vals)

# ── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    # 1. 백업
    log(f"백업: {BACKUP.name}")
    shutil.copy2(DB_PATH, BACKUP)

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row

    # 2. 테이블 생성
    log("테이블 생성: sim_errors_unified")
    conn.execute(CREATE_UNIFIED)
    for idx in CREATE_IDX:
        conn.execute(idx)
    conn.execute(CREATE_FTS)
    conn.commit()

    # 3. 기존 통합 데이터 있으면 초기화 (재실행 대비)
    existing = conn.execute("SELECT COUNT(*) FROM sim_errors_unified").fetchone()[0]
    if existing > 0:
        log(f"기존 {existing}건 삭제 후 재삽입")
        conn.execute("DELETE FROM sim_errors_unified")
        conn.execute("DELETE FROM sim_errors_unified_fts")
        conn.commit()

    # 4. sim_errors_v2 전부 삽입 (우선)
    v2_rows = conn.execute("SELECT * FROM sim_errors_v2").fetchall()
    dedup_set = set()
    v2_count = 0
    for row in v2_rows:
        rec = from_v2(dict(row))
        key = dedup_key(rec["error_message"])
        dedup_set.add(key)
        insert_row(conn, rec)
        v2_count += 1
    conn.commit()
    log(f"sim_errors_v2 삽입: {v2_count}건")

    # 5. sim_errors에서 중복 제거 후 삽입
    se_rows = conn.execute("SELECT * FROM sim_errors").fetchall()
    se_inserted = se_dup = 0
    for row in se_rows:
        rec = from_se(dict(row))
        key = dedup_key(rec["error_message"])
        if key in dedup_set:
            se_dup += 1
            continue
        dedup_set.add(key)
        insert_row(conn, rec)
        se_inserted += 1
    conn.commit()
    log(f"sim_errors 삽입: {se_inserted}건  (중복 제거: {se_dup}건)")

    # 6. FTS 인덱스 재구축
    log("FTS 인덱스 재구축...")
    conn.execute("INSERT INTO sim_errors_unified_fts(sim_errors_unified_fts) VALUES('rebuild')")
    conn.commit()

    # 7. 검증
    total_unified = conn.execute("SELECT COUNT(*) FROM sim_errors_unified").fetchone()[0]
    by_origin = conn.execute("""
        SELECT origin_table, COUNT(*), SUM(fix_worked),
               COUNT(symptom_numerical), COUNT(verification_criteria), COUNT(diagnostic_snippet)
        FROM sim_errors_unified GROUP BY origin_table
    """).fetchall()

    log("\n=== 통합 결과 ===")
    log(f"  sim_errors_unified 총계: {total_unified}건")
    for r in by_origin:
        orig, cnt, fixed, s_num, verif, diag = r
        log(f"  [{orig}] total={cnt}  fix_worked={fixed}  "
            f"symptom_num={s_num}({s_num/cnt*100:.0f}%)  "
            f"verif={verif}({verif/cnt*100:.0f}%)  "
            f"diag={diag}({diag/cnt*100:.0f}%)")

    log("\n=== 전체 채움률 ===")
    for col in ["symptom_numerical","symptom_behavioral","symptom_error_pattern",
                "physics_cause","root_cause","fix_description","verification_criteria","diagnostic_snippet"]:
        n = conn.execute(f"SELECT COUNT(*) FROM sim_errors_unified WHERE {col} IS NOT NULL").fetchone()[0]
        log(f"  {col:30s}: {n}/{total_unified} ({n/total_unified*100:.0f}%)")

    conn.close()
    log("\n완료!")

if __name__ == "__main__":
    main()
