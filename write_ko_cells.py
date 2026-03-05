#!/usr/bin/env python3
"""
notebooks 테이블 cells_ko 한국어 해설 — 전체 버전 (01~08)
- 직역 X, 처음 공부하는 연구자를 위한 교육적 해설
- 소스 비교 시뮬레이션 이미지 포함 (01 노트북)
"""
import sqlite3, json, os
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", "/app/db/knowledge.db"))

# ── 소스 비교 토글 섹션 (01번 노트북 시뮬레이션 세팅에 삽입) ─────────────────
SOURCE_COMPARISON_TOGGLE = """
---

<details class="src-toggle">
<summary>📡 <strong>소스 선택 가이드: Gaussian Source vs EigenMode Source</strong>
  <span style="font-size:11px;color:#60a5fa;margin-left:8px">▶ 클릭해서 펼치기</span>
</summary>

### 언제 어떤 소스를 쓸까?

| | Gaussian Source | EigenMode Source |
|--|--|--|
| **입사 방식** | 지정 위치에 Ez/Hz 성분 직접 인가 | MEEP이 고유모드 프로파일 자동 계산 |
| **모드 순도** | 낮음 — 여러 모드 동시 여기 | 높음 — 원하는 단일 모드만 |
| **사용 케이스** | 빠른 테스트, 방사 패턴, 메타표면 | 도파관 소자, 역설계, S-파라미터 |
| **속도** | 빠름 | 약간 느림 (고유모드 계산 필요) |

---

### ① Gaussian Source vs EigenMode (TE₀)

![비교1](/static/results/src_comp_01_gauss_vs_eig.png)

- **Gaussian**: 셀 전체에 Ez를 인가 → 도파관 내 여러 모드 동시 여기 + 방사 손실
- **EigenMode (TE₀)**: 도파관 고유모드 프로파일로 입사 → 깔끔한 단일 모드 전파

---

### ② mode_num: TE₀ (eig_band=1) vs TE₁ (eig_band=2)

![비교2](/static/results/src_comp_02_mode1_vs_mode2.png)

```python
# TE₀ 기본 모드 (실리콘 포토닉스 기본)
mp.EigenModeSource(src, eig_band=1, eig_parity=mp.ODD_Z, ...)

# TE₁ 1차 고차 모드 (모드 컨버터 설계 시)
mp.EigenModeSource(src, eig_band=2, eig_parity=mp.ODD_Z, ...)
```

> **SOI 역설계**에서 `eig_band=1` → TE₀, `eig_band=2` → TE₁

---

### ③ eig_match_freq: True vs False

![비교3](/static/results/src_comp_03_match_vs_nomatch.png)

```python
# 권장: 실제 분산 관계로 정확한 모드 계산
mp.EigenModeSource(src, eig_match_freq=True, ...)

# 비권장: k-벡터 근사 → 두꺼운 도파관에서 오차 발생 가능
mp.EigenModeSource(src, eig_match_freq=False, ...)
```

> MEEP 공식 문서 권장: **항상 `eig_match_freq=True`** 사용

---

### ④ parity: ODD_Z (TE) vs EVEN_Z (TM)

![비교4](/static/results/src_comp_04_te_vs_tm.png)

```python
mp.ODD_Z   # TE 편광: Ez 성분 우세 — SOI 포토닉스 표준
mp.EVEN_Z  # TM 편광: Hz 성분 우세 — 특수 소자 설계
mp.ODD_Y   # 도파관 폭 방향 대칭 활용 (계산 속도 2배 향상)
```

---

### 📋 파라미터 요약 카드

![요약](/static/results/src_comp_00_params_table.png)

</details>
"""

