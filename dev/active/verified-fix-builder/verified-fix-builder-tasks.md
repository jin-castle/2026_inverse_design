# Verified Fix Builder — Task Checklist
Last Updated: 2026-03-09

---

## Phase 1: Bug Catalog 확장 ✅ COMPLETED (2026-03-09)
- [x] `error_injector.py` BUG_CATALOG에 Divergence 계열 추가 (5종)
  - [x] resolution_large_cell (대형 셀에서 resolution=5)
  - [x] pml_too_thin_wavelength (파장 대비 PML=0.1)
  - [x] until_too_short (until=1, 조기 종료)
  - Acceptance: 각 버그가 Docker에서 실제 에러 발생 ✓
- [x] EigenMode 계열 추가 (2종)
  - [x] eig_center_misaligned
  - [x] eig_band_wrong
  - Acceptance: T>1.0 또는 EigenMode 에러 발생 ✓
- [x] Adjoint 계열 추가 (2종)
  - [x] missing_reset_meep
  - [x] design_variable_shape_mismatch
  - Acceptance: RuntimeError 또는 ValueError 발생 ✓
- [x] Normalization 계열 추가 (2종)
  - [x] missing_norm_run
  - [x] monitor_in_pml
  - [x] monitor_before_source
- [x] MPI 계열 추가 (1종)
  - [x] np_exceeds_chunks
- [x] 추가 버그 (3종): courant_too_high, source_in_pml, wrong_decay_field

**Phase 1 완료**: error_injector.py 8종 → 13종 확장, verified_fix_builder.py에 23종 BUG_CATALOG

---

## Phase 2: verified_fix_builder.py 구현 ✅ COMPLETED (2026-03-09)

### 2.1 기본 구조
- [x] 파일 생성: `tools/verified_fix_builder.py` (28KB)
- [x] `FixPair` dataclass 정의
- [x] `run_in_docker()` 함수 (mpirun --np 2 사용)
- [x] `parse_tr_values()` 함수 (T/R 추출)

### 2.2 핵심 로직
- [x] `inject_bug()` 함수 (error_injector.py 재사용)
- [x] `generate_fix_with_llm()` 함수 (Claude haiku-4-5)
- [x] `is_physical()` 함수 (T/R 검증)
- [x] `generate_fix_description()` 함수 (Before/After 코드 포함, 한국어)

### 2.3 저장 로직
- [x] `store_via_api()` 함수 (/api/ingest/sim_error POST)
  - fix_keywords를 JSON string으로 직렬화 (API 요구사항)
- [x] `VerifiedFixBuilder.build_one()` 전체 파이프라인
- [x] `VerifiedFixBuilder.run_batch()` 배치 실행

### 2.4 CLI
- [x] `--dry-run` 옵션 (실제 Docker 실행 없이 테스트)
- [x] `--limit N` 옵션 (N건만 처리)
- [x] `--pattern-filter` 옵션 (특정 패턴만)
- [x] `--bug-type` 옵션 (특정 버그만)
- [x] 진행 상황 출력

**Phase 2 결과**:
```
python tools/verified_fix_builder.py --dry-run --limit 3   ✅ 3건 dry-run OK
python tools/verified_fix_builder.py --limit 30            ✅ 30건 실제 저장 (16건 fix_worked=1)
sim_errors verified_fix: 30건 저장됨
```

---

## Phase 3: diagnose_engine.py score 개선 ✅ COMPLETED (2026-03-09)
- [x] `SCORE_BY_SOURCE` 딕셔너리 추가 (search_db() 내부)
  ```python
  SCORE_BY_SOURCE = {
      "verified_fix": 0.95,
      "marl_auto": 0.92,
      "error_injector": 0.88,
      "github_structured": 0.72,
      "github_issue": 0.65,
      "kb_fts": 0.65,
      "err_file": 0.60,
  }
  ```
- [x] `search_db()` sim_errors 섹션에서 source별 score 적용
- [x] Docker 배포: `docker cp api/diagnose_engine.py meep-kb-meep-kb-1:/app/api/diagnose_engine.py`
- [x] `docker restart meep-kb-meep-kb-1` 완료

**Phase 3 완료**: verified_fix(0.95) > marl_auto(0.92) > error_injector(0.88) > github(0.65) 순서 적용

---

## Phase 4: 검증 테스트 ⏳ NOT STARTED
- [ ] 테스트 스크립트 작성: `tools/_test_verified_fix.py`
- [ ] 테스트 케이스 1: `resolution=20 + diverge` → Divergence 카드
- [ ] 테스트 케이스 2: `eig_band=0 + T>1` → EigenMode 카드
- [ ] 테스트 케이스 3: `reset_meep 없음` → Adjoint 카드
- [ ] 브라우저 E2E 확인 (스크린샷)

**Phase 4 완료 기준**: 3개 테스트 모두 verified_fix 소스 최상위 반환

---

## Phase 5: 대량 수집 실행 ⏳ NOT STARTED
- [ ] `python tools/verified_fix_builder.py --limit 200` 실행
- [ ] sim_errors verified_fix 소스 100건 이상 확인
- [ ] Docker DB sync (API 경유이므로 자동)

**Phase 5 완료 기준**: sim_errors verified_fix 100건+

---

## 빠른 검증 명령어

```bash
# 현재 sim_errors 상태
python -c "import sqlite3; db=sqlite3.connect('db/knowledge.db'); print(db.execute('SELECT source, COUNT(*) FROM sim_errors GROUP BY source').fetchall())"

# verified_fix_builder 테스트
python tools/verified_fix_builder.py --dry-run --limit 5

# 진단 API 테스트
python tools/_test_verified_fix.py
```
