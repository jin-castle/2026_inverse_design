#!/usr/bin/env python3
"""
Intent Analyzer - 사용자 쿼리의 의도를 LLM으로 파악
ANTHROPIC_API_KEY 없으면 heuristic fallback 자동 사용

v2: pipeline_category / pipeline_stage 감지 추가
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
    "unknown":       "의도 불명확 - 전방위 검색 필요",
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

# ── 파이프라인 카테고리 키워드 매핑 ──────────────────────────────────────────
# (category_id, stage_id, 키워드 목록)
# stage_id: 0 = 카테고리 수준, 1~5 = 역설계 루프 세부 단계
PIPELINE_KEYWORDS = [
    # Category 1: 시뮬레이션 환경 설정
    ("env_setup", 0, [
        "resolution", "cell_size", "pml", "dpml", "boundary", "환경 설정",
        "셀", "cell size", "해상도", "경계 조건", "시뮬레이션 환경",
        "mp.medium", "epsilon", "재료", "mp.Medium",
    ]),
    # Category 2: 지오메트리 구성
    ("geometry", 0, [
        "geometry", "block", "cylinder", "지오메트리", "레이아웃",
        "layout", "구조", "plot2d", "init_sim", "waveguide", "도파로",
        "구조체", "structure", "rod", "sphere", "cone",
    ]),
    # Category 3: 디자인 영역 설정
    ("design_region", 0, [
        "materialgrid", "designregion", "design region", "디자인 영역",
        "nx", "ny", "grid_type", "u_mean", "do_averaging",
        "design variable", "설계 변수", "design_variables",
    ]),
    # Category 4: 시뮬레이션 설정
    ("sim_setup", 0, [
        "eigenmodesource", "eigenmodecoefficient", "dftfields", "gaussiansource",
        "sources", "monitors", "모니터", "소스", "eig_band", "eig_parity",
        "source", "monitor", "add_dft_fields", "dft monitor",
    ]),
    # Category 5 / Stage 5-1: Forward Simulation
    ("inv_loop", 1, [
        "forward sim", "forward simulation", "forward run",
        "forward field", "포워드 시뮬레이션", "포워드 필드",
        "dft field", "dft 필드", "필드 플롯", "field plot",
        "opt([", "fom, grad",
    ]),
    # Category 5 / Stage 5-2: Adjoint Simulation
    # "adjoint"는 강한 신호 — 가중치 2배 적용을 위해 2번 등록
    ("inv_loop", 2, [
        "adjoint", "adjoint", "어드조인트", "어드조인트",
        "adjoint field", "adjoint simulation", "adjoint source",
        "어드조인트 필드", "adjoint field plot", "adjoint run",
        "역방향", "backward", "animate2d", "mp.animate2d",
    ]),
    # Category 5 / Stage 5-3: Gradient 계산
    ("inv_loop", 3, [
        "gradient", "그래디언트", "sensitivity", "민감도",
        "dj/de", "dj/deps", "grad map", "gradient map",
        "gradient visualization", "그래디언트 맵", "sensitivity map",
    ]),
    # Category 5 / Stage 5-4: Beta Scheduling
    ("inv_loop", 4, [
        "beta", "베타", "beta schedule", "projection", "프로젝션",
        "beta scheduling", "continuation", "tanh", "heaviside",
        "binarization", "이진화", "beta_max", "beta_start",
    ]),
    # Category 5 / Stage 5-5: Filter
    ("inv_loop", 5, [
        "filter", "필터", "conic filter", "gaussian filter",
        "conic_filter", "minimum length scale", "fabrication",
        "제조 제약", "length scale", "binary ratio",
    ]),
    # Category 6: 결과물 출력
    ("output", 0, [
        "convergence", "수렴", "history.json", "results", "결과물",
        "final structure", "최종 구조", "convergence plot",
        "save results", "output", "저장",
    ]),
]

# stage_id -> 이름 매핑
STAGE_NAMES = {
    0:  None,
    1:  "forward_sim",
    2:  "adjoint_sim",
    3:  "gradient",
    4:  "beta_scheduling",
    5:  "filter",
}

CATEGORY_DISPLAY = {
    "env_setup":     "Category 1 - 시뮬레이션 환경 설정",
    "geometry":      "Category 2 - 지오메트리 구성",
    "design_region": "Category 3 - 디자인 영역 설정",
    "sim_setup":     "Category 4 - 시뮬레이션 설정",
    "inv_loop":      "Category 5 - 역설계 루프",
    "output":        "Category 6 - 결과물 출력",
}

STAGE_DISPLAY = {
    1: "Stage 5-1 - Forward Simulation",
    2: "Stage 5-2 - Adjoint Simulation",
    3: "Stage 5-3 - Gradient 계산",
    4: "Stage 5-4 - Beta Scheduling",
    5: "Stage 5-5 - Filter / Binarization",
}


def detect_pipeline(query: str) -> dict:
    """
    쿼리에서 파이프라인 카테고리/단계 감지.
    반환: {
        "pipeline_category": str | None,
        "pipeline_stage":    str | None,   # stage 이름 (Stage 5만)
        "pipeline_stage_idx": int,          # 0=미감지, 1~5
        "pipeline_hit": bool,
    }
    """
    q_lower = query.lower()

    best_cat      = None
    best_stage    = 0
    best_score    = 0
    best_kw_len   = 0  # 동점 tiebreak: 가장 긴 키워드 매칭 길이

    for cat_id, stage_id, keywords in PIPELINE_KEYWORDS:
        matched = [kw for kw in keywords if kw.lower() in q_lower]
        score   = len(matched)
        max_kw_len = max((len(kw) for kw in matched), default=0)

        if score > best_score:
            best_score  = score
            best_cat    = cat_id
            best_stage  = stage_id
            best_kw_len = max_kw_len
        elif score == best_score and score > 0:
            # 동점 tiebreak 1: 더 긴 키워드가 매칭된 entry 우선 (더 구체적)
            # 동점 tiebreak 2: stage_id > 0 (더 세분화된 단계) 우선
            if max_kw_len > best_kw_len:
                best_cat    = cat_id
                best_stage  = stage_id
                best_kw_len = max_kw_len
            elif max_kw_len == best_kw_len and stage_id > 0 and best_stage == 0:
                best_cat   = cat_id
                best_stage = stage_id

    if best_score == 0:
        return {
            "pipeline_category":  None,
            "pipeline_stage":     None,
            "pipeline_stage_idx": 0,
            "pipeline_hit":       False,
        }

    return {
        "pipeline_category":  best_cat,
        "pipeline_stage":     STAGE_NAMES.get(best_stage),
        "pipeline_stage_idx": best_stage,
        "pipeline_hit":       True,
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

    if best_score == 0:
        best_intent = "unknown"

    confidence = min(0.5 + best_score * 0.15, 0.85)
    if best_intent == "unknown":
        confidence = 0.3

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
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt = f"""사용자가 MEEP(MIT 전자기 시뮬레이터) 지식베이스에 다음 질문을 했습니다.

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
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw.strip())
        data = json.loads(raw.strip())
        data["method"] = "llm"
        return data
    except Exception:
        return None