# ── 01-Introduction 업데이트 (소스 비교 토글 포함) ───────────────────────────
NB01_KO = {
    0: """# MEEP Adjoint 솔버 — 입문

MEEP의 **역전파(adjoint) 솔버** 입문 튜토리얼입니다.

역전파 솔버의 핵심 아이디어: 사용자가 정의한 목적함수(FOM)의 **임의 개수 설계 변수에 대한 기울기**를 **단 2번의 FDTD 시뮬레이션**만으로 계산합니다.

---

**왜 역전파가 필요한가?**

설계 변수가 100개라면 유한 차분(FD)으로 기울기를 구하려면 시뮬레이션이 **100번 이상** 필요합니다.  
역전파는 설계 변수 수에 관계없이 **항상 2번**만 실행합니다.

| 방법 | 시뮬레이션 횟수 | 비고 |
|------|---------------|------|
| 유한 차분 | N+1 (N=설계 변수 수) | 100개 변수 → 101번 |
| 역전파 | **항상 2번** | 변수 수 무관 |

목적함수는 보통 **고유모드 계수(Eigenmode coefficient)**나 **DFT 필드 세기**로 정의합니다.""",

    2: f"""## 1단계: 시뮬레이션 도메인 설정

일반 MEEP 시뮬레이션과 동일하게 셀 크기, PML, 해상도를 먼저 설정합니다.

```python
cell   = mp.Vector3(10, 10, 0)     # 2D 시뮬레이션
pml    = [mp.PML(1.0)]              # PML 두께 ≥ 1 μm 권장
res    = 20                         # px/μm (빠른 테스트용)
```

{SOURCE_COMPARISON_TOGGLE}""",

    4: """## 2단계: 소스 정의

역설계에는 **EigenModeSource**를 권장합니다:

```python
src = mp.GaussianSource(frequency=fcen, fwidth=df)
sources = [mp.EigenModeSource(
    src,
    eig_band       = 1,          # TE₀ 기본 모드
    eig_match_freq = True,       # 정확한 분산 계산 (필수)
    eig_parity     = mp.ODD_Z,   # TE 편광
    center         = mp.Vector3(-4, 0),
    size           = mp.Vector3(0, 4),
)]
```

> 좁은 대역 펄스(`df = 0.1 * fcen`)를 사용하면 CW 솔버보다 빠르고 안정적입니다.""",

    6: """## 3단계: 지오메트리 & 설계 영역

도파관 기본 구조 위에 **설계 영역(Design Region)**을 정의합니다.

```python
# 설계 영역: 10×10 격자 = 100개 설계 변수
design_region = mpa.DesignRegion(
    mpa.MaterialGrid(mp.Vector3(Nx, Ny, 0),
                     mp.air, mp.Medium(epsilon=12)),
    volume=mp.Volume(center=mp.Vector3(), size=mp.Vector3(1, 1)),
)
```

**설계 변수 → 유전율 매핑**:
```
[0~1 실수] → 보간기 → 유전율 분포 (ε=1~12)
```

보간기 종류:
- **BilinearInterpolation** (내장, 이 예제) → 격자 사이 선형 보간
- **Custom 보간기** → 필터링, 투영 등 제약 조건 적용 가능""",

    8: """## 4단계: 시뮬레이션 객체 생성

앞서 정의한 모든 요소를 `mp.Simulation`으로 조합합니다.

```python
sim = mp.Simulation(
    cell_size       = cell,
    boundary_layers = pml,
    geometry        = geometry,
    sources         = sources,
    resolution      = resolution,
)
```""",

    10: """## 5단계: 목적 수치(Objective Quantity) 정의

역전파 API에서 목적함수는 **측정 가능한 필드 수치의 함수**로 정의합니다.

현재 지원하는 필드 함수:
- `mpa.EigenmodeCoefficient` — 고유모드 계수 (가장 많이 사용)
- `mpa.FourierFields` — DFT 필드 세기
- `mpa.Near2FarFields` — Near-to-Far field 변환

```python
# 도파관 출력부에서 TE₀ 모드 계수 측정
ob_list = [mpa.EigenmodeCoefficient(
    sim,
    mp.Volume(center=mp.Vector3(0, 3), size=mp.Vector3(0, 2)),
    1,   # mode_num=1 (TE₀)
)]
```""",

    12: """## 6단계: 목적함수 수식 정의

목적함수는 `autograd.numpy`로 작성해야 자동 미분이 가능합니다.

```python
import autograd.numpy as npa

def J(a):
    return npa.abs(a) ** 2   # 모드 파워 = |계수|²
```

> ⚠️ **일반 numpy 사용 금지**: 역전파 솔버가 gradient를 계산할 수 없습니다.
> `import autograd.numpy as npa` → `npa.abs()`, `npa.sum()` 등 사용""",

    14: """## 7단계: OptimizationProblem 구성

모든 구성 요소를 `mpa.OptimizationProblem`으로 조합합니다.

```python
opt = mpa.OptimizationProblem(
    simulation          = sim,
    objective_functions = [J],
    objective_arguments = ob_list,
    design_regions      = [design_region],
    fcen                = fcen,
    df                  = 0,      # 단일 주파수
    decay_by            = 1e-6,   # 수렴 임계값
)
```

`opt(x)` 호출 시 내부 동작:
1. **Forward 시뮬레이션** → f₀, DFT 필드 기록
2. **Adjoint 시뮬레이션** → 역방향 시뮬레이션으로 기울기 계산
3. `f0`, `dJ_du` 반환""",

    16: """## 8단계: 초기 설계 변수 설정

```python
x0 = np.random.uniform(0, 1, Nx * Ny)
# 또는 물리적으로 의미 있는 초기값 (예: 전체 실리콘)
x0 = np.ones(Nx * Ny)
```

> **초기값 전략**:
> - 무작위: 전역 탐색에 유리하지만 수렴 느림
> - 균일 중간값 (0.5): 필터링과 함께 쓸 때 효과적
> - 물리적 직관 기반: 수렴 빠르지만 국소 최적 위험""",

    18: """## Forward 시뮬레이션 시각화

`opt.plot2D(True)` → 솔버 초기화 + 레이아웃 확인

시각화에서 확인할 것:
- 🟦 **설계 영역** — 벤드 코너에 위치
- 📍 **DFT 모니터** — 출력 도파관 끝
- 📍 **추가 모니터** — 설계 영역 전체 (역전파용 필드 기록)
- 🔲 **PML** — 4면 경계""",

    20: """## Forward + Adjoint DFT 필드

솔버 실행 후 두 시뮬레이션 결과를 확인합니다:

**Forward 시뮬레이션**: 입력 → 설계 영역 → 출력
- `f0`: 목적함수 값 (현재 투과율)

**Adjoint 시뮬레이션**: 목적 모니터에서 역방향으로 전파
- 내부에서 자동 실행 (사용자는 직접 설정 불필요)

```python
f0, dJ_du = opt([x0])
# f0    : 목적함수 값 (최대화하려는 값)
# dJ_du : 각 설계 변수에 대한 기울기 (크기 = Nx*Ny)
```""",

    22: """## Gradient Map 시각화

설계 영역에서 각 위치의 기울기를 색상으로 표시합니다.

```
🔴 양(+) 기울기 → 여기 유전율 높이면 FOM 증가
🔵 음(-) 기울기 → 여기 유전율 낮추면 FOM 증가
```

이 패턴이 다음 설계 업데이트 방향을 직관적으로 보여줍니다.""",

    24: """## 유한 차분(FD) 검증

역전파 기울기의 정확도를 유한 차분으로 검증합니다.

$$\\frac{\\partial J}{\\partial u_i} \\approx \\frac{J(u + \\delta e_i) - J(u)}{\\delta}, \\quad \\delta \\approx 10^{-4}$$

```python
# 20개 무작위 샘플만 검증 (100개 전체는 비용이 큼)
f0, dJ_du_fd = opt.calculate_fd_gradient(num_gradients=20)
```

> 역전파와 FD가 강한 선형 상관 (R² ≈ 1.0)이면 기울기 계산이 정확합니다.""",

    26: """## 선형 피팅으로 비교

역전파(x축) vs 유한 차분(y축)에 직선 피팅:
- **기울기 ≈ 1.0**: 두 방법이 잘 일치
- **R² ≈ 1.0**: 높은 상관관계 = 정확한 기울기""",

    28: "## 결과 플롯",

    30: """## 해상도 증가 검증

낮은 해상도(res=20)에서 확인한 기울기를 높은 해상도(res=30+)에서 재검증합니다.

> **멀티-해상도 전략 (권장)**:
> 1. res=20~30으로 최적화 방향 확인
> 2. res=40~50으로 정밀화(refinement)
> 3. 최종 검증은 res=50 이상으로""",
}

