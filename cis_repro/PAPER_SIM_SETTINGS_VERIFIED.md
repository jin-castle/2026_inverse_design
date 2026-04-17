# CIS 논문별 시뮬레이션 설정 — PDF 검토 후 정확한 값
> 작성: 2026-04-11 | PDF 직접 분석 + 재현 코드 비교

---

## 논문별 핵심 설정 비교표

| 항목 | Single2022 | Pixel2022 | Freeform | Multilayer | SMA2023 | Simplest | RGBIR2025 |
|------|-----------|----------|---------|-----------|---------|---------|---------|
| **도구** | FDTD | FDTD | FDTD | RCWA+FDTD | FDTD | FDTD | FDTD |
| **수퍼셀** | 1.6μm | 2μm | 1.2μm | 1.2μm | 2.24μm | 1.6μm | 2.2μm |
| **픽셀** | 0.8μm | 1μm | 0.6μm | 0.6μm | 1.12μm | 0.8μm | 1.1μm |
| **재료** | TiO₂ | Si₃N₄ | SiN | Si₃N₄ | Si₃N₄ | Nb₂O₅ | TiO₂ |
| **굴절률** | n=2.1~2.4 | 미명시 | ~1.92 | 미명시 | 미명시 | n=2.32 | 미명시 |
| **높이** | 300nm | 600nm | 600nm | 600nm×2 | 998nm | 512nm | 600nm |
| **FL** | 2μm | ? | 0.6μm | 0.6/1.2μm | 4μm | 1.08μm | 4μm |
| **focal 재료** | Air | SiO₂ | Air | Air | SiO₂? | Air | SiO₂ |
| **기판** | SiO₂ | quartz | glass | SiO₂ | SiO₂ | silica | SiO₂ |
| **cover glass** | ✅ SiO₂ | ✅ quartz | ✅ glass | ? | ❌ 없음 | ✅ SiO₂ | ? |
| **입사 방향** | 위→아래 | 정상 | 기판통과 | 위→아래 | 위→아래 | 기판통과? | 위→아래 |
| **편광** | Ex+Ey | 비편광 | Ex(단일) | 미명시 | 비편광 | Ex+Ey | Ex(0°) |
| **경계 XY** | Periodic | Periodic | ? | Periodic | Periodic | Periodic | Periodic |
| **경계 Z** | PML | PML | ? | ? | ? | absorb | PML |
| **stop_decay** | 1e-6 | 1e-8 | 1e-4 | 1e-3 | 1e-8 | 1e-6 | 1e-8 |
| **효율 분모** | 수퍼셀 입사 | 유닛셀 입사 | 수퍼셀 입사 | 초점면 전체! | 수퍼셀 입사 | 픽셀 ref | 유닛셀 입사 |
| **R 피크 효율** | 58.3% | ~58% | ~60% | ~51% | 64.3% | 58.9% | 49.7% |
| **G 피크 효율** | 52.6% | ~59% | ~57% | ~82% | 70.4% | 57.9% | 55.4% |
| **B 피크 효율** | 69.6% | ~49% | ~65% | ~69% | 54.6% | 48% | 43.2% |

---

## 재현 코드 vs 논문 — 실제 차이 분석

### ❶ Single2022 — 오차 1.3% ✅ (거의 완벽)
```
재현 코드 설정:           논문 설정:
cover_glass = SiO₂ ✓     SiO₂ cover glass ✓
focal = Air ✓             Air focal ✓  
stop_decay = 1e-6 ✓      1e-6 (추정) ✓
pillar_mask 동일 ✓        재현 코드에서 가져옴 ✓
```
→ **결론**: 재현 코드가 원본과 거의 동일해서 오차 1.3% 달성

---

### ❷ Pixel2022 — 오차 0.7% ✅ (최고)
```
재현 코드:               논문:
cover_glass = SiO₂ ✓   quartz glass 통과 입사
stop_decay = 1e-6 ✗     1e-8 (FL=2μm)
pillar_mask 동일 ✓      재현 코드에서 가져옴
```
→ **결론**: pillar_mask 정확, stop_decay 차이는 FL=2μm에서 미미

---

