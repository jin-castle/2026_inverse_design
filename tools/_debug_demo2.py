import subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, 'tools')
from run_concept_demos import preprocess_code
import sqlite3

# 에러난 몇 개 직접 확인
NAMES = ["Block", "FluxRegion", "courant", "resolution"]

conn = sqlite3.connect("db/knowledge.db")
for name in NAMES:
    row = conn.execute("SELECT demo_code FROM concepts WHERE name=?", (name,)).fetchone()
    if not row or not row[0]:
        print(f"{name}: demo_code 없음"); continue
    
    code = preprocess_code(row[0], name)
    tmp = Path(tempfile.gettempdir()) / f"_test_{name}.py"
    tmp.write_text(code, encoding="utf-8")
    
    result = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/_test_{name}.py"],
        capture_output=True, text=True, timeout=30,
        input=None
    )
    # docker cp 먼저
    subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/_test_{name}.py"], capture_output=True)
    result = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/_test_{name}.py"],
        capture_output=True, text=True, timeout=30
    )
    
    print(f"\n=== {name} (exit={result.returncode}) ===")
    out = (result.stderr or result.stdout)
    # 핵심 에러 줄만
    for line in out.splitlines():
        if "Error" in line or "error" in line or "line " in line:
            print(f"  {line}")
    tmp.unlink()
conn.close()
