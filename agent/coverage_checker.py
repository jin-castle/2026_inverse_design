#!/usr/bin/env python3
"""
Coverage Checker — DB 검색 결과가 충분한지 판단

DB 결과가 충분하면 직출력, 부족하면 LLM 생성으로 전환.
"""


def check_coverage(intent: dict, results: list) -> dict:
    """
    DB 검색 결과의 충분성을 판단합니다.

    반환:
    {
      "sufficient": bool,    # DB 결과 충분하면 True
      "reason": str,         # 판단 이유
      "use_generation": bool # LLM 생성 필요하면 True
    }
    """
    intent_type = intent.get("intent", "unknown")

    # 개념 탐색은 항상 LLM 생성 (LLM이 더 잘함)
    if intent_type == "concept_map":
        return {
            "sufficient": False,
            "reason": "개념 설명(concept_map)은 LLM 생성이 더 정확합니다",
            "use_generation": True
        }

    # 결과가 없으면 LLM 생성
    if len(results) == 0:
        return {
            "sufficient": False,
            "reason": "DB에서 관련 자료를 찾지 못했습니다",
            "use_generation": True
        }

    top_score = results[0]["score"]

    # 최상위 결과 유사도가 너무 낮으면 LLM 생성
    if top_score < 0.50:
        return {
            "sufficient": False,
            "reason": f"최상위 결과 유사도가 낮습니다 ({top_score:.2f} < 0.50)",
            "use_generation": True
        }

    # 에러 디버깅: 결과 2개 이상 + 유사도 0.65 이상이어야 충분
    if intent_type == "error_debug":
        if len(results) >= 2 and top_score >= 0.65:
            return {
                "sufficient": True,
                "reason": f"에러 디버깅: {len(results)}건 결과, 최상위 유사도 {top_score:.2f}",
                "use_generation": False
            }
        else:
            reason_parts = []
            if len(results) < 2:
                reason_parts.append(f"결과 {len(results)}건 (2건 미만)")
            if top_score < 0.65:
                reason_parts.append(f"유사도 {top_score:.2f} (0.65 미만)")
            return {
                "sufficient": False,
                "reason": "에러 디버깅 기준 미달: " + ", ".join(reason_parts),
                "use_generation": True
            }

    # 나머지 경우: DB 결과 충분
    return {
        "sufficient": True,
        "reason": f"DB 결과 {len(results)}건, 최상위 유사도 {top_score:.2f}",
        "use_generation": False
    }


if __name__ == "__main__":
    # 간단 테스트
    test_cases = [
        ({"intent": "error_debug"}, [{"score": 0.80}, {"score": 0.70}]),
        ({"intent": "error_debug"}, [{"score": 0.60}]),
        ({"intent": "concept_map"}, [{"score": 0.90}]),
        ({"intent": "doc_lookup"},  []),
        ({"intent": "doc_lookup"},  [{"score": 0.45}]),
        ({"intent": "doc_lookup"},  [{"score": 0.75}, {"score": 0.60}]),
    ]

    for intent, results in test_cases:
        result = check_coverage(intent, results)
        print(f"intent={intent['intent']}, results={len(results)} → "
              f"use_generation={result['use_generation']} ({result['reason']})")
