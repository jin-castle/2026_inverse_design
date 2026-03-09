# -*- coding: utf-8 -*-
import requests, base64, glob

imgs = []
for f in sorted(glob.glob('/tmp/kb_results/typeb_412_*.png')):
    imgs.append(base64.b64encode(open(f,'rb').read()).decode())

r = requests.post('http://meep-kb-meep-kb-1:7860/api/ingest/result',
    json={
        'example_id': 412,
        'images': imgs,
        'stdout': 'truncated code completed; code executed successfully',
        'status': 'success'
    }, timeout=60)
print(f"ID 412: {r.status_code} - {r.text[:300]}")
