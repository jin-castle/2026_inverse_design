import urllib.request, json

KB_URL = "http://localhost:8765"

# 테스트 1: changed_materials (marl_auto 항목)
payload1 = {
    "code": "opt = mpa.OptimizationProblem(...)\nfor i in range(10):\n    f, dJ = opt(x, need_gradient=True)",
    "error": "RuntimeError: changed_materials: cannot add new materials to a simulation after it has been run",
    "n": 5
}
# 테스트 2: Divergence (marl_auto 항목)
payload2 = {
    "code": "sim = mp.Simulation(resolution=5)\nsim.run(until=500)",
    "error": "meep: Simulation diverged at t=42.5. NaN detected in field components.",
    "n": 5
}
# 테스트 3: MPI chunks (marl_auto 항목)
payload3 = {
    "code": "mpirun -np 10 python adjoint_sim.py",
    "error": "MPI_Abort was invoked on rank 0 with errorcode 1. The number of adjoint chunks is not equal",
    "n": 5
}

for i, payload in enumerate([payload1, payload2, payload3], 1):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{KB_URL}/api/diagnose", data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        result = json.loads(r.read())

    print(f"\n[테스트 {i}] {payload['error'][:60]}")
    print(f"  top_score={result['top_score']} | db_sufficient={result['db_sufficient']}")
    for s in result.get('suggestions', [])[:3]:
        marl_flag = "⭐" if "marl_auto" in s.get("source","") else "  "
        print(f"  {marl_flag}[{s['source']}] score={s['score']}: {s['title'][:60]}")
