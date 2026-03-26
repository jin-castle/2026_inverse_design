import subprocess, sys, tempfile, sqlite3
from pathlib import Path
sys.path.insert(0, 'tools')
from run_concept_demos import preprocess_code

DB_PATH = "db/knowledge.db"
NAMES = ["MPB", "phase_velocity", "LDOS", "ring_resonator", "add_energy"]

conn = sqlite3.connect(DB_PATH)
for name in NAMES:
    row = conn.execute("SELECT demo_code FROM concepts WHERE name=?", (name,)).fetchone()
    if not row or not row[0]:
        print(f"{name}: demo_code 없음"); continue

    code = preprocess_code(row[0], name)
    tmp = Path(tempfile.gettempdir()) / f"_dbg_{name}.py"
    tmp.write_text(code, encoding="utf-8")
    subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/_dbg_{name}.py"], capture_output=True)

    result = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/_dbg_{name}.py"],
        capture_output=True, text=True, timeout=60
    )
    err = (result.stderr or result.stdout)
    # 핵심 에러만 추출
    lines = err.splitlines()
    error_lines = [l for l in lines if any(k in l for k in ["Error", "error", "line ", "Traceback"])]
    print(f"\n=== {name} (exit={result.returncode}) ===")
    for l in error_lines[:5]:
        print(f"  {l}")
    tmp.unlink(missing_ok=True)

conn.close()
