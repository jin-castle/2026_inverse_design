import urllib.request, json

# 루트 확인
req = urllib.request.Request("http://localhost:8765/", method="GET")
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print("/ :", resp.status, resp.read()[:200])
except Exception as e:
    print("/ 오류:", e)

# openapi
req2 = urllib.request.Request("http://localhost:8765/openapi.json", method="GET")
try:
    with urllib.request.urlopen(req2, timeout=10) as resp:
        d = json.loads(resp.read())
        paths = list(d.get('paths', {}).keys())
        print("엔드포인트:")
        for p in paths[:20]:
            print(" ", p)
except Exception as e:
    print("openapi 오류:", e)
