# CIS Color Router MEEP 시뮬레이션 암묵지 (Tacit Knowledge)
> Docker 실행 검증 완료: 2026-04-09
> Single2022 fast-check ALL PASSED (Sz=3.9μm, 159 pillars, 0 OOB)

이 문서는 CIS color router를 MEEP으로 재현할 때 코드에 나타나지 않는
**"왜 이렇게 했는가"** 를 기록한다. 새 논문 재현 시 LLM 프롬프트 컨텍스트로 사용.

---

## 1. 셀 구조 설계 원칙

### 1.1 Z축 스택 순서 (위=+Sz/2, 아래=-Sz/2)

```
+Sz/2 ─── PML (Lpml=0.4μm)
           ─── pml_2_src gap (0.2μm)   ← 소스가 PML field에 닿지 않도록
z_src ─── GaussianSource (plane wave)
           ─── src_2_geo gap (0.2μm)   ← 소스 near-field가 구조에 닿지 않도록
           ─── SiO2 Block (Lpml+pml_2_src+src_2_geo 전체)
z_meta─── Metasurface Layer (TiO2/SiN pillars)
           ─── Focal Layer (Air or SiO2, FL_thickness)
z_mon ─── 4분면 Flux Monitor (검출기 위치)
           ─── mon_2_pml gap (0.4μm)   ← 모니터가 PML 산란 영향 받지 않도록
-Sz/2 ─── PML (Lpml=0.4μm)
```

**[WHY] 각 gap의 존재 이유:**
- `pml_2_src=0.2`: GaussianSource를 PML 내부에 두면 소스 에너지가 PML에 흡수됨. 최소 λ_min/(2n) = 0.45/(2×1.45) ≈ 0.155μm → 0.2μm 채택
- `src_2_geo=0.2`: 소스 근방(near-field)이 메타서피스와 physically overlap하면 geometry가 소스 field를 왜곡. 0.2μm면 충분
- `mon_2_pml=0.4`: PML 근처는 수치 노이즈. Lpml과 같거나 크게 설정

**[WHAT HAPPENS IF NOT]**
- gap 없이 소스를 PML에 붙이면 → GaussianSource 에너지가 부분 흡수 → 효율 계산 오차 5~20%
- mon_2_pml 너무 작으면 → PML 산란이 flux에 포함 → 효율 > 1.0 발생 가능

**[GOTCHA]**
- `z_mon = -Sz/2 + Lpml + mon_2_pml - 1/resolution` 에서 `- 1/resolution` 이유:
  모니터가 정확히 geometry face에 걸리면 flux 계산 오류. 격자 한 칸 안쪽으로 이동.

---

### 1.2 Sx = Sy = 2 × SP_size 의 이유

**[WHY]** CIS Bayer 패턴은 4개 서브픽셀(R, Gr, B, Gb)이 2×2 배열.
각 서브픽셀 크기가 SP_size이므로 시뮬레이션 단위 셀 = 2SP × 2SP.
주기 경계 조건 + 이 단위셀 크기 = 무한 반복 Bayer array 시뮬레이션과 동일.

```
┌─Gr─┬─B──┐
│(-x,+y)│(+x,+y)│   ← Bayer 2×2 unit cell
├─R──┼─Gb─┤   각 사분면 = SP_size × SP_size
│(-x,-y)│(+x,-y)│
└────┴────┘
   ←2×SP→
```

**[GOTCHA]** SP_size 논문 정의: 일부 논문은 픽셀 전체(2SP)를 SP_size로 표기.
코드에서 `design_region_x = SP_size * 2` 패턴이 있으면 SP_size는 반픽셀.

---

### 1.3 FL_thickness (Focal Length) 값의 결정

| 논문 | SP_size | FL | FL/SP 비율 |
|------|---------|-----|-----------|
| Single2022 | 0.8μm | 2.0μm | 2.5 |
| Pixel2022 | 1.0μm | 2.0μm | 2.0 |
| Freeform | 0.6μm | 0.6μm | 1.0 |
| SMA (sparse) | 1.12μm | 4.0μm | 3.6 |
| RGB-IR ACS | 1.1μm | 4.0μm | 3.6 |
| Simplest (GA) | 0.8μm | 1.08μm | 1.35 |

