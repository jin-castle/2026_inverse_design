# AutoSim Error DB 구축 계획
> MEEP 자동 시뮬레이션 → 오류 축적 → 진단 개선

## 목표

현재 문제: `diagnose_engine.py`가 "DB에서 관련 항목을 찾지 못했습니다" 반환
→ DB에 오류-해결쌍이 부족하기 때문

해결 전략: `autosim/patterns/`에 있는 200+ 패턴을 체계적으로 실행하면서
실패 케이스를 LLM으로 자동 수정 → 오류+해결쌍을 knowledge.db에 축적
→ 데이터가 쌓일수록 진단 품질 향상

---

## 아키텍처

```
[autosim/patterns/*.py] (200+ 패턴 스크립트)
         ↓ docker exec / subprocess
[AutoSimRunner]  ← 실행 + stdout/stderr 캡처
         ↓ 실패시
[ErrorParser]    ← 에러 타입 분류, 키워드 추출
         ↓
[LLMFixer]       ← 원본코드 + 에러 → 수정코드 생성 (Claude API)
         ↓ 수정 후 재실행
[Verifier]       ← 수정코드가 실제로 성공하는지 검증
         ↓ 성공시
[ErrorDBIngestor] ← knowledge.db + ChromaDB에 저장
         ↓
[DiagnoseEngine] ← 사용자 코드 에러 → DB 검색 → 수정 제안
         ↓
[Web UI /diagnose] ← 진단 결과 표시
```

---

## 핵심 설계 결정

### 1. 실행 환경
- **autosim 패턴**: Python subprocess (Windows, meep 없어도 OK — syntax/logic check 위주)
- **실제 MEEP 실행**: Docker exec (`meep-pilot-worker`) 또는 SimServer SSH
- 우선 Phase 1: subprocess로 syntax 에러 / ImportError / 구조적 오류 수집
- Phase 2: Docker/SimServer에서 실제 MEEP 실행 오류 수집

### 2. DB 저장 구조
기존 `knowledge.db`에 새 테이블 추가:
```sql
CREATE TABLE sim_errors (
    id INTEGER PRIMARY KEY,
    error_type TEXT,           -- "ImportError", "MeepError", etc.
    error_msg TEXT,            -- 실제 에러 메시지
    error_context TEXT,        -- traceback + 코드 스니펫
    original_code TEXT,        -- 원본 코드
    fixed_code TEXT,           -- 수정된 코드
    fix_description TEXT,      -- 한국어 수정 설명
    fix_keywords TEXT,         -- 검색용 키워드 (JSON)
    pattern_name TEXT,         -- autosim 패턴명
    verified BOOLEAN,          -- 수정 후 성공 여부
    created_at TIMESTAMP
);
```

ChromaDB 컬렉션 `sim_errors_v1`에도 벡터 임베딩으로 저장
→ 사용자 에러 메시지로 semantic search 가능

### 3. 진단 개선 전략
기존 DiagnoseEngine 검색 파이프라인에 `sim_errors` 테이블 추가:
1. 키워드 매칭 (기존 + sim_errors)
2. 벡터 검색 (기존 + sim_errors_v1 컬렉션)
3. 오류-해결쌍 직접 매칭 (신규 — 완전 동일 에러)
4. LLM 폴백 (기존)

### 4. 데이터 품질 보장
- Verifier: 수정 코드를 실제 실행해서 성공 확인 후만 저장
- verified=True 항목만 진단에 사용
- 카테고리별 커버리지 추적 (어떤 오류 유형이 부족한지)

---

## 구현 우선순위

### Phase 1 (즉시 — Windows 환경)
1. `sim_errors` 테이블 생성 스크립트
2. `AutoSimRunner`: autosim/patterns/ 실행 + 에러 캡처
3. `ErrorDBIngestor`: DB 저장 (ChromaDB + SQLite)
4. `DiagnoseEngine` 개선: sim_errors 검색 포함

### Phase 2 (SimServer 연동)
5. `LLMFixer`: Claude API로 자동 수정 생성
6. `Verifier`: Docker/SimServer에서 수정 코드 검증
7. 자동화 스케줄러: 주기적으로 새 패턴 실행

### Phase 3 (품질 향상)
8. 커버리지 대시보드: 에러 타입별 수집 현황
9. 사용자 피드백 루프: "이 해결책이 도움이 됐나요?" → DB 개선
10. 유사 에러 클러스터링: 같은 근본 원인 그룹화

---

## 성공 지표
- sim_errors 테이블 200+ 레코드 (verified=True)
- 진단 시 "DB에서 찾지 못함" 응답 비율 50% 이하로 감소
- 에러 카테고리별 최소 10개 이상 해결책 보유
