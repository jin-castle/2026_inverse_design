# PhotonAgent Executor - 자동화 파이프라인 계획

## 목표
MEEP 시뮬레이션 자동 실행 → 에러/결과 분석 → 자동 디버깅 루프 구축
1D grating 문제로 검증 후 논문화

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                  PhotonAgent Executor                    │
│                                                          │
│  query/task                                             │
│      ↓                                                  │
│  [CodeGenerator]  ← meep-kb KB 검색 + Sonnet            │
│      ↓                                                  │
│  [MeepExecutor]   ← Docker 컨테이너에서 MEEP 실행        │
│      ↓                                                  │
│  [OutputParser]   ← stdout/stderr 분석, 결과물 확인      │
│      ├── Error? → [AutoDebugger]                        │
│      │              ↓                                   │
│      │          KB search(error) → code fix → retry     │
│      │              (max 3회)                           │
│      └── Success? → [ResultAnalyzer]                    │
│                      ↓                                  │
│                  FOM, field plots, JSON 결과 반환        │
└─────────────────────────────────────────────────────────┘
```

---

## 컴포넌트 설계

### 1. MeepExecutor
```python
class MeepExecutor:
    def run(self, code: str, timeout: int = 300) -> ExecutionResult:
        # 1. Docker 컨테이너에 임시 파일 생성
        # 2. mpirun -np 4 python /tmp/meep_run_xxx.py 실행
        # 3. stdout/stderr 캡처
        # 4. 생성된 파일 목록 반환 (*.png, *.npy, *.json, *.mp4)
        # 5. exit code 확인
        pass
```

### 2. OutputParser
```python
class OutputParser:
    def parse(self, result: ExecutionResult) -> ParsedResult:
        # 에러 패턴 감지:
        #   - Python traceback
        #   - MEEP specific errors (eig_band, PML, etc.)
        #   - MPI errors
        # 성공 패턴:
        #   - FOM 값 추출 (regex: "FOM.*?(\d+\.\d+)")
        #   - transmission 값
        #   - 생성 파일 확인
        pass
```

### 3. AutoDebugger
```python
class AutoDebugger:
    MAX_RETRIES = 3
    
    def debug_loop(self, code: str, error: str) -> DebugResult:
        for attempt in range(self.MAX_RETRIES):
            # 1. meep-kb에 에러 쿼리
            fix_info = kb_client.query(
                question=error,
                intent="error_debug"
            )
            # 2. 코드에 수정 적용
            fixed_code = apply_fix(code, fix_info)
            # 3. 재실행
            result = executor.run(fixed_code)
            if result.success:
                return DebugResult(success=True, code=fixed_code)
            error = parser.extract_error(result)
        return DebugResult(success=False)
```

### 4. ResultAnalyzer
```python
class ResultAnalyzer:
    def analyze(self, result: ExecutionResult) -> Analysis:
        # FOM 값 시계열
        # 수렴 여부 판단
        # 생성 파일 경로
        # 성능 지표 (transmission, insertion_loss 등)
        pass
```

---

## 1D Grating 검증 계획

### 왜 1D Grating인가?
- 단순하고 well-understood (해석적 해 존재)
- MEEP 예제에 포함됨
- RCWA와 비교 가능 → ground truth 확보
- 역설계도 가능 (duty cycle, depth 최적화)

### Forward Problem (검증)
```
입력: 격자 파라미터 (period, duty_cycle, depth, n_substrate)
출력: diffraction efficiency (order m=0, m=1, m=-1, ...)
검증: RCWA 결과와 비교 (e.g. S4 or rigorous-coupled-wave)
목표: 상대 오차 < 5%
```

### Inverse Design (논문 핵심)
```
목표: m=1 회절 효율 최대화
설계 변수: duty_cycle ∈ [0.1, 0.9], depth ∈ [0.1, 1.0] μm
방법1: Parametric sweep + surrogate fit
방법2: MEEP adjoint (1D grating FOM = |α_m1|²)
```

### 자동화 루프 검증 시나리오
```
시나리오 1: 올바른 파라미터 → 성공 확인
시나리오 2: eig_band=0 오류 코드 → AutoDebugger가 수정
시나리오 3: PML 너무 얇음 → AutoDebugger가 수정
시나리오 4: SiO2 mp.inf 미적용 → AutoDebugger가 수정
```

---

## 구현 단계

### Phase A: MeepExecutor (1-2일)
- [ ] Docker exec API 래퍼
- [ ] 임시 파일 생성/정리
- [ ] timeout 처리
- [ ] 파일 출력 수집

### Phase B: OutputParser (1일)
- [ ] Python traceback 파싱
- [ ] MEEP 에러 패턴 정규식
- [ ] FOM/transmission 값 추출

### Phase C: AutoDebugger (1-2일)
- [ ] meep-kb API 호출 (localhost:8765)
- [ ] 에러 → KB 쿼리 → 코드 패치 적용
- [ ] 재실행 루프 (max 3)

### Phase D: 1D Grating 검증 (2-3일)
- [ ] forward problem MEEP 코드 작성
- [ ] RCWA ground truth 준비 (S4 또는 analytic)
- [ ] AutoDebugger 시나리오 테스트
- [ ] 역설계 루프 테스트

### Phase E: 결과 분석 + 논문 (1주)
- [ ] 성공/실패율 측정
- [ ] vs Claude/GPT 비교 (benchmark)
- [ ] 논문 작성 (ACS Photonics)

---

## 기술 스택
- **MeepExecutor**: `docker` Python SDK (docker-py)
- **meep-kb API**: `httpx` async client (`localhost:8765`)
- **코드 패치**: AST 기반 또는 LLM-based (Sonnet)
- **결과 분석**: numpy, matplotlib, regex

## 파일 구조
```
C:\Users\user\projects\photonics-agent\
├── executor/
│   ├── meep_executor.py
│   ├── output_parser.py
│   └── auto_debugger.py
├── analyzer/
│   └── result_analyzer.py
├── benchmarks/
│   └── grating_1d/
│       ├── forward_problem.py    (MEEP 시뮬레이션)
│       ├── ground_truth.py       (RCWA/analytic)
│       └── inverse_design.py     (adjoint 최적화)
└── tests/
    └── test_debug_scenarios.py
```
