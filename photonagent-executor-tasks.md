# PhotonAgent Executor - Task Checklist

## Phase A: MeepExecutor
- [ ] `docker` Python SDK 설치 확인 (`pip install docker`)
- [ ] `meep_executor.py` 기본 구조 작성
  - [ ] Docker 컨테이너 연결 (meep-kb-meep-kb-1 or 전용 worker)
  - [ ] 임시 파일 생성 (`/tmp/meep_run_{uuid}.py`)
  - [ ] `docker exec` + `mpirun -np 4` 실행
  - [ ] stdout/stderr 캡처
  - [ ] timeout 처리 (default 300s)
  - [ ] 생성 파일 목록 반환
- [ ] 기본 smoke test: 간단한 MEEP 코드 실행 확인

## Phase B: OutputParser
- [ ] `output_parser.py` 작성
  - [ ] Python traceback 감지 (`Traceback (most recent call last)`)
  - [ ] MEEP 에러 패턴 목록:
    - `eig_band=0` (1-indexed error)
    - `nan` or `NaN` in FOM
    - `PML` reflection warning
    - `MPI` slot error
    - `KeyError`, `AttributeError` (API 오류)
  - [ ] FOM 값 추출 (`FOM\s*[=:]\s*([\d.]+)`)
  - [ ] transmission 추출
  - [ ] 성공 판단 (`exit code == 0 AND no traceback`)

## Phase C: AutoDebugger
- [ ] `auto_debugger.py` 작성
  - [ ] meep-kb API 클라이언트 (`httpx` → `POST /api/query`)
  - [ ] 에러 → KB 쿼리 (intent=`error_debug`)
  - [ ] 응답에서 수정 코드 추출
  - [ ] 코드에 패치 적용 (string replace 또는 AST)
  - [ ] 재실행 루프 (max_retries=3)
  - [ ] 각 시도 로깅
- [ ] 통합 테스트: eig_band=0 오류 코드 → 자동 수정 확인

## Phase D: 1D Grating 검증
- [ ] `benchmarks/grating_1d/forward_problem.py`
  - [ ] MEEP 1D grating forward simulation 코드
  - [ ] Diffraction efficiency 계산 (m=0, m=1, m=-1)
  - [ ] 파라미터: period=1μm, duty_cycle=0.5, depth=0.5μm
- [ ] `benchmarks/grating_1d/ground_truth.py`
  - [ ] 해석적 해 또는 RCWA 참조값 (문헌 기반)
- [ ] 자동화 루프 4가지 시나리오 테스트:
  - [ ] 시나리오 1: 정상 코드 → 성공
  - [ ] 시나리오 2: eig_band=0 → AutoDebugger 수정
  - [ ] 시나리오 3: SiO2 mp.inf 미적용 → 수정
  - [ ] 시나리오 4: PML 얇음 → 수정
- [ ] `benchmarks/grating_1d/inverse_design.py`
  - [ ] adjoint로 duty_cycle, depth 최적화
  - [ ] target: m=1 efficiency > 0.8

## Phase E: 논문 준비
- [ ] 성공률 측정 (N=50 쿼리 기준)
- [ ] vs Claude Sonnet / GPT-4o 비교 실험
- [ ] 논문 구조 작성 (ACS Photonics 투고 기준)