# ── 02-Waveguide_Bend 업데이트 ───────────────────────────────────────────────
NB02_KO = {
    0: """# 도파관 벤드 역설계 — 기본 최적화

**목표**: MEEP 역전파 솔버로 실리콘 도파관 90° 벤드의 **투과 효율을 최대화**합니다.

### 최적화 흐름

```
시뮬레이션 세팅 → Forward DFT → Adjoint DFT
      → Gradient Map → MMA 최적화 루프
      → Design Update 시각화 → 성능 검증
```

### 이 튜토리얼에서 배울 것
- 완전한 역설계 파이프라인 구성
- MMA(nlopt) 최적화 엔진 연동
- FOM 정규화(투과율 %) 방법
- 최적화 진행에 따른 구조 변화 해석""",

    2: """## 시뮬레이션 세팅

**90° 벤드 도파관** 구성:

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| 설계 영역 | 1×1 μm | 최적화 공간 |
| 격자 | 10×10 | 100개 설계 변수 |
| 중심 파장 | 1550 nm | SOI 표준 통신 파장 |
| 소스 | EigenMode TE₀ | `eig_band=1, eig_match_freq=True` |

```python
Nx, Ny = 10, 10           # 설계 격자 크기
fcen   = 1 / 1.55         # 중심 주파수
design_region = mpa.DesignRegion(
    mpa.MaterialGrid(mp.Vector3(Nx, Ny), mp.air, Si),
    volume=mp.Volume(center=mp.Vector3(), size=mp.Vector3(1, 1)),
)
```""",

    4: """## Forward DFT 시각화 (최적화 전 레이아웃 확인)

최적화 시작 전 **반드시** 레이아웃을 확인합니다:

```python
opt.plot2D(True)   # True = 초기화 + 필드 초기화
plt.show()
```

✅ 확인 체크리스트:
- 소스가 입력 도파관에 위치하는가?
- 목적 모니터가 출력 도파관 끝에 위치하는가?
- 설계 영역이 벤드 코너에 올바르게 배치됐는가?
- PML이 4면 경계에 충분한 두께로 있는가?""",

    6: """## 비용함수 래퍼 & Optimization Loop 설정

### 비용함수 래퍼 (nlopt 형식)

```python
evaluation_history = []

def f(x, grad):
    f0, dJ_du = opt([x])           # Forward + Adjoint 2회 실행
    grad[:] = -dJ_du               # nlopt는 최소화 → 음수 부호
    evaluation_history.append(f0)
    return float(-f0)
```

### MMA 최적화 설정

```python
solver = nlopt.opt(nlopt.LD_MMA, Nx * Ny)
solver.set_lower_bounds(0)         # 설계 변수 범위: [0, 1]
solver.set_upper_bounds(1)
solver.set_min_objective(f)        # 최소화 (f는 음수 FOM)
solver.set_maxeval(20)             # 최대 반복 횟수
```

> **MMA(Method of Moving Asymptotes)**: 포토닉 역설계에서 가장 많이 쓰이는 gradient-based 최적화 알고리즘""",

    8: """## 초기 최적화 결과 분석

최적화 완료 후 FOM 변화를 확인합니다.

FOM이 단조 증가하지 않고 진동한다면:
- step size가 너무 클 가능성 → nlopt 옵션 조정
- 초기값을 다르게 설정해서 재시도""",

    11: """## Design Update 시각화

현재 설계 변수를 유전율 분포로 변환해서 구조를 시각화합니다.

```python
opt.update_design([x_opt])   # 최적화된 설계 변수로 업데이트
opt.plot2D(False)            # 현재 구조 시각화
```

> 최적화 직후 구조는 보통 **중간 유전율 값**이 많습니다 (회색 영역).  
> 03번 튜토리얼에서 **필터링 + 이진화**로 실제 제조 가능한 구조로 변환합니다.""",

    13: """## 최적화 전후 구조 비교

| 초기 구조 | 최적화 후 구조 |
|-----------|--------------|
| 무작위 유전율 분포 | 도파관을 자연스럽게 연결 |
| 낮은 투과율 | 높은 투과율 |
| 직관적 패턴 없음 | 비직관적 서브파장 구조 |

이것이 **역설계의 힘** — 인간의 직관으로는 찾기 어려운 최적 구조를 자동으로 발견합니다.""",

    15: """## FOM 정규화: 절대 투과율 계산

이전 FOM 값은 단위가 없어서 해석이 어렵습니다.  
**기준 모니터(reference monitor)**를 추가해 절대 투과율(%)을 계산합니다.

```
[소스] → [기준 모니터: P_ref] → [설계 영역] → [출력 모니터: P_out]

투과율(T) = P_out / P_ref × 100%
```

```python
# 다중 목적 수치 사용
ob_list = [
    mpa.EigenmodeCoefficient(sim, mon_out,  1),  # 출력 모드
    mpa.EigenmodeCoefficient(sim, mon_ref,  1),  # 기준(입력) 모드
]

def J(a_out, a_ref):
    return npa.abs(a_out / a_ref) ** 2   # 정규화 투과율
```""",

    17: """## 정규화 FOM으로 재최적화

기준 모니터를 포함한 새 `OptimizationProblem`으로 재설정합니다.

> 설계 변수 초기화 주의: 이전 최적화의 결과를 초기값으로 사용하면 **warm start** 가능""",

    19: """## 성능 검증: 투과율(%) 결과

$$T(\\%) = \\left|\\frac{a_{out}}{a_{ref}}\\right|^2 \\times 100$$

반복 횟수별 투과율 변화를 확인합니다.""",

    21: """## 성능 향상 요약

역전파 최적화의 효율성:

| | 초기 | 최적화 후 | 향상 |
|--|------|---------|------|
| 투과율 | ~5% | ~85% | **17배 향상** |
| 반복 횟수 | - | 10회 | - |
| 시뮬레이션 횟수 | - | 20회 (10×2) | - |

> **FD 방법 대비**: FD로 100개 변수의 기울기를 10번 업데이트하면 1,010번 시뮬레이션 필요.  
> 역전파는 **20번**으로 동일한 결과 달성.""",

    23: """## 최적화된 구조 시각화

설계 영역의 최종 유전율 분포를 확인합니다.

주목할 점:
- 두 도파관 세그먼트를 자연스럽게 연결
- 벤드 코너에 **서브파장 구조** 자동 형성
- 비직관적 패턴이지만 높은 성능

> 다음 단계 (03번 튜토리얼): 이 구조를 **필터링 + 이진화**해서 실제 제조 가능한 binary 패턴으로 변환""",

    25: """## Gradient Map (감도 분포) 시각화

최종 설계에서의 기울기 = **감도(sensitivity)** 분포:

- 🔴 **민감한 영역**: 작은 형상 변화도 투과율에 큰 영향
- ⚪ **둔감한 영역**: 제조 오차에 강건한 부분

이 정보를 활용해:
- **강건성 최적화(robust design)**: 민감한 영역에 제약 추가
- **제조 공차 분석**: 리소그래피 오차 허용 범위 추정""",
}