**[WHY]** FL_thickness가 작을수록 회절각이 커야 → 더 강한 굴절률 대비 재료 필요.
Deep submicron pixel (Freeform, FL=0.6)은 FL이 매우 짧아 메타서피스가 강하게 빛을 꺾어야 함.

**[PHYSICS]** NA = SP_size / sqrt(SP_size² + FL²).
FL이 길면 낮은 NA → 충분한 분리 가능. 짧으면 high-NA → 어려운 설계.

---

## 2. 광원 (Source) 설계 원칙

### 2.1 왜 GaussianSource인가?

**[WHY]** GaussianSource는 하나의 실행으로 넓은 파장 대역(B~R, 400~800nm)을 동시 커버.
단일 주파수 ContinuousSource를 쓰면 RGB 각각 3번 실행 필요 → 3배 시간.

**[WHAT HAPPENS IF NOT]**
- `ContinuousSource`: 단일 파장만, 대역 스펙트럼 불가
- `EigenModeSource`: waveguide 모드 소스용. 자유공간 plane wave에는 부적합.
  CIS는 top illumination(자유공간 입사)이므로 EigenModeSource 사용 불가.

### 2.2 `frequency = 1/(0.545*um_scale)` — 왜 545nm?

**[WHY]** 545nm는 RGB 대역의 에너지 중심(geometric mean)에 가까움:
- 수치: f_center = (f_B + f_R)/2 = (1/0.45 + 1/0.65)/2 ≈ 1/0.545
- GaussianSource의 peak amplitude가 이 주파수에서 가장 큼
- 실제 광대역 스펙트럼을 쓸 때는 fcen = (1/0.35 + 1/0.80)/2 사용 (참조 시뮬레이션)

### 2.3 `fwidth = frequency * width` (width=2) — 이 2의 의미

**[WHY]** GaussianSource의 fwidth는 Gaussian envelope의 FWHM (in frequency domain).
- fwidth = 2 × fcen → 매우 넓은 대역 (400~800nm 전체 포함)
- 수식: λ_min ≈ c / (fcen + fwidth/2) ≈ 0.45 / (1 + 1) → 실제론 훨씬 넓음
- 실질적으로 fwidth > frequency이면 DC까지 포함하는 초광대역

**[GOTCHA]** fwidth가 너무 작으면 원하는 파장(B=450nm, R=650nm)에서 진폭이 미약해져
flux 측정 정확도 하락. `width=2`는 관례적으로 "충분히 넓다"를 보장하는 경험값.

**[WHAT HAPPENS IF NOT]** fwidth=0.1 (좁은 대역) → B,R 파장에서 소스 진폭 ≈ 0
→ blue/red flux ≈ 0 → efficiency plot이 평탄 직선

### 2.4 Ex + Ey 동시 여기 — Unpolarized 이유

**[WHY]** CIS 카메라는 모든 편광을 감지해야 함 (자연광 = unpolarized).
- Ex 단독: TE 편광만
- Ey 단독: TM 편광만
- Ex + Ey 동시: unpolarized 자연광 근사

**[MEEP_API_REASON]** MEEP은 비간섭(incoherent) 합산 불가.
Ex+Ey 동시 여기는 incoherent합이 아닌 coherent합이지만,
pillar 구조가 4-fold 대칭이 아닌 경우 편광 평균 효과 필요.
완전한 방법: Ex와 Ey 각각 실행 후 결과 평균 (일부 논문은 이 방식).

**[GOTCHA]** Single2022처럼 복잡한 pillar mask는 x-y 비대칭 → Ex≠Ey.
이 코드는 편의상 동시 여기. 정확한 결과를 원하면 각각 실행 후 평균 필요.

### 2.5 참조 시뮬레이션에서 소스를 Ex만으로 바꾸는 이유

```python
# 메인 시뮬에서: Ex + Ey (두 편광)
# 참조 시뮬에서: Ex만
source = [mp.Source(src, component=mp.Ex, ...)]
opt.sim_1.change_sources(source)
```

