# Physics Verifier Tasks
Last Updated: 2026-03-09

## Phase 1 — Tier 1 강화 [S] ✅ 완료 (2026-03-09)
- [x] `is_physical()` → `VerificationResult` dataclass 교체
- [x] T/R None → 실패 처리 (None AND None = False)
- [x] T+R 범위: 0.80~1.10 (기존 >1.15만 체크에서 강화)
- [x] T ≥ 0, R ≥ 0 강제
- [x] `is_physical()` 호환 래퍼 유지 (verify_tier1 내부 호출)

## Phase 2 — Tier 2 레퍼런스 비교 [M] ✅ 완료 (2026-03-09)
- [x] `get_reference_tr(original_code, timeout=45)` 함수 구현
  - Docker로 원본 코드 실행 (run_in_docker 재사용)
  - T_ref, R_ref 파싱
  - 실패 시 None 반환 (비교 스킵)
- [x] `verify_tier2(T_fix, R_fix, T_ref, R_ref)` 구현
  - dT = |T_fix - T_ref| / max(T_ref, 0.01) < 0.15
  - dR = |R_fix - R_ref| / max(R_ref, 0.01) < 0.30
  - T_ref < 0.01 이면 비교 스킵 (통과)
- [x] `build_one()` 수정: 버그 주입 전 원본 코드 레퍼런스 실행
- [x] fix_worked: VerificationResult.is_valid 기준으로 결정

## Phase 3 — Tier 3 해상도 수렴 [M] ✅ 구현 완료 (2026-03-09)
- [x] 적용 버그: `resolution_too_low`, `resolution_large_cell`, `courant_too_high`
- [x] `verify_tier3_convergence(fixed_code, bug_name)` 구현
  - code에서 resolution 값 추출 (regex)
  - resolution×2 코드 생성 후 Docker 실행
  - T 변화율 < 10% 이면 수렴 인정
- [x] build_one()에서 Divergence 버그 타입 시 run_tier3=True

## Phase 4 — Tier 4 기하학적 극한값 [S] ✅ 완료 (2026-03-09)
- [x] `PATTERN_PHYSICS_LIMITS` 딕셔너리 구현 (8 패턴: straight/bend/grating/ring/mode/splitter/antenna)
- [x] `verify_tier4(pattern_name, T, R)` 구현 (패턴명 부분 매칭)
- [x] `compute_verification_result()` 통합 함수 구현

## Phase 5 — Tier 5 EigenMode 순도 [L]
- [ ] EigenMode 버그 타입에만 적용
- [ ] 검증 스크립트에 `mp.get_eigenmode_coefficients()` 추가
- [ ] 순도 임계값: 0.85
- ⚠️ 현재: tier5_mode = True (하드코딩, 미구현)

## Skill 패키징 [M] ✅ 완료 (2026-03-09)
- [x] `C:\Users\user\.openclaw\workspace\skills\meep-physics-verifier\` 디렉토리 생성
- [x] `SKILL.md` 작성 (frontmatter + VerificationResult 문서 + Tier 표 + 사용 패턴)
- [x] `scripts/verify_physics.py` — VerificationResult 핵심 로직 + CLI 인터페이스
- [ ] `scripts/reference_runner.py` — 별도 유틸 (verify_physics.py에 통합됨, 불필요)

## 통합 테스트 [S]
- [ ] `python tools/verified_fix_builder.py --bug-type Divergence --limit 10`
- [ ] fix_worked=1 비율 확인 (목표 60%+)
- [ ] T/R 물리검증 건수 확인 (목표 10건+)
- [ ] Docker 환경 실제 실행 확인

## 수용 기준 (Acceptance Criteria)
- VerificationResult.score가 DB fix_description에 포함됨
- Tier 2 레퍼런스 비교가 `adjoint_cylindrical` 패턴에서 정상 동작
- meep-physics-verifier 스킬이 OpenClaw에서 로드됨
- 실행 후 fix_worked=1 비율이 현재 49% → 60% 이상
