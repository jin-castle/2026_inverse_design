#!/usr/bin/env python3
"""SimServer 결과 이미지를 meep-kb API에 제출"""
import os, glob, base64, json, re
import urllib.request

API_URL = "http://localhost:8765/api/ingest/result"
RESULTS_DIR = r"C:\Users\user\projects\meep-kb\simserver_results"

# 파일명에서 ID 추출
example_images = {}
for f in sorted(glob.glob(os.path.join(RESULTS_DIR, "ex_*.png"))):
    fname = os.path.basename(f)
    m = re.match(r'ex_(\d+)_', fname)
    if m:
        eid = int(m.group(1))
        if eid not in example_images:
            example_images[eid] = []
        example_images[eid].append(f)

print(f"제출 대상: {len(example_images)}개 예제 - IDs: {sorted(example_images.keys())}")

for eid, imgs in sorted(example_images.items()):
    images_b64 = []
    for p in sorted(imgs):
        size = os.path.getsize(p)
        if size < 2000:
            print(f"  skip blank: {os.path.basename(p)} ({size}B)")
            continue
        with open(p, 'rb') as fp:
            images_b64.append(base64.b64encode(fp.read()).decode())

    if not images_b64:
        print(f"  id={eid}: 유효 이미지 없음, 스킵")
        continue

    payload = json.dumps({
        "example_id": eid,
        "result_images_b64": images_b64,
        "result_stdout": f"SimServer -np32 실행 완료",
        "result_status": "success"
    }).encode('utf-8')

    req = urllib.request.Request(
        API_URL, data=payload,
        headers={'Content-Type': 'application/json'}, method='POST'
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode())
        print(f"  id={eid}: {len(images_b64)}장 → {result.get('status','?')}")
    except Exception as e:
        print(f"  id={eid}: 실패 - {e}")

print("\n완료!")
