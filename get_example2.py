import urllib.request, json, sys
# The list endpoint requires POST
import urllib.parse

# Try POST
data = json.dumps({"limit": 5}).encode()
req = urllib.request.Request(
    "http://localhost:7860/api/examples/list",
    data=data,
    headers={"Content-Type": "application/json"},
    method='POST'
)
try:
    r = urllib.request.urlopen(req, timeout=10)
    result = json.loads(r.read())
    print(json.dumps(result, ensure_ascii=False)[:2000])
except Exception as e:
    print(f"POST failed: {e}")
    
# Try without params
req2 = urllib.request.Request(
    "http://localhost:7860/api/examples/list",
    data=b'{}',
    headers={"Content-Type": "application/json"},
    method='POST'
)
try:
    r2 = urllib.request.urlopen(req2, timeout=10)
    result2 = json.loads(r2.read())
    print(type(result2))
    if isinstance(result2, list):
        print(f"Got {len(result2)} examples")
        if result2:
            print("Keys:", list(result2[0].keys()))
    else:
        print(json.dumps(result2, ensure_ascii=False)[:500])
except Exception as e:
    print(f"POST2 failed: {e}")