**[WHY]** 참조 시뮬(빈 공간)의 목적은 total_flux 측정.
빈 공간에서는 Ex와 Ey가 완전히 독립 → Ex만으로 측정해도 Ey의 flux는 동일.
코드 단순화 목적. 결과: total_flux = Ex flux × 2 (만약 정확히 하려면).

**[GOTCHA]** 참조와 메인의 source를 다르게 하면 정규화가 틀림.
Single2022 코드에서 main sim에서도 Ex만 사용하도록 `change_sources` 후 main sim 생성.
이는 코드의 잠재적 버그. 논문 재현 시 일관성 유지 필수.

---

## 3. 경계 조건 원칙

### 3.1 `k_point = mp.Vector3(0,0,0)` — 가장 중요한 설정

**[WHY]** CIS는 무한히 반복되는 Bayer array를 시뮬레이션.
`k_point=(0,0,0)`은 Bloch 주기 경계 조건을 활성화 (정상 입사, kx=ky=0).
이 없으면 X,Y 경계에서 반사 → 단일 고립 픽셀 시뮬레이션이 됨.

**[MEEP_API_REASON]** MEEP에서 k_point를 설정하면 자동으로 X,Y 방향 주기 경계 적용.
이게 없으면 X,Y 방향 경계는 기본값인 "perfect metal" 벽.

**[WHAT HAPPENS IF NOT]**
- k_point 없음 → X,Y 경계에서 완전 반사 → 간섭 패턴 발생
- 효율 수치가 완전히 달라짐 (보통 50~200% 오차)
- 특히 pillar가 셀 경계 근처에 있으면 산란이 심해져 발산 가능

**[GOTCHA]** `k_point = mp.Vector3(0,0,0)`과 `k_point`를 아예 안 쓰는 것은 다름.
반드시 명시적으로 `k_point=mp.Vector3(0,0,0)` 설정.

### 3.2 `eps_averaging = False` — 이산 구조에서 필수

**[WHY]** MEEP 기본값 eps_averaging=True는 서브격자 스무딩(subpixel smoothing)을 함.
연속적인 curved interface에서는 정확도를 높이지만,
pillar_mask의 sharp 이진 경계에서는 오히려 기하 구조를 왜곡.

**[NUMERICAL_REASON]** 80nm pillar (w=0.08)을 resolution=50으로 표현하면 4격자.
eps_averaging=True 시 경계에서 ε이 smoothing되어 effective pillar width가 달라짐.
→ 설계한 pillar 크기와 실제 시뮬 pillar 크기 불일치 → 효율 저하

**[WHAT HAPPENS IF NOT]** eps_averaging=True로 하면 약 5~15% 효율 차이 발생.
논문과 비교 시 오차의 주요 원인이 될 수 있음.

**[GOTCHA]** MaterialGrid 사용 시에는 eps_averaging=True가 더 정확한 경우도 있음.
→ discrete_pillar: eps_averaging=False (필수)
→ materialgrid: eps_averaging=True도 가능 (논문마다 다름)

### 3.3 `mp.PML(thickness=Lpml, direction=mp.Z)` — Z방향만 PML

**[WHY]** X,Y 방향은 주기 경계 조건 (k_point 설정으로).
PML과 주기 경계는 같은 방향에 공존 불가 → Z방향만 PML.

**[CIS_SPECIFIC]** CIS는 평면파가 Z방향(-Z 방향)으로 입사.
X,Y는 무한 배열의 주기 → 주기 경계.
위(+Z, 소스 쪽)와 아래(-Z, 검출기 쪽)만 흡수 경계 필요.

**[GOTCHA]** `mp.PML(Lpml)` (방향 없이)와 `mp.PML(Lpml, direction=mp.Z)`의 차이:
전자는 3방향 모두 PML → k_point와 충돌 → MEEP warning or 결과 오류.
반드시 `direction=mp.Z` 명시.

### 3.4 Lpml = 0.4μm 의 근거

