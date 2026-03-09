# MARL → Error DB 컨텍스트
> 환경 정보, 현재 코드 현황, 결정사항

## 현재 코드 위치
```
C:\Users\user\projects\photonics-agent\
  marl_orchestrator.py    ← MARL 메인 (수정 대상)
  marl_analyzer.py        ← 에러 파싱 (재활용)
  physics_validator.py    ← 물리 검증 (재활용)

C:\Users\user\projects\meep-kb\
  api/diagnose_engine.py  ← 진단 엔진 (이미 수정됨)
  api/main.py             ← /api/diagnose 추가됨
  db/knowledge.db         ← errors(596) + sim_errors(255)
  tools/                  ← 새 도구들

Docker: meep-pilot-worker (MEEP 실행 환경)
KB URL: http://localhost:8765
```

## errors 테이블 현황
```
총 596개
  github_issue: 459개 → solution이 영어 토론 원문
  local_log:    133개 → Jin 실제 시뮬레이션 로그
  marl_auto:      2개 → MARL 자동 저장 (너무 적음)
  simulation_log: 2개

solution 컬럼 문제:
  - 원문 그대로라 구조 없음
  - "I found that..." "The issue is..." 형태
  - 코드 스니펫 있는 것: 약 30%
  - 한국어: 0%
```

## sim_errors 테이블 현황
```
총 255개
  github_issue: 242개 → errors 테이블에서 이관
  err_file:      13개 → typee_err_*.txt 파일
  marl_auto:      0개 ← 문제! MARL이 여기에 저장 안 함

컬럼 (기존 스키마):
  run_id, project_id, error_type, error_message,
  meep_version, context, root_cause, fix_applied,
  fix_worked, [추가됨] fix_description, fix_keywords,
  pattern_name, source, original_code, fixed_code
```

## MEEP Docker 환경
```
컨테이너: meep-pilot-worker
실행 명령: docker exec meep-pilot-worker python -c "..."
MEEP 버전: 1.28.0
Python: 3.10
MPI: mpirun -np N (기본 10)
```

## Claude API
```
키: .env 파일 (C:\Users\user\projects\meep-kb\.env)
사용 모델:
  - claude-3-5-haiku-20241022 (배치 처리용, 저렴)
  - claude-sonnet-4 (복잡한 수정용)
비용: Haiku $0.80/M input, $4/M output
```

## 결정사항
1. Solution Structurer: Haiku 모델로 배치 처리 (저렴)
2. ErrorInjector: 별도 스크립트, Docker에서 실행
3. MARL 파이프라인: marl_orchestrator.py Stage 6 수정
4. sim_errors 저장: /api/ingest/sim_error 새 엔드포인트 추가
5. 우선순위: Solution Structurer → MARL 파이프라인 → ErrorInjector 순
