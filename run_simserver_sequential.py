#!/usr/bin/env python3
"""
SimServer에서 실행 — SSH로 복사 후 순차 mpirun 실행
결과는 ngrok URL로 POST
SimServer에서 직접 실행: python3 /tmp/run_simserver.py
"""
import os, subprocess, glob, base64, json, time
import urllib.request

RESULTS_DIR = "/tmp/kb_results_sim"
SCRIPTS_DIR = "/tmp/sim_scripts"
API_URL = "https://rubi-unmirrored-corruptibly.ngrok-free.dev/api/ingest/result"
NP = 32
TIMEOUT = 1800  # 30분

SIMSERVER_IDS = [341, 353, 375, 389, 505, 513, 526, 528, 548, 573]

os.makedirs(RESULTS_DIR, exist_ok=True)

log_path = "/tmp/sim_run.log"

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(log_path, 'a') as f:
        f.write(line + '\n')

def submit_result(eid, img_paths, stdout_text, status):
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
        "images": images_b64,
        "stdout": (stdout_text or "")[:5000],
        "status": status
    }).encode('utf-8')

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read().decode())
        log(f"  → API OK: {result.get('status','?')} (이미지 {len(images_b64)}장)")
        return True
    except Exception as e:
        log(f"  → API 실패: {e}")
        return False

log("=== SimServer 순차 실행 시작 ===")
log(f"대상: {SIMSERVER_IDS}")

total_success = []
total_failed = []

for eid in SIMSERVER_IDS:
    script_path = f"{SCRIPTS_DIR}/ex_{eid}.py"
    if not os.path.exists(script_path):
        log(f"[id={eid}] 스크립트 없음, 스킵")
        continue

    # 기존 결과 파일 제거
    for old in glob.glob(f"{RESULTS_DIR}/ex_{eid}_*.png"):
        os.remove(old)

    log(f"\n[id={eid}] 실행 시작 (-np {NP})...")
    t0 = time.time()

    try:
        result = subprocess.run(
            ['mpirun', '-np', str(NP), 'python3', script_path],
            capture_output=True, text=True, timeout=TIMEOUT,
            cwd='/tmp'
        )
        elapsed = time.time() - t0
        log(f"  returncode={result.returncode}, 소요={elapsed:.0f}s")

        stdout_text = result.stdout + result.stderr
        if result.returncode != 0:
            log(f"  STDERR 마지막 5줄:\n    " + '\n    '.join((result.stderr or '').strip().split('\n')[-5:]))
        else:
            log(f"  stdout 마지막 3줄:\n    " + '\n    '.join((result.stdout or '').strip().split('\n')[-3:]))

        imgs = glob.glob(f"{RESULTS_DIR}/ex_{eid}_*.png")
        log(f"  이미지: {len(imgs)}개")

        if imgs:
            submit_result(eid, imgs, stdout_text, 'success')
            total_success.append(eid)
        elif result.returncode == 0:
            log(f"  returncode=0이지만 이미지 없음")
            submit_result(eid, [], stdout_text, 'failed')
            total_failed.append(eid)
        else:
            submit_result(eid, [], stdout_text, 'failed')
            total_failed.append(eid)

    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        log(f"  TIMEOUT ({elapsed:.0f}s) → timeout 제출")
        payload = json.dumps({
            "example_id": eid, "images": [],
            "stdout": f"Timeout after {elapsed:.0f}s on SimServer -np{NP}",
            "status": "timeout"
        }).encode()
        req = urllib.request.Request(API_URL, data=payload,
            headers={'Content-Type': 'application/json'}, method='POST')
        try:
            urllib.request.urlopen(req, timeout=10)
        except:
            pass
        total_failed.append(eid)

    except Exception as e:
        log(f"  예외: {e}")
        total_failed.append(eid)

log(f"\n=== 완료 ===")
log(f"성공: {total_success}")
log(f"실패/타임아웃: {total_failed}")
