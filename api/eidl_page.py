#!/usr/bin/env python3
"""
EIDL (Electromagnetics & Intelligent Design Lab) 연구실 GitHub 레포지토리 정리 페이지
GET /eidl  →  세부탭 HTML (AI for Photonics / CIS&Color Router / Metalens / Metagrating / Adjoint Library / Tools)
"""

import html as html_mod

def _e(s: str) -> str:
    return html_mod.escape(str(s or ""), quote=True)

# ── 레포 데이터 정의 ───────────────────────────────────────────────────────────
REPOS = {

# ══════════════════════════════════════════════════════════════════════════════
# [1] AI for Photonics — ML/DL 기반 역설계 서로게이트
# ══════════════════════════════════════════════════════════════════════════════
"ai": [
  {
    "name": "Adjoint-FNO",
    "url": "https://github.com/nanophotonics-lab/Adjoint-FNO",
    "status": "public",
    "lang": "Python",
    "updated": "2025-02",
    "stars": 3,
    "description": "Adjoint Method + Fourier Neural Operator 서로게이트 솔버. 튜너블 메타서페이스(LC, ε=2.5~3.5) 빔 조향 최적화. FNO가 adjoint gradient를 예측 → MEEP FDTD iteration 대체.",
    "files": {
      "model.py": "VAE1D + FNO 모델 정의. Encoder1D/Decoder1D/VAE1D + FNO(SpectralConv1d, FNOBlock). Fourier embedding, conditional input 지원",
      "fno_train.py": "FNO 학습 루프. CategoricalStructureAdjointDataset, Adam optimizer, L1 loss. CLI args: --model_name (FNO/NewFNO/MLP/VAE), --dim, --layer_num, --mode, --condition_num",
      "iteration.py": "MEEP adjoint + FNO surrogate 반복 최적화 루프. define_simulator() → LC MaterialGrid 설계영역 → FNO gradient 예측 → first-order Taylor 업데이트",
      "evaluation.py": "빔 조향 평가. condition(0.1~1.0) = 목표 각도(1.15°~11.31°). FourierFields 모니터로 Ez 집중도 측정. J = mean(|Ez[:,1]|²)",
      "utils.py": "AverageMeter, save/load model, logger 유틸",
      "data/dataset.py": "CategoricalStructureAdjointDataset — (structure, adjoint_gradient, label) 쌍 로드"
    },
    "architecture": "Structure(100px) → FNO → AdjointGradient(100px) 예측. Condition(빔 각도)를 conditional input으로 처리",
    "dataset": "GoogleDrive: metalens dataset. train/valid 분리. 100-dim binary fill fraction + adjoint gradient pair",
    "notes": "KDD 제출 검토. surrogate-solver, kdd-adjoint-fno와 연결된 프로젝트"
  },
  {
    "name": "kdd-adjoint-fno",
    "url": "https://github.com/nanophotonics-lab/kdd-adjoint-fno",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2026-01",
    "stars": 0,
    "description": "Adjoint-FNO KDD 학회 제출 버전. 현재 halted (not in use 상태). Adjoint-FNO의 실험 브랜치.",
    "files": {"not in use/": "프로젝트 중단 상태"},
    "notes": "README: 'Not in use - halted project'"
  },
  {
    "name": "surrogate-solver",
    "url": "https://github.com/nanophotonics-lab/surrogate-solver",
    "status": "private",
    "lang": "Cython",
    "updated": "2026-03",
    "stars": 0,
    "description": "서로게이트 솔버용 입력 데이터(랜덤 구조 + 시뮬레이션 데이터) 생성기. Cython 기반 고속 FDTD 데이터 생성 파이프라인.",
    "files": {
      "main.py": "메인 데이터 생성 스크립트",
      "src/design/": "설계 구조 생성 모듈",
      "src/simulation/": "FDTD 시뮬레이션 래퍼 (Cython 가속)",
      "src/visualization/": "결과 시각화",
      "config/": "시뮬레이션 파라미터 설정",
      "environment.yml": "Conda 환경 파일"
    },
    "notes": "GoogleDrive 샘플 데이터셋 제공. Adjoint-FNO 학습 데이터 생성 전용"
  },
  {
    "name": "cond_interp",
    "url": "https://github.com/nanophotonics-lab/cond_interp",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2024-12",
    "stars": 0,
    "description": "Conditional factor 보간 모델. [Joonhyuk Seo, Chanik Kang, Dongjin Seo]. 구조-조건 관계 학습 및 보간.",
    "files": {
      "train.py": "학습 스크립트",
      "core/": "핵심 모델 및 손실함수",
      "configs/": "실험 설정",
      "builder.py": "모델 빌더"
    },
    "notes": "조건부 역설계 보간 실험"
  },
  {
    "name": "MoE",
    "url": "https://github.com/nanophotonics-lab/MoE",
    "status": "private",
    "lang": "Python",
    "updated": "2025-03",
    "stars": 0,
    "description": "Mixture of Experts 기반 포토닉스 역설계. metalens / waveguide / color-routing 등 다중 디바이스 전문가 모델 앙상블.",
    "files": {
      "metalens/": "메탈렌즈 전문가 모델",
      "waveguide/": "도파로 전문가 모델",
      "fom-c/": "FoM-condition 학습 데이터"
    },
    "notes": "WIP (work-in-progress) 상태"
  },
  {
    "name": "WaveY-Net-reproduce",
    "url": "https://github.com/nanophotonics-lab/WaveY-Net-reproduce",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2024-06",
    "stars": 0,
    "description": "WaveY-Net (파동방정식 기반 DNN) 재현 코드. adjoint field 기반 FoM 최적화 재현. 1D binary grating 패턴 최적화.",
    "files": {
      "reproduce.py": "메인 재현 스크립트",
      "reproduce.ipynb": "Jupyter 버전",
      "data_gen_231215.py": "학습 데이터 생성",
      "adjoint_field/": "adjoint 필드 데이터",
      "vis.ipynb": "결과 시각화"
    },
    "notes": "simulation.gif — 최적화 과정 애니메이션 포함"
  },
  {
    "name": "image_restoration_matching",
    "url": "https://github.com/nanophotonics-lab/image_restoration_matching",
    "status": "private",
    "lang": "Python",
    "updated": "2024-06",
    "stars": 0,
    "description": "DNN 메탈렌즈 이미지 복원 논문용 이미지 매칭 코드. 촬영 이미지 ↔ 참조 이미지 정합 알고리즘.",
    "files": {
      "image_match_main.py": "이미지 매칭 메인",
      "brutal_force_matching.py": "전수 탐색 매칭",
      "image_rename.py": "이미지 파일 정리"
    },
    "notes": "3d-printable-free-form-metalens 논문 연관 실험"
  },
  {
    "name": "llm-data",
    "url": "https://github.com/nanophotonics-lab/llm-data",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2025-06",
    "stars": 0,
    "description": "LLM 기반 포토닉스 데이터 처리. MEEP 시뮬레이션 결과 → LLM 학습 데이터 변환. meep-kb와 연관.",
    "files": {"Meep/": "MEEP 관련 LLM 학습 데이터"},
    "notes": "AutoPhotonDesign 논문 데이터 생성 파이프라인으로 추정"
  },
  {
    "name": "EIDL_Bot",
    "url": "https://github.com/nanophotonics-lab/EIDL_Bot",
    "status": "private",
    "lang": "Python",
    "updated": "2025-04",
    "stars": 0,
    "description": "EIDL 연구실 Slack 알림 봇. 다양한 형식 알림 전송.",
    "notes": "연구실 자동화 인프라"
  },
],

# ══════════════════════════════════════════════════════════════════════════════
# [2] CIS & Color Router — CMOS 이미지 센서 + 컬러 라우팅
# ══════════════════════════════════════════════════════════════════════════════
"cis": [
  {
    "name": "Samsung_CIS",
    "url": "https://github.com/nanophotonics-lab/Samsung_CIS",
    "status": "private",
    "lang": "Python",
    "updated": "2025-02",
    "stars": 0,
    "description": "Samsung CMOS Image Sensor 컬러 라우팅 adjoint 최적화. TiO2 freeform 구조, 멀티레이어, 9픽셀 배열. 저자: Junyoung Kim.",
    "files": {
      "final_code/samsung_adam_multi_layer_9pp_PEC_freeform_TiO2.py": "최신 메인 코드. 9-pixel PEC + TiO2 freeform 멀티레이어 adjoint 최적화",
      "final_code/Post_process_adam_multi_layer_9pp_gaus_PEC_pixels.py": "후처리 코드. Gaussian 프로파일 + PEC 픽셀 배열",
      "final_code/Post_process_adam_multi_layer.py": "멀티레이어 후처리",
      "final_code/best_design/": "최적 설계 결과물",
      "old_code/": "이전 버전 코드"
    },
    "notes": "삼성전자 산학 협력 프로젝트. MEEP adjoint 기반 CIS 컬러 라우팅"
  },
  {
    "name": "CIS_Optimization_meep_python",
    "url": "https://github.com/nanophotonics-lab/CIS_Optimization_meep_python",
    "status": "private",
    "lang": "Python",
    "updated": "2023-12",
    "stars": 0,
    "description": "MEEP Python API 기반 CIS adjoint 최적화 v1. CIS 전용 adjoint 라이브러리 Python 버전.",
    "files": {
      "src/": "CIS 최적화 소스 코드 (Python MEEP adjoint)"
    },
    "notes": "CIS_optimization (C++) 이전의 Python 버전"
  },
  {
    "name": "CIS_optimization",
    "url": "https://github.com/nanophotonics-lab/CIS_optimization",
    "status": "private",
    "lang": "C++",
    "updated": "2023-05",
    "stars": 0,
    "description": "MEEP C++ API 기반 CIS adjoint 최적화 라이브러리 v1. 고속 C++ 구현.",
    "files": {"src/": "C++ CIS 최적화 소스"},
    "notes": "CIS_Optimization_meep_python의 C++ 고속화 버전"
  },
  {
    "name": "Nanophotonics_CIS",
    "url": "https://github.com/nanophotonics-lab/Nanophotonics_CIS",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2024-11",
    "stars": 0,
    "description": "나노포토닉스 기반 CIS 최적화 실험. Hynix와 연관된 색분리 소자 설계 실험.",
    "files": {"Nanophotonics_CIS/": "노트북 모음"},
    "notes": "SK Hynix 산학 협력 관련"
  },
  {
    "name": "Hynix",
    "url": "https://github.com/nanophotonics-lab/Hynix",
    "status": "private, fork",
    "lang": "Jupyter Notebook",
    "updated": "2025-01",
    "stars": 0,
    "description": "SK Hynix 산학 협력 프로젝트. 2024/2025 연도별 실험 분류.",
    "files": {"2024/": "2024년 실험", "2025/": "2025년 실험"},
    "notes": "Fork 레포. 색분리 소자 adjoint 최적화"
  },
  {
    "name": "LGD_DEMO",
    "url": "https://github.com/nanophotonics-lab/LGD_DEMO",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2025-06",
    "stars": 0,
    "description": "LG Display 데모 코드. MEEP 시뮬레이션 3버전 (ver1/2/3_mode). 디스플레이 소자 광학 시뮬레이션.",
    "files": {
      "MEEP_ver1/": "기본 MEEP 시뮬레이션",
      "MEEP_ver2/": "개선 버전",
      "MEEP_ver3_mode/": "모드 분석 포함 버전",
      "reproduce/": "재현 코드",
      "example/": "예제"
    },
    "notes": "LG Display 산학 협력"
  },
  {
    "name": "2023-Corning-AI-Challenge",
    "url": "https://github.com/nanophotonics-lab/2023-Corning-AI-Challenge",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2023-12",
    "stars": 0,
    "description": "Corning AI Challenge 2023. LC 튜너블 메타서페이스 빔 조향 최적화. Adjoint-FNO 원형 코드. VAE/FNO/MLP 비교 실험.",
    "files": {
      "model.py": "VAE + FNO + MLP 모델 (Adjoint-FNO와 동일 구조)",
      "fno_train.py": "FNO 학습",
      "cond_vae_train.py": "조건부 VAE 학습",
      "iteration.py": "MEEP adjoint 반복 최적화",
      "fdtd_meep/": "MEEP FDTD 시뮬레이터",
      "visualization.ipynb": "결과 시각화"
    },
    "notes": "Adjoint-FNO 공개 버전의 원본. LC ε=2.5~3.5 빔 조향 ±11.31° 범위"
  },
  {
    "name": "2024-Corning-PSO-28GHz-unitcell",
    "url": "https://github.com/nanophotonics-lab/2024-Corning-PSO-28GHz-unitcell",
    "status": "private",
    "lang": "Python/MATLAB",
    "updated": "2024-02",
    "stars": 0,
    "description": "Corning AI Challenge 2024. 28GHz 유닛셀 PSO-GSA 최적화. Binary-PSOGSA 알고리즘 Python+MATLAB 구현.",
    "files": {
      "Main.m": "MATLAB 메인",
      "pso.py": "Python PSO 구현",
      "data_gen.py": "데이터 생성",
      "BPSOGSA.m": "Binary PSO-GSA 알고리즘"
    },
    "notes": "28GHz 밀리미터파 메타서페이스 단위셀 최적화"
  },
],

# ══════════════════════════════════════════════════════════════════════════════
# [3] Metalens — 메탈렌즈 역설계 및 이미징
# ══════════════════════════════════════════════════════════════════════════════
"metalens": [
  {
    "name": "2025-Large_scale_metalens",
    "url": "https://github.com/nanophotonics-lab/2025-Large_scale_metalens",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2025-07",
    "stars": 0,
    "description": "대면적 원통형 메탈렌즈 adjoint 역설계 (2025). GLC(Gradient-Lens-Condition) 평균화, z-averaging 기법. 해상도별 수렴 비교 (res=10/20/100).",
    "files": {
      "250716_Cylindrical_metalens_reproduce_GLC.py": "GLC 방법 메탈렌즈 재현",
      "250717_Cylindrical_metalens_reproduce_z_averaging_GLC.py": "z-averaging 개선",
      "250721_Cylindrical_metalens_reproduce_z_averaging_GLC_plots.py": "결과 플롯 (iter 250)",
      "Experiment_A~D.ipynb": "4가지 실험 조건 비교",
      "Near-to-far-analysis.ipynb": "Near-to-far field 변환 분석",
      "optimization_history_plots.png": "수렴 히스토리",
      "final_design.npz": "최적 설계 결과"
    },
    "notes": "대면적 메탈렌즈 설계. 'Different weight' vs 'Same weight' 비교"
  },
  {
    "name": "3d-printable-free-form-metalens",
    "url": "https://github.com/nanophotonics-lab/3d-printable-free-form-metalens",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2024-10",
    "stars": 0,
    "description": "3D 프린팅 가능한 자유형 메탈렌즈. freeform adjoint 설계 + image_restoration_matching으로 이미지 복원 평가.",
    "files": {"step1/": "Step 1: 구조 최적화"},
    "notes": "image_restoration_matching 레포와 연계. 논문 투고 관련"
  },
  {
    "name": "TEMPUS_Fresnel-lens",
    "url": "https://github.com/nanophotonics-lab/TEMPUS_Fresnel-lens",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2024-03",
    "stars": 0,
    "description": "TEMPUS 프로젝트: 8μm bend에서 100° FoV Fresnel 렌즈. -Munseong-. 3단계 설계 (Step1/2/Final).",
    "files": {"Step1/": "초기 설계", "Step2/": "개선", "Final/": "최종 설계"},
    "notes": "Tempus-reproduce와 연관. 2023 Tempus 프로젝트"
  },
  {
    "name": "Tempus-reproduce",
    "url": "https://github.com/nanophotonics-lab/Tempus-reproduce",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2023-12",
    "stars": 0,
    "description": "2023 Tempus - 대면적 Fresnel 렌즈 재현. constrain 실험 포함 (231202, constrain_231222).",
    "files": {"231202/": "초기 재현", "constrain_231222/": "제약 조건 추가", "reproduce/": "최종 재현"},
    "notes": "TEMPUS_Fresnel-lens와 연관"
  },
  {
    "name": "2pp",
    "url": "https://github.com/nanophotonics-lab/2pp",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2025-08",
    "stars": 0,
    "description": "Two-photon polymerization (2PP) 기반 3D 메탈렌즈. Connectivity constraint 적용. Si/polymer 기판별 최적화. NA=0.7/1.0 고NA 메탈렌즈.",
    "files": {
      "2PP_CK_fixed_NA_0.7_cc.ipynb": "NA=0.7 Connectivity Constraint",
      "2PP_CK_fixed_NA_1_검증끝.ipynb": "NA=1.0 검증 완료",
      "Connectivity_constraint*.ipynb": "연결성 제약 실험",
      "2D-multi-design-region.py": "2D 다중 설계 영역",
      "3D-multi-design-region.py": "3D 다중 설계 영역",
      "backbone/": "기반 코드",
      "tutorial/": "튜토리얼"
    },
    "notes": "고NA 3D 메탈렌즈 2PP 제조 역설계. connectivity constraint 핵심"
  },
  {
    "name": "general_solver",
    "url": "https://github.com/nanophotonics-lab/general_solver",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2024-12",
    "stars": 0,
    "description": "FDFD Ceviche 기반 범용 서로게이트 솔버 데이터 생성. FixedSize solver, data 생성, validation 포함.",
    "files": {
      "FixedsizeSolver/": "고정 크기 FDFD 솔버",
      "data/": "학습 데이터",
      "validation/": "검증 코드"
    },
    "notes": "Ceviche FDFD → surrogate-solver 학습용 데이터 생성"
  },
  {
    "name": "shape_optimization",
    "url": "https://github.com/nanophotonics-lab/shape_optimization",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2023-08",
    "stars": 0,
    "description": "형상 최적화 (Shape Optimization). chanik_ver / joonho_ver 비교. 메탈렌즈 유닛셀 형상 최적화.",
    "files": {
      "chanik_ver/shapeopt.py": "Chanik 버전 형상 최적화",
      "joonho_ver/": "Joonho 버전",
      "previous_version_2d/": "이전 2D 버전"
    },
    "notes": "연속 위상 → 이산 형상 변환 연구"
  },
  {
    "name": "meta-atom",
    "url": "https://github.com/nanophotonics-lab/meta-atom",
    "status": "private",
    "lang": "-",
    "updated": "2022",
    "stars": 0,
    "description": "메타원자 설계 코드. 메탈렌즈 단위셀 위상 제어 라이브러리.",
    "notes": "초기 메타원자 연구"
  },
],

# ══════════════════════════════════════════════════════════════════════════════
# [4] Metagrating — 회절 격자 역설계
# ══════════════════════════════════════════════════════════════════════════════
"metagrating": [
  {
    "name": "inverse-design-of-ultrathin-metamaterial-absorber",
    "url": "https://github.com/nanophotonics-lab/inverse-design-of-ultrathin-metamaterial-absorber",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2025-03",
    "stars": 0,
    "description": "초박형 메타물질 흡수체 역설계. 2D/3D adjoint 최적화. 관련 논문 제출 코드.",
    "files": {
      "2D-absorber-adjoint-optimization/": "2D 흡수체 adjoint 최적화",
      "3D-absorber-adjoint-optimization/": "3D 흡수체 adjoint 최적화"
    },
    "notes": "논문: inverse design of ultrathin metamaterial absorber"
  },
  {
    "name": "PSO-absorber",
    "url": "https://github.com/nanophotonics-lab/PSO-absorber",
    "status": "private",
    "lang": "Python",
    "updated": "2024-09",
    "stars": 0,
    "description": "Python MEEP 기반 흡수체 PSO-GSA 최적화. Binary-PSOGSA (Mirjalili 2014 기반). 902차원(451×2) 설계 변수. 108 iteration, 100 particles.",
    "files": {
      "pso.py": "PSO-GSA 메인 알고리즘",
      "algorithms/": "최적화 알고리즘 모음"
    },
    "notes": "Adjoint 대비 PSO ablation 비교용"
  },
  {
    "name": "Dispersive_modeling_PSO",
    "url": "https://github.com/nanophotonics-lab/Dispersive_modeling_PSO",
    "status": "private",
    "lang": "MATLAB",
    "updated": "2023-06",
    "stars": 0,
    "description": "PSO로 Lorentz 분산 모델 최적화 (방사 냉각 소자). -Munseong-. MATLAB 구현.",
    "notes": "방사 냉각 메타서페이스 분산 모델링"
  },
  {
    "name": "Optical-Vortex",
    "url": "https://github.com/nanophotonics-lab/Optical-Vortex",
    "status": "private",
    "lang": "MATLAB",
    "updated": "2024-03",
    "stars": 0,
    "description": "광학 소용돌이(Optical Vortex). Perfect absorber + OV beam DEMUX. -Munseong-. hBN 광스핀-궤도 상호작용 포함.",
    "files": {
      "OV-beam-DEMUX/": "OV 빔 다중화 분리",
      "OV-beam-compression/": "OV 빔 압축",
      "Perfect-absorber (C++)/": "완전 흡수체 C++",
      "optical_spin_orbit_interaction_hBN/": "hBN 스핀-궤도 상호작용"
    },
    "notes": "Optical-vortex-adjoint-optimization과 연관"
  },
  {
    "name": "Optical-vortex-adjoint-optimization",
    "url": "https://github.com/nanophotonics-lab/Optical-vortex-adjoint-optimization",
    "status": "private",
    "lang": "C++",
    "updated": "2023-04",
    "stars": 0,
    "description": "광학 소용돌이 adjoint 최적화. C++ MEEP adjoint 라이브러리 기반.",
    "notes": "Optical-Vortex 레포의 adjoint 최적화 버전"
  },
  {
    "name": "Chiral_metasurface",
    "url": "https://github.com/nanophotonics-lab/Chiral_metasurface",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2024-08",
    "stars": 0,
    "description": "3D 키랄 메타서페이스 역설계. MEEP adjoint 3D 최적화. 원편광 선택적 반응 구조.",
    "files": {
      "3d_adjoint_chiral_meta.py": "3D adjoint 최적화 메인",
      "3d_chiral_meta_final.py": "최종 버전",
      "3d_chiral_meta_final_h5_read.ipynb": "HDF5 결과 분석"
    },
    "notes": "키랄 광학 응답 메타서페이스"
  },
  {
    "name": "grayscale_penalizer",
    "url": "https://github.com/nanophotonics-lab/grayscale_penalizer",
    "status": "private",
    "lang": "Makefile",
    "updated": "2023-08",
    "stars": 0,
    "description": "Adjoint 최적화의 grayscale 패널라이저. grating/metalens 적용. Binarization을 강제하는 패널티 항 추가.",
    "files": {
      "grating/": "회절 격자 grayscale 패널라이저",
      "metalens/": "메탈렌즈 패널라이저"
    },
    "notes": "23-Project: Penalizer with adjoint map"
  },
  {
    "name": "Topopt-with-meep",
    "url": "https://github.com/nanophotonics-lab/Topopt-with-meep",
    "status": "private",
    "lang": "Python",
    "updated": "2024-11",
    "stars": 0,
    "description": "FEniCSx 기반 위상 최적화 (FEniTop) + MEEP FDTD 결합. 기계/광학 토폴로지 최적화.",
    "files": {
      "fenitop/": "FEniTop 핵심 라이브러리",
      "scripts/": "실행 스크립트",
      "meshes/": "메시 파일"
    },
    "notes": "기계공학 토폴로지 최적화를 광학에 적용"
  },
  {
    "name": "2023-KIST-2D-PSO",
    "url": "https://github.com/nanophotonics-lab/2023-KIST-2D-PSO",
    "status": "private",
    "lang": "Python",
    "updated": "2023-07",
    "stars": 0,
    "description": "KIST 2023 프로젝트: 2D PSO 기반 메타서페이스 최적화. 2D 시뮬레이션 + PSO 연동.",
    "files": {"2d-sim/": "2D FDTD 시뮬레이션", "pso/": "PSO 알고리즘"},
    "notes": "한국과학기술연구원 산학 협력"
  },
],

# ══════════════════════════════════════════════════════════════════════════════
# [5] Adjoint Library (C++ 핵심 라이브러리)
# ══════════════════════════════════════════════════════════════════════════════
"adjoint_lib": [
  {
    "name": "2022-Cpp-adjoint-library",
    "url": "https://github.com/nanophotonics-lab/2022-Cpp-adjoint-library",
    "status": "private",
    "lang": "C++",
    "updated": "2022-12",
    "stars": 0,
    "description": "EIDL 연구실 C++ adjoint 최적화 라이브러리 원조. MEEP C++ API 직접 사용. FluxPlane, DiffractionPlane, FieldMaximize 등 FoM 모듈.",
    "files": {
      "ale.hpp": "ALE(Adjoint Library for Electromagnetics) 헤더",
      "MeepSimulator.cpp": "MEEP 시뮬레이터 래퍼",
      "OptimizationControl.cpp": "최적화 제어",
      "FluxPlane.cpp": "플럭스 평면 FoM",
      "DiffractionPlane.cpp": "회절 평면 FoM",
      "FieldMaximize.cpp": "필드 최대화 FoM",
      "Geometry.cpp": "설계 영역 기하",
      "MeepUtils.cpp": "MEEP 유틸리티"
    },
    "notes": "모든 C++ 기반 adjoint 레포의 핵심 라이브러리"
  },
  {
    "name": "encrypted_adjoint_library",
    "url": "https://github.com/nanophotonics-lab/encrypted_adjoint_library",
    "status": "private",
    "lang": "C++",
    "updated": "2023",
    "stars": 0,
    "description": "암호화된 adjoint 라이브러리. 외부 공유용 보호 버전.",
    "files": {"src/": "암호화된 소스 코드"},
    "notes": "산학 협력사 배포용 보호 버전"
  },
  {
    "name": "3D_diffraction",
    "url": "https://github.com/nanophotonics-lab/3D_diffraction",
    "status": "private",
    "lang": "C++",
    "updated": "2023-11",
    "stars": 0,
    "description": "3D 회절 코드 검증 + UDC(Under Display Camera) 회절 격자. 2D/3D adjoint 최적화 + DiffractionPlane 검증.",
    "files": {
      "DiffractionPlane.cpp/hpp": "회절 평면 FoM 구현",
      "Example_2D_UDC.cpp": "2D UDC 예제",
      "Example_3D_UDC.cpp": "3D UDC 예제",
      "Example_2D_adjoint_opt_DP.cpp": "2D adjoint 최적화",
      "Example_3D_diffractiongrating_data_gen.cpp": "3D 데이터 생성"
    },
    "notes": "UDC(디스플레이 하 카메라) 회절 격자 최적화"
  },
  {
    "name": "MeepUtils",
    "url": "https://github.com/nanophotonics-lab/MeepUtils",
    "status": "private",
    "lang": "C++",
    "updated": "2023",
    "stars": 0,
    "description": "ALE MeepUtils — C++ MEEP 유틸리티 모음. 2022-Cpp-adjoint-library에서 분리된 유틸리티.",
    "files": {"MeepUtils.cpp/hpp": "MEEP C++ 유틸리티"},
    "notes": "C++ adjoint 라이브러리 공통 유틸"
  },
  {
    "name": "2023-A3SA",
    "url": "https://github.com/nanophotonics-lab/2023-A3SA",
    "status": "private",
    "lang": "C++",
    "updated": "2023-08",
    "stars": 0,
    "description": "A3SA (Augmentation with Adjoint and Semi-Automated) 프로젝트. Adjoint + GAN 결합. GAN으로 adjoint 솔루션 다양화.",
    "files": {
      "adjoint/": "C++ adjoint 최적화",
      "gan/": "GAN augmentation"
    },
    "notes": "23-Project. PSO-for-designing-metasurfaces와 비교 실험"
  },
  {
    "name": "Adjoint_with_RL",
    "url": "https://github.com/nanophotonics-lab/Adjoint_with_RL",
    "status": "private",
    "lang": "C++",
    "updated": "2023-08",
    "stars": 0,
    "description": "Adjoint + 강화학습(RL) 결합. C++ adjoint + RL 에이전트. 최적화 경로 학습.",
    "files": {
      "OptimizationControl.cpp": "RL-제어 최적화",
      "adjoint_calculator.cpp": "Adjoint 계산기",
      "fom_calculator.cpp": "FoM 계산기"
    },
    "notes": "23-Project. RL로 adjoint 스텝 결정"
  },
  {
    "name": "PSO-for-designing-metasurfaces",
    "url": "https://github.com/nanophotonics-lab/PSO-for-designing-metasurfaces",
    "status": "private",
    "lang": "C++",
    "updated": "2022-12",
    "stars": 0,
    "description": "PSO-GSA C++ 메타서페이스 설계. A3SA 비교용 baseline. Binary PSO-GSA 완성 버전.",
    "files": {
      "src/": "PSO-GSA 알고리즘",
      "algorithms/": "알고리즘 모음",
      "demos/": "데모 예제",
      "validation/": "검증 코드",
      "matlab/": "MATLAB 버전"
    },
    "notes": "22-Project. PSO vs Adjoint 비교 baseline"
  },
  {
    "name": "meep-adjoint-mpa-analyze",
    "url": "https://github.com/nanophotonics-lab/meep-adjoint-mpa-analyze",
    "status": "private",
    "lang": "Python",
    "updated": "2023-06",
    "stars": 0,
    "description": "MEEP adjoint 모듈(.mpa) 소스코드 주석 달기 + history 분석. MEEP adjoint 내부 동작 이해 목적.",
    "notes": "MEEP adjoint 공식 코드 분석용"
  },
],

# ══════════════════════════════════════════════════════════════════════════════
# [6] LNOI & 특수 소자
# ══════════════════════════════════════════════════════════════════════════════
"lnoi": [
  {
    "name": "LNOI-KIST",
    "url": "https://github.com/nanophotonics-lab/LNOI-KIST",
    "status": "private",
    "lang": "Python",
    "updated": "2025-09",
    "stars": 0,
    "description": "LNOI (Lithium Niobate on Insulator) 소자 3D adjoint 최적화. KIST 협력. Mode-converter + SWAP-gate 두 소자 설계.",
    "files": {
      "Mode-converter/": "모드 변환기 (TE0→TE1 등). Optimization.py, Sub_Mapping.py, GDS.py, Post_process.py",
      "SWAP-gate/": "양자 SWAP 게이트 설계. Waveguide.py 포함",
      "Target-field-generator/": "목표 필드 생성기"
    },
    "notes": "3D adjoint 최적화. GDS 파일 출력 포함. PROJ-004-LNOI와 연관"
  },
  {
    "name": "2D-material",
    "url": "https://github.com/nanophotonics-lab/2D-material",
    "status": "private",
    "lang": "Python",
    "updated": "2023-04",
    "stars": 0,
    "description": "2D 소재(hBN, MoS2, 그래핀) 광학 시뮬레이션. 전달행렬법(TMM) 구현.",
    "files": {
      "2dmos2ang.py": "MoS2 각도 의존성",
      "Transfer_matrix_method_MoS2.m": "TMM MATLAB"
    },
    "notes": "2D 소재 광학 특성 계산"
  },
  {
    "name": "Oblique_Planewave",
    "url": "https://github.com/nanophotonics-lab/Oblique_Planewave",
    "status": "private",
    "lang": "Python",
    "updated": "2025-03",
    "stars": 0,
    "description": "MEEP 경사 입사 평면파 예제. 3가지 방법 비교: amp_func 사용, Point source 배치, EigenmodeSource 사용.",
    "files": {
      "1. amp_func 사용/": "진폭 함수 방법",
      "2. Point source 오류 및 배치/": "점 소스 방법",
      "3. Eigenmodesource 사용/": "고유모드 소스",
      "wavelength_check/": "파장 검증"
    },
    "notes": "meep-kb Oblique Planewave 개념 참조 레포"
  },
],

# ══════════════════════════════════════════════════════════════════════════════
# [7] Tools & Infrastructure
# ══════════════════════════════════════════════════════════════════════════════
"tools": [
  {
    "name": "meep",
    "url": "https://github.com/nanophotonics-lab/meep",
    "status": "public, fork",
    "lang": "C++",
    "updated": "2023-07",
    "stars": 0,
    "description": "MEEP FDTD 공식 소스 포크. 연구실 커스텀 수정 이력 관리.",
    "notes": "MIT MEEP 공식 fork. GPL v2"
  },
  {
    "name": "mpb_solver",
    "url": "https://github.com/nanophotonics-lab/mpb_solver",
    "status": "private",
    "lang": "Python",
    "updated": "2023-09",
    "stars": 0,
    "description": "MPB(MIT Photonic Bands) 솔버 래퍼. 1D/2D 포토닉 밴드 구조 계산 예제.",
    "files": {
      "example_1D/": "1D MPB 예제",
      "example_2D/": "2D MPB 예제"
    },
    "notes": "모드 해석, 밴드 구조 계산용"
  },
  {
    "name": "legume_2DPhC",
    "url": "https://github.com/nanophotonics-lab/legume_2DPhC",
    "status": "private",
    "lang": "Python",
    "updated": "2025-09",
    "stars": 0,
    "description": "legume 라이브러리 기반 2D 포토닉 결정 계산.",
    "files": {"legume_test.py": "legume 2D PhC 테스트"},
    "notes": "포토닉 밴드갭 계산"
  },
  {
    "name": "GDS_factory",
    "url": "https://github.com/nanophotonics-lab/GDS_factory",
    "status": "private",
    "lang": "Python",
    "updated": "2024-11",
    "stars": 0,
    "description": "GDS Factory를 이용한 실제 소자 설계 계획면. IDT(Interdigital Transducer) 설계.",
    "files": {"IDT/": "IDT 설계 파일"},
    "notes": "실제 디바이스 GDS 레이아웃 설계"
  },
  {
    "name": "meep-installation-guide",
    "url": "https://github.com/nanophotonics-lab/meep-installation-guide",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2023-09",
    "stars": 0,
    "description": "MEEP 설치 가이드. Jupyter + 쉘 스크립트.",
    "files": {
      "meep_installation_guide.ipynb": "Jupyter 설치 가이드",
      "meep_shell.sh": "쉘 스크립트 자동 설치"
    },
    "notes": "연구실 신규 멤버 온보딩용"
  },
  {
    "name": "meep_python",
    "url": "https://github.com/nanophotonics-lab/meep_python",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2023-04",
    "stars": 0,
    "description": "MEEP Python 예제 모음. adjoint 최적화 예제, 기본 시뮬레이션 예제. SK Hynix 관련 코드 포함.",
    "files": {
      "adjoint_optimization_examples/": "Adjoint 최적화 예제",
      "examples/": "기본 시뮬레이션 예제",
      "hynix/": "SK Hynix 관련 코드"
    },
    "notes": "연구실 MEEP Python 예제 저장소"
  },
  {
    "name": "23-Winter-Study",
    "url": "https://github.com/nanophotonics-lab/23-Winter-Study",
    "status": "private",
    "lang": "Jupyter Notebook",
    "updated": "2023-02",
    "stars": 0,
    "description": "EIDL 2023 겨울 스터디. 전자기학, 수치해석, 계산전자기학 공부 자료.",
    "files": {
      "Electromagnetics/": "전자기학",
      "Numerical_Methods/": "수치해석",
      "Computational_Electromagnetics/": "계산전자기학"
    },
    "notes": "연구실 스터디 자료 아카이브"
  },
  {
    "name": "github-practice",
    "url": "https://github.com/nanophotonics-lab/github-practice",
    "status": "private",
    "lang": "Python",
    "updated": "2023-04",
    "stars": 0,
    "description": "EIDL GitHub commit/PR 연습 레포.",
    "notes": "신입 멤버 Git 연습용"
  },
],

}  # END REPOS


