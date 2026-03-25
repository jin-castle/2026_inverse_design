# GitHub Issues 전처리 강화 - Context

## 핵심 파일 경로
- DB: `C:\Users\user\projects\meep-kb\db\knowledge.db`
- 구현: `C:\Users\user\projects\meep-kb\tools\github_preprocessor.py`
- 구현: `C:\Users\user\projects\meep-kb\tools\ingest_research_notes.py`
- 테스트: `C:\Users\user\projects\meep-kb\tools\test_github_preprocess.py`
- 출력: `C:\Users\user\projects\meep-kb\tools\runnable_issues.json`
- 소스: `C:\Users\user\.openclaw\workspace\memory\meep-errors.md`

## DB 스키마

### sim_errors 테이블 (393건 대상)
```sql
id INTEGER, run_id TEXT, project_id TEXT, error_type TEXT,
error_message TEXT, meep_version TEXT, context TEXT,
root_cause TEXT, fix_applied TEXT, fix_worked INTEGER,
created_at DATETIME, fix_description TEXT, fix_keywords TEXT,
pattern_name TEXT, source TEXT, original_code TEXT, fixed_code TEXT,
run_time_sec REAL, code_length INT, mpi_np INT
```
- source: 'github_issue'(242), 'github_structured'(151)
- **original_code**: 모두 NULL → 코드는 context/root_cause/fix_applied에 있음
- context: 마크다운 형식, 코드 블록 포함

### sim_errors_v2 테이블 (현재 114건)
```sql
id INTEGER, run_mode TEXT, run_stage TEXT, iteration INT,
mpi_np INT, device_type TEXT, wavelength_um REAL, resolution INT,
pml_thickness REAL, cell_size TEXT, dim INT,
uses_adjoint INT, uses_symmetry INT,
error_class TEXT, error_type TEXT, error_message TEXT,
traceback_full TEXT, symptom TEXT, trigger_code TEXT, trigger_line TEXT,
physics_cause TEXT, code_cause TEXT, root_cause_chain TEXT,
fix_type TEXT, fix_description TEXT,
original_code TEXT, fixed_code TEXT, code_diff TEXT,
fix_worked INT, source TEXT, meep_version TEXT,
run_time_sec REAL, code_length INT, code_hash TEXT,
created_at TIMESTAMP, original_code_raw TEXT
```

## 코드 블록 분포 (사전 분석)
- context에 ```python: 17건
- context에 ``` (any): 124건
- root_cause에 ```: 56건
- fix_applied에 ```: 27건
- 합산 대상: 모든 필드 통합하면 약 150~200건 코드 후보

## 환경
- Python: Windows (PowerShell 사용, `&&` 불가, 세미콜론 사용)
- 실행: `python C:\path\to\script.py`
- Docker: 불필요 (코드 파싱만)

## 결정사항
1. original_code가 NULL이므로 context + root_cause + fix_applied 필드에서 코드 추출
2. 여러 필드에서 코드 발견 시 가장 긴 것 선택 (best_code)
3. 코드 블록 우선순위: ```python > ```(meep 포함) > ``` > 4-space indent
4. score 70 이상 → runnable, 40~69 → patchable
5. 각 sim_error_id당 최대 1개 코드 (best)

## meep-errors.md 패턴 (8개)
1. EigenMode: eig_band=0 → 에너지 비보존
2. Reflection: SiO2 substrate PML 전 끝남
3. FOM NaN: Gradient 발산 / MaterialGrid instability / Source 위치
4. MPI: "not enough slots" / "Address already in use"
5. 3D Mode Profile: z 좌표계 미반영
6. Decay: stop_when_fields_decayed 임계값 너무 낮음
7. Resolution: Air cladding 구조 res 수렴 문제
8. 3D 효율 급락: 2D 최적화 neff substrate 미포함

## 주의사항
- PowerShell에서 Python 실행: `python script.py` (cd 없이 절대 경로)
- `&&` 연산자 사용 불가 → 세미콜론(`;`) 또는 별도 호출
- 한국어 context 필드: 인코딩 UTF-8 (이미 정상)