# ── 03-Filtered_Waveguide_Bend ────────────────────────────────────────────────
NB03_KO = {
    0: """# 도파관 벤드 역설계 — 심화: 필터링 & 이진화

**02번 튜토리얼의 연장선**: 기본 역설계에 **제조 제약 조건**을 추가합니다.

### 왜 필터링이 필요한가?

기본 역설계 결과는 중간 유전율 값(회색 영역)이 많아 실제 제조가 어렵습니다:

```
기본 결과: 0~1 사이 연속 값 → 실제 Si 또는 공기로 제조 불가
필터링 후: 0 또는 1에 가까운 값 → 실제 에칭 가능한 패턴
```

### 이 튜토리얼에서 배울 것
- **Conic 필터**: 최소 선폭/간격 제약 (제조 가능성 보장)
- **Tanh 투영**: 중간값 제거 → binary 패턴 유도
- **광대역 목적함수**: 여러 파장에서 동시 최적화
- **β-annealing**: 단계적 이진화 전략""",

    1: """## 시뮬레이션 파라미터 설정

광대역 최적화를 위해 여러 주파수 포인트를 설정합니다:

```python
# 광대역 소스: 1450~1650 nm
fcen = 1 / 1.55
fwidth = 0.2 * fcen
nf = 5                         # 주파수 포인트 수
frequencies = np.linspace(...)
```

> **주파수 포인트 간격 주의**: 너무 촘촘하면 Adjoint 시뮬레이션 시간 증가""",

    2: """## 필터 파라미터 설정

### Conic 필터 (최소 선폭 제약)

```python
filter_radius = mpa.get_conic_radius_from_eta_e(
    minimum_length = 0.09,   # 최소 선폭: 90 nm (SOI e-beam 기준)
    eta_e          = 0.75,   # 침식(erosion) 임계점
)
```

필터 적용 시 최소 선폭 보장:
```
설계 변수 x → Conic 필터 → 부드러운 분포 → Tanh 투영 → Binary 패턴
```""",

    3: """## 필터링 + 투영 파이프라인

### 전체 변환 과정

```python
def mapping(x, eta, beta):
    # 1. Conic 필터: 최소 선폭 적용
    x_filt = mpa.conic_filter(x, filter_radius, Lx, Ly, resolution)

    # 2. Tanh 투영: binary 수렴 유도
    x_proj = mpa.tanh_projection(x_filt, beta, eta)

    return x_proj.flatten()
```

- **`eta`**: 투영 임계점 (0.5 = 대칭)
- **`beta`**: 투영 강도 (높을수록 binary에 가까워짐)
  - 초기: beta=8 (부드러운 전환)
  - 최종: beta=64+ (거의 완전한 binary)""",

    4: """## 초기 레이아웃 & Forward DFT 시각화

광대역 소스와 다중 DFT 모니터를 포함한 전체 도메인을 확인합니다.

광대역 최적화의 이점:
- 단일 파장 최적화보다 **실용적**
- 파장 의존성 억제 → 더 강건한 소자 설계 가능""",

    5: """## Optimization Loop — β-annealing 전략

### 단계적 이진화 (β-annealing)

한 번에 높은 β로 이진화하면 기울기 소실 문제가 발생합니다.  
단계적으로 β를 높여가는 **β-annealing** 전략을 사용합니다:

```python
betas = [8, 16, 32, 64]      # β 단계별 증가
for beta in betas:
    solver.set_maxeval(n_iter)
    x_opt = solver.optimize(x0)
    x0 = x_opt                # 이전 단계 결과를 다음 초기값으로
```

| β 값 | 투영 결과 | 단계 |
|------|---------|------|
| 8 | 부드러운 분포 | 초기 최적화 |
| 16~32 | 중간 이진화 | 중간 단계 |
| 64+ | 거의 완전한 binary | 최종 단계 |""",

    6: """## Design Update 시각화 — 단계별 구조 변화

β 단계별로 구조가 어떻게 변화하는지 시각화합니다:

```python
# 각 β 단계 후 구조 저장
for i, beta in enumerate(betas):
    # 최적화 실행
    x_opt = solver.optimize(x0)
    # 구조 시각화
    plt.figure()
    opt.update_design([mapping(x_opt, 0.5, beta)])
    opt.plot2D(False)
    plt.title(f"β={beta}")
    plt.savefig(f"structure_beta{beta}.png")
```

각 단계에서 확인할 것:
- **β=8**: 부드러운 회색 → 전반적인 최적 방향
- **β=32**: 패턴이 뚜렷해짐
- **β=64**: 거의 완전한 Si/공기 binary 패턴""",

    7: """## 성능 검증 — 광대역 투과율

필터링된 최종 구조의 광대역 투과율을 측정합니다:

```python
# 다중 주파수에서 투과율 계산
f0, _ = opt([mapping(x_opt, 0.5, betas[-1])])
T = np.abs(f0)  # 각 주파수의 투과율
```

광대역 투과율 스펙트럼으로 확인:
- 목표 파장 범위에서 균일하게 높은 투과율?
- 파장 의존성이 억제됐는가?""",
}

