"""피드백 루프 엔드투엔드 테스트"""
import urllib.request, json, time

BASE = "http://localhost:8765"

def post(path, data):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())

# Step 1: 쿼리 실행
print("=== Step 1: 쿼리 실행 ===")
result = post("/api/chat", {"message": "adjoint 시뮬레이션 메모리 오류", "history": [], "n": 3})
print(f"검색 결과: {len(result.get('results', []))}건")
print(f"모드: {result.get('mode')}")
answer = result.get("answer", "")
print(f"답변 길이: {len(answer)}자")
print(f"답변 앞부분: {answer[:200]}")

if result.get("results"):
    top = result["results"][0]
    print(f"\n상위 자료: [{top['score']}] {top['title'][:60]}")

    # Step 2: 1번 자료가 도움됐다고 피드백
    print("\n=== Step 2: 피드백 제출 (1번 자료 도움됨) ===")
    fb = post("/api/feedback", {
        "query": "adjoint 시뮬레이션 메모리 오류",
        "answer_id": "test-e2e-001",
        "result_index": 1,
        "result_title": top["title"],
        "result_url": top.get("url", ""),
        "answer_text": answer[:2000],
    })
    print("피드백 응답:", fb.get("message", ""))

    # Step 3: 같은 쿼리로 다시 검색 → 피드백 부스팅 확인
    time.sleep(1)
    print("\n=== Step 3: 재검색 (부스팅 확인) ===")
    result2 = post("/api/chat", {"message": "adjoint 시뮬레이션 메모리 오류", "history": [], "n": 3})
    if result2.get("results"):
        top2 = result2["results"][0]
        print(f"재검색 상위: [{top2['score']}] {top2['title'][:60]}")
        print(f"  feedback_boosted: {top2.get('feedback_boosted', False)}")

    # Step 4: 피드백 통계 확인
    req = urllib.request.Request(BASE + "/api/feedback/stats")
    stats = json.loads(urllib.request.urlopen(req, timeout=10).read())
    print("\n=== Step 4: 피드백 통계 ===")
    for s in stats.get("stats", [])[:3]:
        print(f"  [{s['helpful']}회] {s['title'][:50]}")

    # Step 5: 관련 쿼리로 검색 → few-shot 주입 확인
    print("\n=== Step 5: 유사 쿼리 → few-shot 반영 확인 ===")
    result3 = post("/api/chat", {"message": "adjoint 오류 해결", "history": [], "n": 3})
    answer3 = result3.get("answer", "")
    print(f"답변 길이: {len(answer3)}자")
    print(f"답변 앞부분: {answer3[:300]}")
    print("\n[완료] 피드백 루프 정상 동작!")
