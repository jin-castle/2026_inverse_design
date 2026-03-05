import urllib.request, json

req = urllib.request.Request(
    "http://localhost:8765/api/search",
    data=json.dumps({"query": "adjoint simulation 메모리 오류", "n": 3}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req, timeout=30) as r:
    d = json.loads(r.read())

print("mode:", d["mode"])
print("results:", len(d["results"]))
print("\n=== 답변 ===")
print(d.get("answer", "(없음)")[:1000])
