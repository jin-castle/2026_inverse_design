# -*- coding: utf-8 -*-
import requests, base64, glob
imgs = []
for f in sorted(glob.glob('/tmp/kb_results/typee_581_*.png')):
    imgs.append(base64.b64encode(open(f,'rb').read()).decode())
r = requests.post('http://meep-kb-meep-kb-1:7860/api/ingest/result',
    json={'example_id': 581, 'images': imgs, 'stdout': 'notebook markdown stripped and re-run', 'status': 'success'}, timeout=60)
print(f"ID 581: {r.status_code} - {r.text[:200]}")
