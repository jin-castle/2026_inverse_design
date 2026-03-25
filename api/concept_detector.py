"""
MEEP 개념 감지기 (Concept Detector)
쿼리에서 MEEP 개념 키워드를 감지하여 매칭되는 개념 이름을 반환.
"""

CONCEPT_KEYWORDS = {
    "PML": ["pml", "perfectly matched layer", "흡수 경계", "absorbing boundary", "반사 방지", "경계 조건"],
    "EigenmodeSource": ["eigenmodesource", "eigenmode source", "고유모드 소스", "eig_band", "도파관 모드", "eigensource"],
    "FluxRegion": ["flux", "투과율", "반사율", "transmission", "reflection", "fluxregion", "add_flux", "플럭스"],
    "resolution": ["resolution", "해상도", "격자", "pixels per", "spatial discretization", "discretization"],
    "GaussianSource": ["gaussiansource", "gaussian", "가우시안", "fcen", "fwidth", "펄스", "gaussian pulse", "broadband"],
    "Harminv": ["harminv", "공진", "q factor", "quality factor", "resonance", "공진 주파수", "q값"],
    "Symmetry": ["symmetry", "대칭", "mirror", "even_y", "odd_z", "대칭 조건", "symmetry reduction"],
    "adjoint": ["adjoint", "역설계", "gradient", "최적화", "inverse design", "adjoint method", "어드조인트", "adjoint solver"],
    "MaterialGrid": ["materialgrid", "material_grid", "design variable", "topology", "재료 격자", "역설계 격자"],
    "DFT": ["add_dft_fields", "dft fields", "주파수 도메인", "frequency domain", "near field dft", "dft monitor"],
    "courant": ["courant", "쿠란트", "cfl", "timestep", "dt", "수치 안정", "numerical stability", "time step"],
    "stop_when_fields_decayed": ["stop_when_fields_decayed", "stop_when", "수렴 조건", "convergence", "run until", "fields decayed"],
    "MPB": ["mpb", "밴드 구조", "band structure", "photonic crystal", "dispersion", "밴드갭", "band gap"],
    "near2far": ["near2far", "near_to_far", "far field", "원거리 필드", "방사 패턴", "radiation pattern", "add_near2far"],
    "eig_band": ["eig_band", "te0", "te1", "tm0", "tm1", "mode number", "모드 번호", "mode order"],
}

# 개념 질문 패턴 (에러가 아닌 개념 질문임을 확인)
CONCEPT_QUESTION_PATTERNS = [
    "뭐야", "뭔가요", "뭐죠", "뭐예요",
    "설명", "explain", "what is",
    "어떻게", "how to", "how do",
    "왜", "why",
    "개념", "concept", "정의", "define",
    "사용법", "usage", "사용하는", "사용해",
    "란", "이란", "이란?",
    "알려줘", "알려주세요",
    "이해", "understand",
]

ERROR_PATTERNS = [
    "에러", "오류", "error", "traceback", "exception",
    "fix", "해결", "수정", "왜 안되", "왜 실패",
    "attributeerror", "typeerror", "valueerror", "importerror",
    "failed", "crash", "crash", "segfault",
]


def detect_concept(query: str) -> str | None:
    """
    쿼리에서 MEEP 개념 감지.
    매칭되면 concept name 반환, 없으면 None.
    우선순위: 긴 키워드 먼저 매칭 (substring 오탐 방지).
    """
    q = query.lower()

    # 각 개념에 대해 키워드 체크
    for concept, keywords in CONCEPT_KEYWORDS.items():
        # 긴 키워드 먼저 정렬하여 정확도 향상
        sorted_kws = sorted(keywords, key=len, reverse=True)
        for kw in sorted_kws:
            if kw in q:
                return concept

    return None


def is_concept_question(query: str) -> bool:
    """
    개념 질문인지 에러 질문인지 판단.
    개념 키워드가 있고, 개념 질문 패턴이 있으며, 에러 패턴이 없어야 함.
    """
    has_error = any(p in query.lower() for p in ERROR_PATTERNS)
    has_concept_q = any(p in query.lower() for p in CONCEPT_QUESTION_PATTERNS)
    has_concept_kw = detect_concept(query) is not None

    return has_concept_kw and has_concept_q and not has_error


def detect_all_concepts(query: str) -> list[str]:
    """쿼리에서 언급된 모든 MEEP 개념 감지 (여러 개 가능)"""
    q = query.lower()
    found = []
    for concept, keywords in CONCEPT_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            found.append(concept)
    return found


def get_concept_confidence(query: str, concept_name: str) -> float:
    """특정 개념과 쿼리의 매칭 신뢰도 계산 (0.0 ~ 1.0)"""
    if concept_name not in CONCEPT_KEYWORDS:
        return 0.0

    q = query.lower()
    keywords = CONCEPT_KEYWORDS[concept_name]

    # 매칭된 키워드 수 기반 신뢰도
    matched = sum(1 for kw in keywords if kw in q)
    if matched == 0:
        return 0.0

    # 이름 직접 매칭 시 높은 신뢰도
    if concept_name.lower() in q:
        return 0.98

    # 키워드 매칭 비율 기반
    confidence = min(0.95, 0.60 + (matched / len(keywords)) * 0.35)
    return round(confidence, 2)
