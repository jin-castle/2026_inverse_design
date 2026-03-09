import urllib.request, json

base = 'http://meep-kb-meep-kb-1:7860'

# /docs에서 openapi schema 가져오기
try:
    resp = urllib.request.urlopen(f'{base}/openapi.json', timeout=5)
    schema = json.loads(resp.read().decode())
    paths = list(schema.get('paths', {}).keys())
    print('API 경로 목록:')
    for p in sorted(paths):
        methods = list(schema['paths'][p].keys())
        print(f'  {p}: {methods}')
except Exception as e:
    print(f'openapi.json 오류: {e}')
