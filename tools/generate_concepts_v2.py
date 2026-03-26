#!/usr/bin/env python3
"""
MEEP 추가 개념 40개를 LLM으로 생성하여 concepts 테이블에 저장.
기존 15개(PML, EigenmodeSource, FluxRegion, resolution, GaussianSource,
Harminv, Symmetry, DFT, MaterialGrid, adjoint, eig_band,
stop_when_fields_decayed, MPB, near2far, courant)에 추가.

Usage: python -X utf8 tools/generate_concepts_v2.py [--concept Block] [--all]
"""
import os, sys, json, re, sqlite3, time, argparse
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

DB_PATH = Path(__file__).parent.parent / "db" / "knowledge.db"

CONCEPTS = [
    # ──────── 소스(Source) ────────
    {
        "name": "ContinuousSource",
        "name_ko": "연속파 소스",
        "aliases": ["continuous wave", "CW source", "monochromatic source"],
        "category": "source",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#continuoussource",
        "demo_hint": "단일 주파수 1550nm ContinuousSource로 직선 도파관 전파. 정상 상태 Ez 필드 시각화",
    },
    {
        "name": "CustomSource",
        "name_ko": "사용자 정의 소스",
        "aliases": ["custom source", "arbitrary waveform", "custom pulse"],
        "category": "source",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#customsource",
        "demo_hint": "sin^2 형태 펄스를 CustomSource로 정의. 임의 파형 시간 프로파일 시각화",
    },
    {
        "name": "SourceVolume",
        "name_ko": "소스 볼륨 (면/선/점 소스)",
        "aliases": ["source volume", "line source", "plane source", "point source"],
        "category": "source",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#source",
        "demo_hint": "점 소스 vs 면 소스 비교. 방사 패턴 차이를 Ez 필드로 시각화",
    },
    # ──────── 기하/재료(Geometry/Materials) ────────
    {
        "name": "Block",
        "name_ko": "직육면체 구조체",
        "aliases": ["mp.Block", "rectangular waveguide", "dielectric block"],
        "category": "geometry",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#block",
        "demo_hint": "Si 직사각형 도파관(폭 0.5μm, 높이 0.22μm) Block 정의. 단면 유전율 분포 시각화",
    },
    {
        "name": "Cylinder",
        "name_ko": "원통형 구조체",
        "aliases": ["mp.Cylinder", "cylinder", "circular rod", "disk resonator"],
        "category": "geometry",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#cylinder",
        "demo_hint": "Si 기둥(반경 0.2μm) Cylinder 정의. 포토닉 결정 단위 셀에서 필드 분포",
    },
    {
        "name": "Sphere",
        "name_ko": "구형 구조체",
        "aliases": ["mp.Sphere", "sphere", "microsphere", "whispering gallery"],
        "category": "geometry",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#sphere",
        "demo_hint": "유전체 구(반경 0.5μm) Mie 산란. 산란 단면적(scattering cross section) 계산",
    },
    {
        "name": "Prism",
        "name_ko": "프리즘 (다각형 단면 구조체)",
        "aliases": ["mp.Prism", "polygon", "arbitrary cross section", "tapered waveguide"],
        "category": "geometry",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#prism",
        "demo_hint": "삼각형 단면 테이퍼 구조를 Prism으로 정의. 도파관 테이퍼 투과율 측정",
    },
    {
        "name": "Medium",
        "name_ko": "매질 (유전체/금속 재료 정의)",
        "aliases": ["mp.Medium", "epsilon", "index", "dielectric", "material"],
        "category": "geometry",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#medium",
        "demo_hint": "Si(n=3.48)와 SiO2(n=1.44) Medium 정의. SOI 도파관 단면 유전율 시각화",
    },
    {
        "name": "LorentzianSusceptibility",
        "name_ko": "로렌츠 분산 매질",
        "aliases": ["Lorentzian", "dispersive medium", "resonant susceptibility", "frequency dependent"],
        "category": "geometry",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#susceptibilities",
        "demo_hint": "로렌츠 공진 근처 파장에서 흡수 스펙트럼 계산. 투과율 vs 주파수 플롯",
    },
    {
        "name": "DrudeSusceptibility",
        "name_ko": "드루드 모델 (금속/플라즈모닉)",
        "aliases": ["Drude", "metal", "plasmonic", "free electron"],
        "category": "geometry",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#susceptibilities",
        "demo_hint": "금 나노 입자(DrudeSusceptibility) SPR 시뮬레이션. 국소 전기장 증강 Ez 시각화",
    },
    # ──────── 시뮬레이션 설정(Simulation Setup) ────────
    {
        "name": "Simulation",
        "name_ko": "시뮬레이션 클래스 (핵심 객체)",
        "aliases": ["mp.Simulation", "sim", "simulation object", "main class"],
        "category": "simulation",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#the-simulation-class",
        "demo_hint": "Simulation 객체의 필수 파라미터(cell_size, geometry, sources, resolution) 설명. 최소 실행 예제",
    },
    {
        "name": "cell_size",
        "name_ko": "계산 영역 크기",
        "aliases": ["cell size", "computational domain", "mp.Vector3", "simulation box"],
        "category": "simulation",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#the-simulation-class",
        "demo_hint": "다양한 cell_size 설정 예시. PML 포함 적정 크기 결정 방법 설명",
    },
    {
        "name": "k_point",
        "name_ko": "블로흐 주기 경계 조건 (k 벡터)",
        "aliases": ["k point", "Bloch periodic", "phase shift boundary", "wavevector"],
        "category": "simulation",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#the-simulation-class",
        "demo_hint": "k_point=mp.Vector3(0.5) 주기 경계로 포토닉 결정 밴드 계산. 분산 관계 플롯",
    },
    {
        "name": "at_every",
        "name_ko": "주기적 스텝 함수",
        "aliases": ["at_every", "step function", "output_every", "during simulation"],
        "category": "simulation",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#run-and-step-functions",
        "demo_hint": "at_every(10, mp.output_efield_z)로 10 스텝마다 Ez 저장. 애니메이션 프레임 생성",
    },
    {
        "name": "in_volume",
        "name_ko": "특정 영역 내 연산",
        "aliases": ["in_volume", "volume region", "spatial restriction", "subregion"],
        "category": "simulation",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#run-and-step-functions",
        "demo_hint": "in_volume으로 도파관 코어 영역만 필드 출력. 관심 영역 집중 분석",
    },
    # ──────── 모니터/출력(Monitor/Output) ────────
    {
        "name": "get_array",
        "name_ko": "필드 배열 추출",
        "aliases": ["get_array", "field extraction", "numpy array", "sim.get_array"],
        "category": "monitor",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#field-retrieval-functions",
        "demo_hint": "get_array(mp.Ez, vol=...)로 Ez 2D 배열 추출. matplotlib imshow 시각화",
    },
    {
        "name": "plot2D",
        "name_ko": "MEEP 내장 2D 시각화",
        "aliases": ["sim.plot2D", "visualization", "geometry plot", "field plot"],
        "category": "monitor",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#visualization",
        "demo_hint": "sim.plot2D()로 유전율 구조와 Ez 필드를 함께 시각화. 컬러맵 커스터마이징",
    },
    {
        "name": "add_energy",
        "name_ko": "에너지 밀도 모니터",
        "aliases": ["add_energy", "energy monitor", "electromagnetic energy", "stored energy"],
        "category": "monitor",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#energy-density-spectra",
        "demo_hint": "공진기 내부 저장 에너지 시간 변화 모니터링. 링 공진기 에너지 축적 시각화",
    },
    {
        "name": "LDOS",
        "name_ko": "국소 상태 밀도 (Purcell 인자)",
        "aliases": ["LDOS", "local density of states", "Purcell factor", "spontaneous emission"],
        "category": "monitor",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#local-density-of-states",
        "demo_hint": "금속 나노 안테나 근방 Purcell 인자 계산. 자연 방출률 증강비(F_p) 주파수 스펙트럼",
    },
    {
        "name": "output_efield",
        "name_ko": "전기장 HDF5 출력",
        "aliases": ["output_efield_z", "output_hfield", "h5 output", "field dump"],
        "category": "monitor",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#output-functions",
        "demo_hint": "output_efield_z로 Ez 필드를 HDF5에 저장 → h5py로 읽어서 imshow 시각화",
    },
    # ──────── 분석(Analysis) ────────
    {
        "name": "get_eigenmode_coefficients",
        "name_ko": "모드 계수 추출 (파워 분해)",
        "aliases": ["get_eigenmode_coefficients", "mode decomposition", "modal power", "alpha"],
        "category": "analysis",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#mode-decomposition",
        "demo_hint": "Y자 분기 도파관에서 TE0/TE1 모드 파워 비율 추출. 각 포트 모드 계수 계산",
    },
    {
        "name": "mode_decomposition",
        "name_ko": "모드 분해 (S-매트릭스)",
        "aliases": ["mode decomposition", "S-matrix", "S-parameter", "port modes"],
        "category": "analysis",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/Mode_Decomposition/",
        "demo_hint": "MMI 1x2 스플리터 S-matrix 계산. S11(반사), S21/S31(투과) 계수 추출",
    },
    {
        "name": "phase_velocity",
        "name_ko": "위상 속도 및 군속도",
        "aliases": ["phase velocity", "group velocity", "dispersion", "effective index"],
        "category": "analysis",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/Band_Diagram,_Resonant_Modes,_and_Transmission_in_a_Photonic_Crystal_Waveguide/",
        "demo_hint": "도파관 분산 관계 k(ω) 계산. n_eff = c*k/ω 유효 굴절률 vs 파장 플롯",
    },
    {
        "name": "epsilon_r",
        "name_ko": "유전율 분포 추출",
        "aliases": ["epsilon_r", "get_epsilon", "dielectric profile", "refractive index map"],
        "category": "analysis",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#field-retrieval-functions",
        "demo_hint": "sim.get_array(component=mp.Dielectric)로 유전율 맵 추출. 구조 검증 시각화",
    },
    # ──────── 최적화(Optimization) ────────
    {
        "name": "OptimizationProblem",
        "name_ko": "MEEP 최적화 문제 클래스",
        "aliases": ["OptimizationProblem", "mpa.OptimizationProblem", "meep adjoint solver"],
        "category": "optimization",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#meep-adjoint",
        "demo_hint": "OptimizationProblem 설정: sim, objective_function, design_variables. 첫 FOM + gradient 계산",
    },
    {
        "name": "design_region",
        "name_ko": "역설계 영역 정의",
        "aliases": ["design region", "mpa.DesignRegion", "design variable region"],
        "category": "optimization",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#meep-adjoint",
        "demo_hint": "2μm × 2μm 설계 영역 DesignRegion 정의. MaterialGrid와 연결하여 초기 구조 시각화",
    },
    {
        "name": "filter_and_project",
        "name_ko": "필터링 + 이진화 투영",
        "aliases": ["filter project", "conic filter", "gaussian filter", "threshold projection"],
        "category": "optimization",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/AdjointSolver/#filtering-and-thresholding",
        "demo_hint": "conic_filter + simple_2d_filter 파이프라인. 필터링 전/후 구조 비교 시각화",
    },
    {
        "name": "beta_projection",
        "name_ko": "이진화 강도 (β 파라미터)",
        "aliases": ["beta", "binary projection", "binarization", "heaviside projection"],
        "category": "optimization",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/AdjointSolver/#fabrication-constraints",
        "demo_hint": "β=1 vs β=64 Heaviside 투영 비교. 그레이스케일→이진 구조 전환 과정 시각화",
    },
    {
        "name": "nlopt",
        "name_ko": "NLopt 최적화 알고리즘",
        "aliases": ["nlopt", "NLOPT", "L-BFGS", "gradient optimizer", "scipy minimize"],
        "category": "optimization",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/AdjointSolver/#optimization-with-nlopt",
        "demo_hint": "nlopt.opt(nlopt.LD_MMA, n) 설정. adjoint gradient 기반 MMA 최적화 반복 수렴 플롯",
    },
    {
        "name": "FOM",
        "name_ko": "Figure of Merit (목적 함수)",
        "aliases": ["FOM", "objective function", "figure of merit", "merit function", "loss"],
        "category": "optimization",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/AdjointSolver/",
        "demo_hint": "TE0 모드 변환기 FOM = |α_TE1|² 정의. FOM 최대화 목표 설명 및 초기값 계산",
    },
    {
        "name": "eig_parity",
        "name_ko": "고유모드 패리티 (TE/TM 선택)",
        "aliases": ["eig_parity", "ODD_Z", "EVEN_Z", "ODD_Y", "TE TM parity"],
        "category": "source",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_User_Interface/#eigenmodesource",
        "demo_hint": "ODD_Z(TE 편광) vs EVEN_Z(TM 편광) 모드 비교. 각 편광의 Ez/Hz 필드 패턴 시각화",
    },
    # ──────── MPI/성능(MPI/Performance) ────────
    {
        "name": "mpi",
        "name_ko": "MPI 병렬 시뮬레이션",
        "aliases": ["MPI", "mpirun", "parallel MEEP", "distributed computing"],
        "category": "simulation",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Parallel_MEEP/",
        "demo_hint": "mpirun -np 4 python script.py 실행. am_master()로 rank-0만 출력. 병렬 효율 설명",
    },
    {
        "name": "chunk",
        "name_ko": "계산 청크 (MPI 도메인 분할)",
        "aliases": ["chunk", "domain decomposition", "MPI chunk", "load balancing"],
        "category": "simulation",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Parallel_MEEP/#chunks-and-communication",
        "demo_hint": "chunk_layout 시각화. 4 프로세스에서 도메인 분할 방식 설명",
    },
    # ──────── 포토닉 디바이스(Photonic Devices) ────────
    {
        "name": "waveguide",
        "name_ko": "실리콘 도파관 기초",
        "aliases": ["waveguide", "strip waveguide", "channel waveguide", "rib waveguide"],
        "category": "device",
        "difficulty": "basic",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/Straight_Waveguide/",
        "demo_hint": "SOI 220nm Si 도파관(폭 0.5μm). TE0 전파, 투과율 99% 이상 확인",
    },
    {
        "name": "ring_resonator",
        "name_ko": "링 공진기",
        "aliases": ["ring resonator", "microring", "WGM", "add-drop filter"],
        "category": "device",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/Ring_Resonator_in_Cylindrical_Coordinates/",
        "demo_hint": "링 공진기 FSR, Q factor, 결합 효율 계산. 투과/낙하 포트 스펙트럼 비교",
    },
    {
        "name": "photonic_crystal",
        "name_ko": "포토닉 결정",
        "aliases": ["photonic crystal", "PhC", "photonic bandgap", "periodic structure"],
        "category": "device",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/Photonic_Crystal_Slab/",
        "demo_hint": "삼각형 격자 공기 구멍 PhC. 밴드갭 주파수 범위 및 투과 스펙트럼 계산",
    },
    {
        "name": "grating_coupler",
        "name_ko": "격자 결합기",
        "aliases": ["grating coupler", "GC", "diffraction grating", "fiber coupling"],
        "category": "device",
        "difficulty": "advanced",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/Grating_Coupler/",
        "demo_hint": "1D 격자 결합기 주입 효율 vs 파장 스펙트럼. 최적 격자 주기/duty cycle 탐색",
    },
    {
        "name": "mmi_splitter",
        "name_ko": "MMI 1×2 광분배기",
        "aliases": ["MMI", "multimode interference", "1x2 splitter", "3dB coupler", "power splitter"],
        "category": "device",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/",
        "demo_hint": "MMI 1×2 스플리터 50:50 분배 확인. 두 출력 포트 T1, T2 플럭스 측정",
    },
    {
        "name": "bend",
        "name_ko": "도파관 굴곡부 (손실 분석)",
        "aliases": ["waveguide bend", "90 degree bend", "S-bend", "bend loss"],
        "category": "device",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/Basics/",
        "demo_hint": "90° 굴곡 Si 도파관. 굽힘 반경 vs 투과 손실 스윕. 최소 굽힘 반경 결정",
    },
    {
        "name": "taper",
        "name_ko": "도파관 테이퍼 (단열 변환)",
        "aliases": ["taper", "adiabatic taper", "mode converter", "width taper"],
        "category": "device",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/",
        "demo_hint": "선형 테이퍼(0.4→2.0μm, 길이 10μm). 테이퍼 길이 vs 삽입 손실 스윕",
    },
    {
        "name": "directional_coupler",
        "name_ko": "방향성 결합기",
        "aliases": ["directional coupler", "DC", "evanescent coupling", "coupling length"],
        "category": "device",
        "difficulty": "intermediate",
        "doc_url": "https://meep.readthedocs.io/en/latest/Python_Tutorials/",
        "demo_hint": "두 평행 도파관 방향성 결합기. 갭 vs 결합 길이에 따른 파워 이동 비율 계산",
    },
]


