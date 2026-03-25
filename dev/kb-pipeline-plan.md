# kb_pipeline.py — 자동 오케스트레이터 구현 계획

## Executive Summary

`kb_pipeline.py`는 meep-kb의 전체 데이터 처리 파이프라인을 하나의 파일로 통합하는 오케스트레이터다.
새 데이터가 들어오면 자동으로 `batch_live_runner → physics_enricher → verified_fix_v2` 순서로 실행되며,
각 단계를 선택적으로 실행하거나 드라이런으로 계획만 확인할 수 있다.

## 현재 상태

| 도구 | 상태 | 문제점 |
|------|------|--------|
| batch_live_runner.py | ✅ 완성 | `run_batch()` 함수 존재, 직접 호출 가능 |
| physics_enricher.py | ⚠️ CLI 전용 | `enrich_pending()` 함수 없음 → 추가 필요 |
| verified_fix_v2.py | ✅ 거의 완성 | `run_pipeline()` 함수 존재, `fix_pending()` 래퍼 추가 필요 |
| error_collector.py | ✅ 완성 | `collect_v2()`, `migrate_db()` 사용 가능 |

**DB 현황** (2026-03-25 기준):
- live_runs: 190건
- sim_errors_v2: 114건 (fix_worked=1: 11건, fix_worked=0: 103건)
- physics_cause 없음: 2건

## 목표 상태

```
[입력 소스] examples | github_issues | sim_errors_unverified
        ↓
[Step 1] batch_live_runner.run_batch() → live_runs + sim_errors_v2 저장
        ↓
[Step 2] physics_enricher.enrich_pending() → physics_cause/code_cause 채우기
        ↓
[Step 3] verified_fix_v2.fix_pending() → LLM 수정 → Docker 검증
        ↓
[리포트] 각 단계별 통계 출력 + DB 현황
```

## 파이프라인 흐름도

```
kb_pipeline.py --source examples --limit 20 --steps run,enrich,fix
                    │
         ┌──────────┴──────────┐
         │   --steps 파싱      │
         │   run,enrich,fix    │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │     Step: run       │  (선택적)
         │  run_batch()        │
         │  → live_runs 저장   │
         │  → sim_errors_v2    │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │    Step: enrich     │  (선택적)
         │  enrich_pending()   │
         │  → physics_cause    │
         │  → code_cause 채움  │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │     Step: fix       │  (선택적)
         │  fix_pending()      │
         │  → LLM fix 생성     │
         │  → Docker 검증      │
         │  → fix_worked=1     │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │   리포트 출력        │
         │   + DB 현황          │
         └─────────────────────┘
```

## Phase별 구현 계획

### Phase 1: 기존 파일 리팩터링

**1a. physics_enricher.py 수정**
- `enrich_pending(limit=20, model='haiku') -> dict` 함수 추가
- 반환값: `{total, success, failed}`
- 기존 `main()` 로직을 재사용

**1b. verified_fix_v2.py 수정**  
- `fix_pending(limit=10, skip_markdown=True) -> dict` 함수 추가
- 반환값: `{total, fixed, failed, skipped}`
- 마크다운 혼재 코드 자동 skip 포함

### Phase 2: 마크다운 클렌저 구현

`kb_pipeline.py` 또는 `error_collector.py`에 `clean_code()` 추가:
- ` ```python ... ``` ` 블록 추출
- `In [N]:` / `Out[N]:` 제거
- `## 헤더` 제거
- 연속 빈줄 정리
- `import meep` 포함 여부 최종 확인

### Phase 3: kb_pipeline.py 구현

메인 오케스트레이터 작성:
- CLI argparse 구성
- 단계별 실행 로직
- 드라이런 지원
- 리포트 출력

### Phase 4: 테스트 스크립트 작성

`tools/test_kb_pipeline.py` 5개 테스트:
1. `--dry-run` → 계획 출력 확인
2. `--steps enrich --dry-run` → 대상 목록 출력
3. `--steps fix --fix-limit 3` → fix_worked=1 증가
4. `--steps run,enrich --source examples --limit 3` → 전체 파이프라인
5. DB 현황 정상 출력

## 성공 기준

- [ ] `python -X utf8 tools/kb_pipeline.py --dry-run` → 에러 없이 계획 출력
- [ ] `python -X utf8 tools/kb_pipeline.py --steps enrich --dry-run` → 목록 출력
- [ ] `python -X utf8 tools/test_kb_pipeline.py` → ALL PASSED
- [ ] git commit 성공

## 리스크

| 리스크 | 대응 |
|--------|------|
| physics_enricher 함수 추출 시 기존 CLI 깨짐 | 함수 추가만, 기존 main() 유지 |
| 마크다운 클렌저 정규식 오류 | 유닛 테스트로 검증 |
| Docker 컨테이너 미실행 | 테스트 3은 실제 실행 필요, 컨테이너 확인 후 실행 |
