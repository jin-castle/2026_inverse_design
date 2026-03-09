# MARL → Error DB 파이프라인 계획
> Simulator → Error → DB → 진단 전체 아키텍처

## 현황 진단

### 현재 흐름 (문제 있는 상태)
```
MARL 실행
  → 에러 발생 → /api/ingest/error → errors 테이블 (마지막 2개만)
  → 자동 수정 → 결과가 sim_errors에 안 들어감

GitHub Issues 596개
  → solution = 영어 토론 원문 (구조 없음)
  → diagnose_engine이 검색해도 쓸모 없는 텍스트 반환
```

### 목표 흐름 (구현 후)
```
MARL 실행
  → 에러 발생
  → Debugger (meep-kb 조회 + LLM 수정)
  → 수정 성공 시 → sim_errors 저장 (verified=1, 원본코드+수정코드+설명)
  → /api/diagnose가 즉시 활용 가능

GitHub Issues 596개
  → Solution Structurer (Claude Haiku 배치)
  → "원인 / 해결방법 / 수정코드" 구조로 변환
  → errors 테이블 업데이트 + sim_errors 삽입

autosim patterns 127개
  → ErrorInjector: 의도적 버그 삽입 (eig_band=0, PML 없음 등)
  → Docker MEEP 실행 → 실제 traceback 캡처
  → LLM 수정 → 검증 → sim_errors 저장
```

---

## 목표 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA SOURCES (입력)                          │
├──────────────────┬─────────────────┬───────────────────────────┤
│ autosim/patterns │ GitHub Issues   │ MARL 실제 시뮬레이션       │
│ (127개 정상 코드)│ (596개 issues) │ (PROJ-001, PROJ-002...)   │
│      ↓           │      ↓          │          ↓                │
│ ErrorInjector    │SolutionStruct.  │ MARLOrchestrator          │
│ 의도적 버그 삽입  │ LLM 구조화      │ Stage 5 Debugger          │
└──────────────────┴─────────────────┴───────────────────────────┘
         ↓                  ↓                    ↓
┌─────────────────────────────────────────────────────────────────┐
│                    PROCESSING (처리)                            │
│                                                                 │
│  Docker MEEP 실행 → traceback 캡처                             │
│  LLM (Claude Haiku) → 수정 코드 생성                           │
│  Verifier → 수정 코드 재실행 → 성공 확인                        │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    sim_errors DB (저장)                         │
│                                                                 │
│  error_type    | error_message | context                       │
│  original_code | fixed_code    | fix_description               │
│  fix_worked=1  | source        | created_at                    │
│                                                                 │
│  목표: 1,000개 verified 레코드                                  │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    /api/diagnose (출력)                         │
│                                                                 │
│  사용자 에러 입력                                               │
│  → FTS 검색 + 벡터 검색                                        │
│  → sim_errors에서 매칭된 verified 해결책 반환                   │
│  → "DB 기반 답변" 표시                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4개 서브시스템 설계

### 1. Solution Structurer (즉시 가능, 가장 효과 큼)
```
목적: GitHub Issues 영어 토론 → 구조화된 한국어 해결책
입력: errors 테이블 (solution = 영어 토론 텍스트)
출력: sim_errors 테이블 (원인 + 해결방법 + 코드)

처리:
  FOR each error in errors WHERE solution_structured IS NULL:
    prompt = "MEEP 에러 토론에서 핵심 해결책 추출해줘"
    response = Claude Haiku API
    → 원인 (2문장)
    → 해결방법 (3~5 bullet)
    → 수정 코드 스니펫 (있으면)
    → sim_errors INSERT

비용: $0.25/M tokens → 596개 처리 약 $0.5~1 예상
시간: 배치 실행 약 30분
```

### 2. ErrorInjector (Docker 필요, 데이터 품질 최고)
```
목적: 정상 코드에 의도적 버그 삽입 → 실제 MEEP traceback 수집
입력: autosim/patterns/*.py (127개)
출력: (original_code, error_traceback, fixed_code) 쌍

주입 버그 카탈로그:
  - eig_band=0 (1로 고쳐야 함)
  - PML 없이 시뮬레이션
  - resolution=0 또는 음수
  - cell_size와 source 위치 불일치
  - EigenModeSource eig_parity 잘못된 조합
  - MaterialGrid 차원 오류
  - MPI split_chunks 불균형
  - adjoint reset_meep() 버그 (pmp130 환경)

각 패턴 × 관련 버그 = 최대 500개 에러 쌍 생성 가능
```

### 3. MARL → sim_errors 파이프라인 (Stage 6 강화)
```
현재: _store_error_to_kb() → /api/ingest/error → errors 테이블만
개선: 수정 성공 시 → sim_errors 직접 저장 (원본코드 + 수정코드 포함)

수정할 파일: photonics-agent/marl_orchestrator.py
  - _stage6_kb_ingest() 함수
  - 성공 시 sim_errors에도 POST
  - 포함 정보: error_msg, original_code, fixed_code, fix_description
```

### 4. Continuous Runner (자동화)
```
목적: SimServer에서 MARL 배치 실행 → 자동 DB 축적
대상: PROJ-001 (PhC-CFBS), PROJ-002 (Mode Converter) 시뮬레이션 변형들
주기: 시뮬레이션 완료 시마다 자동 실행
방법: 
  - nohup python marl_batch_runner.py > marl.log 2>&1 &
  - 결과 meep-kb에 POST
  - ngrok으로 외부 접근 가능
```

---

## 기대 결과

| 서브시스템 | 추가 데이터 | 소요 시간 | 비용 |
|-----------|-----------|---------|------|
| Solution Structurer | +300~400 structured | 30분 | ~$1 |
| ErrorInjector | +200~400 verified | 2~4시간 | 전기세만 |
| MARL 파이프라인 | 시뮬레이션마다 +1~5 | 자동 | 0 |
| **합계** | **1,000개+ 도달** | **당일** | ~$1 |
