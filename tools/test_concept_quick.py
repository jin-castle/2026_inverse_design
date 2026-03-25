# -*- coding: utf-8 -*-
import urllib.request, json, time

def post(path, data):
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        'http://localhost:8765' + path, data=body,
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )
    r = urllib.request.urlopen(req, timeout=20)
    return json.loads(r.read())

# 서버 준비 대기
for i in range(10):
    try:
        urllib.request.urlopen('http://localhost:8765/', timeout=5)
        print("서버 준비 완료")
        break
    except:
        print(f"  대기 중... ({i+1}/10)")
        time.sleep(3)

# TEST 1: PML 개념 질문
print("\n[TEST 1] PML 개념 질문")
r = post('/api/concept', {'query': 'PML what is it'})
print(f"  matched: {r.get('matched_concept')}")
print(f"  name_ko: {r.get('name_ko')}")
print(f"  confidence: {r.get('confidence')}")
print(f"  summary: {(r.get('summary') or '')[:80]}")
print(f"  explanation 길이: {len(r.get('explanation') or '')}자")
print(f"  demo_code 있음: {len(r.get('demo_code') or '') > 50}")
print(f"  common_mistakes: {len(r.get('common_mistakes') or [])}")
print(f"  related_concepts: {r.get('related_concepts', [])}")

# TEST 2: concepts 목록
print("\n[TEST 2] /api/concepts 목록")
r2 = urllib.request.urlopen('http://localhost:8765/api/concepts', timeout=10)
data2 = json.loads(r2.read())
print(f"  총 {data2.get('total')}개 개념")
for c in data2.get('concepts', [])[:5]:
    print(f"  - {c['name']} ({c.get('name_ko','')})")

# TEST 3: 한국어 질문
print("\n[TEST 3] EigenmodeSource 질문")
r3 = post('/api/concept', {'query': 'EigenmodeSource how to use'})
print(f"  matched: {r3.get('matched_concept')}")
print(f"  confidence: {r3.get('confidence')}")