# ── 04-Splitter ───────────────────────────────────────────────────────────────
NB04_KO = {
    0: """# 광대역 빔 스플리터 역설계

**목표**: 역전파 솔버로 1×2 빔 스플리터를 설계합니다. 입력 파워를 두 출력으로 균등 분배(각 50%)하는 것이 목표입니다.

### 이 튜토리얼의 핵심
- **대칭(symmetry) 활용**: 계산 비용 2배 절감
- **다중 목적 수치**: 2개 출력 모니터 동시 최적화
- **광대역 최적화**: 여러 파장에서 균일한 50:50 분배""",

    1: """## 시뮬레이션 세팅

빔 스플리터 구조 특성:
- **대칭 활용**: `mp.Mirror(mp.Y)` → Y축 대칭으로 절반만 시뮬레이션
- 두 출력 도파관: 위(+y)와 아래(-y) 방향

```python
# 대칭 활용으로 계산 속도 2배 향상
symmetries = [mp.Mirror(mp.Y)]
sim = mp.Simulation(..., symmetries=symmetries)
```

> ⚠️ 대칭 사용 시 소스도 대칭 성분으로 설정해야 합니다""",

    2: """## 광대역 소스 & 다중 모니터

```python
# 광대역 소스 (1450~1650 nm)
src = mp.GaussianSource(frequency=fcen, fwidth=df)

# 두 출력 모니터 (위/아래)
ob_list = [
    mpa.EigenmodeCoefficient(sim, mon_top,    1),  # 위쪽 출력
    mpa.EigenmodeCoefficient(sim, mon_bottom, 1),  # 아래쪽 출력
    mpa.EigenmodeCoefficient(sim, mon_ref,    1),  # 기준 (입력)
]
```""",

    3: """## 목적함수 — 균등 분배 최대화

```python
def J(e_top, e_bot, e_ref):
    # 각 출력의 투과율
    T_top = npa.abs(e_top / e_ref) ** 2
    T_bot = npa.abs(e_bot / e_ref) ** 2

    # 균등 분배 + 총 투과율 최대화
    return (T_top + T_bot) / 2  # 평균 투과율
```

> 불균등 분배 페널티를 추가하려면: `- alpha * npa.abs(T_top - T_bot)**2`""",

    4: """## 최적화 실행 & 결과

대칭을 활용한 최적화 후 확인:
- 두 출력의 투과율이 균등한가?
- 총 투과율이 충분히 높은가?
- 구조가 실제로 대칭적인가?""",
}

