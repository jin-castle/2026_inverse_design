#!/usr/bin/env python3
"""
Coverage Checker — DB 커버리지 기반 LLM 생성 여부 결정

조건:
  - top_score >= 0.82 AND results >= 3  → db_only  (LLM 생략, 고신뢰도)
  - doc_lookup이고 top_score >= 0.70 AND results >= 2 → db_only
  - results == 0                        → use_generation (DB 없음, LLM 폴백)
  - 그 외                               → use_generation (Grounded generation)
"""

# LLM 생략 기준
_SCORE_HIGH     = 0.82   # 고신뢰도 임계값
_SCORE_DOC      = 0.70   # doc_lookup 전용 완화 임계값
_MIN_RESULTS    = 3      # 고신뢰도 최소 결과 수
_MIN_RESULTS_DOC = 2     # doc_lookup 최소 결과 수


def check_coverage(intent: dict, results: list) -> dict:
    """
    DB 결과의 신뢰도를 평가해 LLM 호출 여부를 결정합니다.

    Returns:
        dict with keys:
          sufficient       (bool) — DB 결과가 충분한지
          reason           (str)  — 판단 이유
          use_generation   (bool) — LLM 생성 호출 여부
    """
    # ── 결과 없음: LLM 폴백 ──────────────────────────────────────────────────
    if not results:
        return {
            "sufficient":      False,
            "reason":          "DB에서 관련 자료를 찾지 못했습니다 → LLM 폴백",
            "use_generation":  True,
        }

    top_score   = float(results[0].get("score", 0))
    n_results   = len(results)
    intent_type = intent.get("intent", "unknown")

    # ── 고신뢰도: LLM 생략 ──────────────────────────────────────────────────
    if top_score >= _SCORE_HIGH and n_results >= _MIN_RESULTS:
        return {
            "sufficient":      True,
            "reason":          (
                f"고신뢰도 DB 결과 {n_results}건 "
                f"(top_score={top_score:.2f} ≥ {_SCORE_HIGH}) → db_only"
            ),
            "use_generation":  False,
        }

    # ── doc_lookup 완화 기준 ─────────────────────────────────────────────────
    if intent_type == "doc_lookup" and top_score >= _SCORE_DOC and n_results >= _MIN_RESULTS_DOC:
        return {
            "sufficient":      True,
            "reason":          (
                f"[doc_lookup] DB 결과 {n_results}건 "
                f"(top_score={top_score:.2f} ≥ {_SCORE_DOC}) → db_only"
            ),
            "use_generation":  False,
        }

    # ── 그 외: Grounded generation ───────────────────────────────────────────
    return {
        "sufficient":      top_score >= 0.5,
        "reason":          (
            f"DB 결과 {n_results}건 (top_score={top_score:.2f}) "
            f"→ LLM Grounded generation"
        ),
        "use_generation":  True,
    }
