#!/usr/bin/env python3
"""539, 562, 592 재실행"""
import os, subprocess, glob, base64, json, time
import urllib.request

RESULTS_DIR = "/tmp/kb_results"
SCRIPTS_DIR = "/tmp/worker_scripts"
API_URL = "http://meep-kb-meep-kb-1:7860/api/ingest/result"
MPIRUN = "/usr/bin/mpirun"
PYTHON = "/opt/conda/envs/mp/bin/python3"
NP = 4
TIMEOUT = 1500

TARGET_IDS = [539, 562, 592]

os.makedirs(RESULTS_DIR, exist_ok=True)
log_path = "/tmp/remaining_run.log"

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(log_path, 'a') as f:
        f.write(line + '\n')

def submit(eid, img_paths, stdout_text, status):
    images_b64 = []
    for p in sorted(img_paths):
        size = os.path.getsize(p)
        if size < 2000:
            log(f"  skip blank: {os.path.basename(p)} ({size}B)")
            continue
        with open(p, 'rb') as fp:
            images_b64.append(base64.b64encode(fp.read()).decode())

    payload = json.dumps({
        "example_id": eid,
        "result_images_b64": images_b64,
        "result_stdout": (stdout_text or "")[:3000],
        "result_status": status
    }).encode('utf-8')

    req = urllib.request.Request(API_URL, data=payload,
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        r = json.loads(resp.read().decode())
        log(f"  → API OK: {r} (이미지 {len(images_b64)}장)")
    except Exception as e:
        log(f"  → API 실패: {e}")

log(f"=== 재실행 시작: {TARGET_IDS} ===")

for eid in TARGET_IDS:
    script_path = f"{SCRIPTS_DIR}/ex_{eid}.py"
    if not os.path.exists(script_path):
        log(f"[{eid}] 스크립트 없음")
        continue

    # 기존 결과 제거
    for old in glob.glob(f"{RESULTS_DIR}/ex_{eid}_*.png") + glob.glob(f"{RESULTS_DIR}/ex_{eid}_r*.png"):
        os.remove(old)

    log(f"\n[id={eid}] 실행 시작...")
    t0 = time.time()

    try:
        result = subprocess.run(
            [MPIRUN, '--allow-run-as-root', '-np', str(NP), PYTHON, script_path],
            capture_output=True, text=True, timeout=TIMEOUT, cwd='/tmp'
        )
        elapsed = time.time() - t0
        log(f"  rc={result.returncode}, {elapsed:.0f}s")
        if result.returncode != 0:
            log(f"  ERR: " + '\n    '.join((result.stderr or '').strip().split('\n')[-5:]))

        imgs = glob.glob(f"{RESULTS_DIR}/ex_{eid}_*.png") + glob.glob(f"{RESULTS_DIR}/ex_{eid}_r*.png")
        log(f"  이미지 {len(imgs)}개")

        if imgs:
            submit(eid, imgs, result.stdout + result.stderr, 'success')
        else:
            submit(eid, [], result.stdout + result.stderr, 'failed' if result.returncode != 0 else 'success')
    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT → 제출")
        submit(eid, [], "timeout", 'timeout')
    except Exception as e:
        log(f"  예외: {e}")

log("=== 완료 ===")
