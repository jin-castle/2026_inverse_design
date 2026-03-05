#!/usr/bin/env python3
"""
Coverage Checker — 항상 LLM 생성 사용 (Grounded RAG 방식)

DB 결과가 있으면 DB에만 기반해서 한국어로 정리,
DB 결과가 없으면 "관련 정보 없음" 명시.
"""


def check_coverage(intent: dict, results: list) -> dict:
    """
    항상 LLM 생성을 사용합니다.
    단, DB 결과가 있을 때는 DB 내용만으로 grounded generation.
    """
    if not results:
        return {
            "sufficient": False,
            "reason": "DB에서 관련 자료를 찾지 못했습니다",
            "use_generation": True
        }

    top_score = results[0]["score"]
    return {
        "sufficient": True,
        "reason": f"DB 결과 {len(results)}건 (최상위 유사도 {top_score:.2f}) → LLM으로 한국어 정리",
        "use_generation": True   # 항상 LLM 사용 (Grounded generation)
    }
