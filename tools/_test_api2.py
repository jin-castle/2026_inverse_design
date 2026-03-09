import urllib.request, json

payload = {
    "code": "import meep as mp\nsim = mp.Simulation(cell_size=mp.Vector3(10,10,0), resolution=20)",
    "error": "MPIError: The number of adjoint chunks (3) is not equal to the number of forward chunks (0)"
}
data = json.dumps(payload).encode('utf-8')
# 포트 7860 사용
req = urllib.request.Request(
    "http://localhost:7860/api/diagnose",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST"
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    db_results = result.get('db_results', [])
    print(f"DB 결과: {len(db_results)}개")
    for r in db_results[:3]:
        print(f"  [{r.get('source')}] {r.get('type')}: {r.get('title','')[:60]}")
        if r.get('solution'):
            print(f"    -> {r.get('solution','')[:100]}")
    mode = result.get('mode', '?')
    print(f"mode: {mode}")
except Exception as e:
    print(f"오류: {e}")
