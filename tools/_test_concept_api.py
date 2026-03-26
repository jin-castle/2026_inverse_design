"""PML 개념 감지 + chat API 응답 확인."""
import urllib.request, json

URL = "http://localhost:8765/api/chat"
body = json.dumps({"message": "PML이 뭐야", "history": [], "n": 5}).encode()
req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read())

print("=== concept 섹션 ===")
c = data.get("concept")
if c:
    print(f"  matched: {c['matched']}")
    print(f"  name_ko: {c['name_ko']}")
    print(f"  summary: {c['summary'][:100]}")
    print(f"  image: {c['result_images']}")
    print(f"  mistakes: {len(c['common_mistakes'])}개")
    print(f"  related: {c['related_concepts']}")
    print(f"  demo_code: {len(c.get('demo_code',''))}자")
else:
    print("  ❌ concept 없음")

print(f"\n=== 일반 결과: {len(data.get('results',[]))}건 ===")
print(f"mode: {data.get('mode')}")
print(f"intent: {data.get('intent')}")
