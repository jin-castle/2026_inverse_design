# MEEP 시뮬레이션 오류: Timeout

아래 오류가 발생했습니다:

```
Execution exceeded 60 seconds
```

수치적 증상: until_after_sources=1500, resolution=40, 40회 반복 시뮬레이션

동작 증상: PML 반사파 순환으로 수렴 시간 기하급수 증가, 파장 미정의로 물리 스케일 불명확

오류 패턴:
```
Execution exceeded 60 seconds
```

이 문제의 원인과 해결 방법을 알려주세요.