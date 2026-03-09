# -*- coding: utf-8 -*-
import requests, base64, glob

imgs = []
for f in sorted(glob.glob('/tmp/kb_results/typee_533_*.png')):
    imgs.append(base64.b64encode(open(f,'rb').read()).decode())

r = requests.post('http://meep-kb-meep-kb-1:7860/api/ingest/result',
    json={
        'example_id': 533,
        'images': imgs,
        'stdout': 'notebook markdown stripped; code cleaned and executed',
        'status': 'success'
    }, timeout=60)
print(f"ID 533: {r.status_code} - {r.text[:300]}")
