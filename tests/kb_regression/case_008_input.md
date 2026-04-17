# MEEP 시뮬레이션 문제 문의

아래 오류가 발생했습니다:

```
AssertionError: 86.90826609300862 != 86.90861548199773 within 7 places (0.00034938898910752414 difference)
```

수치적 증상: flux difference ~3.5×10⁻⁴, assertAlmostEqual places=7 (tolerance 5×10⁻⁸)

동작 증상: 청크 분할 방식에 따라 동일 물리량의 수치가 달라짐

오류 패턴:
```
AssertionError: * != * within 7 places
```

이 문제의 원인과 해결 방법을 알려주세요.