#!/usr/bin/env python3
"""
Intent Analyzer — 사용자 쿼리의 의도를 LLM으로 파악
ANTHROPIC_API_KEY 없으면 heuristic fallback 자동 사용
"""

import os, re, json

ANTHROPIC_API_KEY = os.environ.get(
    "ANTHROPIC_API_KEY",
    "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"
)

# ── 의도 유형 정의 ───────────────────────────────────────────────────────────
INTENT_TYPES = {
    "error_debug":   "에러/오류/크래시 해결 방법 탐색",
    "code_example":  "코드 예제/사용법 탐색",
    "concept_map":   "개념/API 관계 탐색 (뭐야, 어떻게 연결, 전체 파악)",
    "doc_lookup":    "공식 문서/설명 검색",
    "unknown":       "의도 불명확 — 전방위 검색 필요",
}

# ── 한국어 감지 패턴 ─────────────────────────────────────────────────────────
KO_PATTERN = re.compile(r'[\uAC00-\uD7A3]')

# ── 휴리스틱 키워드 ──────────────────────────────────────────────────────────
HEURISTICS = {
    "error_debug": [
        "오류", "에러", "error", "crash", "죽", "안 돼", "안돼", "실패",
        "NaN", "Inf", "발산", "문제", "이상", "exception", "traceback",
        "abort", "killed", "segfault", "RuntimeError", "failed", "bug",
        "왜", "안 됨", "작동 안", "뭔가 이상",
        "blows up", "blow up", "diverge", "unstable", "explode",
        "wrong", "incorrect", "doesn't work", "not working",
    ],
    "code_example": [
        "예제", "코드", "example", "how to", "어떻게", "사용법", "구현",
        "implement", "write", "sample", "template", "보여줘", "만들어",
        "설정", "쓰는 법", "쓰려면", "사용하려면", "코드 좀", "작성"
    ],
    "concept_map": [
        "뭐야", "뭔가요", "what is", "what are", "설명", "개념",
        "관계", "연결", "탐색", "전체", "구조", "어떤 것들", "종류",
        "explain", "relationship", "overview", "list all", "show all",
        "adjoint랑", "랑 뭐", "이랑", "와 뭐"
    ],
    "doc_lookup": [
        "문서", "documentation", "레퍼런스", "reference", "API",
        "파라미터", "parameter", "인수", "argument", "옵션", "option",
        "공식", "official", "매뉴얼", "manual", "가이드", "guide"
    ],
}


def detect_language(text: str) -> str:
    ko_chars = len(KO_PATTERN.findall(text))
    total    = len(text.replace(" ", ""))
    if total == 0:
        return "en"
    ratio = ko_chars / total
    if ratio > 0.3:
        return "ko"
    elif ratio > 0.05:
        return "mixed"
    return "en"


def heuristic_intent(query: str) -> dict:
    """LLM 없이 키워드 기반 의도 분류"""
    q_lower = query.lower()
    scores  = {intent: 0 for intent in HEURISTICS}

    for intent, keywords in HEURISTICS.items():
        for kw in keywords:
            if kw.lower() in q_lower:
                scores[intent] += 1

    best_intent = max(scores, key=scores.get)
    best_score  = scores[best_intent]

    # 점수 없으면 unknown
    if best_score == 0:
        best_intent = "unknown"

    confidence = min(0.5 + best_score * 0.15, 0.85)
    if best_intent == "unknown":
        confidence = 0.3

    # 핵심 키워드 추출 (영어 단어 + MEEP API명)
    words = re.findall(r'[A-Za-z][A-Za-z0-9_]{2,}', query)
    meep_terms = [w for w in words if w[0].isupper() or w.lower() in
                  ["adjoint", "mpi", "pml", "dft", "mpb", "nan", "inf"]]
    keywords = list(dict.fromkeys(meep_terms + words))[:4]

    return {
        "intent":     best_intent,
        "lang":       detect_language(query),
        "keywords":   keywords,
        "confidence": round(confidence, 2),
        "reason":     f"휴리스틱: '{best_intent}' 키워드 {best_score}개 매칭",
        "method":     "heuristic"
    }


def llm_intent(query: str) -> dict:
    """Claude API로 의도 분석"""
    try:
        import anthropic
        client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt  = f"""사용자가 MEEP(MIT 전자기 시뮬레이터) 지식베이스에 다음 질문을 했습니다.

질문: "{query}"

아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "intent": "error_debug|code_example|concept_map|doc_lookup|unknown",
  "lang": "ko|en|mixed",
  "keywords": ["영어 핵심 키워드 최대 3개"],
  "confidence": 0.0~1.0,
  "reason": "판단 이유 한 줄"
}}

의도 정의:
- error_debug: 에러/오류/크래시 해결 (예: "발산해", "crash", "이상함", "안 돼")
- code_example: 코드 예제/사용법 (예: "어떻게 써", "예제 보여줘", "how to")
- concept_map: 개념/API 관계 탐색 (예: "뭐야", "관계가", "전체 구조")
- doc_lookup: 문서/레퍼런스 (예: "파라미터", "API 문서", "옵션")
- unknown: 위 어디에도 해당 없음"""

        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}]
        )
        raw  = msg.content[0].text.strip()
        # 마크다운 코드블록 제거 (```json ... ``` 또는 ``` ... ```)
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw.strip())
        # JSON 파싱
        data = json.loads(raw.strip())
        data["method"] = "llm"
        return data
    except Exception as e:
        return None


def analyze(query: str, use_llm: bool = True, verbose: bool = False) -> dict:
    """
    의도 분석 메인 함수.
    LLM 실패 시 heuristic으로 자동 fallback.
    """
    result = None

    if use_llm and ANTHROPIC_API_KEY:
        result = llm_intent(query)

    if result is None:
        result = heuristic_intent(query)

    if verbose:
        method = "🤖 LLM" if result.get("method") == "llm" else "📏 Heuristic"
        print(f"\n{method} 의도 분석:")
        print(f"  의도:   {result['intent']} — {INTENT_TYPES.get(result['intent'], '')}")
        print(f"  언어:   {result['lang']}")
        print(f"  키워드: {result['keywords']}")
        print(f"  신뢰도: {result['confidence']:.0%}")
        print(f"  이유:   {result['reason']}")

    return result


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "adjoint 돌리다가 죽었어"
    result = analyze(q, verbose=True)