# ── HTML 생성 ──────────────────────────────────────────────────────────────────
def _get_patterns_for_repo(repo_name: str) -> list:
    """DB에서 해당 레포 관련 패턴 조회"""
    import sqlite3
    from pathlib import Path
    DB = Path(__file__).parent.parent / "db" / "knowledge.db"
    try:
        conn = sqlite3.connect(str(DB))
        rows = conn.execute(
            "SELECT pattern_name, description, code_snippet FROM patterns WHERE author_repo LIKE ?",
            (f"%{repo_name}%",)
        ).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def _repo_card(r: dict, tab: str) -> str:
    status_color = {"public": "#22c55e", "private": "#94a3b8",
                    "public, fork": "#3b82f6", "private, fork": "#8b5cf6",
                    "private, Jupyter Notebook": "#94a3b8"}.get(r.get("status",""), "#94a3b8")
    lang_colors = {"Python":"#3776ab","C++":"#f34b7d","Jupyter Notebook":"#f37726",
                   "MATLAB":"#e16737","Cython":"#fedf5b","Python/MATLAB":"#3776ab","-":"#666"}
    lang = r.get("lang", "-")
    lang_color = lang_colors.get(lang, "#888")

    # Files section
    files_html = ""
    if r.get("files"):
        files_html = '<div class="eidl-files"><div class="eidl-files-title">📂 파일 구조</div>'
        for fname, fdesc in r["files"].items():
            files_html += f'<div class="eidl-file-row"><span class="eidl-fname">{_e(fname)}</span><span class="eidl-fdesc">{_e(fdesc)}</span></div>'
        files_html += '</div>'

    stars_html = f'<span class="eidl-stars">⭐ {r.get("stars",0)}</span>' if r.get("stars",0) > 0 else ""
    notes_html = f'<div class="eidl-notes">💡 {_e(r.get("notes",""))}</div>' if r.get("notes") else ""
    arch_html = f'<div class="eidl-arch"><strong>🔧 아키텍처:</strong> {_e(r.get("architecture",""))}</div>' if r.get("architecture") else ""
    dataset_html = f'<div class="eidl-dataset"><strong>📊 데이터셋:</strong> {_e(r.get("dataset",""))}</div>' if r.get("dataset") else ""

    # meep-kb 패턴 링크
    patterns = _get_patterns_for_repo(r["name"])
    patterns_html = ""
    if patterns:
        patterns_html = '<div class="eidl-patterns"><div class="eidl-patterns-title">⚙️ meep-kb 패턴 ({} 개)</div>'.format(len(patterns))
        for pat_name, pat_desc, pat_code in patterns:
            code_preview = (pat_code or "")[:400].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            pat_id = f"pat-{_e(pat_name)}"
            patterns_html += f'''
<div class="eidl-pattern-item">
  <div class="eidl-pattern-header" onclick="togglePatCode('{pat_id}')">
    <a href="/dict#{_e(pat_name)}" target="_blank" class="eidl-pattern-name">⚙️ {_e(pat_name)}</a>
    <span class="eidl-pattern-desc">{_e((pat_desc or "")[:80])}</span>
    <span class="eidl-code-toggle">▶ 코드 보기</span>
  </div>
  <pre id="{pat_id}" class="eidl-code-block" style="display:none"><code class="language-python">{code_preview}
...</code></pre>
</div>'''
        patterns_html += '</div>'

    return f'''
<div class="eidl-card" id="{_e(tab)}-{_e(r["name"])}">
  <div class="eidl-card-header">
    <a href="{_e(r["url"])}" target="_blank" class="eidl-repo-name">{_e(r["name"])}</a>
    <div class="eidl-badges">
      <span class="eidl-badge" style="background:{status_color}22;color:{status_color};border:1px solid {status_color}44">{_e(r.get("status",""))}</span>
      <span class="eidl-badge" style="background:{lang_color}22;color:{lang_color};border:1px solid {lang_color}44">{_e(lang)}</span>
      {stars_html}
      <span class="eidl-updated">🕐 {_e(r.get("updated",""))}</span>
    </div>
  </div>
  <div class="eidl-desc">{_e(r.get("description",""))}</div>
  {arch_html}
  {dataset_html}
  {files_html}
  {patterns_html}
  {notes_html}
</div>'''


