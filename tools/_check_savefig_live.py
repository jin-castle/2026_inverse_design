"""이미지 없는 개념 몇 개를 Docker에서 직접 실행하고 출력 확인."""
import subprocess, sqlite3, re, tempfile
from pathlib import Path
import sys
sys.path.insert(0, 'tools')
from run_concept_demos import preprocess_code

NAMES = ["FluxRegion", "GaussianSource", "Harminv", "bend", "DFT"]
conn = sqlite3.connect("db/knowledge.db")

for name in NAMES:
    row = conn.execute("SELECT demo_code FROM concepts WHERE name=?", (name,)).fetchone()
    code = preprocess_code(row[0], name) if row and row[0] else ""
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)

    tmp = Path(tempfile.gettempdir()) / f"_chk_{safe}.py"
    tmp.write_text(code, encoding="utf-8")
    subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/_chk_{safe}.py"], capture_output=True)
    result = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/_chk_{safe}.py"],
        capture_output=True, text=True, timeout=90
    )
    # 이미지 있는지 확인
    chk = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "sh", "-c", f"ls /tmp/concept_{safe}.png 2>&1"],
        capture_output=True, text=True
    )
    img_exists = "No such" not in chk.stdout

    print(f"\n=== {name} (exit={result.returncode}, img={img_exists}) ===")
    if not img_exists:
        # savefig 라인 찾기
        for i, line in enumerate(code.splitlines()):
            if "savefig" in line:
                print(f"  savefig line {i}: {line.strip()}")
        # stderr 마지막
        err = result.stderr[-300:] if result.stderr else result.stdout[-200:]
        for l in err.splitlines()[-5:]:
            print(f"  {l}")

conn.close()
