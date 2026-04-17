# -*- coding: utf-8 -*-
"""
run_batch_fix.py - 7건 일괄 처리
"""
import os, sys, json, time, urllib.request
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "tools"))
sys.path.insert(0, str(BASE / "api"))

try:
    from dotenv import load_dotenv
    load_dotenv(str(BASE / ".env"))
except ImportError:
    pass

IDS = [4, 11, 38, 43, 52, 58, 65]


def call_llm_gemini(prompt: str, api_key: str) -> str:
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 16384}
    }).encode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}"
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read())
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError(f"No candidates: {json.dumps(data)[:200]}")
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            fr = candidates[0].get("finishReason", "unknown")
            raise ValueError(f"No parts. finishReason={fr}")
        return parts[0].get("text", "")


import verified_fix_v2 as vfv2

gemini_key = os.environ.get("GEMINI_API_KEY")
if not gemini_key:
    print("❌ GEMINI_API_KEY 없음")
    sys.exit(1)

def patched_call_llm(prompt, api_key):
    return call_llm_gemini(prompt, gemini_key)

vfv2.call_llm = patched_call_llm
os.environ["ANTHROPIC_API_KEY"] = "gemini_patched"

results = {}
for id_ in IDS:
    print(f"\n{'='*60}")
    print(f"🚀 ID={id_} 처리 시작")
    try:
        rs = vfv2.run_pipeline(limit=1, dry_run=False, record_id=id_)
        r = rs[0] if rs else {"id": id_, "status": "no_result", "message": "no result returned"}
        results[id_] = r
        print(f"✅ ID={id_} 완료: status={r.get('status')}")
    except Exception as e:
        results[id_] = {"id": id_, "status": "exception", "message": str(e)}
        print(f"❌ ID={id_} 예외: {e}")
    time.sleep(2)

print(f"\n{'='*60}")
print("📊 최종 결과:")
success = sum(1 for r in results.values() if r.get("status") == "fixed")
failed = sum(1 for r in results.values() if r.get("status") not in ("fixed", "skip", "not_reproducible", "dry_run"))
skipped = sum(1 for r in results.values() if r.get("status") in ("skip", "not_reproducible"))
print(f"  성공: {success}건")
print(f"  실패: {failed}건")
print(f"  스킵: {skipped}건")
for id_, r in results.items():
    print(f"  ID={id_}: {r.get('status')} | {r.get('message','')[:60]}")
