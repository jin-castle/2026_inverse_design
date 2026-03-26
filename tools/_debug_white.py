"""하얀 이미지 개념의 코드를 Docker에서 실행하고 실제 원인 파악."""
import subprocess, sqlite3, re, tempfile
from pathlib import Path
import sys
sys.path.insert(0, 'tools')
from run_concept_demos import preprocess_code

NAMES = ["Block", "Cylinder", "PML", "Medium", "mpi", "taper",
         "eig_band", "eig_parity", "LorentzianSusceptibility", "OptimizationProblem"]

conn = sqlite3.connect("db/knowledge.db")

for name in NAMES:
    row = conn.execute("SELECT demo_code FROM concepts WHERE name=?", (name,)).fetchone()
    code = preprocess_code(row[0], name) if row and row[0] else ""
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)

    tmp = Path(tempfile.gettempdir()) / f"_white_{safe}.py"
    tmp.write_text(code, encoding="utf-8")
    subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/_white_{safe}.py"], capture_output=True)

    result = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/_white_{safe}.py"],
        capture_output=True, text=True, timeout=60
    )

    # PNG 실제 크기 확인
    chk = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "sh", "-c",
         f"python3 -c \"from PIL import Image; img=Image.open('/tmp/concept_{safe}.png'); print(img.size, img.getextrema())\" 2>&1"],
        capture_output=True, text=True, timeout=10
    )

    print(f"\n=== {name} ===")
    print(f"  exit: {result.returncode}")
    print(f"  img info: {chk.stdout.strip()}")

    # 핵심: plt.savefig 호출 직전 코드 + 어떤 plot이 있는지
    for i, line in enumerate(code.splitlines()):
        if any(k in line for k in ["savefig", "plt.plot", "plt.imshow", "plt.figure", "fig,", "plt.colorbar", "add_subplot"]):
            print(f"  L{i+1}: {line.strip()}")

    # stderr 중 오류 라인
    stderr = result.stderr or result.stdout
    for l in stderr.splitlines():
        if any(k in l for k in ["Error", "Warning", "warning"]) and "Glyph" not in l:
            print(f"  ⚠ {l.strip()[:100]}")

    tmp.unlink(missing_ok=True)

conn.close()
