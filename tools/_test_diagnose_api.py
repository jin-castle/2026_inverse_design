import urllib.request, json

# 엔드포인트 목록 확인
req = urllib.request.Request("http://localhost:8765/openapi.json")
with urllib.request.urlopen(req, timeout=10) as r:
    d = json.loads(r.read())
paths = list(d.get('paths', {}).keys())
print("엔드포인트:", paths)

# /api/diagnose 테스트
payload = {
    "code": "import meep as mp\nsim = mp.Simulation(resolution=20)\nsim.run(until=100)",
    "error": "MPIError: adjoint chunks (3) != forward chunks (0)\nSimulation diverged",
    "n": 4
}
data = json.dumps(payload).encode('utf-8')
req2 = urllib.request.Request(
    "http://localhost:8765/api/diagnose",
    data=data, headers={"Content-Type": "application/json"}, method="POST"
)
try:
    with urllib.request.urlopen(req2, timeout=30) as r:
        result = json.loads(r.read())
    print(f"\nDB 결과: {result.get('db_count')}개, 벡터: {result.get('vec_count')}개")
    print(f"top_score: {result.get('top_score')}, db_sufficient: {result.get('db_sufficient')}")
    print(f"에러타입: {result.get('error_info',{}).get('primary_type')}")
    print(f"제안 수: {len(result.get('suggestions',[]))}")
    for s in result.get('suggestions', [])[:3]:
        print(f"  [{s.get('source')}] {s.get('title','')[:60]} (score={s.get('score')})")
    print(f"LLM: {result.get('llm_result',{}).get('available')}")
except Exception as e:
    print(f"오류: {e}")
    import traceback; traceback.print_exc()
