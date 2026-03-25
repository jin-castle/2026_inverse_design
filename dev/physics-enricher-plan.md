# Physics Enricher - Plan

## Executive Summary

`sim_errors_v2` 테이블에 저장된 12개 MEEP 시뮬레이션 에러 레코드에 대해
Claude Haiku LLM을 사용하여 `physics_cause`, `code_cause`, `root_cause_chain` 필드를
자동으로 채워넣는 파이프라인을 구축한다.

사용자가 에러를 쿼리할 때 단순 에러 메시지 뿐 아니라
"왜 이 에러가 물리학적으로 발생했는지"를 이해할 수 있게 된다.

## 현재 상태

- 총 12개 레코드, 모두 physics_cause / code_cause가 비어있음
- 에러 유형 분포:
  - AttributeError (id=1, 11): `sim.run_mode` 없음
  - physics_error T>100% (id=2, 12): 낮은 resolution, EigenMode 문제
  - SyntaxError (id=3): Python 2 → 3 print 문법
  - Harminv/AssertionError (id=4, 10): harminv 수렴 문제
  - FileNotFoundError (id=5): HDF5 파일 경로 없음
  - TypeError MaterialGrid (id=6): API 변경
  - RuntimeError HDF5 (id=7): 파일 오픈 실패
  - AssertionError 수치 (id=8): 결과 불일치
  - MPIDeadlockRisk (id=9): try-except + MPI collective
  - AssertionError (id=10): 수치 검증 실패

## physics_cause vs code_cause 구분 기준

| 필드 | 설명 | 예시 |
|------|------|------|
| physics_cause | 전자기학/광학 법칙 관점에서 왜 이 에러가 발생하는가 | "PML은 복소 좌표 변환으로 감쇠를 추가하므로..." |
| code_cause | 구체적으로 어떤 코드/파라미터 설정이 잘못되었는가 | "sim.run_mode 속성은 MEEP API에 존재하지 않음" |

- `code_error`: physics_cause는 "왜 이 코드 패턴이 문제인가"의 물리/시스템 원리를 설명
- `physics_error`: physics_cause는 직접적인 전자기 물리 법칙 위반을 설명
- `numerical_error`: physics_cause는 수치 안정성 이론(Courant 조건 등)을 설명
- `config_error`: physics_cause는 시스템/파일시스템이 왜 이 설정을 요구하는가를 설명

## root_cause_chain 보강 전략

- 3~5단계 JSON 배열
- Level 1: 겉으로 드러난 증상 (에러 메시지)
- Level 2: 직접 원인 (어떤 코드/파라미터가 트리거)
- Level 3: 근본 원인 (물리/설계 레벨)
- Level 4 (선택): 예방책 또는 더 깊은 원인

## LLM 프롬프트 설계

- 모델: claude-3-5-haiku-20241022 (기본), sonnet 재시도 옵션
- 에러 유형별 PHYSICS_HINTS 주입 (Divergence, EigenMode, PML, MPIError, Adjoint)
- 출력 형식: PHYSICS_CAUSE: / CODE_CAUSE: / ROOT_CAUSE_CHAIN: 파싱
- 파싱 실패 시 "길이 부족" 체크로 sonnet 재시도

## 성공 기준

- 모든 12개 레코드에 physics_cause (≥50자), code_cause (≥20자) 채워짐
- root_cause_chain JSON 파싱 가능
- test_physics_enricher.py ALL PASSED
