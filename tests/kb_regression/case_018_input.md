# MEEP 시뮬레이션 오류: MPIDeadlockRisk

아래 오류가 발생했습니다:

```
[{'pattern': 'try-except 안에 MPI collective 연산 (sim.run, get_array 등)', 'risk': 'high', 'reason': '일부 rank에서 exception 발생 시 해당 rank는 except로 빠지고 나머지는 collective에서 무한 대기 → deadlock', 'fix': 'try 블록에서 MP
```

동작 증상: 시뮬레이션 무한 대기 (프로세스 응답 없음)

오류 패턴:
```
MPI deadlock (일부 rank에서 exception 발생 시 collective 연산에서 무한 대기)
```

이 문제의 원인과 해결 방법을 알려주세요.