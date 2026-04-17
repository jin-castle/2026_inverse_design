# case_007 - 입력 쿼리

## 사용자 호소
[{'pattern': 'try-except 안에 MPI collective 연산 (sim.run, get_array 등)', 'risk': 'high', 'reason': '일부 rank에서 exception 발생 시 해당 rank는 except로 빠지고 나머지는 collective에서 무한 대기 → deadlock', 'fix': 'try 블록에서 MP. 시뮬레이션 중단/응답 없음 (hanging): 특정 rank만 except 블록으로 이탈하여 MPI 동기화 장벽에서 프로세스 간 교착 상태 발생

## 메타데이터
- error_type: MPIDeadlockRisk
- symptom_numerical: N/A
- symptom_behavioral: 시뮬레이션 중단/응답 없음 (hanging): 특정 rank만 except 블록으로 이탈하여 MPI 동기화 장벽에서 프로세스 간 교착 상태 발생
- symptom_error_pattern: MPI deadlock: 일부 rank에서 exception 발생 후 다른 rank들이 collective operation에서 무한 대기
- source_id: sim_errors_v2.id=9
