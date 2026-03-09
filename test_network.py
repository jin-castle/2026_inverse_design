import urllib.request, json
try:
    resp = urllib.request.urlopen('http://meep-kb-meep-kb-1:7860/health', timeout=5)
    print('meep-kb API 접근 OK:', resp.read().decode()[:100])
except Exception as e:
    print('ERROR:', e)

# localhost:8765도 시도
try:
    resp = urllib.request.urlopen('http://host.docker.internal:8765/health', timeout=5)
    print('host.docker.internal:8765 OK:', resp.read().decode()[:100])
except Exception as e:
    print('host.docker.internal ERROR:', e)
