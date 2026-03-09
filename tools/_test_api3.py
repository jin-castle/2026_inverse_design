import urllib.request, json

payload = {
    "code": "import meep as mp\nsim = mp.Simulation(cell_size=mp.Vector3(10,10,0), resolution=20)",
    "error": "MPIError: adjoint chunks (3) is not equal to forward chunks (0)"
}
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(
    "http://localhost:8765/api/diagnose",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST"
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    result = json.loads(raw)
    db_results = result.get('db_results', [])
    print(f"DB 결과: {len(db_results)}개")
    for r in db_results[:4]:
        print(f"  [{r.get('source')}] {r.get('type')}: {r.get('title','')[:60]}")
        sol = r.get('solution','')
        if sol:
            print(f"    -> {sol[:100]}")
    mode = result.get('mode', '?')
    print(f"\nmode: {mode}")
except Exception as e:
    print(f"오류: {e}")
    import traceback
    traceback.print_exc()