PROMPT_TEMPLATE = """당신은 MEEP FDTD 시뮬레이션 전문가이자 교수입니다.
MEEP의 "{name}" ({name_ko}) 개념을 설명해주세요.

참고 URL: {doc_url}
카테고리: {category}
난이도: {difficulty}
데모 힌트: {demo_hint}

다음 형식으로 작성하세요:

SUMMARY:
[1~2문장 핵심 요약. 비전문가도 이해할 수 있게]

EXPLANATION:
[상세 설명 (마크다운 형식, 한국어)
- 물리/수학적 원리 (수식 포함, LaTeX 형식: $수식$)
- MEEP에서 어떻게 구현되어 있는지
- 파라미터 설명
- 언제 사용하는지]

PHYSICS_BACKGROUND:
[수식 중심의 물리 배경 설명
예: PML은 복소 좌표 변환 $\\tilde{{x}} = x(1 + i\\sigma/\\omega)$을 사용하여...]

COMMON_MISTAKES:
["실수 1: ...", "실수 2: ...", "실수 3: ..."]

RELATED_CONCEPTS:
["개념1", "개념2"]

DEMO_CODE:
```python
# {demo_hint}
# 완전히 독립 실행 가능한 코드 (import부터 결과 출력까지)
# matplotlib.use('Agg') 필수
# plt.savefig('output.png') 로 이미지 저장
# 100줄 이내, resolution=10~20 (빠른 실행)
import meep as mp
...
```

DEMO_DESCRIPTION:
[코드가 보여주는 것 설명. 실행 결과로 무엇을 볼 수 있는지]
"""


