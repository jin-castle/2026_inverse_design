#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
typec 시뮬레이션 완료 모니터링 + 자동 제출
meep-pilot-worker 내에서 실행
"""
import os, glob, base64, requests, time

API_URL = "http://meep-kb-meep-kb-1:7860/api/ingest/result"
RESULTS_DIR = "/tmp/kb_results"
# 너무 오래 걸리는 것은 스킵 (505: 25시간, 400: 46분 이상)
SKIP_IDS = {505}
IDS = [333,341,353,375,381,389,400,513,526,528,539,548,554,562,573,575,592]

submitted = set()

def submit(eid):
    imgs = sorted(glob.glob(f"{RESULTS_DIR}/typec_{eid}_*.png"))
    if not imgs:
        return False
    b64 = []
    for p in imgs:
        if os.path.getsize(p) < 2000:
            continue
        with open(p, "rb") as f:
            b64.append(base64.b64encode(f.read()).decode())
    if not b64:
        return False
    try:
        r = requests.post(API_URL, json={
            "example_id": eid,
            "images": b64,
            "stdout": f"16-core MPI re-run, {len(b64)} image(s)",
            "status": "success"
        }, timeout=30)
        print(f"[SUBMIT] id={eid}: {len(b64)}장 -> {r.json().get('status','?')}", flush=True)
        return True
    except Exception as e:
        print(f"[SUBMIT] id={eid} 실패: {e}", flush=True)
        return False

print("모니터링 시작 (60초 간격, 최대 30분)")
start = time.time()
max_wait = 1800  # 30분

while time.time() - start < max_wait:
    remaining = []
    for eid in IDS:
        if eid in submitted or eid in SKIP_IDS:
            continue
        imgs = glob.glob(f"{RESULTS_DIR}/typec_{eid}_*.png")
        if imgs:
            if submit(eid):
                submitted.add(eid)
        else:
            remaining.append(eid)

    elapsed = int(time.time() - start)
    print(f"[{elapsed}s] 제출완료: {sorted(submitted)} | 대기중: {remaining}", flush=True)

    if not remaining:
        print("모든 완료!", flush=True)
        break
    time.sleep(60)

print(f"\n최종: 제출 {len(submitted)}개: {sorted(submitted)}")
print(f"미완료: {[i for i in IDS if i not in submitted and i not in SKIP_IDS]}")
