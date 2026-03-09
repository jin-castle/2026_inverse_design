#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
typec 시뮬레이션을 순서대로 하나씩 실행 + 완료 시 바로 API 제출
meep-pilot-worker 내에서 실행
"""
import subprocess, os, glob, base64, requests, time, json

API_URL = "http://meep-kb-meep-kb-1:7860/api/ingest/result"
RESULTS_DIR = "/tmp/kb_results"
MPI_CMD = "/usr/bin/mpirun"
PYTHON = "/opt/conda/envs/mp/bin/python3"
TIMEOUT = 900  # 15분

# 이미 제출된 것 제외, 505(25시간)는 스킵
SKIP = {378, 559, 505}
IDS = [341, 353, 526, 573, 575, 333, 381, 389, 513, 528, 539, 548, 554, 562, 592, 375, 400]

results = {"success": [], "failed": [], "timeout": []}

def submit(eid, stdout_tail=""):
    imgs = sorted(glob.glob(f"{RESULTS_DIR}/typec_{eid}_*.png"))
    if not imgs:
        print(f"  [!] id={eid}: 이미지 없음", flush=True)
        return False
    b64 = []
    for p in imgs:
        if os.path.getsize(p) > 2000:
            b64.append(base64.b64encode(open(p,'rb').read()).decode())
    if not b64:
        print(f"  [!] id={eid}: 유효 이미지 없음 (blank)", flush=True)
        return False
    try:
        r = requests.post(API_URL, json={
            "example_id": eid,
            "images": b64,
            "stdout": stdout_tail[-2000:] if stdout_tail else "16-core MPI re-run",
            "status": "success"
        }, timeout=30)
        print(f"  [OK] id={eid}: {len(b64)}장 제출 -> {r.json().get('status','?')}", flush=True)
        return True
    except Exception as e:
        print(f"  [ERR] id={eid} 제출 실패: {e}", flush=True)
        return False

os.makedirs(RESULTS_DIR, exist_ok=True)

for eid in IDS:
    if eid in SKIP:
        print(f"\n[SKIP] id={eid}", flush=True)
        continue

    script = f"/tmp/typec_{eid}.py"
    log_file = f"/tmp/typec2_{eid}.log"

    print(f"\n{'='*50}", flush=True)
    print(f"[START] id={eid} ...", flush=True)

    # 이미 이미지가 있으면 바로 제출
    if glob.glob(f"{RESULTS_DIR}/typec_{eid}_*.png"):
        print(f"  기존 이미지 발견, 바로 제출", flush=True)
        if submit(eid):
            results["success"].append(eid)
        continue

    if not os.path.exists(script):
        print(f"  [!] 스크립트 없음: {script}", flush=True)
        results["failed"].append(eid)
        continue

    t0 = time.time()
    try:
        proc = subprocess.run(
            [MPI_CMD, "--allow-run-as-root", "-np", "8", PYTHON, script],
            capture_output=True, text=True, timeout=TIMEOUT
        )
        elapsed = int(time.time() - t0)
        stdout = (proc.stdout or "") + (proc.stderr or "")
        print(f"  완료 ({elapsed}s), returncode={proc.returncode}", flush=True)
        print(f"  마지막 출력: {stdout[-200:].strip()}", flush=True)

        # 로그 저장
        with open(log_file, "w") as f:
            f.write(stdout)

    except subprocess.TimeoutExpired:
        elapsed = int(time.time() - t0)
        print(f"  [TIMEOUT] id={eid} ({elapsed}s)", flush=True)
        results["timeout"].append(eid)
        continue
    except Exception as e:
        print(f"  [ERR] id={eid}: {e}", flush=True)
        results["failed"].append(eid)
        continue

    # 이미지 제출
    if submit(eid, stdout):
        results["success"].append(eid)
    else:
        results["failed"].append(eid)

print(f"\n{'='*50}", flush=True)
print(f"완료: {results}", flush=True)

with open("/tmp/typec_run2_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("결과 저장: /tmp/typec_run2_results.json", flush=True)
