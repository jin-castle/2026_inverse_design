#!/usr/bin/env python3
"""
meep-pilot-worker 컨테이너 내에서 실행
Worker 그룹 예제들을 순차적으로 mpirun 실행 후 API 제출
"""
import os, subprocess, glob, base64, json, time
import urllib.request

RESULTS_DIR = "/tmp/kb_results"
SCRIPTS_DIR = "/tmp/worker_scripts"
API_URL = "http://meep-kb-meep-kb-1:7860/api/ingest/result"
MPIRUN = "/usr/bin/mpirun"
NP = 4
TIMEOUT = 1500  # 25분

WORKER_IDS = [333, 381, 400, 539, 562, 592]

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(SCRIPTS_DIR, exist_ok=True)

log_path = "/tmp/worker_run.log"

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
        "stdout": stdout_text[:5000] if stdout_text else "",
        "status": status
    }).encode('utf-8')

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode())
        log(f"  → API 제출 OK: {result.get('status','?')} (이미지 {len(images_b64)}장)")
        return True
    except Exception as e:
        log(f"  → API 제출 실패: {e}")
        return False

log("=== Worker 순차 실행 시작 ===")
log(f"대상: {WORKER_IDS}")

total_success = []
total_failed = []

for eid in WORKER_IDS:
    script_path = f"{SCRIPTS_DIR}/ex_{eid}.py"
    if not os.path.exists(script_path):
        log(f"[id={eid}] 스크립트 없음, 스킵")
        continue

    # 기존 결과 파일 제거
    for old in glob.glob(f"{RESULTS_DIR}/ex_{eid}_*.png"):
        os.remove(old)

    log(f"\n[id={eid}] 실행 시작...")
    t0 = time.time()

    try:
        result = subprocess.run(
            [MPIRUN, '--allow-run-as-root', '-np', str(NP), '/opt/conda/envs/mp/bin/python3', script_path],
            capture_output=True, text=True, timeout=TIMEOUT,
            cwd='/tmp'
        )
        elapsed = time.time() - t0
        log(f"  returncode={result.returncode}, 소요={elapsed:.0f}s")

        stdout_text = result.stdout + result.stderr
        if result.stdout:
            log(f"  stdout 마지막 5줄:\n    " + '\n    '.join(result.stdout.strip().split('\n')[-5:]))
        if result.returncode != 0:
            log(f"  STDERR:\n    " + '\n    '.join((result.stderr or '').strip().split('\n')[-5:]))

        # 이미지 파일 수집
        imgs = glob.glob(f"{RESULTS_DIR}/ex_{eid}_*.png")
        log(f"  이미지: {len(imgs)}개")

        if imgs:
            status = 'success'
            submit_result(eid, imgs, stdout_text, status)
            total_success.append(eid)
        elif result.returncode == 0:
            log(f"  returncode=0이지만 이미지 없음 → failed 제출")
            submit_result(eid, [], stdout_text, 'failed')
            total_failed.append(eid)
        else:
            log(f"  실행 실패 → failed 제출")
            submit_result(eid, [], stdout_text, 'failed')
            total_failed.append(eid)

    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        log(f"  TIMEOUT ({elapsed:.0f}s > {TIMEOUT}s) → timeout 제출")
        payload = json.dumps({
            "example_id": eid,
            "images": [],
            "stdout": f"Timeout after {elapsed:.0f}s",
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
        log(f"  예외 발생: {e}")
        total_failed.append(eid)

log(f"\n=== 완료 ===")
log(f"성공: {total_success}")
log(f"실패/타임아웃: {total_failed}")
