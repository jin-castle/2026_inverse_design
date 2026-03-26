"""nlopt 개념 demo_code 직접 실행 테스트."""
import subprocess, sqlite3, tempfile, re
from pathlib import Path
import sys
sys.path.insert(0, 'tools')
from run_concept_demos import preprocess_code

conn = sqlite3.connect("db/knowledge.db")
row = conn.execute("SELECT demo_code FROM concepts WHERE name='nlopt'").fetchone()
code = row[0] if row else ""
conn.close()

print("=== nlopt demo_code (첫 50줄) ===")
for i, line in enumerate(code.splitlines()[:50], 1):
    print(f"  {i:3}: {line}")

processed = preprocess_code(code, "nlopt")
safe = "nlopt"
tmp = Path(tempfile.gettempdir()) / "test_nlopt.py"
tmp.write_text(processed, encoding="utf-8")
subprocess.run(["docker", "cp", str(tmp), "meep-pilot-worker:/tmp/test_nlopt.py"], capture_output=True)

result = subprocess.run(
    ["docker", "exec", "meep-pilot-worker", "python3", "/tmp/test_nlopt.py"],
    capture_output=True, text=True, timeout=90
)
print(f"\nexit={result.returncode}")
out = (result.stderr or result.stdout)
for line in out.splitlines():
    if any(k in line for k in ["Error", "error", "rror", "Warning", "rning"]):
        print(f"  {line}")
print("stdout (last 5):")
for line in result.stdout.splitlines()[-5:]:
    print(f"  {line}")

# 이미지 확인
chk = subprocess.run(
    ["docker", "exec", "meep-pilot-worker", "sh", "-c",
     "python3 -c \"from PIL import Image; img=Image.open('/tmp/concept_nlopt.png'); print(img.size, img.getextrema())\" 2>&1"],
    capture_output=True, text=True
)
print(f"\n이미지: {chk.stdout.strip()}")
tmp.unlink(missing_ok=True)
