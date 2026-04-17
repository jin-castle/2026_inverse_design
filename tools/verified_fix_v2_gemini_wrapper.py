# -*- coding: utf-8 -*-
"""
verified_fix_v2_gemini_wrapper.py
Gemini API를 사용하여 verified_fix_v2.py를 실행하는 래퍼.
ANTHROPIC_API_KEY 대신 GEMINI_API_KEY를 사용.
"""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "tools"))
sys.path.insert(0, str(BASE / "api"))

# .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(str(BASE / ".env"))
except ImportError:
    pass


def call_llm_gemini(prompt: str, api_key: str) -> str:
    """Gemini 2.5 Pro API 호출 (v1beta, 16384 출력 토큰)"""
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
            raise ValueError(f"No candidates in response: {json.dumps(data)[:200]}")
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            finish_reason = candidates[0].get("finishReason", "unknown")
            raise ValueError(f"No parts in response. finishReason={finish_reason}")
        return parts[0].get("text", "")


def patch_and_run(record_id: int):
    """verified_fix_v2 모듈을 Gemini로 패치하여 실행"""
    import verified_fix_v2 as vfv2

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        print("❌ GEMINI_API_KEY 없음")
        sys.exit(1)

    # call_llm 함수를 Gemini 버전으로 교체
    def patched_call_llm(prompt: str, api_key: str) -> str:
        return call_llm_gemini(prompt, gemini_key)

    vfv2.call_llm = patched_call_llm

    # 더미 API key (run_pipeline에서 None 체크만 하므로)
    os.environ["ANTHROPIC_API_KEY"] = "gemini_patched"

    vfv2.run_pipeline(limit=1, dry_run=False, record_id=record_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, required=True)
    args = parser.parse_args()
    patch_and_run(args.id)