TAB_META = {
    "ai":          ("🤖", "AI for Photonics",     "FNO 서로게이트 · VAE · 데이터 생성 · LLM"),
    "cis":         ("📷", "CIS & Color Router",    "CMOS 이미지 센서 · 컬러 라우팅 · Samsung/Hynix/LGD"),
    "metalens":    ("🔭", "Metalens & Imaging",    "대면적 메탈렌즈 · 2PP · Fresnel · 이미지 복원"),
    "metagrating": ("🌈", "Metagrating & Absorber","흡수체 · 회절격자 · 키랄 · 광학소용돌이 · PSO"),
    "adjoint_lib": ("⚙️", "Adjoint Library",       "C++ 핵심 라이브러리 · RL · GAN augmentation"),
    "lnoi":        ("💎", "LNOI & Special Device", "LNOI 양자소자 · 2D 소재 · 경사입사"),
    "tools":       ("🔧", "Tools & Infrastructure","MEEP 포크 · MPB · GDS · 설치가이드 · 스터디"),
}


def generate_eidl_html() -> str:
    # 탭 버튼
    tab_btns = ""
    tab_panes = ""
    first = True
    for key, (icon, title, subtitle) in TAB_META.items():
        repos = REPOS.get(key, [])
        active = "active" if first else ""
        tab_btns += f'''
    <button class="eidl-tab-btn {active}" onclick="switchEidlTab('{_e(key)}', this)">
      <span class="eidl-tab-icon">{icon}</span>
      <span class="eidl-tab-title">{_e(title)}</span>
      <span class="eidl-tab-count">{len(repos)}</span>
    </button>'''

        cards_html = "\n".join(_repo_card(r, key) for r in repos)
        tab_panes += f'''
  <div id="eidl-tab-{_e(key)}" class="eidl-tab-pane {"active" if first else ""}">
    <div class="eidl-tab-header">
      <h2>{icon} {_e(title)}</h2>
      <p class="eidl-tab-subtitle">{_e(subtitle)}</p>
    </div>
    <div class="eidl-cards-grid">
      {cards_html}
    </div>
  </div>'''
        first = False

    # 전체 통계
    total = sum(len(v) for v in REPOS.values())
    public = sum(1 for v in REPOS.values() for r in v if "public" in r.get("status",""))
    private = total - public

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EIDL GitHub Repository</title>
<style>
:root {{
  --bg: #0f172a; --surface: #1e293b; --border: #334155;
  --accent: #38bdf8; --text: #e2e8f0; --muted: #94a3b8;
  --card-bg: #1e293b; --card-border: #334155;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }}

/* ── 헤더 ── */
.eidl-header {{
  background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%);
  border-bottom: 1px solid var(--border);
  padding: 28px 32px 0;
}}
.eidl-header-top {{
  display: flex; align-items: center; gap: 16px; margin-bottom: 6px;
}}
.eidl-logo {{ font-size: 32px; }}
.eidl-org-name {{ font-size: 22px; font-weight: 700; color: var(--accent); }}
.eidl-org-sub {{ font-size: 13px; color: var(--muted); margin-bottom: 16px; }}
.eidl-stats {{
  display: flex; gap: 24px; font-size: 13px; color: var(--muted); margin-bottom: 12px;
}}
.eidl-stat {{ display: flex; align-items: center; gap: 6px; }}
.eidl-stat strong {{ color: var(--text); font-size: 18px; }}

/* ── 세부탭 네비 ── */
.eidl-tab-nav {{
  display: flex; gap: 4px; overflow-x: auto; padding-top: 8px;
  scrollbar-width: none;
}}
.eidl-tab-nav::-webkit-scrollbar {{ display: none; }}
.eidl-tab-btn {{
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  padding: 10px 20px; background: none; border: none; cursor: pointer;
  color: var(--muted); border-bottom: 2px solid transparent;
  transition: all 0.2s; white-space: nowrap; min-width: 120px;
}}
.eidl-tab-btn:hover {{ color: var(--text); background: rgba(56,189,248,0.05); }}
.eidl-tab-btn.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
.eidl-tab-icon {{ font-size: 20px; }}
.eidl-tab-title {{ font-size: 11px; font-weight: 600; }}
.eidl-tab-count {{
  font-size: 10px; background: #334155; border-radius: 10px;
  padding: 1px 7px; color: var(--muted);
}}
.eidl-tab-btn.active .eidl-tab-count {{ background: #1e40af; color: #93c5fd; }}

/* ── 탭 패널 ── */
.eidl-tab-pane {{ display: none; padding: 24px 32px; }}
.eidl-tab-pane.active {{ display: block; }}
.eidl-tab-header {{ margin-bottom: 20px; }}
.eidl-tab-header h2 {{ font-size: 20px; font-weight: 700; color: var(--text); margin-bottom: 4px; }}
.eidl-tab-subtitle {{ font-size: 13px; color: var(--muted); }}

/* ── 카드 그리드 ── */
.eidl-cards-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(520px, 1fr));
  gap: 16px;
}}
.eidl-card {{
  background: var(--card-bg); border: 1px solid var(--card-border);
  border-radius: 10px; padding: 18px;
  transition: border-color 0.2s, box-shadow 0.2s;
}}
.eidl-card:hover {{
  border-color: #38bdf855; box-shadow: 0 0 12px rgba(56,189,248,0.1);
}}
.eidl-card-header {{
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 12px; margin-bottom: 10px; flex-wrap: wrap;
}}
.eidl-repo-name {{
  font-size: 15px; font-weight: 700; color: var(--accent);
  text-decoration: none;
}}
.eidl-repo-name:hover {{ text-decoration: underline; }}
.eidl-badges {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
.eidl-badge {{
  font-size: 10px; padding: 2px 8px; border-radius: 99px; font-weight: 600;
}}
.eidl-stars {{ font-size: 11px; color: #fbbf24; }}
.eidl-updated {{ font-size: 11px; color: var(--muted); }}
.eidl-desc {{ font-size: 13px; color: var(--text); line-height: 1.6; margin-bottom: 12px; }}
.eidl-arch, .eidl-dataset {{
  font-size: 12px; color: #a5b4fc; margin-bottom: 8px; line-height: 1.5;
}}
.eidl-files {{
  background: #0f172a; border: 1px solid #1e3a5f;
  border-radius: 6px; padding: 10px 12px; margin-bottom: 10px;
}}
.eidl-files-title {{ font-size: 11px; color: var(--muted); font-weight: 600; margin-bottom: 8px; }}
.eidl-file-row {{ display: flex; gap: 10px; margin-bottom: 5px; align-items: baseline; }}
.eidl-fname {{
  font-size: 11px; color: #86efac; font-family: 'Courier New', monospace;
  white-space: nowrap; min-width: 220px; max-width: 280px;
  overflow: hidden; text-overflow: ellipsis;
}}
.eidl-fdesc {{ font-size: 11px; color: var(--muted); line-height: 1.4; }}
.eidl-notes {{
  font-size: 11px; color: #fbbf24; padding: 6px 10px;
  background: rgba(251,191,36,0.08); border-left: 2px solid #fbbf24;
  border-radius: 0 4px 4px 0;
}}

/* ── 검색 ── */
.eidl-search-wrap {{ margin-bottom: 16px; }}
.eidl-search {{
  width: 100%; max-width: 400px; padding: 8px 14px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 6px; color: var(--text); font-size: 13px;
}}
.eidl-search:focus {{ outline: none; border-color: var(--accent); }}

/* ── meep-kb 패턴 링크 ── */
.eidl-patterns {{
  border: 1px solid #1e3a5f; border-radius: 6px;
  padding: 10px 12px; margin-bottom: 10px; background: #0a1628;
}}
.eidl-patterns-title {{
  font-size: 11px; color: #60a5fa; font-weight: 700; margin-bottom: 8px;
}}
.eidl-pattern-item {{
  border-bottom: 1px solid #1e293b; padding: 5px 0;
}}
.eidl-pattern-item:last-child {{ border-bottom: none; }}
.eidl-pattern-header {{
  display: flex; align-items: baseline; gap: 8px; cursor: pointer;
  flex-wrap: wrap;
}}
.eidl-pattern-header:hover .eidl-pattern-name {{ text-decoration: underline; }}
.eidl-pattern-name {{
  font-size: 11.5px; color: #7dd3fc; font-weight: 600;
  white-space: nowrap;
}}
.eidl-pattern-desc {{
  font-size: 10.5px; color: var(--muted); flex: 1;
}}
.eidl-code-toggle {{
  font-size: 10px; color: #475569; cursor: pointer; white-space: nowrap;
  padding: 1px 6px; border: 1px solid #334155; border-radius: 4px;
  transition: all 0.2s;
}}
.eidl-code-toggle:hover {{ color: var(--accent); border-color: var(--accent); }}
.eidl-code-block {{
  background: #020617; border-radius: 5px; padding: 10px 12px;
  margin-top: 6px; font-size: 10.5px; overflow-x: auto;
  max-height: 300px; overflow-y: auto;
  border: 1px solid #1e3a5f;
}}
.eidl-code-block code {{
  color: #94a3b8; font-family: 'Courier New', monospace; white-space: pre;
}}

@media (max-width: 768px) {{
  .eidl-cards-grid {{ grid-template-columns: 1fr; }}
  .eidl-tab-btn {{ min-width: 90px; padding: 8px 12px; }}
  .eidl-header, .eidl-tab-pane {{ padding-left: 16px; padding-right: 16px; }}
}}
</style>
</head>
<body>

<!-- ── 헤더 ── -->
<div class="eidl-header">
  <div class="eidl-header-top">
    <span class="eidl-logo">🏛️</span>
    <div>
      <div class="eidl-org-name">EIDL — Electromagnetics &amp; Intelligent Design Lab</div>
    </div>
  </div>
  <div class="eidl-org-sub">
    포토닉스 역설계 연구실 GitHub 레포지토리 전체 정리
    &nbsp;·&nbsp; <a href="https://github.com/nanophotonics-lab" target="_blank" style="color:var(--accent)">github.com/nanophotonics-lab</a>
  </div>
  <div class="eidl-stats">
    <div class="eidl-stat">📦 총 <strong>{total}</strong> 레포</div>
    <div class="eidl-stat">🔓 공개 <strong>{public}</strong></div>
    <div class="eidl-stat">🔒 비공개 <strong>{private}</strong></div>
    <div class="eidl-stat">🔬 adjoint · FNO · PSO · GAN · RL</div>
  </div>

  <!-- 탭 네비게이션 -->
  <nav class="eidl-tab-nav">
    {tab_btns}
  </nav>
</div>

<!-- ── 탭 내용 ── -->
{tab_panes}

<script>
function switchEidlTab(name, btn) {{
  document.querySelectorAll('.eidl-tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.eidl-tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('eidl-tab-' + name).classList.add('active');
  btn.classList.add('active');
  window.location.hash = 'eidl-' + name;
}}

function togglePatCode(id) {{
  const el = document.getElementById(id);
  const toggle = el.previousElementSibling.querySelector('.eidl-code-toggle');
  if (el.style.display === 'none') {{
    el.style.display = 'block';
    toggle.textContent = '▼ 접기';
    toggle.style.color = 'var(--accent)';
  }} else {{
    el.style.display = 'none';
    toggle.textContent = '▶ 코드 보기';
    toggle.style.color = '';
  }}
}}
window.addEventListener('load', () => {{
  const h = window.location.hash.replace('#eidl-','');
  const pane = document.getElementById('eidl-tab-' + h);
  if (pane) {{
    const btn = document.querySelector(`.eidl-tab-btn[onclick*="${{h}}"]`);
    if (btn) switchEidlTab(h, btn);
  }}
}});
</script>
</body>
</html>"""
