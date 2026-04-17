# MEEP 시뮬레이션 오류: TypeError

아래 오류가 발생했습니다:

```
TypeError: Dimensions of C (10, 21) should be one smaller than X(21) and Y(10) while using shading='flat' see help(pcolormesh)
```

수치적 증상: C(10,21) vs X(21)×Y(10)

오류 패턴:
```
Dimensions of C should be one smaller than X and Y while using shading='flat'
```

이 문제의 원인과 해결 방법을 알려주세요.