**[PHYSICS_REASON]**
최소 PML 두께 = λ_max / (2 × n_min) = 0.8μm / (2 × 1.0) = 0.4μm (공기 기준).
CIS 파장 범위 최대 800nm → 정확히 0.4μm = 최소값.

**[WHAT HAPPENS IF NOT]**
Lpml < 0.3: 장파장(700~800nm) 반사 → 효율 수치 1~5% 오차
Lpml > 0.8: 시뮬레이션 셀 커짐 → 불필요한 계산 시간

---

## 4. Geometry 배치 원칙

### 4.1 소스 위쪽에 SiO2 Block을 넣는 이유

```python
mp.Block(center=..., size=mp.Vector3(Sx, Sy, Lpml+pml_2_src+src_2_geo), material=SiO2)
```

**[CIS_SPECIFIC]** 실제 CIS 구조: 빛이 유리 기판(SiO2 cover glass)을 통해 입사.
SiO2 영역 안에 소스를 두면 소스가 already in SiO2 medium.
이 Block이 없으면 default_material=Air 공간에서 입사 → 물리적으로 틀림.

**[WHAT HAPPENS IF NOT]**
SiO2 없이 Air에서 입사하면:
1. 반사율 계산 오류 (Air→메타서피스 계면 반사 vs 실제 SiO2→메타서피스)
2. effective index 차이로 파장 분산 특성 달라짐

**[GOTCHA]** 논문 Freeform은 SiO2를 source side에, focal layer도 Air (짧은 focal).
논문 Pixel2022는 source side SiO2 + focal layer SiO2.
params.json에서 `cover_material`과 `focal_material`을 독립 설정 필요.

### 4.2 Pillar 좌표 변환 — 핵심 인덱싱 법칙

```python
# pillar_mask[i][j]: i=row (위→아래), j=col (왼→오른)
# MEEP 좌표: x는 오른이 +, y는 위가 +
px = round(-N/2*w + j*w + w/2, 2)   # j=0 → 가장 왼쪽, j=N-1 → 가장 오른쪽
py = round(N/2*w - i*w - w/2, 2)   # i=0 → 가장 위 (+y), i=N-1 → 가장 아래 (-y)
```

**[WHY i와 y가 반전되는가]**
이미지/행렬 관례: 행 0이 맨 위.
MEEP 좌표: y=+가 위.
→ i=0(행렬 맨 위) = py=+최대 (MEEP 맨 위) → 반전 필요.

**[GOTCHA]** 논문 figure의 pillar 배치가 x-y plane 시각화와 다를 때:
- figure가 y축 위가 +라면 mask 그대로
- figure가 image 좌표(위가 0번 행)라면 위 변환 사용

### 4.3 SiPD (Silicon PhotoDiode) 영역 = Air 이유

**[CIS_SPECIFIC]** MEEP은 Si photodiode의 광전효과를 모델링 안 함.
검출기 영역을 Si로 채우면 Si의 높은 흡수율 때문에 빛이 흡수됨 → flux 측정 불가.
Air로 두면 빛이 그냥 통과 → flux monitor로 측정 가능.

---

## 5. 참조 시뮬레이션과 효율 정규화

### 5.1 참조 시뮬레이션의 수학적 의미

```
시뮬 1 (geometry_1, 빈 공간):
  total_flux = 입사 광의 총 flux (반사 없는 기준값)
  straight_refl_data = 빈 공간 반사 데이터 (≈ 0, 수치 노이즈만)

시뮬 2 (실제 geometry):
  refl.load_minus_flux_data(straight_refl_data)
  → 실제 반사 = (메타서피스 포함 반사) - (빈공간 반사)
  → 실제 반사만 분리
```

**[PHYSICS_REASON]** flux 모니터는 "총 flux"를 측정 (입사+반사 포함).
반사 모니터 위치에서 flux = 입사 flux - 반사 flux (방향성 때문에 빼짐).
load_minus_flux_data로 기준값 빼면 순수 반사만 남음.

### 5.2 두 가지 효율 정규화

