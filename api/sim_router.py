#!/usr/bin/env python3
"""sim_router.py - 시뮬레이션 추적 FastAPI 라우터 /api/sim/*"""
import sqlite3, json, uuid, os
from typing import Optional, List, Any
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
DB_FILE = Path(os.environ.get("APP_DIR", "/app")) / "db/knowledge.db"
SCHEMA_FILE = Path(__file__).parent.parent / "db/sim_knowledge_schema.sql"


def _conn():
    c = sqlite3.connect(str(DB_FILE), timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _ensure(c):
    if SCHEMA_FILE.exists():
        c.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    else:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS sim_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT UNIQUE NOT NULL,
            project_id TEXT NOT NULL, script_name TEXT, meep_version TEXT,
            mpi_procs INTEGER DEFAULT 1, resolution INTEGER, n_params INTEGER,
            optimizer TEXT, beta_schedule TEXT, n_iter INTEGER,
            use_adjoint INTEGER DEFAULT 1, adjoint_working INTEGER DEFAULT 0,
            best_fom REAL, final_fom REAL, runtime_sec REAL,
            status TEXT DEFAULT 'running', notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sim_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, project_id TEXT,
            error_type TEXT NOT NULL, error_message TEXT NOT NULL,
            meep_version TEXT, context TEXT, root_cause TEXT,
            fix_applied TEXT, fix_worked INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sim_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_name TEXT UNIQUE NOT NULL, category TEXT NOT NULL,
            meep_version TEXT, description TEXT, code_snippet TEXT NOT NULL,
            do_this TEXT, not_this TEXT, verified INTEGER DEFAULT 0,
            source_run_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sim_params (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT,
            param_name TEXT NOT NULL, param_value TEXT NOT NULL,
            param_type TEXT, effect TEXT, recommended INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_sim_runs_project ON sim_runs(project_id);
        CREATE INDEX IF NOT EXISTS idx_sim_errors_type ON sim_errors(error_type);
        CREATE INDEX IF NOT EXISTS idx_sim_patterns_cat ON sim_patterns(category);
        """)
    c.commit()


# ── Pydantic 모델
class SimRunReq(BaseModel):
    project_id: str
    script_name: str = ""
    meep_version: str = ""
    mpi_procs: int = 1
    resolution: int = 32
    n_params: int = 0
    optimizer: str = "adam"
    beta_schedule: List[Any] = []
    n_iter: int = 0
    use_adjoint: bool = True
    notes: str = ""

class SimFinishReq(BaseModel):
    run_id: str
    best_fom: Optional[float] = None
    final_fom: Optional[float] = None
    runtime_sec: Optional[float] = None
    adjoint_working: bool = False
    status: str = "success"
    notes: str = ""

class SimErrorReq(BaseModel):
    run_id: str
    project_id: str
    error_type: str
    error_message: str
    meep_version: str = ""
    context: dict = {}
    root_cause: str = ""
    fix_applied: str = ""
    fix_worked: bool = False

class SimPatternReq(BaseModel):
    pattern_name: str
    category: str
    meep_version: str = ""
    description: str = ""
    code_snippet: str
    do_this: str = ""
    not_this: str = ""
    verified: bool = False
    source_run_id: str = ""


# ── 엔드포인트
@router.post("/run/start")
async def start_run(req: SimRunReq):
    run_id = f"{req.project_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    c = _conn(); _ensure(c)
    try:
        c.execute(
            "INSERT OR REPLACE INTO sim_runs "
            "(run_id,project_id,script_name,meep_version,mpi_procs,"
            "resolution,n_params,optimizer,beta_schedule,n_iter,use_adjoint,status,notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, req.project_id, req.script_name, req.meep_version, req.mpi_procs,
             req.resolution, req.n_params, req.optimizer, json.dumps(req.beta_schedule),
             req.n_iter, int(req.use_adjoint), "running", req.notes))
        c.commit()
    finally:
        c.close()
    return {"run_id": run_id}

@router.post("/run/finish")
async def finish_run(req: SimFinishReq):
    c = _conn(); _ensure(c)
    try:
        c.execute(
            "UPDATE sim_runs SET best_fom=?,final_fom=?,runtime_sec=?,"
            "adjoint_working=?,status=?,updated_at=CURRENT_TIMESTAMP "
            "WHERE run_id=?",
            (req.best_fom, req.final_fom, req.runtime_sec,
             int(req.adjoint_working), req.status, req.run_id))
        c.commit()
    finally:
        c.close()
    return {"status": "updated", "run_id": req.run_id}

@router.post("/error")
async def log_error(req: SimErrorReq):
    c = _conn(); _ensure(c)
    try:
        c.execute(
            "INSERT INTO sim_errors "
            "(run_id,project_id,error_type,error_message,meep_version,"
            "context,root_cause,fix_applied,fix_worked) VALUES (?,?,?,?,?,?,?,?,?)",
            (req.run_id, req.project_id, req.error_type, req.error_message,
             req.meep_version, json.dumps(req.context), req.root_cause,
             req.fix_applied, int(req.fix_worked)))
        c.commit()
    finally:
        c.close()
    return {"status": "logged"}

@router.post("/pattern")
async def log_pattern(req: SimPatternReq):
    c = _conn(); _ensure(c)
    try:
        c.execute(
            "INSERT OR REPLACE INTO sim_patterns "
            "(pattern_name,category,meep_version,description,"
            "code_snippet,do_this,not_this,verified,source_run_id) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (req.pattern_name, req.category, req.meep_version, req.description,
             req.code_snippet, req.do_this, req.not_this, int(req.verified),
             req.source_run_id))
        c.commit()
    finally:
        c.close()
    return {"status": "saved"}

@router.get("/runs")
async def get_runs(project_id: str = "", limit: int = 20):
    c = _conn(); _ensure(c)
    try:
        if project_id:
            rows = c.execute(
                "SELECT * FROM sim_runs WHERE project_id=? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit)).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM sim_runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return {"runs": [dict(r) for r in rows]}
    finally:
        c.close()

@router.get("/errors")
async def get_errors(error_type: str = "", fixed_only: bool = False):
    c = _conn(); _ensure(c)
    try:
        q = "SELECT * FROM sim_errors WHERE 1=1"
        params = []
        if error_type:
            q += " AND error_type=?"; params.append(error_type)
        if fixed_only:
            q += " AND fix_worked=1"
        q += " ORDER BY created_at DESC LIMIT 50"
        rows = c.execute(q, params).fetchall()
        return {"errors": [dict(r) for r in rows]}
    finally:
        c.close()

@router.get("/patterns")
async def get_patterns(category: str = "", verified_only: bool = False):
    c = _conn(); _ensure(c)
    try:
        q = "SELECT * FROM sim_patterns WHERE 1=1"
        params = []
        if category:
            q += " AND category=?"; params.append(category)
        if verified_only:
            q += " AND verified=1"
        q += " ORDER BY created_at DESC"
        rows = c.execute(q, params).fetchall()
        return {"patterns": [dict(r) for r in rows]}
    finally:
        c.close()

@router.get("/best")
async def get_best(project_id: str):
    c = _conn(); _ensure(c)
    try:
        row = c.execute(
            "SELECT * FROM sim_runs WHERE project_id=? AND adjoint_working=1 "
            "AND status='success' ORDER BY best_fom DESC LIMIT 1",
            (project_id,)).fetchone()
        return {"best": dict(row) if row else None}
    finally:
        c.close()

@router.post("/diagnose-error")
async def diagnose_sim_error(body: dict):
    error_msg = body.get("error_message", "")
    c = _conn(); _ensure(c)
    try:
        rows = c.execute(
            "SELECT error_type, root_cause, fix_applied, fix_worked FROM sim_errors "
            "WHERE error_message LIKE ? OR error_type LIKE ? "
            "ORDER BY fix_worked DESC, created_at DESC LIMIT 5",
            (f"%{error_msg[:60]}%", f"%{error_msg[:30]}%")).fetchall()
        return {"known_fixes": [dict(r) for r in rows]}
    finally:
        c.close()
