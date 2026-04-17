# CIS Color Router 논문 재현 체크리스트 템플릿
> 작성일: 2026-04-11
> 목적: 논문 재현 전 PDF를 읽고 필수 설정 항목을 정확히 파악하기 위한 템플릿

---

## 📋 논문 정보

| 항목 | 내용 |
|------|------|
| 논문 제목 | |
| 저자 / 저널 / 연도 | |
| DOI | |
| 시뮬레이션 도구 | FDTD (Lumerical/MEEP) / RCWA / 기타 |

---

## 🔑 재현 시 반드시 확인해야 할 항목

### 1. 소자 구조 파라미터

| 항목 | 논문 값 | 확인 여부 |
|------|--------|---------|
| **수퍼셀(유닛셀) 크기** | μm × μm | ☐ |
| **단일 픽셀 크기** | μm × μm | ☐ |
| **메타서피스 재료** | (TiO₂/SiN/Nb₂O₅ 등) | ☐ |
| **굴절률 (n)** | @ 가시광 (정확한 값 or 참고문헌) | ☐ |
| **필라 높이/두께 (h)** | nm | ☐ |
| **최소 feature size** | nm (격자 크기 결정에 중요!) | ☐ |
| **Focal length** | μm (메타서피스→검출기 거리) | ☐ |
| **Focal layer 재료** | Air / SiO₂ / 기타 | ☐ |
| **기판 재료** | SiO₂ / quartz / glass 등 | ☐ |
| **기판 두께** | μm (검출 위치에 영향) | ☐ |

> ⚠️ **주의**: Focal length = 메타서피스 하단 면에서 검출 면까지의 거리. 논문에 따라 "기판 포함" vs "기판 제외"가 다름.

---

### 2. 전체 레이어 스택 구조 (필수!)

논문 figure를 보고 **위→아래** 방향으로 직접 그려넣기:

```
입사광 방향: (위→아래 / 아래→위) — 논문 확인 필수!

[ ? ] ← 소스 위 매질 (air? SiO₂ cover glass?)
[ 메타서피스 레이어 ] ← 재료, 높이
[ ? ] ← 레이어 사이 매질 (multilayer의 경우)
[ focal layer ] ← Air or SiO₂, 두께
[ 기판 ] ← 재료, 두께
[ 검출 면 ] ← monitor 위치
```

> ⚠️ **가장 흔한 실수**: 
> - Single2022: 소스 위쪽 = SiO₂ (cover glass 있음)  
> - SMA2023: 소스 위쪽 = Air (cover glass 없음)  
> - Pixel2022: 소스 위쪽 = quartz glass 통해 입사  
> - Simplest: 기판 뒤에서 입사하는 inverted 구조 있음  

---

### 3. 광원 & 경계 조건 (시뮬 오차의 핵심!)

| 항목 | 논문 값 | MEEP 구현 | 확인 |
|------|--------|----------|------|
| **입사 방향** | 위→아래 / 아래→위 | | ☐ |
| **편광** | Ex / Ey / Ex+Ey(비편광) / 0° / 45° | | ☐ |
| **광원 종류** | 평면파 / Gaussian / 기타 | GaussianSource | ☐ |
| **광원 대역폭** | 파장 범위 (nm) | fwidth 계산 | ☐ |
| **X,Y 경계 조건** | Periodic / Bloch | k_point=(0,0,0) | ☐ |
| **Z 경계 조건** | PML 두께 | direction=mp.Z | ☐ |
| **수렴 기준** | 1e-3 / 1e-6 / 1e-8 | stop_when_dft_decayed | ☐ |

> ⚠️ **수렴 기준**: FL이 길수록 (≥3μm) 더 엄격한 기준 필요 (1e-8 권장)  
> ⚠️ **편광**: 논문이 "polarization-independent" 이더라도 시뮬은 Ex+Ey 각각 or 동시 여기  

---

### 4. 효율 정의 (정규화 분모 — 논문마다 다름!)

| 논문 | 효율 정의 | 분모 |
|------|---------|------|
| Single2022 | averaged transmittance | **수퍼셀 전체 입사 에너지** |
| Pixel2022 | colour collection efficiency | **유닛셀 전체 입사 에너지** |
| SMA2023 | spectral routing efficiency | **수퍼셀 전체 입사 에너지** |
| Multilayer | relative efficiency | **전체 초점면 에너지** (입사 아님!) |
| Freeform | routing efficiency | **수퍼셀 입사 에너지** |
| RGBIR2025 | colour collection efficiency | **유닛셀 입사 에너지** |
| Simplest | transmittance | **각 픽셀 기준 (Bayer ref 대비)** |

> ⚠️ **Multilayer 주의**: 분모가 "전체 초점면 에너지"라서 pixel-norm과 다름!  
> → 직접 비교 시 "absolute efficiency = relative × transmittance" 변환 필요

**현재 MEEP 재현 코드의 효율 정의:**
```python
Tr = red_flux[d] / tran_flux_p[d]   # pixel-normalized (픽셀 면적 flux 분모)
Trt = red_flux[d] / total_flux[d]   # total-normalized (전체 입사 flux 분모)
```
→ 논문 정의가 어느 것인지 확인 후 적용!

---

### 5. Bayer 사분면 배치 (논문마다 다름!)

논문 figure에서 R/G/G/B 위치 확인:

