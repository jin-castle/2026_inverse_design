"""15개 문제 이미지를 Docker에서 직접 재실행하여 실제 에러 원인 파악."""
import subprocess, sqlite3, re, tempfile
from pathlib import Path
import sys
sys.path.insert(0, 'tools')
from run_concept_demos import preprocess_code

ISSUES = [
    "nlopt", "Harminv", "LDOS", "ring_resonator", "add_energy",
    "at_every", "get_eigenmode_coefficients", "phase_velocity",
    "LorentzianSusceptibility", "Medium", "DrudeSusceptibility",
    "FOM", "GaussianSource", "MPB", "OptimizationProblem"
]

conn = sqlite3.connect("db/knowledge.db")
results = {}
for name in ISSUES:
    row = conn.execute("SELECT demo_code FROM concepts WHERE name=?", (name,)).fetchone()
    if not row or not row[0]:
        results[name] = "no_code"
        continue

    code = preprocess_code(row[0], name)
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    tmp = Path(tempfile.gettempdir()) / f"_chk15_{safe}.py"
    tmp.write_text(code, encoding="utf-8")
    subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/_chk15_{safe}.py"], capture_output=True)

    r = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/_chk15_{safe}.py"],
        capture_output=True, text=True, timeout=120
    )
    tmp.unlink(missing_ok=True)

    # 이미지 크기 + pixel 분포
    chk = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "sh", "-c",
         f"python3 -c \"from PIL import Image,ImageStat; i=Image.open('/tmp/concept_{safe}.png').convert('RGB'); s=ImageStat.Stat(i); print(f'size={{i.size}} mean={{[round(x,1) for x in s.mean]}}')\" 2>&1"],
        capture_output=True, text=True, timeout=10
    )

    stderr_key = ""
    for line in (r.stderr or r.stdout).splitlines():
        if any(k in line for k in ["Error", "warning", "Warning", "rror", "skip", "not install"]):
            if "Glyph" not in line:
                stderr_key = line.strip()[:120]
                break

    results[name] = {
        "exit": r.returncode,
        "img": chk.stdout.strip(),
        "issue": stderr_key
    }

conn.close()

print("\n=== 15개 이미지 실행 결과 ===\n")
blank = []  # 빈/흰색으로 확인됨
real_error = []  # 실제 실행 오류
ok_but_white = []  # 실행은 됐지만 그래프 내용이 흰색

for name, r in results.items():
    if r == "no_code":
        print(f"❌ {name}: 코드 없음")
        real_error.append(name)
        continue

    exit_ok = r["exit"] == 0
    img_info = r["img"]
    issue = r["issue"]

    # mean > 240이면 사실상 흰색
    is_white = False
    if "mean=" in img_info:
        import re as _re
        m = _re.search(r'mean=\[([^\]]+)\]', img_info)
        if m:
            means = [float(x) for x in m.group(1).split(',')]
            is_white = all(v > 230 for v in means)

    status = "✅" if (exit_ok and not is_white) else ("⚠️" if exit_ok else "❌")
    print(f"{status} {name}:")
    print(f"   exit={r['exit']} | {img_info}")
    if issue:
        print(f"   issue: {issue}")

    if not exit_ok or issue:
        real_error.append(name)
    elif is_white:
        blank.append(name)
    else:
        ok_but_white.append(name)

print(f"\n실행 오류: {real_error}")
print(f"빈 그래프: {blank}")
print(f"실제 정상 (흰 배경이지만 내용 있음): {ok_but_white}")
