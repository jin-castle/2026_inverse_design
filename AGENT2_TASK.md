# Agent 2 Task: Failed MEEP 예제 분석 및 재실행

## 목표
meep-kb DB에서 failed/timeout 예제들을 분석하고, 수정 후 재실행하여 결과를 저장한다.

## 환경
- meep-pilot-worker 컨테이너: MEEP 1.31.0, conda env `mp`
- meep-kb 컨테이너: `meep-kb-meep-kb-1` (API: http://172.19.0.2:7860)
- MPI: 최대 4개 시뮬레이션 동시 실행, 각 4코어 → 총 16코어
- 실행 명령: `/opt/conda/envs/mp/bin/mpirun -np 4 /opt/conda/envs/mp/bin/python3 script.py`

## 실패 분류 기준

### Type A: Import/Module 오류
- `ModuleNotFoundError`, `ImportError`
- `__file__` is not defined
- 해결: mock `__file__` 추가, 절대 경로로 수정

### Type B: 문법/API 오류
- `SyntaxError`, `AttributeError`, `TypeError`
- 해결: MEEP 1.31.0 API에 맞게 수정

### Type C: 런타임 timeout (>45초)
- 해결: MPI 4코어로 재실행
- 코드에 `mpirun -np 4` 적용

### Type D: 데이터 의존성 오류
- 외부 파일(.h5, .csv 등) 없음
- 해결: 스킵 또는 자체 데이터 생성

## 작업 순서

### Step 1: 오류 분류
`agent2_failed.json` 읽어서 각 예제의 오류 타입 분류

### Step 2: 수정 스크립트 작성
각 예제마다:
1. 오류 원인 파악
2. 수정 코드 작성 (`/tmp/fixed_{id}.py`)
3. plt.savefig 후킹으로 이미지 캡처
4. stdout 캡처

### Step 3: MPI 병렬 실행 (timeout 예제)
```bash
# 4개 동시 실행 (각 4코어)
for id in timeout_list:
    mpirun -np 4 python3 /tmp/fixed_{id}.py &
    
# 최대 4개 동시 실행으로 제한
```

### Step 4: 결과 제출
meep-kb API로 결과 전송:
```python
POST http://meep-kb-meep-kb-1:7860/api/ingest/result
{
    "example_id": id,
    "images": [base64_png, ...],
    "stdout": "...",
    "status": "success"
}
```

### Step 5: 실행 스크립트
`C:\Users\user\projects\meep-kb\run_failed.py` 작성:
- 오류 분류기
- 자동 수정기
- MPI 실행기 (최대 4개 병렬)
- 결과 제출기

## 중요 사항
- `mpirun --allow-run-as-root -np 4` (root 실행 허용 플래그 필요)
- plt.show() → savefig로 반드시 대체
- 각 스크립트에 `import __main__; __main__.__file__ = "/tmp/fixed_{id}.py"` 추가
- 타임아웃: 스크립트당 최대 120초

## 완료 후 알림
```
openclaw system event --text "Agent2 완료: Failed 예제 재실행 완료. 성공: N개" --mode now
```
