# Verified Fix Builder — Context
Last Updated: 2026-03-09

## SESSION PROGRESS (2026-03-09)

### ✅ COMPLETED
- 계획 문서 작성 (plan.md, context.md, tasks.md)
- 문제 분석: GitHub 텍스트 반환 → 검증된 코드 수정 쌍 필요
- **Phase 1**: error_injector.py BUG_CATALOG 확장 (8종 → 13종)
  - 추가: resolution_large_cell, pml_too_thin_wavelength, until_too_short, missing_reset_meep, monitor_before_source
- **Phase 2**: verified_fix_builder.py 완전 구현 (tools/verified_fix_builder.py, 28KB)
  - BUG_CATALOG 23종 (독자 확장)
  - FixPair dataclass, run_in_docker(), generate_fix_with_llm(), store_via_api() 구현
  - CLI: --dry-run, --limit, --bug-type, --pattern-filter
  - 30건 저장 완료 (fix_worked=1: 16건, fix_worked=0: 14건)
- **Phase 3**: diagnose_engine.py SCORE_BY_SOURCE 추가 + Docker 배포 완료
  - verified_fix: 0.95, marl_auto: 0.92, error_injector: 0.88, github_*: 0.65

### 📊 현재 sim_errors 상태
```
github_issue:     242건
error_injector:   164건
github_structured:151건
verified_fix:      30건  ← 신규 추가
err_file:          13건
marl_auto:          3건
```

### 🟡 남은 작업
- Phase 4: 테스트 스크립트 작성 (_test_verified_fix.py)
- Phase 5: 대량 수집 (--limit 200)

### ⚠️ 알려진 이슈
- 많은 autosim 패턴이 `from common import *` 의존 → Docker에서 ModuleNotFoundError
  - 이 경우 에러는 캡처되지만 T/R 검증 불가 (fix_worked=0으로 저장)
  - 실제 MEEP 실행 가능한 패턴에서는 정상 작동 (adjoint_solver_basics 등)
- eig_center_misaligned/design_variable_shape_mismatch 버그: SyntaxError 발생
  - regex 치환 시 Python 문법 오류 발생 → 개선 필요
- ANTHROPIC_API_KEY: .env 파일에서 로드 필요
  - 실행 시: `$env:ANTHROPIC_API_KEY=(Get-Content .env | ...)`

### 💡 결정사항 업데이트
- fix_keywords: API가 JSON string 요구 → `json.dumps(list)` 직렬화 필수
- PYTHONIOENCODING=utf-8 필요 (Windows cp949 인코딩 이슈)

---

## 핵심 파일 위치

### meep-kb 프로젝트
```
C:\Users\user\projects\meep-kb\
├── api/
│   ├── main.py              ← FastAPI 엔드포인트 (/api/ingest/sim_error)
│   └── diagnose_engine.py   ← search_db() 함수, score 체계
├── db/
│   └── knowledge.db         ← SQLite (sim_errors 테이블)
├── tools/
│   ├── error_injector.py    ← 기존 버그 주입기 (8종, 참조용!)
│   ├── ingest_errors_to_sim.py
│   └── verified_fix_builder.py  ← 구현 목표 파일
└── autosim/
    └── patterns/            ← *.py 패턴 파일 (150+개)
```

### Docker 환경
```
meep-kb API 컨테이너: meep-kb-meep-kb-1 (포트 8765)
MEEP 실행 컨테이너:   meep-pilot-worker
  - 실행: docker exec meep-pilot-worker mpirun --allow-run-as-root -np 2 python /workspace/script.py
  - 파일 전달: docker cp script.py meep-pilot-worker:/workspace/script.py
  - 또는: 임시파일 사용 (error_injector.py 방식 참조)
```

---

## sim_errors 테이블 스키마

```sql
CREATE TABLE sim_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    project_id TEXT,
    error_type TEXT,          -- 'Divergence', 'EigenMode', 'Adjoint', 'MPIError', 'PML'
    error_message TEXT,       -- 실제 traceback
    meep_version TEXT,
    context TEXT,
    root_cause TEXT,          -- 한 줄 원인 설명
    fix_applied TEXT,         -- 적용된 수정 (deprecated, fix_description 사용)
    fix_worked INTEGER,       -- 1=검증됨, 0=미검증
    fix_description TEXT,     -- 상세 설명 + Before/After 코드 포함
    fix_keywords TEXT,        -- JSON 배열
    pattern_name TEXT,        -- 패턴 파일명__버그명
    source TEXT,              -- 'verified_fix', 'error_injector', 'marl_auto', ...
    original_code TEXT,       -- 버그 있는 코드
    fixed_code TEXT,          -- 검증된 수정 코드
    created_at TEXT
);
```

---

## /api/ingest/sim_error 엔드포인트

```
POST http://localhost:8765/api/ingest/sim_error
Content-Type: application/json

{
  "error_type": "Divergence",
  "error_message": "Simulation diverged at t=42.5...",
  "original_code": "...",
  "fixed_code": "...",
  "fix_description": "...",
  "root_cause": "...",
  "context": "...",
  "fix_keywords": ["resolution", "divergence"],
  "pattern_name": "waveguide__resolution_too_low",
  "source": "verified_fix",
  "fix_worked": 1,
  "project_id": "verified_fix_builder",
  "meep_version": ""
}
```

---

## error_injector.py 참조 패턴 (재사용)

```python
# Docker 실행 방식 (error_injector.py에서 가져오기)
def run_in_docker(code: str, timeout=25) -> tuple[int, str]:
    """임시 파일 → Docker cp → mpirun 실행"""
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
        f.write(code.encode())
        tmp_path = f.name
    try:
        script_name = Path(tmp_path).name
        subprocess.run(['docker', 'cp', tmp_path, f'meep-pilot-worker:/workspace/{script_name}'],
                      capture_output=True, timeout=10)
        result = subprocess.run(
            ['docker', 'exec', 'meep-pilot-worker',
             'mpirun', '--allow-run-as-root', '--np', '2',
             'python', f'/workspace/{script_name}'],
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout + result.stderr
    finally:
        os.unlink(tmp_path)
```

---

## 주요 결정사항

1. **LLM 수정 방식**: Claude API (`claude-haiku-4-5`) — 비용 최소화
2. **Docker 타임아웃**: 30초 (빠른 테스트 스크립트만 사용)
3. **저장 방식**: API 경유 (`/api/ingest/sim_error`) — WAL 충돌 방지
4. **fix_description 형식**: Before/After 코드 블록 포함 (```python 형식)
5. **검증 기준**: exit_code=0 AND (T+R < 1.1 OR T>0 OR abs 값 reasonable)
6. **배치 크기**: 50개씩 처리 후 진행 상황 저장

---

## Claude API 설정

```python
import anthropic
client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수

# LLM fix 생성
response = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=1000,
    messages=[{
        "role": "user",
        "content": f"""MEEP Python 코드 수정 전문가입니다.
다음 에러를 수정하세요.

에러: {error_message}
원인: {bug_info['root_cause']}
수정 힌트: {bug_info['fix_description']}

원본 코드:
```python
{buggy_code}
```

수정된 코드만 출력 (설명 없이):"""
    }]
)
```

---

## Quick Resume

1. `plan.md` 읽기 (전체 구조 파악)
2. `tasks.md` 확인 (현재 체크포인트)
3. `tools/error_injector.py` 참조 (Docker 실행 패턴)
4. `tools/verified_fix_builder.py` 구현 시작
5. 테스트: `python tools/verified_fix_builder.py --dry-run --limit 5`
