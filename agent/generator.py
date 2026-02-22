#!/usr/bin/env python3
"""
Generator — Claude API로 RAG 기반 답변 생성

DB 결과를 컨텍스트로 사용해 Claude가 최종 답변을 만들어냄.
Generation 모드에서는 항상 Hallucination 경고를 포함.
"""

import os

ANTHROPIC_API_KEY = os.environ.get(
    "ANTHROPIC_API_KEY",
    "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"
)

HALLUCINATION_WARNING = (
    "이 답변은 Claude AI가 생성한 것으로, DB에 없는 내용을 포함할 수 있습니다. "
    "중요한 내용은 공식 MEEP 문서나 GitHub Issues에서 직접 확인하세요."
)


def _build_context(db_results: list) -> str:
    """DB 결과를 LLM 컨텍스트 문자열로 변환"""
    if not db_results:
        return ""

    lines = ["=== MEEP DB 참고 자료 ===\n"]
    for i, r in enumerate(db_results[:5], 1):
        rtype = r.get("type", "?")
        title = r.get("title", "")
        score = r.get("score", 0)

        lines.append(f"[{i}] [{rtype}] {title} (유사도: {score:.2f})")

        if r.get("cause"):
            lines.append(f"    원인: {r['cause'][:300]}")
        if r.get("solution"):
            lines.append(f"    해결: {r['solution'][:300]}")
        if r.get("code"):
            snippet = r["code"][:300].strip()
            lines.append(f"    코드:\n```python\n{snippet}\n```")
        if r.get("url"):
            lines.append(f"    출처: {r['url']}")
        lines.append("")

    return "\n".join(lines)


def generate(query: str, intent: dict, db_results: list) -> dict:
    """
    Claude API로 답변 생성.

    반환:
    {
      "answer": str,              # 생성된 답변 (한국어, Hallucination 경고 포함)
      "sources_used": int,        # 참조한 DB 결과 수
      "is_db_grounded": bool,     # DB 기반 여부
      "hallucination_warning": bool,  # 항상 True (generation 모드)
      "warning_message": str      # 경고 메시지
    }
    """
    context = _build_context(db_results)
    is_db_grounded = bool(db_results)
    intent_type = intent.get("intent", "unknown")

    # ── 프롬프트 구성 ──────────────────────────────────────────────────────
    if is_db_grounded:
        prompt = f"""당신은 MEEP(MIT 전자기 시뮬레이터) 전문가입니다.

{context}

위의 MEEP DB 자료를 참고해서 다음 질문에 답하세요.
DB에 없는 내용은 일반 지식으로 답하되, 해당 부분에 '[DB 외 정보]' 태그를 붙이세요.

질문: {query}

답변 요구사항:
- 반드시 한국어로 답변하세요
- 코드 예제가 필요하면 Python 코드 블록으로 포함하세요
- DB 자료의 번호([1], [2] 등)를 인용할 때 명시하세요
- 구체적이고 실용적인 답변을 제공하세요
- 의도 유형({intent_type})에 맞게 답변 형식을 조정하세요

"""
    else:
        prompt = f"""당신은 MEEP(MIT 전자기 시뮬레이터) 전문가입니다.

MEEP KB에서 관련 자료를 찾지 못했습니다. 일반 MEEP 지식으로 답변합니다.

질문: {query}

답변 요구사항:
- 반드시 한국어로 답변하세요
- 코드 예제가 필요하면 Python 코드 블록으로 포함하세요
- DB 검색 결과가 없으므로 일반 지식 기반으로 답하되, 불확실한 내용에는 주의를 표시하세요
- 구체적이고 실용적인 답변을 제공하세요
- 의도 유형({intent_type})에 맞게 답변 형식을 조정하세요

"""

    # Hallucination 자기인식 지시 (항상 추가)
    prompt += """답변 마지막에 반드시 아래 문구를 추가하세요:

---
⚠️ **주의**: 이 답변은 AI가 생성한 것입니다. DB에 없는 내용은 부정확할 수 있으니 [공식 MEEP 문서](https://meep.readthedocs.io)에서 확인하세요.
"""

    # ── Claude API 호출 ────────────────────────────────────────────────────
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = msg.content[0].text.strip()

    except Exception as e:
        answer = (
            f"❌ LLM 생성 실패: {e}\n\n"
            f"DB 검색 결과 {len(db_results)}건을 직접 참고하세요.\n\n"
            "---\n"
            "⚠️ **주의**: 이 답변은 AI가 생성한 것입니다. "
            "공식 MEEP 문서에서 확인하세요."
        )

    return {
        "answer": answer,
        "sources_used": len(db_results),
        "is_db_grounded": is_db_grounded,
        "hallucination_warning": True,
        "warning_message": HALLUCINATION_WARNING,
    }


if __name__ == "__main__":
    # 간단 테스트
    test_results = [
        {
            "source": "vector", "type": "ERROR", "score": 0.72,
            "title": "adjoint simulation segfault",
            "cause": "MPI + adjoint 동시 사용 시 메모리 오류",
            "solution": "meep.Simulation 생성 전 mp.quiet(True) 호출",
            "url": "https://github.com/NanoComp/meep/issues/123",
            "code": ""
        }
    ]

    result = generate(
        query="adjoint 돌리다가 죽었어",
        intent={"intent": "error_debug", "lang": "ko"},
        db_results=test_results
    )

    print("=== 생성 결과 ===")
    print(f"is_db_grounded: {result['is_db_grounded']}")
    print(f"sources_used: {result['sources_used']}")
    print(f"hallucination_warning: {result['hallucination_warning']}")
    print(f"\n답변:\n{result['answer']}")
