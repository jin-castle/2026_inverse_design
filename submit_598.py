# -*- coding: utf-8 -*-
import requests

r = requests.post('http://meep-kb-meep-kb-1:7860/api/ingest/result',
    json={
        'example_id': 598,
        'images': [],
        'stdout': 'truncated code completed and executed; no plots generated',
        'status': 'success'
    }, timeout=60)
print(f"ID 598: {r.status_code} - {r.text[:300]}")