def parse_response(text: str) -> dict:
    result = {}
    SECTION_TAGS = [
        "SUMMARY", "EXPLANATION", "PHYSICS_BACKGROUND",
        "COMMON_MISTAKES", "RELATED_CONCEPTS", "DEMO_CODE", "DEMO_DESCRIPTION"
    ]

    # 각 섹션 헤더의 시작 위치(줄 시작) 찾기
    section_line_starts = {}
    section_content_starts = {}
    for tag in SECTION_TAGS:
        # ## SUMMARY: 또는 SUMMARY: 형식 모두 처리
        m = re.search(rf'(?m)^[#\-\s]*{tag}\s*:', text)
        if m:
            section_line_starts[tag] = m.start()
            section_content_starts[tag] = m.end()

    def get_section(tag: str) -> str:
        if tag not in section_content_starts:
            return ""
        start = section_content_starts[tag]
        end = len(text)
        # 현재 섹션보다 뒤에 있는 다른 섹션 헤더 중 가장 가까운 것 찾기
        for other_tag, other_line_start in section_line_starts.items():
            if other_tag != tag and other_line_start > section_line_starts[tag]:
                end = min(end, other_line_start)
        return text[start:end].strip()

    def clean_section(s: str) -> str:
        # 앞뒤 구분선(---) 제거
        s = re.sub(r'^\s*---+\s*\n?', '', s).strip()
        s = re.sub(r'\n?\s*---+\s*$', '', s).strip()
        s = re.sub(r'\n?\s*===+\s*$', '', s).strip()
        return s

    result["summary"] = clean_section(get_section("SUMMARY"))
    result["explanation"] = clean_section(get_section("EXPLANATION"))
    result["physics_background"] = clean_section(get_section("PHYSICS_BACKGROUND"))
    result["demo_description"] = clean_section(get_section("DEMO_DESCRIPTION"))

    cm_text = clean_section(get_section("COMMON_MISTAKES"))
    try:
        m = re.search(r'\[[\s\S]*?\]', cm_text)
        if m:
            result["common_mistakes"] = json.dumps(json.loads(m.group(0)), ensure_ascii=False)
        else:
            lines = []
            for l in cm_text.split('\n'):
                l = l.strip().lstrip('-').lstrip('*').strip().strip('"').strip("'").rstrip(',')
                if l and l not in ['[', ']']:
                    lines.append(l)
            result["common_mistakes"] = json.dumps(lines[:5], ensure_ascii=False)
    except:
        result["common_mistakes"] = json.dumps([cm_text[:200]] if cm_text else [], ensure_ascii=False)

    rc_text = clean_section(get_section("RELATED_CONCEPTS"))
    try:
        m = re.search(r'\[[\s\S]*?\]', rc_text)
        if m:
            result["related_concepts"] = json.dumps(json.loads(m.group(0)), ensure_ascii=False)
        else:
            lines = []
            for l in rc_text.split('\n'):
                l = l.strip().lstrip('-').lstrip('*').strip().strip('"').strip("'").rstrip(',')
                if l and l not in ['[', ']']:
                    lines.append(l)
            result["related_concepts"] = json.dumps(lines[:8], ensure_ascii=False)
    except:
        result["related_concepts"] = json.dumps([], ensure_ascii=False)

    m = re.search(r'DEMO_CODE:\s*\n```python\n(.*?)```', text, re.DOTALL)
    if not m:
        m = re.search(r'```python\n(.*?)```', text, re.DOTALL)
    result["demo_code"] = m.group(1).strip() if m else ""

    return result


