# -*- coding: utf-8 -*-
import sys, urllib.request, json

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://localhost:8765"

def search(q, n=3):
    body = json.dumps({"query": q, "n": n}).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/api/search", data=body,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

queries_ko = [
    "모드 변환기",
    "역설계 최적화",
    "adjoint 오류",
    "베타 스케줄",
    "광자 결정 구조",
    "위상 최적화",
]

queries_en = [
    "mode converter",
    "adjoint optimization",
    "beta schedule",
]

print("=" * 60)
print("meep-kb 한국어 검색 테스트")
print("=" * 60)

for q in queries_ko + queries_en:
    lang = "KO" if any(ord(c) > 127 for c in q) else "EN"
    try:
        r = search(q)
        intent = r.get("intent", {})
        results = r.get("results", [])
        mode = r.get("mode", "?")
        elapsed = r.get("elapsed_ms", "?")
        detected_lang = intent.get("lang", "?")
        intent_type = intent.get("type", "?")
        print(f"\n[{lang}] \"{q}\"")
        print(f"  mode={mode} | detected_lang={detected_lang} | intent={intent_type} | {elapsed}ms")
        for i, res in enumerate(results[:3], 1):
            score = res.get("score", 0)
            title = res.get("title", "?")[:55]
            src = res.get("source", "?")
            rtype = res.get("type", "?")
            print(f"  {i}. [{score:.0%}][{rtype}/{src}] {title}")
    except Exception as e:
        print(f"\n[{lang}] \"{q}\" -> ERROR: {e}")

print("\n" + "=" * 60)
print("완료")