def analyze(query: str, use_llm: bool = True, verbose: bool = False) -> dict:
    """
    의도 분석 메인 함수.
    LLM 실패 시 heuristic으로 자동 fallback.
    pipeline_category / pipeline_stage 항상 추가.
    """
    # 기존 intent 분석
    result = None
    if use_llm and ANTHROPIC_API_KEY:
        result = llm_intent(query)
    if result is None:
        result = heuristic_intent(query)

    # 파이프라인 단계 감지 (항상 실행, heuristic)
    pipeline = detect_pipeline(query)
    result.update(pipeline)

    if verbose:
        method = "LLM" if result.get("method") == "llm" else "Heuristic"
        print(f"\n[{method}] 의도 분석:")
        print(f"  의도:      {result['intent']} - {INTENT_TYPES.get(result['intent'], '')}")
        print(f"  언어:      {result['lang']}")
        print(f"  키워드:    {result['keywords']}")
        print(f"  신뢰도:    {result['confidence']:.0%}")
        print(f"  이유:      {result['reason']}")
        if pipeline["pipeline_hit"]:
            cat  = pipeline["pipeline_category"]
            sidx = pipeline["pipeline_stage_idx"]
            print(f"  파이프라인: {CATEGORY_DISPLAY.get(cat, cat)}", end="")
            if sidx > 0:
                print(f" > {STAGE_DISPLAY.get(sidx, '')}", end="")
            print()
        else:
            print(f"  파이프라인: (미감지)")

    return result


if __name__ == "__main__":
    import sys
    queries = sys.argv[1:] or [
        "adjoint 돌리다가 죽었어",
        "어드조인트 필드 플롯하는 법",
        "MaterialGrid 어떻게 설정해",
        "gradient 맵 시각화",
        "beta 스케줄링 언제 올려야 해",
        "EigenModeSource eig_band 설정",
        "conic filter minimum length scale",
        "resolution PML 설정",
        "convergence plot 저장",
    ]
    for q in queries:
        print(f"\n{'='*50}")
        print(f"Query: {q}")
        analyze(q, verbose=True)
