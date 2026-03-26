"""DFT colormap을 jet으로 바꾼 나머지 개념들 Docker 재실행."""
import subprocess, sqlite3, re, tempfile
from pathlib import Path
import sys
sys.path.insert(0, 'tools')
from run_concept_demos import preprocess_code

DB_PATH = Path("db/knowledge.db")
RESULTS_DIR = Path("db/results")

conn = sqlite3.connect(str(DB_PATH), timeout=15)

# jet으로 업데이트됐고 아직 재실행 안 한 것들
already_done = {
    "PML", "bend", "waveguide", "EigenmodeSource", "FluxRegion",
    "get_array", "plot2D", "Symmetry", "directional_coupler", "grating_coupler"
}

rows = conn.execute(
    "SELECT name, demo_code FROM concepts WHERE demo_code LIKE '%get_dft_array%'"
).fetchall()

targets = [(n, c) for n, c in rows if n not in already_done]
print(f"재실행 대상: {len(targets)}개\n")

success = 0
for name, code in targets:
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    processed = preprocess_code(code, name)

    tmp = Path(tempfile.gettempdir()) / f"_rerun_{safe}.py"
    tmp.write_text(processed, encoding="utf-8")
    subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/_rerun_{safe}.py"],
                   capture_output=True)
    r = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/_rerun_{safe}.py"],
        capture_output=True, text=True, timeout=180
    )
    tmp.unlink(missing_ok=True)

    if r.returncode != 0:
        print(f"  ❌ {name}: {r.stderr.splitlines()[-3:]}")
        continue

    # 이미지 회수
    output_path = f"/tmp/concept_{safe}.png"
    img_local = RESULTS_DIR / f"concept_{safe}.png"
    cp = subprocess.run(
        ["docker", "cp", f"meep-pilot-worker:{output_path}", str(img_local)],
        capture_output=True, timeout=10
    )
    if cp.returncode == 0 and img_local.exists() and img_local.stat().st_size > 5000:
        size = img_local.stat().st_size // 1024
        conn.execute(
            "UPDATE concepts SET demo_code=?, result_images=?, updated_at=CURRENT_TIMESTAMP WHERE name=?",
            (processed, f"/static/results/concept_{safe}.png", name)
        )
        conn.commit()
        print(f"  ✅ {name}: {size}KB")
        success += 1
    else:
        print(f"  ⚠️ {name}: 이미지 회수 실패")

conn.close()
print(f"\n=== 완료: {success}/{len(targets)} ===")
