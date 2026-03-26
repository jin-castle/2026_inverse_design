# migration-v2-context.md — 마이그레이션 환경 컨텍스트

## 핵심 파일 경로
| 역할 | 경로 |
|------|------|
| 데이터베이스 | C:\Users\user\projects\meep-kb\db\knowledge.db |
| 마이그레이션 스크립트 | C:\Users\user\projects\meep-kb\tools\migrate_to_v2.py |
| 테스트 스크립트 | C:\Users\user\projects\meep-kb\tools\test_migrate_v2.py |
| Physics Enricher | C:\Users\user\projects\meep-kb\tools\physics_enricher.py |
| 점수 체계 | C:\Users\user\projects\meep-kb\api\diagnose_engine.py |
| 환경변수 | C:\Users\user\projects\meep-kb\.env |

## 테이블 스키마

### sim_errors (소스)
컬럼: id, run_id, project_id, error_type, error_message, meep_version,
      context, root_cause, fix_applied, fix_worked, created_at,
      fix_description, fix_keywords, pattern_name, source, original_code,
      fixed_code, run_time_sec, code_length, mpi_np

### sim_errors_v2 (대상)
5계층 구조:
- Layer 1: run_mode, run_stage, iteration, mpi_np
- Layer 2: device_type, wavelength_um, resolution, pml_thickness, cell_size, dim, uses_adjoint, uses_symmetry
- Layer 3: error_class, error_type, error_message, traceback_full, symptom
- Layer 4: trigger_code, trigger_line, physics_cause, code_cause, root_cause_chain
- Layer 5: fix_type, fix_description, original_code, fixed_code, code_diff, fix_worked
- Meta: source, meep_version, run_time_sec, code_length, code_hash, created_at, original_code_raw

추가 컬럼: original_code_raw (ALTER TABLE로 추가된 컬럼)

## 현재 DB 상태 (2026-03-25 기준)
- sim_errors_v2 총 114건
- fix_worked=1: 15건
- code_hash 인덱스 존재 (비-UNIQUE → 중복 방지는 WHERE NOT EXISTS로 구현)

## 환경
- Python: 3.x (Windows)
- ANTHROPIC_API_KEY: .env에서 로드
- Docker: 불필요 (DB 직접 접근)

## 결정사항
1. code_hash UNIQUE 제약 없음 → INSERT 전 EXISTS 체크로 중복 방지
2. physics_cause는 마이그레이션 후 별도로 physics_enricher 호출
3. original_code 없는 레코드도 마이그레이션 (code_hash = SHA256(""))
4. fixed_code 없는 레코드는 code_diff = ""

## SCORE_BY_SOURCE (diagnose_engine.py)
```python
"live_run":          0.98,
"verified_fix":      0.95,
"marl_auto":         0.92,
"error_injector":    0.88,  # → 0.93으로 상향 예정
"github_structured": 0.72,
"github_issue":      0.65,
```

## SESSION PROGRESS
- [2026-03-25] 마이그레이션 계획 수립, plan/context/tasks 문서 작성
- [2026-03-25] migrate_to_v2.py 구현 및 실행 예정
