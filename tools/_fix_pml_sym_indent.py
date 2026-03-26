"""PML, Symmetry - preprocess_code 없이 직접 실행."""
import subprocess, sqlite3, re
from pathlib import Path

DB_PATH = Path("db/knowledge.db")
RESULTS_DIR = Path("db/results")

conn = sqlite3.connect(str(DB_PATH), timeout=15)

for name in ["PML", "Symmetry"]:
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    code = conn.execute("SELECT demo_code FROM concepts WHERE name=?", (name,)).fetchone()[0]

    # 파일로 직접 저장 (preprocess_code 없이)
    import tempfile
    tmp = Path(tempfile.gettempdir()) / f"direct_{safe}.py"
    tmp.write_text(code, encoding="utf-8")
    subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/direct_{safe}.py"], capture_output=True)

    r = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/direct_{safe}.py"],
        capture_output=True, text=True, timeout=180
    )
    print(f"{name}: exit={r.returncode}")
    if r.returncode != 0:
        for l in (r.stderr or r.stdout).splitlines()[-5:]:
            print(f"  {l}")
    else:
        img_local = RESULTS_DIR / f"concept_{safe}.png"
        cp = subprocess.run(
            ["docker", "cp", f"meep-pilot-worker:/tmp/concept_{safe}.png", str(img_local)],
            capture_output=True, timeout=10
        )
        size = img_local.stat().st_size // 1024 if img_local.exists() else 0
        print(f"  이미지: {size}KB")
        if size > 5:
            conn.execute(
                "UPDATE concepts SET result_images=?, updated_at=CURRENT_TIMESTAMP WHERE name=?",
                (f"/static/results/concept_{safe}.png", name)
            )
            conn.commit()
    tmp.unlink(missing_ok=True)

conn.close()
