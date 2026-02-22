#!/usr/bin/env python3
"""
Search Router — intent + lang → 검색 방식 결정
"""

from typing import NamedTuple

class SearchPlan(NamedTuple):
    methods:   list   # ["keyword", "vector", "graph"]
    db_types:  list   # ["errors", "examples", "docs", "all"]
    graph_mode: str   # "neighbor" | "traverse"
    graph_depth: int
    n_results:  int
    rationale:  str


def route(intent: dict, n: int = 5) -> SearchPlan:
    """
    의도(intent dict) → SearchPlan 반환

    라우팅 규칙:
    - error_debug   → 키워드 + 벡터 (errors), 그래프 보완
    - code_example  → 키워드 + 벡터 (examples)
    - concept_map   → 그래프 트래버설 우선
    - doc_lookup    → 벡터 (docs) + 키워드
    - unknown       → 3가지 전부 (confidence 낮으면 더 넓게)
    - KO/mixed      → 그래프 alias 먼저 추가
    - confidence < 0.5 → 전방위 실행
    """
    i         = intent.get("intent", "unknown")
    lang      = intent.get("lang", "en")
    conf      = intent.get("confidence", 0.5)
    is_ko     = lang in ("ko", "mixed")
    low_conf  = conf < 0.5

    # ── 기본 플랜 ────────────────────────────────────────────────────────────
    if i == "error_debug":
        methods    = ["keyword", "vector"]
        db_types   = ["errors"]
        graph_mode = "neighbor"
        depth      = 1
        rationale  = "에러 해결: 키워드(정확매칭) + 벡터(의미검색) 병렬"
        if is_ko:
            methods = ["graph", "keyword", "vector"]
            rationale += " + 그래프(한국어alias)"

    elif i == "code_example":
        methods    = ["keyword", "vector"]
        db_types   = ["examples"]
        graph_mode = "neighbor"
        depth      = 1
        rationale  = "코드예제: 키워드 + 벡터(examples)"
        if is_ko:
            methods = ["graph", "keyword", "vector"]
            rationale += " + 그래프(한국어alias→API노드)"

    elif i == "concept_map":
        methods    = ["graph", "vector"]
        db_types   = ["all"]
        graph_mode = "traverse"
        depth      = 2
        rationale  = "개념탐색: 그래프 트래버설(depth=2) + 벡터 보완"

    elif i == "doc_lookup":
        methods    = ["vector", "keyword"]
        db_types   = ["docs", "errors"]
        graph_mode = "neighbor"
        depth      = 1
        rationale  = "문서검색: 벡터(docs) + 키워드"
        if is_ko:
            methods = ["graph", "vector", "keyword"]
            rationale += " + 그래프(한국어alias)"

    else:  # unknown
        methods    = ["graph", "vector", "keyword"]
        db_types   = ["all"]
        graph_mode = "traverse"
        depth      = 1
        rationale  = "의도불명: 전방위 검색(그래프+벡터+키워드)"

    # ── 신뢰도 낮으면 전방위로 확장 ─────────────────────────────────────────
    if low_conf and "keyword" not in methods:
        methods.append("keyword")
        rationale += " [저신뢰도→키워드추가]"
    if low_conf and "graph" not in methods:
        methods.insert(0, "graph")
        rationale += " [저신뢰도→그래프추가]"

    return SearchPlan(
        methods=methods,
        db_types=db_types,
        graph_mode=graph_mode,
        graph_depth=depth,
        n_results=n,
        rationale=rationale
    )
