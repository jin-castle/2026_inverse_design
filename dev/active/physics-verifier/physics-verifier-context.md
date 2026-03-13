# Physics Verifier Context
Last Updated: 2026-03-09

## 핵심 파일
- `tools/verified_fix_builder.py` — 수정 대상. `is_physical()`, `build_one()` 함수
- `tools/gemini_answers.json` — Gemini 인제스트 예시
- `tools/ingest_gemini_answers.py` — Gemini 파이프라인

## Docker 실행 패턴
```python
def run_in_docker(code: str, timeout: int = 30) -> tuple[int, str]:
    # docker cp → docker exec mpirun --allow-run-as-root --np 2 python /workspace/name.py
    # (returncode, stdout+stderr)
```

## 현재 T/R 파싱
```python
def parse_tr_values(output: str) -> tuple[Optional[float], Optional[float]]:
    # 패턴: T=0.xxx, tran=0.xxx, Transmission=0.xxx
    # 패턴: R=0.xxx, refl=0.xxx, Reflection=0.xxx
```

## 패턴별 기하학적 극한값 (Tier 4)
```python
PATTERN_PHYSICS_LIMITS = {
    "straight_waveguide": {"T_min": 0.85, "R_max": 0.10},
    "bend_flux":          {"T_min": 0.50, "R_max": 0.40},
    "grating":            {"T_min": 0.10, "R_max": 0.90},
    "ring_resonator":     {"T_min": 0.01, "T_max": 0.99},
    "mode_converter":     {"T_min": 0.50, "R_max": 0.30},
    "splitter":           {"T_min": 0.20, "R_max": 0.30},
}
```

## 레퍼런스 비교 전략 (Tier 2)
```python
# build_one() 흐름 변경
# BEFORE: original → inject_bug(buggy) → docker(buggy) → llm_fix(fixed) → docker(fixed)
# AFTER:  original → docker(original=ref) → inject_bug(buggy) → docker(buggy) → llm_fix(fixed) → docker(fixed) → compare(fixed, ref)

# 오차 기준
T_TOLERANCE = 0.15   # T 오차 ±15%
R_TOLERANCE = 0.30   # R 오차 ±30% (반사율은 변동폭 큼)
MIN_T_REF = 0.01     # 너무 작은 T_ref는 비교 의미 없음
```

## Skill 위치
- 로컬: `C:\Users\user\.openclaw\workspace\skills\meep-physics-verifier\`
- 참조: `C:\Users\user\claude-code-infrastructure-showcase\.claude\skills\error-tracking\SKILL.md`

## 주요 결정사항
- Tier 2 레퍼런스 비교: 원본 코드 Docker 실행 1회 추가 (비용 허용)
- Tier 3 해상도 수렴: Divergence 버그 타입에만 적용 (비용 절감)
- Tier 4/5: 선택적 적용 (패턴명/버그 유형 매칭 시만)
- fix_worked 기준: Tier1+Tier2 모두 통과 시 1, 아니면 0

## SESSION PROGRESS
- [x] 계획서 작성
- [x] is_physical() → VerificationResult 리팩터링 (2026-03-09)
- [x] Tier 2 레퍼런스 비교 구현 (get_reference_tr + verify_tier2)
- [x] Tier 3 해상도 수렴 구현 (verify_tier3_convergence, Divergence 전용)
- [x] Tier 4 기하학적 극한값 구현 (verify_tier4 + PATTERN_PHYSICS_LIMITS)
- [ ] Tier 5 EigenMode 순도 구현 (Phase 5 예정)
- [x] meep-physics-verifier Skill 생성 (SKILL.md + scripts/verify_physics.py)
- [ ] 실제 Docker 환경 통합 테스트 (fix_worked 비율 확인)
