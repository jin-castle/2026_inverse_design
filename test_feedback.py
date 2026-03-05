import urllib.request, json

# 1. 피드백 제출 테스트
req = urllib.request.Request(
    "http://localhost:8765/api/feedback",
    data=json.dumps({
        "query": "adjoint 메모리 오류",
        "answer_id": "test-001",
        "result_index": 1,
        "result_title": "adjoint simulation crash upon calling run",
        "result_url": "https://github.com/NanoComp/meep/issues/2309"
    }).encode(),
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req, timeout=10) as r:
    d = json.loads(r.read())
print("피드백 제출:", d)

# 2. 통계 확인
req2 = urllib.request.Request("http://localhost:8765/api/feedback/stats")
with urllib.request.urlopen(req2, timeout=10) as r:
    d2 = json.loads(r.read())
print("피드백 통계:", d2)
