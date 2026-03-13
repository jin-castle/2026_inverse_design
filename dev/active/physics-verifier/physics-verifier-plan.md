# Physics Verifier Plan
Last Updated: 2026-03-09

## Executive Summary
현재 `verified_fix_builder.py`의 `is_physical(T, R)` 함수는 T+R < 1.15 단순 체크만 수행.
다층(Tier 1~5) 물리 검증 시스템으로 고도화하고, 이를 재사용 가능한 OpenClaw Skill로 패키징.

## Current State
```python
# 현재 — 너무 허술
def is_physical(T, R):
    if T is None and R is None: return True  # None도 통과!
    if T > 1.1: return False
    if T + R > 1.15: return False
    return True
```

## Proposed Future State: VerificationResult 다층 검증

```python
@dataclass
class VerificationResult:
    tier1_energy:      bool   # T+R 에너지 보존 0.85~1.05
    tier2_reference:   bool   # 원본 코드 대비 오차 <15%
    tier3_convergence: bool   # 해상도 수렴성 (Divergence 특화)
    tier4_geometry:    bool   # 기하학적 극한값 (직선WG→T>0.9)
    tier5_mode:        bool   # EigenMode 순도 >0.85
    score: float              # 가중 합산 (0.0~1.0)
    is_valid: bool            # Tier1+Tier2 필수
    details: dict             # 각 Tier별 수치
```

## Implementation Phases

### Phase 1 — Tier 1 강화 (즉시, 낮은 비용)
- T/R None 처리: 출력 없으면 검증 실패로 간주
- T+R 범위 강화: 0.85~1.05 (현재 >1.15만 체크)
- T, R 각각 0 이상 강제

### Phase 2 — Tier 2 레퍼런스 비교 (핵심, 중간 비용)
- `build_one()` 메서드: 버그 주입 전 원본 코드 T_ref/R_ref 추출
- 수정 코드 결과를 레퍼런스와 비교 (T 오차 <15%, R <30%)
- Docker 실행 1회 추가 (원본 → 버그 → 수정: 총 3회)

### Phase 3 — Tier 3 수렴성 (Divergence 특화)
- `resolution_too_low`, `resolution_large_cell` 버그에만 적용
- resolution×2 코드 생성 후 실행
- T 변화율 <10% 이면 수렴 인정

### Phase 4 — Tier 4 기하학적 극한값
- PATTERN_PHYSICS_LIMITS 딕셔너리: 패턴명 → (T_min, R_max) 매핑
- straight_waveguide: T_min=0.90, R_max=0.05
- bend_waveguide: T_min=0.65
- grating: T_range=(0.2, 0.95) (넓은 범위 허용)

### Phase 5 — Tier 5 EigenMode 순도
- 시뮬레이션 출력에서 mode_coeff 파싱
- `mp.get_eigenmode_coefficients()` 결과 해석

## Skill 패키징

### Skill 구조
```
meep-physics-verifier/
├── SKILL.md
└── scripts/
    ├── verify_physics.py     — 핵심 검증 로직
    └── reference_runner.py   — 레퍼런스 T/R 추출
```

### Skill 트리거
"MEEP 시뮬레이션 결과 물리 검증", "T/R 값 검증", "에너지 보존 확인"

## Success Metrics
- verified_fix fix_worked=1 비율: 현재 49% → 목표 60%+
- T/R 물리검증 건수: 현재 1건 → 목표 50건+
- 허위 검증(잘못된 fix_worked=1) 감소

## Dependencies
- verified_fix_builder.py (수정 대상)
- meep-pilot-worker Docker 컨테이너
- /api/ingest/sim_error API 엔드포인트
