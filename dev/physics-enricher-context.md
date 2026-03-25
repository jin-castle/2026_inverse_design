# Physics Enricher - Context

## 핵심 파일 경로

| 파일 | 설명 |
|------|------|
| `C:\Users\user\projects\meep-kb\tools\physics_enricher.py` | 메인 구현 |
| `C:\Users\user\projects\meep-kb\tools\test_physics_enricher.py` | 검증 스크립트 |
| `C:\Users\user\projects\meep-kb\db\knowledge.db` | SQLite DB |
| `C:\Users\user\projects\meep-kb\.env` | ANTHROPIC_API_KEY 보관 |

## 환경

- Python 3.x, Windows (PowerShell)
- anthropic 패키지 사용 (pip install anthropic)
- docker 없음, 직접 API 호출
- 실행: `python -X utf8 tools/physics_enricher.py`

## DB 스키마 (관련 컬럼)

```sql
sim_errors_v2:
  - id, error_class, error_type, error_message, traceback_full
  - symptom, trigger_code, run_mode, device_type
  - resolution, pml_thickness, wavelength_um, dim, uses_adjoint
  - original_code
  - physics_cause TEXT   -- 채울 대상
  - code_cause TEXT      -- 채울 대상  
  - root_cause_chain TEXT -- 채울 대상 (JSON)
```

## 현재 데이터 현황

- 총 12개 레코드, 모두 physics_cause/code_cause = NULL
- 에러 유형: AttributeError, physics_error(T>100%), SyntaxError, Harminv, 
             FileNotFoundError, TypeError(MaterialGrid), RuntimeError(HDF5),
             AssertionError, MPIDeadlockRisk

## API 설정

```python
from dotenv import load_dotenv
load_dotenv('C:/Users/user/projects/meep-kb/.env')
import os
api_key = os.environ.get('ANTHROPIC_API_KEY')
```

## 제약 조건

- 한국어로 설명 작성 (프롬프트에 명시)
- physics_cause: 2~4문장, 물리 수식 포함 권장, ≥50자
- code_cause: 1~2문장, 구체적 수치, ≥20자
- root_cause_chain: JSON 배열, 3~5단계

## SESSION PROGRESS

- [2026-03-25] 계획 수립, DB 상태 확인 완료
- [2026-03-25] physics_enricher.py 구현 완료
- [2026-03-25] test_physics_enricher.py 검증 완료
- [2026-03-25] git commit 완료