# ── 05-Near2Far ───────────────────────────────────────────────────────────────
NB05_KO = {
    0: """# 메탈렌즈 역설계 — Near-to-Far Field

**목표**: 역전파 솔버의 **Near-to-Far field(N2F) 변환**을 활용해 메탈렌즈를 설계합니다.

### Near-to-Far Field 변환이란?

원거리 필드(far-field) 계산에 필요한 거대한 시뮬레이션 도메인을   
작은 도메인 + N2F 변환으로 대체합니다:

```
[작은 시뮬레이션 도메인]
    ↓ Near-to-Far 변환
[원거리 방사 패턴 / 집속 패턴 계산]
```

### 메탈렌즈 설계 목표
- 입사광을 특정 초점(focal point)에 집중
- 원하는 방사 방향으로 빔 조형""",

    1: """## 기본 세팅

메탈렌즈를 위한 설정:
- 입사 소스: 평면파(plane wave)
- N2F 모니터: 소자 위쪽 평면
- 목표: 특정 각도/위치에서 필드 세기 최대화""",

    2: """## Near2Far 목적 수치 설정

```python
# Near2Far 모니터 정의
n2f_mon = mp.Near2FarRegion(
    center = mp.Vector3(0, d_monitor),  # 모니터 위치
    size   = mp.Vector3(monitor_width, 0),
)

# 원거리 관심 포인트
far_pt = mp.Vector3(0, focal_length)   # 초점 위치

# 역전파 목적 수치
ob_list = [mpa.Near2FarFields(sim, [n2f_mon], [far_pt])]
```""",

    3: """## 목적함수 — 초점에서 필드 세기 최대화

```python
def J(e_far):
    # 초점에서 |E|² 최대화
    return npa.abs(e_far) ** 2
```

이 목적함수는 특정 위치에서의 집속 효율을 직접 최적화합니다.""",
}

