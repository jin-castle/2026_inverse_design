-- sim_knowledge_schema.sql
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
