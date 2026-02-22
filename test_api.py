#!/usr/bin/env python3
"""API 통합 테스트"""
import json, urllib.request, urllib.error

BASE = "http://localhost:8765"

def post(path, data):
    body = json.dumps(data).encode()
    req  = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read())

def sep(title=""):
    print("\n" + "="*60)
    if title:
        print(f"  {title}")
        print("="*60)

# 1. DB 상태
sep("TEST 1: /api/status")
s = get("/api/status")
print(f"  errors:   {s['db_errors']}")
print(f"  examples: {s['db_examples']}")
print(f"  docs:     {s['db_docs']}")
print(f"  nodes:    {s['graph_nodes']}")
print(f"  edges:    {s['graph_edges']}")
print(f"  ready:    {s['server_ready']}")

# 2. DB 직출력 테스트
sep("TEST 2: DB 직출력 모드 — adjoint 에러")
r = post("/api/search", {"query": "adjoint 돌리다가 죽었어", "n": 3})
print(f"  mode:                {r['mode']}")
print(f"  intent:              {r['intent']['type']}  {r['intent']['confidence']:.0%}")
print(f"  methods:             {r['methods_used']}")
print(f"  results:             {len(r['results'])}건")
print(f"  hallucination_warn:  {r['hallucination_warning']}")
print(f"  coverage:            {r['coverage']['reason']}")
if r.get("answer"):
    print(f"  answer snippet:      {r['answer'][:80]}...")
for i, res in enumerate(r["results"], 1):
    print(f"    [{i}] {res['type']} {res['score']:.2f}  {res['title'][:55]}")

# 3. Generation 모드 테스트
sep("TEST 3: LLM Generation 모드 — adjoint 개념")
r2 = post("/api/search", {"query": "adjoint가 뭐야", "n": 3})
print(f"  mode:                {r2['mode']}")
print(f"  intent:              {r2['intent']['type']}  {r2['intent']['confidence']:.0%}")
print(f"  hallucination_warn:  {r2['hallucination_warning']}")
if r2.get("warning_message"):
    print(f"  warning_message:     {r2['warning_message'][:80]}...")
if r2.get("answer"):
    ans = r2["answer"]
    print(f"  answer (첫 200자):\n{ans[:200]}")
print(f"  sources_used (results): {len(r2.get('results', []))}건")

# 4. Chat API 테스트
sep("TEST 4: /api/chat — 히스토리 포함")
c = post("/api/chat", {
    "message": "simulation blows up after a few steps",
    "history": [],
    "n": 3
})
print(f"  mode:    {c['mode']}")
print(f"  intent:  {c['intent']['type']}")
print(f"  history: {len(c.get('history', []))}개 메시지")
print(f"  elapsed: {c['elapsed_ms']}ms")

sep("모든 테스트 완료")
