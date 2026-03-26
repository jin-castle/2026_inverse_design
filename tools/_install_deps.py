"""Docker에 누락 패키지 설치 + 실행 환경 점검."""
import subprocess

pkgs = ["nlopt", "scipy", "h5py"]
for pkg in pkgs:
    r = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "pip", "install", pkg, "-q",
         "--root-user-action=ignore"],
        capture_output=True, text=True, timeout=120
    )
    # 설치 확인
    chk = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", "-c", f"import {pkg}; print('{pkg}: OK')"],
        capture_output=True, text=True, timeout=10
    )
    status = "✅" if chk.returncode == 0 else "❌"
    print(f"{status} {pkg}: {chk.stdout.strip() or chk.stderr.strip()[:80]}")
