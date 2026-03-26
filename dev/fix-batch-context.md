# fix-batch-context.md — 환경 및 컨텍스트 문서

## 핵심 파일 경로
| 파일 | 경로 | 설명 |
|------|------|------|
| DB | `db/knowledge.db` | SQLite, sim_errors_v2 테이블 |
| verified_fix_v2 | `tools/verified_fix_v2.py` | LLM 수정 + Docker 검증 파이프라인 |
| run_fix_batch_safe | `tools/run_fix_batch_safe.py` | 8건 즉시 실행 배치 (신규) |
| code_cleaner | `tools/code_cleaner.py` | 마크다운 혼재 코드 정제 (신규) |
| test_fix_batch | `tools/test_fix_batch.py` | 배치 검증 테스트 (신규) |

## 환경
- meep-kb 루트: `C:\Users\user\projects\meep-kb\`
- Python: `python -X utf8` (인코딩 명시 필수)
- MEEP 컨테이너: `meep-pilot-worker` (실행 중)
- ANTHROPIC_API_KEY: `.env`에서 자동 로드
- Shell: PowerShell (`;` 사용, `&&` 불가)

## DB 스키마 (sim_errors_v2 관련 컬럼)
```
id, run_mode, run_stage, error_class, error_type, error_message,
traceback_full, symptom, trigger_code, trigger_line,
physics_cause, code_cause, root_cause_chain,
fix_type, fix_description,
original_code, fixed_code, code_diff,
fix_worked (0=미처리, 1=성공),
source, meep_version, run_time_sec, code_length, code_hash,
created_at
```
- `original_code_raw` 컬럼: Phase 2에서 ALTER TABLE로 추가

## 마크다운 혼재 패턴 분석
- `# [MD]` 주석으로 시작하는 코드 31건
  - 마크다운 설명 텍스트가 `# [MD]` 로 구분되어 삽입됨
  - 실제 Python 코드는 일반 코드블록 또는 `import meep` 이후
- 기타 마크다운: ` ``` `, `##`, `**`, `---` 등
- Jupyter 패턴: `In [N]:`, `Out[N]:`

## verified_fix_v2.py 동작
1. DB에서 레코드 조회 (--id 옵션)
2. original_code 재실행 → 에러 재현 확인
3. LLM(claude-sonnet-4-6)에 물리 컨텍스트 포함 수정 요청
4. fixed_code Docker 재실행 검증
5. 성공 시 fix_worked=1, fixed_code, code_diff 업데이트

## # [MD] 코드 정제 전략
```
# [MD]\n# 제목\n\n# [MD]\n설명 텍스트...
```
- `# [MD]` 섹션 전체를 제거
- 남은 순수 Python 코드만 추출
- `import meep` 포함 여부 확인 (없으면 None 반환)
- `mp.Simulation` 또는 `meep.Simulation` 포함 여부 확인

## 결정사항
- subprocess: `capture_output=False` (터미널 직접 출력, 버퍼링 방지)
- timeout: 180s (verified_fix_v2 내부 blocking 방지)
- 배치 간격: `time.sleep(2)` (API rate limit 방지)
- 원본 보존: `original_code_raw` 컬럼에 원본, `original_code`에 정제본

## SESSION PROGRESS
- [2026-03-25] Phase 1~5 계획 수립
- [2026-03-25] run_fix_batch_safe.py 작성 중