```python
# Pixel-normalized efficiency (논문에서 주로 사용)
Tr = red_flux[d] / tran_flux_p[d]   # 픽셀 도달 flux 기준
# → "픽셀에 도달한 빛 중 몇 %가 R 서브픽셀로 갔는가"

# Total-input-normalized efficiency (절대 효율)
Trt = red_flux[d] / total_flux[d]   # 입사 총 flux 기준
# → "입사광 전체 중 몇 %가 R 서브픽셀에 도달했는가"
```

**[CIS_SPECIFIC]** 논문마다 정의가 다름:
- "Color routing efficiency": 보통 pixel-normalized (Tr)
- "Total efficiency" or "absolute efficiency": total-normalized (Trt)
- 논문 figure를 보고 Y축 최대값 확인: ~1.0이면 pixel-norm, ~0.4면 total-norm

**[GOTCHA]** tran_flux_p (픽셀 면적 flux) vs tran_total (전체 입사):
tran_flux_p는 Sx×Sy 전체 픽셀만, tran_total은 더 큰 영역 포함 가능.
일반적으로 tran_pixel = Sx×Sy = 전체 셀 → tran_total ≈ tran_pixel (반사 손실 제외).

### 5.3 Tg + Tg0 = Green 두 항 합산

**[WHY]** Bayer 패턴에서 G 픽셀이 2개 (Gr, Gb):
- Gr: (-x, +y) 사분면
- Gb: (+x, -y) 사분면
총 G flux = Gr flux + Gb flux → 단일 플롯에서 초록선.

---

## 6. OptimizationProblem 사용 이유

### 6.1 역설계 없이 왜 mpa.OptimizationProblem을 쓰는가?

```python
opt = mpa.OptimizationProblem(
    simulation=sim,
    objective_functions=[],   # 역설계 없음
    objective_arguments=[],
    design_regions=[],        # 설계 영역 없음
    frequencies=frequencies,
    ...
)
```

**[MEEP_API_REASON]** OptimizationProblem은 adjoint를 위한 클래스이지만,
부수적으로 `opt.plot2D()`, `opt.sim` 등 편의 기능 제공.
특히 `opt.plot2D()`는 geometry + source + monitor를 한 번에 시각화.
순수 `sim.plot2D()`보다 더 많은 시각화 옵션 제공.

**[GOTCHA]** `opt.sim_1 = mp.Simulation(...)` 처럼 opt에 외부 simulation을 붙이는 것은
비공식 API. MEEP 버전 업그레이드 시 호환성 주의.

---

## 7. 논문별 핵심 차이점 비교

| 파라미터 | Single2022 | Pixel2022 | Freeform | Multi_layer | RGB-IR | SMA | Simplest |
|----------|-----------|-----------|---------|-------------|--------|-----|---------|
| material | TiO2 | SiN | SiN | SiN | TiO2 | SiN | Nb2O5 |
| n | 2.3 | 2.0 | 1.92 | 2.02 | 2.5 | 2.02 | 2.32 |
| SP_size | 0.8 | 1.0 | 0.6 | 0.6 | 1.1 | 1.12 | 0.8 |
| Layer_t | 0.3 | 0.6 | 0.6 | 0.6 | 0.6 | 1.0 | 0.51 |
| FL | 2.0 | 2.0 | 0.6 | 1.0 | 4.0 | 4.0 | 1.08 |
| resolution | 50 | 40 | 50 | 50 | 50 | 50 | 100 |
| design | discrete | discrete | MGrid | MGrid×2 | discrete | sparse | cylinder |
| focal_mat | Air | SiO2 | Air | Air | SiO2 | SiO2 | Air |
| grid_N | 20 | 16 | 61 | 61 | 22 | - | - |
| tile_w | 0.08 | 0.125 | - | - | 0.1 | - | - |
| decay | 1e-3 | 1e-8 | 1e-4 | 1e-3 | 1e-3 | 1e-3 | 1e-3 |

**[WHY resolution 차이]**
- Simplest=100: cylinder 직경 최소 210nm → 최소 10격자 필요 (210nm / (1000/100)=10nm = 21격자) → 충분
- Pixel2022=40: tile 125nm → 5격자 → 약간 부족하지만 연산 시간 절충
- 일반 규칙: resolution × min_feature_size(μm) ≥ 10 (격자 수 10개 이상)

