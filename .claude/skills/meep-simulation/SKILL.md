---
name: meep-simulation
description: >
  MEEP/MPB/legume 시뮬레이션 가이드. FDTD, 밴드 계산, adjoint 최적화,
  에러 해결, 코드 패턴이 필요할 때 자동 활성화. DB: 592건 에러,
  601건 코드 예제, 2497건 문서.
---

# MEEP/MPB/legume 시뮬레이션 가이드

## 역할
광자 결정 시뮬레이션 (FDTD / 밴드 계산 / adjoint 역설계) 전반을 지원한다.

## 이 스킬이 활성화되는 상황
- MEEP / MPB / legume 코드 작성 또는 디버깅
- 시뮬레이션 에러 해결
- 파라미터 설계 또는 최적화 전략 수립

## 상세 레퍼런스 (필요 시만 로드)
- 에러 해결: `resources/common-errors.md`
- API 치트시트: `resources/api-cheatsheet.md`
- 연구자 코드 패턴: `resources/code-patterns.md`

## 빠른 체크리스트

### MEEP 시뮬레이션 전
- [ ] resolution 충분한가? (최소 `pixels_per_λ >= 8`)
- [ ] PML 두께 적절한가? (`dpml >= λ/2`)
- [ ] Source type 맞는가? (GaussianSource vs ContinuousSrc)
- [ ] Flux 위치가 PML 바깥인가?

### MPB 밴드 계산 전
- [ ] k-point 단위 확인 (격자 역공간 or Cartesian 1/a)
- [ ] num_bands 충분한가?
- [ ] TE/TM 편광 구분 (run_te / run_tm)

### legume GME 전
- [ ] gmax 값 충분한가? (기본 3~4)
- [ ] gmode_inds 범위 확인 (0=기본 TE-like)
- [ ] z 좌표 컨벤션: legume z=0은 구조 최상단
- [ ] kpoints 단위: Cartesian 1/a (2π/a 아님!)

## DB 검색 방법
```bash
cd C:\Users\user\projects\meep-kb
python query/search.py "에러 메시지 또는 키워드"
```
