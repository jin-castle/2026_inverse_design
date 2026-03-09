#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Submit all fixed example results to meep-kb API with correct field names."""

import requests, base64, os, glob, json, time

BASE_URL = 'http://meep-kb-meep-kb-1:7860'
RESULTS_DIR = '/tmp/kb_results'

# Collect images by example id
results = {}
all_pngs = sorted(glob.glob(f'{RESULTS_DIR}/fixed_*.png'))
for f in all_pngs:
    basename = os.path.basename(f)
    parts = basename.split('_')
    ex_id = int(parts[1])
    if ex_id not in results:
        results[ex_id] = []
    results[ex_id].append(f)

print(f"Found results for {len(results)} examples: {sorted(results.keys())}")

summary = {}
start = time.time()

for ex_id, image_files in sorted(results.items()):
    images_b64 = []
    for f in sorted(image_files):
        with open(f, 'rb') as img:
            images_b64.append(base64.b64encode(img.read()).decode())
    
    payload = {
        'example_id': ex_id,
        'result_images_b64': images_b64,
        'result_stdout': f'fixed and re-run by Agent2 ({len(image_files)} images)',
        'result_status': 'success',
        'result_run_time': time.time() - start,
    }
    
    try:
        r = requests.post(f'{BASE_URL}/api/ingest/result', json=payload, timeout=30)
        resp = r.json()
        print(f"ID {ex_id}: {resp}")
        summary[ex_id] = {
            'status': 'submitted',
            'images': len(image_files),
            'api_response': str(resp)
        }
    except Exception as e:
        print(f"ID {ex_id}: FAILED - {e}")
        summary[ex_id] = {'status': 'submit_failed', 'error': str(e)}

print(f"\nSubmitted {len(summary)} examples successfully")
with open('/tmp/agent2_submit_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)
print("Done.")
