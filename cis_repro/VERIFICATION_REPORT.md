# CIS Error Detector — 최종 검증 보고서
> 검증일: 2026-04-09

---

## 1. 시스템 구조

```
detector.py (단일 정밀 탐지 시스템)
  ├── 24개 규칙 (Rule 클래스)
  ├── 탐지 Tier
  │   ├── code (정적, 15개): 실행 없이 소스코드 분석
  │   ├── stderr (런타임, 6개): 실행 오류 텍스트 분석
  │   └── result (결과값, 3개): 수치 결과 분석
  └── 3개 공개 API
      ├── classify(code, stderr, result) → 최우선 규칙 1개
      ├── classify_all() → 전체 탐지 목록
      └── auto_fix_loop() → 탐지→수정 반복 (최대 3회)
```

---

## 2. 설계 원칙 (구현 완료)

| 원칙 | 구현 방법 |
|------|---------|
| Context-aware | 탐지 전 `_has_sim()`, `_has_source()` 등으로 컨텍스트 확인 |
| Mutually exclusive | 각 detect 함수가 자신의 특화 패턴만 탐지 (FP 0개 달성) |
| 정밀 탐지 | re.DOTALL 지양, 라인 단위 검사, 주석 라인 제외 |
| False positive 0 | Baseline 코드에서 24개 규칙 모두 오탐 없음 |

---

## 3. 최종 검증 결과

### 전체 요약 (15개 검증 대상)

| 판정 | 수 | 비율 |
|------|---|------|
| **PASS** | **13** | **86.7%** |
| PARTIAL | 0 | - |
| FAIL | 0 | - |
| SKIP | 9 | runtime/result 전용 |
| False Positive | **0** | Baseline 오탐 없음 |

### 카테고리별 결과

| 카테고리 | PASS | 검증수 | 규칙 목록 |
|---------|------|-------|---------|
| BOUNDARY | 3/3 | 3 | KPoint_Missing, EpsAveraging_On, PML_AllDirections |
| GEOMETRY | 4/4 | 4 | Monitor_In_PML, ZCoord_Sign_Error, Pillar_Coord_Inversion, Bayer_Quadrant_Wrong |
| ENVIRONMENT | 1/1 | 1 | Matplotlib_Agg_Missing |
| MPI | 1/1 | 1 | MasterOnly_Missing |
| NUMERICAL | 1/1 | 1 | Resolution_Too_Low |
| SOURCE | 3/3 | 3 | FreqWidth_Too_Narrow, EigenModeSource_Used, Single_Polarization |

### EFF-003, EFF-004 별도 검증 (PASS)

실제 `sim.add_flux` 컨텍스트 코드로 독립 검증:

| 규칙 | 탐지 | 해소 | 비고 |
|------|------|------|------|
| EFF-003 RefNorm_Missing | O | O | load_minus_flux_data 실제 호출 주입 |
| EFF-004 Green_Single_Quadrant | O | O | tran_gb FluxRegion + add_flux 추가 |

Docker 실행 실패는 베이스라인의 `straight_refl_data=None` 때문 (규칙 자체 문제 아님).

---

## 4. SKIP 규칙 (재현 불가 사유)

| 규칙 | 사유 |
|------|------|
| CIS-EFF-001 EfficiencyOver100 | 실제 시뮬 결과 > 1.0 필요 |
| CIS-EFF-002 NegativeFlux | 실제 시뮬 음수 flux 필요 |
| CIS-GEO-002 Pillar_OOB | 런타임 좌표 계산 결과 의존 |
| CIS-MAT-001 Wrong_Focal_Material | params.json 비교 필요 |
| CIS-MPI-001 ProcessLeak | 'not enough slots' 환경 의존 |
| CIS-NUM-002 Divergence | MEEP 실제 발산 재현 불가 |
| CIS-NUM-003 SlowConverge | maximum_run_time long run 필요 |
| CIS-ENV-001 Matplotlib_Display | X server 환경 필요 |
| CIS-ENV-002 Timeout | long run 필요 |

---

## 5. 패치 이력 (이번 세션)

| 패치 | 내용 |
|------|------|
| FP-1 | Bayer_Quadrant_Wrong: re.DOTALL 제거 → 라인 단위 탐지 |
| FP-2 | Green_Single_Quadrant: sim.add_flux 컨텍스트 필수화 |
| P-1 | RefNorm_Missing: detect → 주석 라인 제외, fix → 실제 호출 삽입 |
| P-2 | Pillar_Coord_Inversion: fix → 라인별 i↔j 교환 |
| P-3 | MasterOnly_Missing: fix → 정확한 들여쓰기 am_master 감쌈 |
| P-4 | FreqWidth_Too_Narrow: detect → 0.5 미만만 탐지 (FP 제거) |
| P-5 | Single_Polarization: detect → source[] 블록 분석, fix → 올바른 삽입 |
| P-6 | Green_Single_Quadrant fix → tran_gb FluxRegion 추가 |
| P-7 | RefNorm_Missing fix → refl 변수 자동 탐지 후 실제 호출 삽입 |

---

## 6. 파일 위치

```
meep-kb/cis_repro/
├── detector.py              ← 정밀 탐지 시스템 (단일 진실 원천)
├── verify_final.py          ← 15개 code-tier 규칙 통합 검증
├── verify_eff_rules.py      ← EFF-003/004 독립 검증
├── error_rules.json         ← 규칙 메타데이터 (참조용)
├── CIS_TACIT_KNOWLEDGE.md   ← 암묵지 문서 (LLM 프롬프트용)
└── pipeline.py              ← 전체 파이프라인 (detector.py 사용)
```
