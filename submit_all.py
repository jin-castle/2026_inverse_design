#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Submit all fixed example results to meep-kb API."""

import requests, base64, os, glob, json

BASE_URL = 'http://meep-kb-meep-kb-1:7860'
RESULTS_DIR = '/tmp/kb_results'

# Map of example_id -> list of image files in order
results = {}

all_pngs = sorted(glob.glob(f'{RESULTS_DIR}/fixed_*.png'))
for f in all_pngs:
    basename = os.path.basename(f)
    # Extract ID from filename like fixed_382_00.png
    parts = basename.split('_')
    ex_id = int(parts[1])
    if ex_id not in results:
        results[ex_id] = []
    results[ex_id].append(f)

print(f"Found results for {len(results)} examples: {sorted(results.keys())}")

summary = {}

for ex_id, image_files in sorted(results.items()):
    images_b64 = []
    for f in sorted(image_files):
        with open(f, 'rb') as img:
            images_b64.append(base64.b64encode(img.read()).decode())
    
    payload = {
        'example_id': ex_id,
        'images': images_b64,
        'stdout': f'fixed and re-run successfully ({len(image_files)} images)',
        'status': 'success'
    }
    
    try:
        r = requests.post(f'{BASE_URL}/api/ingest/result', json=payload, timeout=30)
        resp = r.json()
        print(f"ID {ex_id}: {resp}")
        summary[ex_id] = {'status': 'submitted', 'images': len(image_files), 'response': str(resp)}
    except Exception as e:
        print(f"ID {ex_id}: FAILED - {e}")
        summary[ex_id] = {'status': 'submit_failed', 'error': str(e)}

print(f"\nDone! Submitted {len(summary)} examples.")
with open('/tmp/agent2_submit_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)
