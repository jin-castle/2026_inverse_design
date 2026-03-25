# kb_pipeline.py — 컨텍스트 문서

## 핵심 파일 경로

| 파일 | 경로 | 역할 |
|------|------|------|
| **구현 대상** | `tools/kb_pipeline.py` | 오케스트레이터 |
| **테스트** | `tools/test_kb_pipeline.py` | 검증 스크립트 |
| batch_live_runner | `tools/batch_live_runner.py` | Step 1 실행기 |
| physics_enricher | `tools/physics_enricher.py` | Step 2 분석기 |
| verified_fix_v2 | `tools/verified_fix_v2.py` | Step 3 수정기 |
| live_runner | `tools/live_runner.py` | Docker 실행 |
| error_collector | `tools/error_collector.py` | DB 저장 |
| data_auditor | `tools/data_auditor.py` | audit_report.json |

## 환경

- meep-kb 루트: `C:\Users\user\projects\meep-kb\`
- DB: `C:\Users\user\projects\meep-kb\db\knowledge.db`
- MEEP 컨테이너: `meep-pilot-worker` (meep 1.31.0)
- API: `http://localhost:8765`
- .env 위치: `C:\Users\user\projects\meep-kb\.env`
- ANTHROPIC_API_KEY: `.env`에서 로드

## DB 현황 (2026-03-25)

```
live_runs:     190건
sim_errors_v2: 114건
  fix_worked=1: 11건
  fix_worked=0: 103건
physics_cause 없음: 2건
```

## 기존 함수 시그니처

### batch_live_runner.run_batch()
```python
def run_batch(
    source: str = "examples",      # examples | github_issues | sim_errors_unverified
    limit: int = 20,
    dry_run: bool = False,
    timeout: int = 120,
    skip_checkpoint: bool = False,
) -> dict:
    # 반환: {total, success, error, timeout, mpi_deadlock_risk, blocked, skipped}
```

### verified_fix_v2.run_pipeline()
```python
def run_pipeline(limit: int = 10, dry_run: bool = False, record_id: int = None) -> list:
    # 반환: [{id, status, fix_type, fix_description, message}, ...]
```

## 추가할 함수 시그니처

### physics_enricher.enrich_pending()
```python
def enrich_pending(limit: int = 20, model: str = 'haiku') -> dict:
    # 반환: {total, success, failed}
```

### verified_fix_v2.fix_pending()
```python
def fix_pending(limit: int = 10, skip_markdown: bool = True) -> dict:
    # 반환: {total, fixed, failed, skipped}
    # skip_markdown=True: 마크다운 혼재 코드 자동 skip
```

## 마크다운 혼재 판별 기준

`clean_code()` 함수:
```python
def clean_code(code: str) -> str:
    # 1. ```python ... ``` 블록만 추출
    # 2. In [N]: / Out[N]: 제거
    # 3. ## 헤더 제거
    # 4. 연속 빈줄 정리
    # 최종: import meep 포함 여부 확인
```

마크다운 판별:
- ` ``` ` 존재
- `In [` 존재 (Jupyter 노트북)
- `## ` 존재 (마크다운 헤더)

## 결정사항

1. **subprocess 대신 직접 import** — 성능과 에러 전파를 위해
2. **physics_enricher.py 함수 추가** — 기존 main() 유지, enrich_pending() 추가
3. **verified_fix_v2.py 함수 추가** — 기존 run_pipeline() 유지, fix_pending() 래퍼 추가
4. **clean_code()는 kb_pipeline.py에** — 별도 모듈화 불필요
5. **테스트 3은 실제 Docker 실행** — fix_limit=3으로 소규모만

## 주의사항

- Windows PowerShell: `&&` 미지원 → `;` 사용
- Python 실행: `-X utf8` 필수 (한국어 출력)
- Docker 컨테이너 확인: `docker ps | findstr meep-pilot-worker`
- DB는 `C:\Users\user\projects\meep-kb\db\knowledge.db` (API DB와 동일)