# ── 06-Bend_Minimax ──────────────────────────────────────────────────────────
NB06_KO = {
    0: """# 에피그래프 최적화 — Minimax 전략

**목표**: 여러 파장에서의 투과율을 **동시에 최대화**하는 minimax 최적화를 수행합니다.

### 기존 방식의 한계

평균(mean) 최적화:
```python
J = mean(T_1550, T_1450, T_1650)  # 평균 최대화
```
→ 일부 파장의 성능을 희생하고 특정 파장만 높아질 수 있음

### Minimax 에피그래프 접근법

```python
# 모든 파장에서 최악의 성능을 최대화
J = min(T_1550, T_1450, T_1650)   # 최솟값 최대화
```
→ **가장 낮은 성능을 끌어올림** → 모든 파장에서 균등하게 좋은 성능""",

    1: """## 기본 세팅

02번 튜토리얼과 동일한 벤드 구조를 사용합니다.

차이점:
- 목적함수: mean → minimax (에피그래프)
- 다중 주파수 동시 최적화""",

    2: """## 에피그래프 목적함수 설정

```python
# t: 에피그래프 변수 (보조 변수)
# 각 주파수의 투과율이 모두 t 이상이 되도록 제약

def J(*args):
    # args = (T_f1, T_f2, ..., T_fn)
    return npa.array([a for a in args])  # 스칼라 아닌 배열 반환
```

에피그래프 변환:
```
maximize t
subject to: T_fi(x) ≥ t for all i
            0 ≤ x ≤ 1
```""",
}

