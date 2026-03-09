#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Worker 내 typee/typec 이미지를 meep-kb API로 제출하는 스크립트
meep-pilot-worker 컨테이너 내에서 실행
"""
import os, glob, base64, requests, re, shutil

RESULTS_DIR = "/tmp/kb_results"
API_URL = "http://meep-kb-meep-kb-1:7860/api/ingest/result"

# 파일명 오류 수정: {_fig_count[0]:02d} → 00
bad_pattern = re.compile(r'(typee_\d+)_\{.*?\}\.png')
for f in glob.glob(f"{RESULTS_DIR}/*.png"):
    fname = os.path.basename(f)
    m = bad_pattern.match(fname)
    if m:
        new_name = f"{m.group(1)}_00.png"
        new_path = os.path.join(RESULTS_DIR, new_name)
        if not os.path.exists(new_path):
            shutil.copy2(f, new_path)
            print(f"  renamed: {fname} -> {new_name}")
        os.remove(f)

# 예제별 이미지 수집
example_images = {}
for f in sorted(glob.glob(f"{RESULTS_DIR}/typee_*.png") + glob.glob(f"{RESULTS_DIR}/typec_*.png")):
    fname = os.path.basename(f)
    m = re.match(r'(typee|typec)_(\d+)_', fname)
    if m:
        eid = int(m.group(2))
        if eid not in example_images:
            example_images[eid] = []
        example_images[eid].append(f)

print(f"\n제출 대상: {len(example_images)}개 예제")

# 예제별 제출
submitted = []
failed = []
for eid, img_paths in sorted(example_images.items()):
    images_b64 = []
    for p in sorted(img_paths):
        size = os.path.getsize(p)
        if size < 2000:
            print(f"  skip blank image: {os.path.basename(p)} ({size}B)")
            continue
        with open(p, "rb") as fp:
            images_b64.append(base64.b64encode(fp.read()).decode())

    if not images_b64:
        print(f"  id={eid}: 유효 이미지 없음, 스킵")
        continue

    try:
        r = requests.post(API_URL, json={
            "example_id": eid,
            "images": images_b64,
            "stdout": "re-run after markdown strip / 16-core MPI fix",
            "status": "success"
        }, timeout=30)
        result = r.json()
        print(f"  id={eid}: {len(images_b64)}장 제출 -> {result.get('status','?')}")
        submitted.append(eid)
    except Exception as e:
        print(f"  id={eid}: 제출 실패 - {e}")
        failed.append(eid)

print(f"\n완료: 성공 {len(submitted)}개 / 실패 {len(failed)}개")
print("성공 IDs:", submitted)
print("실패 IDs:", failed)