```
표준 배치 (Single2022 기준):    SMA2023 배치:
┌────┬────┐                    ┌────┬────┐
│ Gr │ B  │ (+y)               │ R  │ G2 │ (+y)
├────┼────┤                    ├────┼────┤
│ R  │ Gb │ (-y)               │ G1 │ B  │ (-y)
└────┴────┘                    └────┴────┘
  (-x) (+x)                      (-x) (+x)
```

| 채널 | 표준 좌표 | 이 논문의 실제 좌표 |
|------|---------|----------------|
| R | (-x, -y) | |
| Gr | (-x, +y) | |
| B | (+x, +y) | |
| Gb | (+x, -y) | |

---

### 6. FDTD Resolution & 격자 크기

| 항목 | 계산/확인 |
|------|---------|
| 논문 격자 크기 | nm |
| 최소 feature size | nm |
| 최소 격자 수 (격자크기/feature) | 개 (≥8 권장) |
| MEEP resolution = 1000/격자크기 | px/μm |
| 복셀 수 (Sx×Sy×Sz×res³) | (실행 시간 결정) |

> ⚠️ **SMA2023의 경우**: G pillar = 160nm → MEEP res=50이면 160×50/1000=8격자 (겨우)  
>   → res=100 이상 권장하지만 시뮬시간 8배↑  

---

## 📊 기존 논문 재현 실제 설정 비교 (현재까지 파악된 차이점)

| 논문 | cover_glass | ref_sim | stop_decay | bayer | 특이사항 |
|------|-----------|---------|-----------|-------|---------|
| **Single2022** | ✅ SiO₂ | air | 1e-6 | standard | 기준 논문 |
| **Pixel2022** | ✅ SiO₂ | air | 1e-8 | standard | quartz 기판 통과 |
| **SMA2023** | ❌ 없음 | air | 1e-8 | sma배치 다름 | 소스=Air 직접 입사 |
| **Simplest** | ✅ SiO₂ | with_cover | 1e-6 | standard | 기판 아래서 입사 가능 |
| **RGBIR2025** | ✅ SiO₂ | air | 1e-8 | standard | 0°편광만 |
| **Freeform** | ✅ glass | air | 1e-4 | standard | RCWA아님 FDTD |
| **Multilayer** | - | with_cover | 1e-3 | standard | RCWA 설계→FDTD 검증 |

---

## ✅ 재현 전 필수 체크리스트

```
□ 1. 논문 Figure 1 (구조도) 보고 레이어 스택 직접 그리기
□ 2. Supplementary Material에서 굴절률, 격자 크기 확인
□ 3. 효율 정의 찾아서 분모 확인 (pixel-norm vs total-norm vs relative)
□ 4. Bayer 사분면 R/G/B 위치 figure에서 확인
□ 5. 편광 조건 확인 (논문이 비편광이라도 시뮬에서 Ex+Ey 여부)
□ 6. 입사 방향 확인 (위→아래 vs 아래→위)
□ 7. Cover glass 여부 확인 (소스 위쪽 매질)
□ 8. Focal layer 재료 확인 (Air vs SiO₂)
□ 9. 수렴 기준 확인 (FL≥3μm → 1e-8 필수)
□ 10. 논문 보고 효율 수치 표에 기재 (비교 기준)
□ 11. 최소 feature size × resolution ≥ 8격자 확인
□ 12. params.json에 모두 기재 후 검토
```

---

## 📝 params.json 확장 템플릿

```json
{
  "paper_id": "XXX2024",
  "paper_title": "",
  
  // ── 소자 구조 ──────────────────────────────
  "material_name": "TiO2",
  "n_material": 2.3,
  "SP_size": 0.8,
  "Layer_thickness": 0.3,
  "FL_thickness": 2.0,
  "focal_material": "Air",
  "EL_thickness": 0,
  "n_layers": 1,
  
  // ── 기판/커버 구조 ─────────────────────────
  "cover_glass": true,          // 소스 위쪽 SiO₂ cover 유무
  "cover_material": "SiO2",    // cover material
  "substrate_material": "SiO2", // 기판 재료
  "sipd_material": "Air",      // SiPD 영역 재료
  "light_from": "top",         // "top": 위→아래, "bottom": 아래→위
  
  // ── 광원 & 경계 ────────────────────────────
  "source_polarization": "both",  // "Ex", "Ey", "both"
  "stop_decay": "1e-6",
  "ref_sim_type": "air",          // "air" or "with_cover"
  
  // ── 효율 정의 ──────────────────────────────
  "efficiency_norm": "pixel",     // "pixel": tran_flux_p, "total": total_flux, "relative": focal_plane
  "bayer_config": "standard",     // "standard" or paper-specific
  
  // ── Bayer 배치 (논문 figure 확인 후 기재) ──
  "bayer_layout": {
    "R":  {"x": -1, "y": -1},
    "Gr": {"x": -1, "y": +1},
    "B":  {"x": +1, "y": +1},
    "Gb": {"x": +1, "y": -1}
  },
  
  // ── FDTD ──────────────────────────────────
  "resolution": 50,
  
  // ── 논문 보고 효율 (비교 기준) ─────────────
  "target_efficiency_definition": "pixel-norm",
  "target_efficiency": {"R": 0.0, "G": 0.0, "B": 0.0},
  "paper_peak_efficiency": {"R": 0.0, "G": 0.0, "B": 0.0},
  
  // ── 특이사항 ──────────────────────────────
  "notes": ""
}
```
