import urllib.request, json

queries = [
    "adjoint 메모리 오류",
    "EigenModeSource 설정",
    "simulation 발산",
    "mode converter 설계",
]

for q in queries:
    req = urllib.request.Request(
        "http://localhost:8765/api/search",
        data=json.dumps({"query": q, "n": 5}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read())
    scores = [(r["score"], r["source"], r["title"][:40]) for r in d["results"]]
    print(f"\n[{q}]")
    for s, src, t in scores:
        print(f"  {s:.3f} [{src}] {t}")