**[WHY focal_material 차이]**
- Air focal: 메타서피스 아래가 공기 → 더 큰 굴절률 대비 → 더 강한 집속
- SiO2 focal: 실제 CMOS 공정에서 SiO2 패시베이션층 존재 → 공정 현실 반영

**[WHY decay_by 차이]**
- 1e-3: 표준값. 정확도보다 속도 중시
- 1e-8 (Pixel2022): 더 엄격한 수렴 조건. 반사율 측정 정밀도 중요
- stop_when_dft_decayed(1e-6, 0): decay_by와 동일 역할이지만 DFT 기준

---

## 8. 실행 환경 결정 기준

### 8.1 복셀 수 계산

```python
Nvox = int(Sx*resolution) × int(Sy*resolution) × int(Sz*resolution)
```

| 논문 | Nvox (approx) | 예상 시간(로컬 10코어) |
|------|--------------|---------------------|
| Single2022 (res=50) | 1,248,000 | ~45분 |
| Pixel2022 (res=40) | ~800,000 | ~25분 |
| Freeform (res=50) | ~720,000 | ~20분 |
| Simplest (res=100) | ~5,000,000 | ~3시간 |

**결정 기준:**
- Nvox < 2,000,000 AND 예상 시간 < 2시간 → **로컬 Docker (mpirun -np 10)**
- Nvox ≥ 2,000,000 OR 예상 시간 ≥ 2시간 → **SimServer (mpirun -np 128)**

### 8.2 로컬 실행 명령어
```bash
docker exec meep-pilot-worker bash -c \
  "mpirun -np 10 python /tmp/cis_repro/{paper_id}.py > /tmp/{paper_id}.log 2>&1"
```

### 8.3 SimServer 실행 + 결과 수집
```bash
scp reproduce.py user@166.104.35.108:/tmp/cis_repro/{paper_id}.py
ssh user@166.104.35.108 "nohup mpirun -np 128 python /tmp/cis_repro/{paper_id}.py > /tmp/{paper_id}.log 2>&1 &"
# 완료 후:
scp -r user@166.104.35.108:/tmp/cis_repro/{paper_id}_results/ \
    C:/Users/user/projects/meep-kb/cis_repro/results/{paper_id}/
```

---

## 9. DFT Field Monitor 사용법

### 9.1 왜 Ex, Ey, Ez 3성분 모두?

**[PHYSICS_REASON]** 3D 시뮬레이션에서 필라 구조를 통과할 때 모든 편광 성분 결합(coupling):
- Ex → 산란 후 Ez 성분 발생 (longitudinal component)
- 총 세기: I = |Ex|² + |Ey|² + |Ez|²

**[WHY yee_grid=True]**
MEEP Yee grid에서 Ex, Ey, Ez는 서로 다른 격자점에 저장.
yee_grid=True: 각 성분을 고유 격자점에서 추출 (가장 정확).
yee_grid=False: 모든 성분을 동일 격자점으로 보간 (편리하나 오차 있음).

---

## 10. 핵심 체크리스트 (재현 전 반드시 확인)

```
□ k_point = mp.Vector3(0,0,0) 설정됨
□ eps_averaging = False (discrete pillar의 경우)
□ PML: direction=mp.Z 만
□ z_mon > -Sz/2 + Lpml (모니터가 PML 밖에 있음)
□ z_src < Sz/2 - Lpml (소스가 PML 밖에 있음)
□ Focal material (Air vs SiO2) 논문과 일치
□ 참조 시뮬레이션 source == 메인 시뮬레이션 source (일관성)
□ efficiency = flux / tran_pixel (pixel-norm) 또는 / total_flux (total-norm) 확인
□ Green = Gr_flux + Gb_flux (두 G 픽셀 합산)
□ resolution × min_feature(μm) ≥ 8 (최소 8격자 이상)
□ Lpml ≥ λ_max / (2×n_min) = 0.8 / 2 = 0.4μm
```