### ❸ SMA2023 — 오차 47% ❌ (핵심 문제들)
```
재현 코드:              논문:
cover_glass = ❌ 없음   ✓ (SiO₂가 아닌 Air 입사) → 현재 코드 맞음!
FL_thickness = 4μm ✓   4μm (hd=4μm) ✓
stop_decay = 1e-8 ✓    1e-8 ✓
pillar 좌표:            논문 Figure 확인 필요
  G1 위치가 달랐음 → 수정
height = 1.0μm ✗        h = 998nm ≈ 1μm
```
→ **진짜 원인**: 논문의 Si₃N₄ 굴절률이 불명확 + pillar 좌표 정확성
  - 논문에 n 값이 Supplementary에만 있음
  - R pillar(920nm)는 크지만, G pillar(160nm)가 너무 작아 res=50에서 8격자밖에 안됨
  - res=100 이상 필요 → 시간 문제

---

### ❹ Simplest2023 — 오차 52% ❌
```
재현 코드:              논문:
stop_decay = 1e-6 ✓    1e-6 ✓
ref_sim = with_cover ✓  SiO₂ cover 있는 참조 시뮬 ✓ (수정됨)
extra_materials 누락 ✗  SiN 포함 필요
FL = 1.08μm ✓          z = -1.59μm ≈ 1.08μm ✓
```
→ **진짜 원인**: 논문이 Lumerical의 inverted 구조 (기판 뒤에서 입사)를 
  MEEP에서 재현하는 방식의 차이. 논문 피크 효율이 100%가 넘는 수치들이 있어
  Bayer reference(25/50/25%) 대비 enhancement ratio를 효율로 표현함.
  즉 **효율 정의 자체가 다름!**

---

### ❺ RGBIR2025 — 오차 45% ❌
```
재현 코드:              논문:
stop_decay = 1e-6 ✗     1e-8 (FL=4μm) ✗ 수정 필요
편광 = Ex+Ey ✗          0° 선형편광 (Ex만) ✗
pillar_mask 동일 ✓       재현 코드에서 가져옴
grid = 25nm ✓           최적화 격자 25nm ✓
```
→ **즉각 수정 가능한 것**: 
  1. 편광을 Ex+Ey → Ex만으로
  2. stop_decay 1e-6 → 1e-8

---

## 🚨 공통 오차 패턴 정리 (새 논문 재현 시 반드시 확인)

### A. 효율 정의 오해 (가장 큰 오차 원인)
```
논문들의 효율 정의:
  - "per total incident on supercell" = MEEP의 total_flux 기준
  - "per pixel area flux" = MEEP의 tran_flux_p 기준  
  - "relative to focal plane energy" = 완전히 다른 방식 (Multilayer)
  - "× of Bayer reference" = enhancement ratio (Simplest)

→ 논문 값과 비교 시 어느 기준으로 계산했는지 명시 필수!
```

### B. 입사 방향 & Cover glass
```
논문마다 다름:
  위→아래 입사: Single2022, Pixel2022, SMA2023, RGBIR2025
  기판 통해 입사: Simplest2023 (inverted), Freeform (일부 조건)

Cover glass (소스 위쪽):
  있음: Single2022(SiO₂), Pixel2022(quartz), Simplest(SiO₂), Multilayer
  없음: SMA2023 (Air에서 직접 입사!)
```

### C. 수렴 기준 (stop_decay)
```
FL(μm)에 따른 권장값:
  FL < 1μm  → 1e-3 또는 1e-4
  1 ≤ FL < 3μm → 1e-6
  FL ≥ 3μm  → 1e-8 (필수!)

FL이 4μm인 SMA, RGBIR → 반드시 1e-8
```

### D. 편광 조건
```
논문이 "polarization independent"라 해도:
  - 구조가 진짜 대칭이면 Ex=Ey → Ex+Ey 동시 여기 OK
  - RGBIR2025처럼 비대칭 GA 구조 → 0° 편광(Ex만) 시뮬 필요
  
→ 논문 Methods에서 "Ex and Ey" 또는 "x-polarized" 확인 필수
```

---

## 📌 다음 재현 시 즉각 적용할 수정사항

| 논문 | 수정 내용 | 예상 효과 |
|------|---------|---------|
| **RGBIR2025** | stop_decay=1e-8, 편광=Ex만 | 오차 45%→20% 예상 |
| **SMA2023** | res=100 시도 (G pillar 160nm 표현 위해) | 오차 감소 가능 |
| **Simplest** | 효율 정의를 Bayer ref 대비 enhancement로 재계산 | 비교 가능 |
| **Multilayer** | relative efficiency 정의 적용 | 비교 가능 |
