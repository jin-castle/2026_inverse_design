"""
MEEP 개념 감지기 (Concept Detector)
쿼리에서 MEEP 개념 키워드를 감지하여 매칭되는 개념 이름을 반환.
"""

CONCEPT_KEYWORDS = {
    # ── 경계/소스 ──────────────────────────────────────────────────────────
    "PML": ["pml", "perfectly matched layer", "흡수 경계", "absorbing boundary", "반사 방지", "경계 조건", "pml이 뭐", "pml 뭐야"],
    "EigenmodeSource": ["eigenmodesource", "eigenmode source", "고유모드 소스", "도파관 모드 소스", "eigensource", "eigenmodecoeff"],
    "GaussianSource": ["gaussiansource", "gaussian source", "가우시안 소스", "fcen", "fwidth", "가우시안 펄스", "gaussian pulse", "broadband source"],
    "ContinuousSource": ["continuoussource", "continuous source", "연속파", "단색광", "cw source", "monochromatic"],
    "CustomSource": ["customsource", "custom source", "사용자 정의 소스", "arbitrary waveform"],
    "SourceVolume": ["sourcevolume", "source volume", "소스 볼륨", "line source", "plane source", "점 소스"],
    # ── 모니터 ──────────────────────────────────────────────────────────────
    "FluxRegion": ["fluxregion", "add_flux", "플럭스", "flux region", "투과율 측정", "반사율 측정", "transmission", "reflection monitor"],
    "DFT": ["add_dft_fields", "dft fields", "dft field", "주파수 도메인 필드", "frequency domain field", "near field dft"],
    "near2far": ["near2far", "near_to_far", "far field", "원거리 필드", "방사 패턴", "radiation pattern", "add_near2far"],
    "LDOS": ["ldos", "local density of states", "purcell", "purcell factor", "자발방출", "spontaneous emission", "국소 상태 밀도"],
    "add_energy": ["add_energy", "energy monitor", "에너지 모니터", "저장 에너지", "stored energy", "electromagnetic energy"],
    # ── 시뮬레이션 설정 ──────────────────────────────────────────────────────
    "Simulation": ["mp.simulation", "simulation 클래스", "시뮬레이션 객체", "simulation object", "sim = mp.simulation"],
    "resolution": ["resolution", "해상도", "격자 해상도", "pixels per micron", "spatial discretization", "격자 간격"],
    "cell_size": ["cell_size", "cell size", "계산 영역", "computational domain", "simulation box", "셀 크기"],
    "courant": ["courant", "쿠란트", "cfl", "쿠란트 수", "courant factor", "numerical stability", "수치 안정성"],
    "stop_when_fields_decayed": ["stop_when_fields_decayed", "stop_when", "수렴 종료", "convergence condition", "fields decayed", "run until"],
    "k_point": ["k_point", "k point", "블로흐", "bloch", "주기 경계", "periodic boundary", "wavevector"],
    "Symmetry": ["symmetry", "대칭", "mirror symmetry", "even_y", "odd_z", "대칭 조건", "symmetry reduction"],
    "at_every": ["at_every", "step function", "주기적 출력", "during simulation"],
    "mpi": ["mpi", "mpirun", "병렬 시뮬레이션", "parallel meep", "am_master", "병렬 처리"],
    # ── 기하/재료 ────────────────────────────────────────────────────────────
    "Block": ["mp.block", "block 구조", "직육면체", "rectangular", "도파관 블록"],
    "Cylinder": ["mp.cylinder", "cylinder", "원통", "원기둥", "circular rod"],
    "Sphere": ["mp.sphere", "sphere", "구형", "microsphere", "mie scattering", "mie 산란"],
    "Prism": ["mp.prism", "prism", "다각형 단면", "taper 프리즘", "arbitrary cross"],
    "Medium": ["mp.medium", "medium", "유전율", "epsilon", "굴절률", "refractive index", "dielectric medium", "n=3.48"],
    "LorentzianSusceptibility": ["lorentzian", "로렌츠", "dispersive", "frequency dependent", "분산 매질"],
    "DrudeSusceptibility": ["drude", "드루드", "metal", "plasmonic", "free electron", "금속 모델"],
    # ── 분석 ────────────────────────────────────────────────────────────────
    "Harminv": ["harminv", "공진 모드", "q factor", "quality factor", "resonance frequency", "공진 주파수", "q값"],
    "MPB": ["mpb", "밴드 구조", "band structure", "photonic crystal band", "dispersion relation", "밴드갭", "band gap"],
    "get_array": ["get_array", "필드 배열", "field array", "numpy array 추출", "sim.get_array"],
    "get_eigenmode_coefficients": ["get_eigenmode_coefficients", "모드 계수", "mode coefficients", "modal power", "mode decomposition"],
    "epsilon_r": ["get_epsilon", "유전율 분포", "dielectric profile", "epsilon map", "굴절률 분포"],
    "phase_velocity": ["phase velocity", "위상 속도", "group velocity", "군속도", "effective index", "유효 굴절률"],
    # ── 최적화 ──────────────────────────────────────────────────────────────
    "adjoint": ["adjoint", "역설계", "어드조인트", "adjoint method", "inverse design", "gradient-based"],
    "MaterialGrid": ["materialgrid", "material grid", "design variable", "topology optimization", "역설계 격자", "토폴로지 최적화"],
    "OptimizationProblem": ["optimizationproblem", "optimization problem", "mpa.optimization", "최적화 문제"],
    "design_region": ["design_region", "designregion", "역설계 영역", "design region"],
    "filter_and_project": ["filter and project", "conic filter", "gaussian filter", "threshold projection", "필터링 투영"],
    "beta_projection": ["beta", "beta projection", "이진화", "binarization", "heaviside", "projection parameter"],
    "nlopt": ["nlopt", "l-bfgs", "mma", "gradient optimizer", "scipy minimize", "최적화 알고리즘"],
    "FOM": ["fom", "figure of merit", "목적 함수", "objective function", "merit function"],
    # ── 포토닉 소자 ─────────────────────────────────────────────────────────
    "waveguide": ["waveguide", "도파관", "strip waveguide", "channel waveguide", "rib waveguide", "실리콘 도파관"],
    "ring_resonator": ["ring resonator", "링 공진기", "microring", "wgm", "add-drop"],
    "photonic_crystal": ["photonic crystal", "포토닉 결정", "phc", "photonic bandgap", "포토닉 밴드갭"],
    "grating_coupler": ["grating coupler", "격자 결합기", "gc", "diffraction grating", "파이버 결합"],
    "mmi_splitter": ["mmi", "multimode interference", "광분배기", "1x2 splitter", "3db coupler"],
    "bend": ["waveguide bend", "도파관 굴곡", "90 degree bend", "s-bend", "bend loss", "굽힘 손실"],
    "taper": ["taper", "테이퍼", "adiabatic taper", "mode converter", "width taper", "폭 변환"],
    "directional_coupler": ["directional coupler", "방향성 결합기", "evanescent coupling", "결합 길이"],
    # ── 기타 ─────────────────────────────────────────────────────────────────
    "eig_band": ["eig_band", "eig band", "te0 모드", "te1 모드", "mode number", "모드 번호"],
    "eig_parity": ["eig_parity", "odd_z", "even_z", "odd_y", "te 편광", "tm 편광", "parity"],
    "plot2D": ["plot2d", "sim.plot2d", "시각화", "visualization", "geometry plot", "field plot"],
    "output_efield": ["output_efield", "output_efield_z", "hdf5", "h5 output", "필드 출력"],
    "chunk": ["chunk", "도메인 분할", "domain decomposition", "mpi chunk", "load balancing"],
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
