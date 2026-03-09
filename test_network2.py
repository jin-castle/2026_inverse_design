import urllib.request, json

base = 'http://meep-kb-meep-kb-1:7860'
for path in ['/', '/docs', '/api/examples/1', '/api/ingest/result']:
    try:
        resp = urllib.request.urlopen(f'{base}{path}', timeout=5)
        print(f'OK {path}: {resp.status}')
    except Exception as e:
        print(f'ERR {path}: {e}')