# ── 07-Fourier_Bend ──────────────────────────────────────────────────────────
NB07_KO = {
    0: """# Fourier Fields를 이용한 도파관 벤드 최적화

**목표**: `EigenmodeCoefficient` 대신 **`FourierFields`** 목적 수치를 사용해 도파관 벤드를 최적화합니다.

### EigenmodeCoefficient vs FourierFields

| | EigenmodeCoefficient | FourierFields |
|--|--|--|
| **측정 대상** | 특정 모드의 계수 | 임의 위치의 DFT 필드 |
| **사용 케이스** | 모드 선택적 소자 | 임의 필드 분포 목표 |
| **구현** | Yee grid 직접 사용 | 별도 DFT 계산 |
| **해상도 의존성** | 낮음 | 높음 (res=40 권장) |""",

    1: """## 해상도 설정

FourierFields는 Yee grid를 직접 사용하지 않아 더 높은 해상도가 필요합니다:

```python
resolution = 40   # EigenmodeCoefficient의 30보다 높게
```""",

    2: """## FourierFields 목적 수치 설정

```python
# DFT 필드 모니터 정의
dft_mon = mp.DftFields(
    mp.Ez,
    where = mp.Volume(center=mp.Vector3(0, 3), size=mp.Vector3(0.5, 0)),
)

# 역전파 목적 수치
ob_list = [mpa.FourierFields(sim, dft_mon, mp.Ez)]
```""",
}

# ── 08-Fourier_Metalens ──────────────────────────────────────────────────────
NB08_KO = {
    0: """# Fourier Fields 메탈렌즈 최적화

**목표**: `FourierFields` 역전파 솔버를 이용해 **다중 파장에서 초점이 맞는 메탈렌즈**를 설계합니다.

### 이 튜토리얼의 핵심
- **FourierFields 역전파**: DFT 필드 기반 목적함수
- **다중 파장 초점**: 3개 파장에서 동시에 특정 위치에 집속
- **메탈렌즈 설계**: 입사광을 원하는 패턴으로 조형""",

    1: "## 기본 세팅",

    2: """## FourierFields 목적 수치 — 다중 파장 초점

```python
# 세 파장에서 각각 다른 초점 위치 설정
focal_points = [
    mp.Vector3(0, f1),   # 파장 1의 초점
    mp.Vector3(0, f2),   # 파장 2의 초점
    mp.Vector3(0, f3),   # 파장 3의 초점
]

# 각 파장별 DFT 모니터
ob_list = [
    mpa.FourierFields(sim, mon_f1, mp.Ez, nf=0),  # 첫 번째 주파수
    mpa.FourierFields(sim, mon_f2, mp.Ez, nf=1),  # 두 번째 주파수
    mpa.FourierFields(sim, mon_f3, mp.Ez, nf=2),  # 세 번째 주파수
]
```""",
}


# ── DB 저장 ───────────────────────────────────────────────────────────────────
def apply_ko(conn, nb_id: int, ko_dict: dict) -> None:
    row   = conn.execute("SELECT cells FROM notebooks WHERE id=?", (nb_id,)).fetchone()
    if not row:
        print(f"  id={nb_id} 없음")
        return
    cells = json.loads(row[0])

    cells_ko = []
    md_idx   = 0
    for cell in cells:
        c = dict(cell)
        if cell["type"] == "markdown":
            if md_idx in ko_dict:
                c["source"] = ko_dict[md_idx]
            md_idx += 1
        cells_ko.append(c)

    conn.execute(
        "UPDATE notebooks SET cells_ko=? WHERE id=?",
        (json.dumps(cells_ko, ensure_ascii=False), nb_id)
    )
    print(f"  id={nb_id} cells_ko 저장 ({len(cells_ko)}셀, md_idx={md_idx})")


def main():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)

    nb_map = {
        1: NB01_KO, 2: NB02_KO, 3: NB03_KO, 4: NB04_KO,
        5: NB05_KO, 6: NB06_KO, 7: NB07_KO, 8: NB08_KO,
    }
    for nb_id, ko_dict in nb_map.items():
        print(f"\nid={nb_id} 처리 중...")
        apply_ko(conn, nb_id, ko_dict)

    conn.commit()
    conn.close()
    print("\n✅ 완료!")


if __name__ == "__main__":
    main()