def generate_concept(concept: dict, api_key: str) -> dict:
    import anthropic
    prompt = PROMPT_TEMPLATE.format(
        name=concept["name"],
        name_ko=concept["name_ko"],
        doc_url=concept["doc_url"],
        category=concept["category"],
        difficulty=concept["difficulty"],
        demo_hint=concept["demo_hint"],
    )
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = msg.content[0].text
    return parse_response(response_text)


def save_concept(conn: sqlite3.Connection, concept: dict, parsed: dict):
    conn.execute("""
        INSERT INTO concepts
            (name, name_ko, aliases, category, difficulty,
             summary, explanation, physics_background, common_mistakes, related_concepts,
             demo_code, demo_description,
             result_status, meep_version, doc_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', '1.31.0', ?)
        ON CONFLICT(name) DO UPDATE SET
            name_ko=excluded.name_ko,
            aliases=excluded.aliases,
            category=excluded.category,
            difficulty=excluded.difficulty,
            summary=excluded.summary,
            explanation=excluded.explanation,
            physics_background=excluded.physics_background,
            common_mistakes=excluded.common_mistakes,
            related_concepts=excluded.related_concepts,
            demo_code=excluded.demo_code,
            demo_description=excluded.demo_description,
            doc_url=excluded.doc_url,
            updated_at=CURRENT_TIMESTAMP
    """, (
        concept["name"],
        concept["name_ko"],
        json.dumps(concept["aliases"], ensure_ascii=False),
        concept["category"],
        concept["difficulty"],
        parsed.get("summary", ""),
        parsed.get("explanation", ""),
        parsed.get("physics_background", ""),
        parsed.get("common_mistakes", "[]"),
        parsed.get("related_concepts", "[]"),
        parsed.get("demo_code", ""),
        parsed.get("demo_description", ""),
        concept["doc_url"],
    ))
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--concept", help="특정 개념만 생성 (예: Block)")
    parser.add_argument("--all", action="store_true", help="모든 40개 개념 생성")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="이미 있는 개념 건너뜀")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY가 없습니다.")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH), timeout=10)

    if args.concept:
        targets = [c for c in CONCEPTS if c["name"].lower() == args.concept.lower()]
        if not targets:
            print(f"[ERROR] 개념 '{args.concept}'을 찾지 못했습니다.")
            available = [c["name"] for c in CONCEPTS]
            print(f"사용 가능: {available}")
            sys.exit(1)
    else:
        targets = CONCEPTS

    total = len(targets)
    success = 0
    errors = []

    print(f"총 {total}개 개념 생성 시작...")

    for i, concept in enumerate(targets):
        name = concept["name"]

        if args.skip_existing:
            existing = conn.execute(
                "SELECT summary FROM concepts WHERE name=? AND summary IS NOT NULL AND LENGTH(summary) > 10",
                (name,)
            ).fetchone()
            if existing:
                print(f"[{i+1}/{total}] ⏭️  {name} (already exists, skipping)")
                success += 1
                continue

        print(f"[{i+1}/{total}] 🔄 {name} ({concept['name_ko']}) 생성 중...")
        try:
            parsed = generate_concept(concept, api_key)

            if not parsed.get("summary") or len(parsed["summary"]) < 20:
                print(f"  ⚠️  WARNING summary 짧음: {repr(parsed.get('summary',''))[:50]}")

            save_concept(conn, concept, parsed)
            print(f"  ✅ 저장 완료 (summary: {len(parsed.get('summary',''))}자, code: {len(parsed.get('demo_code',''))}자)")
            success += 1

            if i < total - 1:
                time.sleep(1)

        except Exception as e:
            print(f"  ❌ 실패: {e}")
            errors.append((name, str(e)))

    conn.close()
    print(f"\n=== 완료: {success}/{total} ===")
    if errors:
        print("실패 목록:")
        for name, err in errors:
            print(f"  - {name}: {err}")


if __name__ == "__main__":
    main()
