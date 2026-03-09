# -*- coding: utf-8 -*-
import sqlite3

DB_PATH = '/app/db/knowledge.db'

descriptions = {}

# ── 337: antenna-radiation.py (smartalecH) ──────────────────────────────────
descriptions[337] = """## 안테나 방사 패턴 (Dipole Antenna Radiation Pattern)

### 물리적 배경
점 쌍극자 안테나(point dipole antenna)에서 방출되는 전자기파의 공간 방사 패턴을 FDTD로 계산합니다. 자유공간에 놓인 Ez 성분의 전기 쌍극자 소스는 이론적으로 sin²θ 의존성을 가지는 토로이달(toroidal) 방사 패턴을 나타냅니다. 이 시뮬레이션의 핵심은 **near-to-far-field (NF2FF) 변환**으로, 근거리 DFT 필드를 Huygens 원리 기반으로 원거리 방사 패턴으로 변환합니다. 이는 계산 셀이 유한하더라도 무한 공간의 방사 패턴을 정확히 얻을 수 있는 핵심 기법입니다.

### 시뮬레이션 세팅
- **셀 크기**: (4+2×1)μm = 6μm × 6μm (정사각형 2D)
- **해상도**: 50 pixels/μm → 파장 λ=1μm일 때 픽셀 50개/파장 (충분히 정밀)
- **PML**: 두께 1μm, 4방향 적용 → 반사 없는 흡수 경계
- **소스**: 가우시안 펄스 (fcen=1.0, df=0.4), Ez 성분 → TE 편광 쌍극자
- **소스 위치**: 셀 중심 (0, 0) → 전방향 균일 방사를 위한 배치

### 핵심 MEEP API
- `mp.GaussianSource(fcen, fwidth)`: 광대역 주파수 응답 획득용 가우시안 시간 펄스
- `sim.add_near2far()`: 근거리 → 원거리 변환 모니터 추가. `mp.Near2FarRegion`으로 박스 또는 선분 정의
- `sim.get_farfields()`: 지정된 각도에서 원거리 E, H 필드 계산
- `mp.Farfield`: 방사 강도 I ∝ |E|² 계산에 사용
- `np.angle`: 각도 배열 생성 (0~2π)

### 결과 해석
극좌표 그래프(polar plot)에서 방사 패턴은 이론적 sin²θ와 일치하는 8자형(figure-8) 모양을 보입니다. Ez 소스는 z축을 대칭축으로 하므로 2D에서는 xy 평면상 방사가 균일하게 나타나며, 이 시뮬레이션에서는 TE 모드의 방위각 의존성을 직접 확인합니다. 시뮬레이션 결과와 이론값의 오차는 NF2FF 모니터 위치 및 PML 반사율에 의존합니다.

### 연구 활용
SOI 포토닉스에서 광원(LED, 레이저 다이오드) 방사 패턴 모델링, 광자 결정 슬래브에서의 방사 손실 계산, 안테나-인-패키지(AiP) 설계, 나노안테나 방향성(directivity) 최적화에 직접 응용됩니다. NF2FF 기법은 역설계 목적함수에서 원거리 빔 패턴 제약 조건 구현에도 활용됩니다.
"""

# ── 348: oblique-planewave.py (smartalecH) ──────────────────────────────────
descriptions[348] = """## 경사 입사 평면파 (Oblique Incidence Plane Wave)

### 물리적 배경
평면파(plane wave)를 특정 각도(θ)로 경사 입사시키는 시뮬레이션입니다. 광학 필터, 격자 분광기, 경사 입사 반사율/투과율 계산에 필수적인 기법입니다. 핵심 원리는 **블로흐 경계 조건(Bloch boundary conditions)**을 이용해 k벡터의 x성분(k_x = n·f·sinθ)을 구현하는 것입니다. 이때 소스 위상을 위치에 따라 exp(ik_x·x)로 변조하여 원하는 입사각을 실현합니다.

### 시뮬레이션 세팅
- **셀 크기**: 14μm(X) × 10μm(Y), 2D
- **PML**: X방향만 두께 2μm → Y방향은 블로흐 주기 경계
- **해상도**: 50 pixels/μm
- **소스**: CW(연속파) 또는 가우시안 펄스, 회전 각도 rot_angle 파라미터로 제어
- **경계 조건**: `mp.k_point = mp.Vector3(kx, 0, 0)` 설정으로 블로흐 위상 적용

### 핵심 MEEP API
- `mp.k_point`: 블로흐 파수 벡터 설정. 균일 매질에서 경사 평면파 구현의 핵심
- `EigenModeSource`: 특정 k 방향의 고유모드 소스 (더 정확한 경사 입사)
- `np.radians(rot_angle)`: 회전 각도 → 라디안 변환
- `kx = fcen * np.sin(rot_angle)`: x방향 블로흐 파수 계산 공식

### 결과 해석
시뮬레이션 결과 이미지는 경사 입사된 평면파의 위상 전면(wavefront)을 보여줍니다. 위상 전면이 X축과 이루는 각도가 입력한 rot_angle과 일치하면 소스 설정이 올바른 것입니다. 균일 매질에서는 파면이 직선을 유지해야 하며, 계면에서는 스넬 법칙에 따른 굴절을 확인할 수 있습니다.

### 연구 활용
SOI 포토닉스에서 각도 의존 반사율/투과율 측정(예: 편광 분리기, 빔 스티어링 소자), 격자 커플러의 최적 입사각 설계, 메타서피스의 위상 프로필 검증, 포토닉 결정에서의 밴드 구조 관련 각도 응답 분석에 활용됩니다.
"""

# ── 363: bend-flux.py (smartalecH) ──────────────────────────────────────────
descriptions[363] = """## 90도 도파관 벤드 투과율 (Waveguide 90° Bend Transmission)

### 물리적 배경
2D 직사각형 도파관의 90도 급격한 벤드(abrupt bend)에서 전자기파의 투과율(transmission)과 반사율(reflection)을 계산합니다. 도파관 도파 모드가 벤드를 통과할 때 발생하는 산란 손실을 정량화하는 것이 목표입니다. 이는 포토닉 집적 회로(PIC) 설계에서 핵심 요소로, 실제 SOI 도파관 설계에서 최적 벤드 반경 결정의 기초가 됩니다. Poynting 정리에 기반한 **파워 플럭스 계산**을 사용합니다.

### 시뮬레이션 세팅
- **셀 크기**: 16μm(X) × 32μm(Y), 2D
- **해상도**: 10 pixels/μm (빠른 계산용, 정밀 계산 시 50 이상 권장)
- **PML**: 두께 1μm, 4방향
- **재료**: ε=11.56 (Si에 근사) 도파관, 너비 1μm
- **소스**: CW Gaussian, 도파관 입력단에 Ez 라인 소스
- **플럭스 모니터**: 입력 기준 플럭스(직선 도파관)와 벤드 투과 플럭스 비교

### 핵심 MEEP API
- `sim.add_flux()`: DFT 파워 플럭스 모니터 추가. `mp.FluxRegion`으로 단면 정의
- `sim.get_flux_data()` / `sim.load_minus_flux_data()`: 반사율 계산용 기준 플럭스 저장/차감
- `mp.get_fluxes()`: 각 주파수에서 플럭스 값 배열 반환
- **규격화**: 직선 도파관 시뮬레이션을 먼저 실행해 기준값 얻은 후, 벤드 시뮬레이션과 비교

### 결과 해석
출력 그래프는 주파수 또는 파장에 대한 투과율(T)과 반사율(R)을 보여줍니다. 이상적인 경우 T+R=1이어야 하며, 손실(1-T-R)은 산란 또는 방사 손실을 의미합니다. 급격한 90도 벤드에서는 일반적으로 투과율이 70-90% 수준을 보이며, 벤드를 곡선으로 최적화하면 99% 이상 달성 가능합니다.

### 연구 활용
SOI 220nm 플랫폼에서 도파관 라우팅 최적화, 포토닉 집적 회로(PIC) 벤드 손실 최소화 설계, 역설계(topology optimization)를 통한 벤드 구조 최적화의 기준값 제공에 직접 활용됩니다. PROJ-002 모드 컨버터 및 테이퍼 설계에서 벤드 구간 손실 평가에도 적용 가능합니다.
"""

# ── 380: straight-waveguide.py (smartalecH) ─────────────────────────────────
descriptions[380] = """## 직선 도파관 기초 (Straight Waveguide - MEEP 튜토리얼 기초)

### 물리적 배경
MEEP 입문 예제로, 2D 직선 도파관에서 전자기파 전파를 시각화합니다. 도파관은 높은 유전율 재료(ε=12, Si 근사)가 낮은 유전율 재료(공기, ε=1)에 둘러싸인 구조로, 전반사(total internal reflection)에 의해 빛이 코어 내부에 갇혀 진행합니다. 이 예제는 MEEP의 기본 워크플로우(셀 정의 → 지오메트리 → 소스 → 시뮬레이션 → 출력)를 완전히 보여줍니다.

### 시뮬레이션 세팅
- **셀 크기**: 16μm(X) × 8μm(Y), 2D (z=0 평면)
- **해상도**: 10 pixels/μm
- **PML**: 1μm 두께 (기본 4방향)
- **지오메트리**: `mp.Block` — 너비 1μm, x방향 무한 길이, ε=12
- **소스**: `mp.ContinuousSource` (fcen=0.15) 또는 가우시안 펄스, Ez 성분, 도파관 내부 배치

### 핵심 MEEP API
- `mp.Block(size, center, material)`: 직육면체 기하학적 객체 정의. `mp.inf`는 무한 길이
- `mp.Medium(epsilon=12)`: 단순 비분산 유전체 재료 정의
- `sim.run(mp.at_every(0.6, mp.output_efield_z), until=200)`: 정해진 시간 간격으로 Ez 필드 출력
- `sim.plot2D()`: 셀 레이아웃(유전율 분포 + 소스 위치 + 모니터) 시각화
- `mp.output_png`: 필드 시각화 이미지 생성 (h5py 또는 matplotlib 사용)

### 결과 해석
세 개의 이미지를 생성합니다: (1) 유전율 분포 — 고유전율 도파관 코어가 밝게 표시됨, (2) Ez 필드 스냅샷 — 도파관을 따라 진행하는 TE 모드의 정상파 패턴, (3) 시간 평균 강도 — 도파관 내부에 에너지가 집중된 안내 모드 프로파일. PML 영역에서 반사 없이 필드가 흡수되는 것을 확인합니다.

### 연구 활용
MEEP 환경 검증의 첫 번째 단계로 필수적인 예제입니다. 이 기초 위에 역설계 시뮬레이션, 모드 분해(EigenModeSource), DFT 모니터 등 고급 기능을 추가합니다. SOI 도파관 단면 최적화(너비, 높이 파라미터 스윕)의 출발점으로 활용됩니다.
"""

# ── 383: gaussian-beam.py (smartalecH) ──────────────────────────────────────
descriptions[383] = """## 가우시안 빔 전파 (Gaussian Beam Propagation)

### 물리적 배경
가우시안 빔은 레이저 출력의 이상적인 TEM₀₀ 모드로, 빔 웨이스트(beam waist) w₀에서 최소 크기를 가지며 레일리 거리(Rayleigh length) z_R = πw₀²/λ 특성을 가집니다. MEEP에서 가우시안 빔은 `GaussianBeamSource`를 이용해 실제 복소 빔 프로파일(위상 곡률 포함)을 소스 평면에 인가합니다. 이는 단순 평면파와 달리 회절(diffraction)과 집속(focusing) 특성을 정확히 재현합니다.

### 시뮬레이션 세팅
- **셀 크기**: 14μm × 14μm, 2D
- **해상도**: 50 pixels/μm
- **PML**: 두께 2μm
- **소스**: `mp.GaussianBeamSource` — 빔 웨이스트 위치(beam_x0), 빔 반경(beam_w0), 전파 방향(beam_kdir) 지정
- **빔 파라미터**: beam_x0=(0,3.0)는 소스로부터 3μm 위에 포커스, 자유공간 전파

### 핵심 MEEP API
- `mp.GaussianBeamSource(src, component, beam_x0, beam_kdir, beam_w0, beam_E0)`:
  - `beam_x0`: 빔 웨이스트 위치 (포커스 점)
  - `beam_kdir`: 전파 방향 단위벡터
  - `beam_w0`: 빔 웨이스트 반경 w₀
  - `beam_E0`: 편광 벡터
- `sim.plot2D()`: 필드 분포 + 소스 위치 시각화

### 결과 해석
이미지에서 가우시안 빔이 웨이스트 위치에서 집속되었다가 발산하는 모래시계 형태의 강도 분포를 볼 수 있습니다. 회절 한계(diffraction limit)에 의해 빔 웨이스트가 작을수록 발산 각도가 커지며, 이 트레이드오프가 가우시안 빔의 핵심 특성입니다. PML에서 빔이 반사 없이 흡수되는지 확인하는 것이 중요합니다.

### 연구 활용
광섬유-칩 커플링(fiber-to-chip coupling), 격자 커플러(grating coupler) 설계에서 자유공간 빔과 도파관 모드의 결합 효율 계산, 집속 이온 빔(FIB) 또는 레이저 가공 시뮬레이션, 포토닉 신경망의 자유공간 레이어 설계에 활용됩니다.
"""

# ── 394: faraday-rotation.py (smartalecH) ───────────────────────────────────
descriptions[394] = """## 패러데이 회전 (Faraday Rotation in Gyrotopic Medium)

### 물리적 배경
패러데이 회전은 자기광학(magneto-optical) 효과로, 선형 편광된 빛이 외부 자기장이 인가된 자이로트로픽(gyrotropic) 매질을 통과할 때 편광면이 회전하는 현상입니다. 이는 MEEP에서 비대칭 유전율 텐서(off-diagonal 성분 존재)를 가진 매질로 모델링됩니다. 자이로트로픽 로렌츠 모델: ε_xy = -ε_yx = iσ_n B₀/(f₀² - f² - iγf) 형태의 분산 관계를 가집니다.

### 시뮬레이션 세팅
- **매질 파라미터**: ε_n=1.5 (배경 유전율), f₀=1.0 (공진 주파수), γ=1e-6 (감쇠율), σ_n=0.1, B₀=0.15 (외부 자기장)
- **셀**: 1D 전파 (z방향)
- **소스**: Ex 편광 CW 평면파 → 자이로트로픽 매질 통과 후 Ey 성분 생성 여부 확인
- **재료**: `mp.Medium(epsilon=..., mu_offdiag=...)` 또는 분산 자이로트로픽 매질 설정

### 핵심 MEEP API
- `mp.Medium(epsilon_diag, epsilon_offdiag)`: 비대칭 유전율 텐서 정의
- `mp.GyrotropicLorentzianSusceptibility`: 자이로트로픽 로렌츠 분산 추가
- `sim.get_array(component=mp.Ex/Ey)`: 공간상 Ex, Ey 필드 분포 추출
- `np.arctan2(Ey, Ex)`: 편광각 계산 → 패러데이 회전각 θ_F 측정

### 결과 해석
두 이미지는 각각 (1) Ex, Ey 필드 공간 분포와 (2) 위치에 따른 편광 회전각(도)을 보여줍니다. 자이로트로픽 매질 내부에서 편광이 선형으로 회전(패러데이 회전각 α = VBd, V: Verdet 상수)하는 것을 확인합니다. 이론값과의 비교로 MEEP 자기광학 구현의 정확성을 검증합니다.

### 연구 활용
광학 아이솔레이터(optical isolator), 써큘레이터(circulator), 자기광학 변조기 설계에 직접 응용됩니다. 특히 SOI 플랫폼에 통합된 자기광학 소자 시뮬레이션, 포토닉 집적 회로에서 비가역(non-reciprocal) 소자 구현 연구에 핵심적인 기법입니다.
"""

# ── 401: absorbed_power_density.py (smartalecH) ─────────────────────────────
descriptions[401] = """## 흡수 파워 밀도 (Absorbed Power Density in SiO₂ Cylinder)

### 물리적 배경
분산성 재료(SiO₂)로 만들어진 실린더에 평면파가 입사될 때 재료 내부의 **흡수 파워 밀도(absorbed power density)**를 계산합니다. 복소 유전율 ε = ε' + iε''을 가진 손실 매질에서 흡수된 전력은 P_abs = ½ Re(J·E*) = (ω/2) Im(ε) |E|²으로 주어집니다. 이는 나노포토닉스에서 광열(photothermal) 효과, 광기계(optomechanical) 응용, 광전 변환 효율 계산에 핵심적입니다.

### 시뮬레이션 세팅
- **해상도**: 100 pixels/μm (고정밀 재료 분산 계산 필요)
- **PML**: 두께 1μm
- **재료**: `meep.materials.SiO₂` — 실제 분산 데이터(Sellmeier 계수) 포함
- **지오메트리**: 반지름 r=1μm 실린더, 공기 패딩 2μm
- **소스**: CW 평면파 (1D → 2D 확장 적용)

### 핵심 MEEP API
- `meep.materials.SiO2`: 내장 분산 재료 라이브러리 활용
- `sim.add_dft_fields()`: DFT E, H 필드 저장 → 흡수 파워 계산
- `sim.get_dft_array()`: 특정 주파수에서 DFT 필드 배열 추출
- 흡수 파워: `P = 0.5 * omega * np.imag(eps) * np.abs(E)**2`
- `sim.flux_in_box()` 또는 `sim.electric_energy_in_box()`: 총 흡수 파워 계산

### 결과 해석
두 이미지는 각각 (1) 실린더 내부 및 주변의 전기장 강도 분포와 (2) 흡수 파워 밀도 공간 분포를 보여줍니다. 실린더 내부에서 공진(Mie 공진)에 의한 필드 증강이 일어나면 흡수 파워 밀도가 국소적으로 크게 증가합니다. 색상 스케일은 파워 밀도의 상대적 크기를 나타냅니다.

### 연구 활용
나노입자 광가열(plasmonic heating), 광학 트래핑(optical trapping) 힘 계산, 태양전지 활성층 흡수 효율 최적화, 광열 치료(photothermal therapy)용 나노입자 설계 시뮬레이션에 활용됩니다. 역설계에서 흡수 최대화 또는 최소화 목적함수 구현의 기초가 됩니다.
"""

# ── 402: finite_grating.py (smartalecH) ─────────────────────────────────────
descriptions[402] = """## 유한 격자 산란 (Finite Grating Scattering)

### 물리적 배경
유한한 수의 주기를 가진 격자(finite grating)에서 평면파 산란을 계산합니다. 무한 주기 격자와 달리, 유한 격자는 가장자리 효과(edge effects)와 회절 차수 간 결합이 발생합니다. 격자 방정식: sin(θ_m) = sin(θ_i) + mλ/Λ (m: 회절 차수, Λ: 격자 주기)에 따라 여러 방향으로 빛이 회절됩니다. 이 시뮬레이션은 산란된 필드만 추출하기 위해 **total-field/scattered-field (TFSF)** 접근법을 사용합니다.

### 시뮬레이션 세팅
- **해상도**: 50 pixels/μm
- **격자 파라미터**: 주기 gp=10μm, 높이 gh=0.5μm, 채움비 gdc=0.5, 기판 두께 dsub=3μm
- **재료**: Si (n≈3.45) 격자, SiO₂ 기판
- **field_profile=True**: 공기 영역의 산란 필드 프로파일 계산
- **PML**: X방향만 적용, Y방향은 주기 경계(Bloch)

### 핵심 MEEP API
- `mp.Source`와 위상 변조: 특정 각도 입사 구현
- `sim.add_flux()`: 각 회절 차수 방향으로 플럭스 모니터 배치
- `sim.get_array(component=mp.Ez)`: 공간 필드 배열 추출
- **near2far**: 유한 격자의 원거리 회절 패턴 계산에 활용

### 결과 해석
이미지는 격자 위 공기 영역에서 산란된 Ez 필드를 보여줍니다. 격자 구조에서 0차(정반사), ±1차, ±2차 회절이 각도에 따라 나뉘어 진행하는 것을 확인합니다. 격자의 양 끝 가장자리에서 에지 회절(edge diffraction) 패턴도 관찰됩니다. 무한 격자 해석해와 비교해 유한성 효과를 정량화할 수 있습니다.

### 연구 활용
격자 커플러(grating coupler) 설계, 분광기 격자 효율 최적화, 홀로그래픽 광학 소자(HOE), 메타서피스 회절 패턴 계산에 활용됩니다. 유한 격자의 채움비(duty cycle)와 높이를 파라미터로 스윕하여 최적 회절 효율을 역설계하는 기초 예제입니다.
"""

# ── 404: refl-quartz.py (smartalecH) ────────────────────────────────────────
descriptions[404] = """## 석영 유리 반사 스펙트럼 (Fused Quartz Reflectance Spectrum)

### 물리적 배경
융합 석영(fused quartz, SiO₂)의 가시광 파장 범위(400-800nm)에서 수직 입사 반사율 스펙트럼을 계산합니다. 비분산 매질에서 수직 입사 반사율은 R = |(n-1)/(n+1)|²이지만, 실제 SiO₂는 파장에 따라 굴절률이 변하는 분산(dispersion)이 있습니다. MEEP의 내장 분산 재료 데이터베이스를 활용해 광대역(broadband) 반사율을 단일 시뮬레이션으로 계산합니다.

### 시뮬레이션 세팅
- **셀**: 1D (z방향), 크기 sz=10+2×1μm
- **해상도**: 200 pixels/μm (가시광 단파장 계산에 필요한 고해상도)
- **PML**: z방향 두께 1μm
- **주파수**: fmin=1/0.8, fmax=1/0.4 (800nm~400nm 범위)
- **소스**: 광대역 가우시안 펄스, Ez 평면파

### 핵심 MEEP API
- `meep.materials.fused_quartz`: Sellmeier 모델 기반 실제 분산 데이터 포함
- `sim.add_flux()`: 반사 및 투과 DFT 플럭스 모니터
- `sim.load_minus_flux_data()`: 기준(공기만) 시뮬레이션의 플럭스를 차감하여 순수 반사율 계산
- `np.array(mp.get_fluxes(refl_flux)) / np.array(mp.get_fluxes(tran_flux))`: 반사율 스펙트럼
- **nfreq=500**: 광대역에서 충분한 주파수 해상도

### 결과 해석
주파수(또는 파장)에 대한 반사율 R(λ) 그래프를 출력합니다. SiO₂의 경우 가시광 범위에서 굴절률이 약 1.44~1.47로 비교적 평탄하여, 반사율이 약 3.4~3.7% 수준을 보입니다. 이 결과를 프레넬 방정식 R = |(n-1)/(n+1)|² (n: 파장별 실제 굴절률)와 비교하여 시뮬레이션 정확도를 검증합니다.

### 연구 활용
SiO₂ 기판 반사율은 SOI 플랫폼에서 박막 코팅 설계, 반사 방지막(AR coating) 최적화, 실리콘 포토닉스 소자 패키징 인터페이스 분석의 기초 데이터를 제공합니다. 광대역 분산 재료 시뮬레이션 워크플로우의 표준 예제로 활용됩니다.
"""

# ── 503: binary_grating.py (NanoComp) ───────────────────────────────────────
descriptions[503] = """## 이진 회절 격자 (Binary Diffraction Grating)

### 물리적 배경
이진 격자(binary grating)는 직사각형 단면의 주기적 구조로, 입사광을 여러 회절 차수로 분리합니다. 격자 효율은 격자 주기(Λ), 높이(h), 채움비(fill factor, f)에 의존합니다. 리고루스 결합파 해석(RCWA)의 FDTD 버전으로, MEEP는 **블로흐 주기 경계 조건**을 이용해 무한 주기 격자를 효율적으로 시뮬레이션합니다. 각 회절 차수 m의 효율 η_m은 해당 방향 플럭스/입사 플럭스로 계산됩니다.

### 시뮬레이션 세팅
- **해상도**: 60 pixels/μm
- **격자**: 주기 gp=10μm, 높이 gh=0.5μm, 채움비 gdc=0.5
- **기판**: dsub=3μm, 하부 패딩 dpad=3μm
- **PML**: Y방향 (입사/투과 방향), X방향은 블로흐 주기 경계
- **소스**: CW 또는 가우시안 펄스, 수직 입사 (k_x=0)
- **블로흐 경계**: `sim.k_point = mp.Vector3(0, 0, 0)` (수직) 또는 경사 입사 시 kx 설정

### 핵심 MEEP API
- `mp.k_point`: 블로흐 경계 파수 설정
- `sim.add_flux()`: 각 회절 차수별 플럭스 모니터 (각도로 계산)
- 회절 차수 플럭스 모니터 위치: 격자 위/아래 각도별로 FluxRegion 배치
- `np.angle`: 각 회절 차수의 투과/반사 각도 계산
- 효율 계산: η_m = flux_m / flux_incident

### 결과 해석
이미지는 각 회절 차수의 효율(%)을 막대 그래프 또는 주파수 의존 곡선으로 보여줍니다. 대칭 격자(채움비=0.5)에서는 짝수 차수가 억제되고 홀수 차수(±1, ±3)만 나타납니다. 0차(직진 투과)와 ±1차 효율이 격자 높이에 따라 주기적으로 변화하는 것을 확인합니다. 총 효율 합이 1에 가까울수록 PML 반사나 수치 오차가 작음을 의미합니다.

### 연구 활용
회절 격자 설계(분광기, 홀로그램), 격자 커플러 최적화, 포토닉 결정 슬래브 회절 분석, 편광 선택적 빔 스플리터 설계에 활용됩니다. 채움비와 높이를 파라미터로 스윕하여 원하는 회절 차수 효율을 최대화하는 역설계 워크플로우의 표준 기반입니다.
"""

# ── 504: cylinder_cross_section.py (NanoComp) ───────────────────────────────
descriptions[504] = """## 실린더 산란 및 소광 단면적 (Cylinder Scattering/Extinction Cross Section)

### 물리적 배경
유한 높이 실린더(dielectric cylinder)에서 빛의 산란 및 소광을 계산합니다. 소광 단면적(extinction cross section) σ_ext = σ_scat + σ_abs 는 Mie 이론으로 해석적으로 계산 가능하며, MEEP 결과와 직접 비교합니다. 이는 나노 입자, 포토닉 결정 기둥, 광학 공진기 등 원통형 구조 설계의 기초입니다. 광학 정리(optical theorem): σ_ext = (4π/k) Im(f(0)) (f(0): 전방 산란 진폭)를 활용합니다.

### 시뮬레이션 세팅
- **실린더**: 반지름 r=0.7, 높이 h=2.3 (MEEP 단위, 실제 파장과 무관한 normalized)
- **주파수 범위**: frq_min ~ frq_max (2πr/10 ~ 2πr/2 파장 범위)
- **소스**: 광대역 가우시안 펄스, 평면파
- **nfreq**: 여러 주파수에서 DFT 플럭스 동시 계산
- **Total-field/Scattered-field (TFSF)**: 산란 필드만 추출하는 핵심 기법

### 핵심 MEEP API
- `mp.Source`를 TFSF 소스로 설정: 실린더 외부는 total field, 내부는 scattered field
- `sim.add_flux()`: TFSF 경계 안/밖 플럭스로 산란 단면적 계산
- Mie 이론 비교: `miepython` 또는 `scipy` 기반 해석해
- `sigma_scat = flux_scat / intensity_incident`: 산란 단면적 규격화

### 결과 해석
파장 또는 주파수에 따른 소광/산란 단면적 곡선을 보여줍니다. Mie 공진(whispering gallery mode, 리서나펀드 공진)에서 단면적이 급격히 증가합니다. MEEP 계산 결과와 Mie 이론 해석해가 일치하면 시뮬레이션의 정확도가 검증된 것입니다. 고해상도(nfreq 높게)일수록 공진 피크가 더 명확하게 분해됩니다.

### 연구 활용
나노입자 센서 설계, 포토닉 결정 기둥 공진기 Q인자 추출, 메타원자(meta-atom) 단위 셀 설계, 나노 안테나의 산란 패턴 최적화에 직접 활용됩니다. MEEP와 Mie 이론의 비교는 새로운 시뮬레이션 설정의 정확도 검증 표준 절차입니다.
"""

# ── 508: antenna-radiation.py (NanoComp) ────────────────────────────────────
descriptions[508] = """## 쌍극자 안테나 방사 패턴 (NanoComp 업데이트 버전)

### 물리적 배경
자유공간에서 쌍극자 안테나의 방사 패턴을 near-to-far field 변환으로 계산합니다. 이 버전은 smartalecH 버전의 개선판으로, 상수(RESOLUTION_UM)를 명시적으로 정의하고 docstring으로 튜토리얼 참조를 포함합니다. 전기 쌍극자에서 방사되는 전자기파의 공간 각도 분포를 극좌표계로 시각화하여 이론적 sin²θ 패턴과 비교합니다.

### 시뮬레이션 세팅
- **RESOLUTION_UM = 50**: 명명 규칙 개선 (단위 명시)
- **셀 크기**: (sxy+2×dpml)² 정사각형, 2D
- **PML**: dpml=1μm, 4방향
- **소스**: GaussianSource(fcen, fwidth), Ez 쌍극자
- **NF2FF 모니터**: 셀 중심 주변 박스 형태로 배치

### 핵심 MEEP API
- `sim.add_near2far(fcen, 0, 1, *[mp.Near2FarRegion(...)])`: 근거리 필드 수집
- `sim.get_farfields(n2f, 1000, center=mp.Vector3(), size=mp.Vector3(0))`: 1000개 각도에서 원거리 필드
- 방사 강도: `E2 = np.sum(np.abs(ff['Ex'])**2 + np.abs(ff['Ey'])**2 + np.abs(ff['Ez'])**2, axis=2)`
- `ax.plot(angles, gain/gain.max())`: 극좌표 방사 패턴

### 결과 해석
극좌표 그래프에서 쌍극자 방사 패턴이 이론적 sin²θ 패턴과 일치하는 8자형 모양을 보입니다. Ez 소스이므로 z축으로 극소, 수평 방향으로 극대인 특성이 2D에서는 전방향 균일로 나타납니다. 시뮬레이션 결과(실선)와 이론값(점선) 비교로 NF2FF 변환 정확도를 검증합니다.

### 연구 활용
광자 집적 회로에서의 수직 방사 손실 계산, VCSEL(vertical-cavity surface-emitting laser) 방사 패턴, 광학 안테나 어레이 설계, 포토닉 결정에서의 결함 모드 방사 패턴 분석에 활용됩니다.
"""

# ── 520: oblique-planewave.py (NanoComp) ────────────────────────────────────
descriptions[520] = """## 경사 입사 평면파 (NanoComp - EigenModeSource 기반)

### 물리적 배경
이 버전은 smartalecH 버전을 개선하여 `EigenModeSource`를 이용한 더 정확한 경사 입사 평면파를 구현합니다. EigenModeSource는 MEEP의 MPB 솔버를 내부적으로 호출하여 주어진 k벡터에서의 정확한 고유모드를 소스로 사용합니다. 이는 단순 위상 변조 소스보다 훨씬 순수한 단일 모드를 보장합니다. 균일 매질에서 평면파는 유일한 고유모드이므로 MPB 고유값과 해석해가 일치해야 합니다.

### 시뮬레이션 세팅
- **mp.verbosity(2)**: 상세 출력으로 MPB 고유값 수렴 확인
- **해상도**: 50 pixels/μm
- **k_point**: 경사 각도에 해당하는 블로흐 파수 벡터
- **EigenModeSource**: `eig_band=1` (기본 모드), `direction=mp.NO_DIRECTION` 설정 필요 시

### 핵심 MEEP API
- `mp.EigenModeSource(src, center, size, eig_kpoint, eig_band, eig_match_freq, direction)`:
  - `eig_kpoint`: 원하는 k벡터 방향 (블로흐 파수)
  - `eig_band`: 사용할 밴드 인덱스 (1 = 기본 모드)
  - `eig_match_freq=True`: 소스 주파수와 고유모드 주파수 매칭
- `mp.k_point`: 블로흐 경계 조건 설정 (EigenModeSource와 일치해야 함)

### 결과 해석
이미지는 경사 입사 EigenMode 소스의 파면 구조를 보여줍니다. EigenModeSource는 단순 소스 대비 소스 면에서 반사파가 없고, 원하는 모드만 순수하게 여기합니다. 균일 매질에서 파면이 직선 유지 + 블로흐 경계에서 연속이면 설정이 올바른 것입니다.

### 연구 활용
경사 입사 FDTD가 필요한 모든 SOI 소자 시뮬레이션(격자 커플러 각도 최적화, 경사 입사 필터, 편광 의존 소자)에서 EigenModeSource를 활용하면 더 정확하고 깨끗한 결과를 얻을 수 있습니다.
"""

# ── 536: 3rd-harm-1d.py (NanoComp) ──────────────────────────────────────────
descriptions[536] = """## 1D 3차 고조파 발생 (Third Harmonic Generation in Kerr Medium)

### 물리적 배경
3차 고조파 발생(Third Harmonic Generation, THG)은 비선형 광학의 대표 현상으로, 기본 주파수 ω의 강한 빛이 Kerr 비선형 매질(χ⁽³⁾ ≠ 0)을 통과할 때 3ω 성분이 생성됩니다. 지배 방정식: P_NL = ε₀χ⁽³⁾|E|²E. MEEP에서는 `chi3` 파라미터로 Kerr 비선형성을 구현하며, 비선형 동방정식을 완전히 시간 영역에서 풉니다. 이는 위상 정합(phase matching) 조건 Δk = k(3ω) - 3k(ω) = 0을 직접 검증할 수 있습니다.

### 시뮬레이션 세팅
- **1D 시뮬레이션**: z방향 전파, 빠른 계산 가능
- **재료**: `mp.Medium(index=n, chi3=c)` — Kerr 비선형성 포함 균일 매질
- **소스**: 기본 주파수 fcen, 높은 진폭(비선형 효과 발생 조건)
- **DFT 모니터**: fcen, 2×fcen, 3×fcen에서 필드 기록
- **nfreq 설정**: 기본파, 2차, 3차 고조파를 포함하는 주파수 범위

### 핵심 MEEP API
- `mp.Medium(index=n, chi3=c)`: Kerr 비선형 매질. chi3 단위 주의 (MEEP 단위계)
- `sim.add_dft_fields()` + `sim.get_dft_array()`: 특정 주파수 DFT 필드 추출
- 시뮬레이션 진폭: `mp.Source(..., amplitude=A)` — A² ∝ 입력 강도
- `np.abs(dft_field)**2`: DFT 필드 → 강도 변환

### 결과 해석
두 이미지: (1) 공간상 기본파(ω)와 3차 고조파(3ω) 필드 비교 — 고조파가 매질 내에서 성장하는 것을 확인. (2) 변환 효율(3ω 파워 / 기본파 파워) vs 전파 거리 또는 입력 강도. 위상 정합이 안 맞으면 고조파 파워가 주기적으로 진동하고, 정합되면 단조 증가합니다.

### 연구 활용
LiNbO₃(LNOI), GaAs 등 강한 비선형성 재료의 고조파 발생 소자 설계, 집적 포토닉스에서의 온칩 파장 변환, PROJ-004 LNOI 역설계와 같은 비선형 포토닉 소자 시뮬레이션에 직접 연결됩니다. 위상 정합 구조(periodic poling, modal phase matching) 설계 검증에 활용됩니다.
"""

# ── 538: bend-flux.py (NanoComp) ────────────────────────────────────────────
descriptions[538] = """## 90도 도파관 벤드 투과율 (NanoComp 업데이트 버전)

### 물리적 배경
smartalecH 버전의 개선판으로, 동일한 물리(90도 도파관 벤드 투과율/반사율 계산)를 더 현대적인 Python 코드 스타일로 구현합니다. 특히 `from __future__ import division` 제거, 타입 힌트 추가, 상수 명명 개선 등이 포함됩니다. 물리적 내용: 도파관 도파 모드의 90도 벤드 통과 시 산란 손실 계산, 기준(직선) 시뮬레이션과의 비교로 규격화된 투과율/반사율 측정.

### 시뮬레이션 세팅
- **셀**: sx=16μm × sy=32μm, 2D
- **해상도**: 10 pixels/μm (빠른 계산)
- **PML**: dpml=1.0μm
- **도파관**: ε=11.56, 너비 1μm, L자형 레이아웃 (수평 + 수직)
- **플럭스 모니터**: 입력(참조), 투과(벤드 후 수직 도파관), 반사(입력단 역방향)

### 핵심 MEEP API
- `sim.add_flux(fcen, 0, 1, mp.FluxRegion(...))`: 단일 주파수 플럭스 (df=0)
- `sim.save_flux()` / `sim.load_minus_flux()`: 반사율 계산을 위한 참조 플럭스 관리
- `mp.get_fluxes(flux_obj)`: 각 주파수 플럭스 값 목록 반환
- T_bend = flux_bend / flux_straight: 규격화 투과율
- R_bend = -flux_refl / flux_straight: 규격화 반사율 (부호 주의)

### 결과 해석
단일 주파수 투과율(T)과 반사율(R) 수치 출력 및 도파관 구조 + 플럭스 모니터 위치 시각화. T ≈ 0.9 이상이면 낮은 손실 벤드로 판단, T < 0.7이면 최적화 필요. T+R < 1이면 나머지는 방사 손실로 귀속됩니다.

### 연구 활용
SOI PIC에서 도파관 벤드는 필수 소자입니다. 이 시뮬레이션을 기반으로 벤드 반경 vs 손실 트레이드오프를 분석하고, 역설계로 임의 형상 벤드를 최적화(목표: T→1)하는 것이 실용적 응용입니다.
"""

# ── 546: antenna_pec_ground_plane.py (NanoComp) ─────────────────────────────
descriptions[546] = """## PEC 접지면 위 안테나 방사 패턴 (Antenna Above PEC Ground Plane)

### 물리적 배경
완전 전기 도체(Perfect Electric Conductor, PEC) 접지면 위에 배치된 쌍극자 안테나의 방사 패턴을 계산합니다. 이미지 방법론(method of images)에 의해 접지면은 안테나의 거울상(image dipole)으로 대체할 수 있으며, 반공간(upper half-space)에서의 방사 패턴이 자유공간 패턴과 달라집니다. PEC 경계에서는 E_tangential = 0 조건으로 인해 z방향 전기장이 증가하고 수평 방향 전기장이 상쇄됩니다.

### 시뮬레이션 세팅
- **PEC 접지면**: y=0 평면에 `mp.perfect_electric_conductor` 또는 특수 경계 조건 적용
- **안테나**: y>0 반공간에 Ez 쌍극자 소스 배치 (접지면으로부터 거리 d)
- **NF2FF**: 반원형 모니터로 상반공간 방사 패턴 추출
- **비교**: d/λ = 0.25, 0.5 등 다양한 높이에서 패턴 변화 분석

### 핵심 MEEP API
- PEC 경계: `mp.Boundary(mp.PEC)` 또는 geometry에 금속 블록 배치
- `sim.add_near2far()`: 반원형(상반공간) NF2FF 모니터
- 패턴 계산: 각도 0°~180° 범위
- 이미지 방법 비교: 해석적 결과 = 2×자유공간 패턴 × cos(kd·cosθ) 형태의 어레이 인자

### 결과 해석
두 이미지: (1) 접지면 포함 전체 필드 분포 (Ez 스냅샷) — PEC에서 E_z 최대, 접지면 위아래 패턴이 대칭. (2) 상반공간 방사 패턴 극좌표 그래프 — 접지면 없을 때 대비 특정 방향 방사 증가/감소. 안테나와 접지면 사이 거리(d/λ)에 따라 패턴이 크게 변합니다.

### 연구 활용
SOI 포토닉스 칩에서 기판(SiO₂/Si) 위에 놓인 광학 안테나 설계, 수직 출력 커플러(vertical emitter) 방사 패턴 제어, 포토닉 결정 나노캐비티의 집광 효율 향상(반사기 활용), 광학 LIDAR 칩의 방사 패턴 최적화에 활용됩니다.
"""

# ── 551: antenna_pec_ground_plane_1D.py (NanoComp) ──────────────────────────
descriptions[551] = """## PEC 접지면 안테나 — 브릴루앙존 적분 (1D Brillouin Zone Integration)

### 물리적 배경
PEC 접지면 위 안테나 방사 패턴을 **브릴루앙존(Brillouin Zone, BZ) 적분** 기법으로 계산합니다. 1D 격자(슬래브 기하)에서 안테나 방사를 k공간 적분으로 분해하여 각 k_parallel에 대해 별도 시뮬레이션을 실행하고 합산합니다. 이 기법은 주기 구조(포토닉 결정, 그레이팅)에서 방사 패턴 계산에 필수적이며, 단일 시뮬레이션보다 훨씬 정확한 결과를 제공합니다.

### 시뮬레이션 세팅
- **기하**: 1D (y방향) 슬래브, x방향 주기 경계
- **BZ 적분**: k_x를 -0.5/a ~ 0.5/a 범위로 분할하여 각 k_x별 시뮬레이션
- **합산**: 각 k_x의 방사 파워를 가중 합산 → 각도 분해 방사 스펙트럼
- **from typing import Tuple**: 타입 힌트로 코드 명확성 향상

### 핵심 MEEP API
- `mp.k_point = mp.Vector3(kx, 0, 0)`: 각 BZ 점에서 블로흐 파수 설정
- 루프: `for kx in np.linspace(-0.5, 0.5, n_kpoints): sim.reset(); sim.run()`
- `sim.add_near2far()`: 각 k_x에서 NF2FF 데이터 수집
- BZ 합산: 각 k_x의 방사 파워를 수치 적분으로 합산

### 결과 해석
이미지는 BZ 적분으로 얻은 각도 분해 방사 스펙트럼을 보여줍니다. 직접 계산(546번 예제)과 비교하면 BZ 적분 방법이 특히 주기 구조가 있을 때 더 정확한 결과를 제공합니다. 방사 패턴의 각도 분해능은 k_x 샘플링 수(n_kpoints)에 비례합니다.

### 연구 활용
주기 구조 위에 배치된 광원의 방사 패턴 정확한 계산, 포토닉 결정 슬래브에서의 방사 손실 분석, 격자 커플러의 각도-파장 다이어그램(dispersion diagram) 계산, LED 추출 효율 계산(각도 적분) 등 포토닉스 연구의 고급 분석 기법으로 활용됩니다.
"""

# ── 561: straight-waveguide.py (NanoComp) ───────────────────────────────────
descriptions[561] = """## 직선 도파관 기초 (NanoComp 업데이트 버전)

### 물리적 배경
smartalecH 버전의 개선판으로 동일한 물리를 현대적 Python 코드로 구현합니다. 2D 직선 도파관에서 ε=12 코어가 공기 클래딩 사이에서 빛을 안내하는 기본 원리를 시연합니다. 전반사에 의한 도파 모드의 형성, Ez 필드의 공간 분포, PML 흡수 경계의 동작을 시각화합니다. 이 예제는 모든 포토닉스 FDTD 연구의 출발점입니다.

### 시뮬레이션 세팅
- **셀**: Vector3(16, 8, 0) — 16μm × 8μm 2D
- **지오메트리**: `mp.Block(Vector3(mp.inf, 1, mp.inf), center=Vector3(), material=mp.Medium(epsilon=12))` — 너비 1μm 무한 도파관
- **소스**: `mp.Source(mp.ContinuousSource(fcen=0.15), component=mp.Ez, center=Vector3(-7, 0))` — 도파관 시작단
- **해상도**: 10 (기본 튜토리얼 수준)
- **PML**: 기본 1μm (모든 방향)

### 핵심 MEEP API
- `mp.Simulation(cell_size, geometry, sources, resolution, boundary_layers)`: 시뮬레이션 객체 생성
- `sim.run(until=200)`: 200 시간 단위 동안 실행 (CW 소스는 정상 상태 도달 필요)
- `sim.plot2D()`: matplotlib 기반 2D 레이아웃 + 필드 시각화
- `mp.output_efield_z`: Ez 필드 출력 함수

### 결과 해석
세 이미지: (1) 유전율 분포 — 고유전율(ε=12) 코어가 밝게 표시, (2) 시뮬레이션 레이아웃 — 지오메트리 + 소스 + PML 위치, (3) Ez 필드 스냅샷 — 도파관 코어를 따라 진행하는 도파 모드의 정상파 패턴. 도파관 외부 클래딩 영역에서 에바네센트(evanescent) 필드 감소가 확인됩니다.

### 연구 활용
SOI 도파관 파라미터(코어 너비, 유전율 비율) 스윕의 기반 예제, 더 복잡한 SOI 소자(방향성 커플러, 링 공진기, 역설계 소자) 시뮬레이션의 기초 설정 템플릿으로 활용됩니다.
"""

# ── 564: gaussian-beam.py (NanoComp) ────────────────────────────────────────
descriptions[564] = """## 가우시안 빔 전파 (NanoComp 업데이트 버전)

### 물리적 배경
smartalecH 버전의 개선판으로 GaussianBeamSource를 이용한 가우시안 빔 시뮬레이션을 현대적 Python으로 구현합니다. 가우시안 빔의 특성: 빔 웨이스트 w₀, 레일리 거리 z_R = πw₀²/λ, 발산각 θ = λ/(πw₀). 자유공간 전파에서 빔이 웨이스트를 지나 확산하는 회절 현상을 FDTD로 정확히 재현합니다.

### 시뮬레이션 세팅
- **셀**: Vector3(s=14, s=14), 정사각형 14μm × 14μm
- **해상도**: 50 pixels/μm
- **PML**: 두께 2μm
- `beam_x0 = Vector3(0, 3.0)`: 빔 포커스가 소스로부터 y=+3μm 위치
- `beam_kdir = Vector3(0, -1, 0)`: 아래 방향 전파
- `beam_w0`: 빔 웨이스트 반경 (기본값 ≈ 1-2μm)
- `beam_E0 = Vector3(1, 0, 0)`: Ex 편광

### 핵심 MEEP API
- `mp.GaussianBeamSource`: MEEP 내장 가우시안 빔 소스 클래스
  ```python
  src = mp.GaussianBeamSource(
      src=mp.ContinuousSource(frequency=fcen),
      center=mp.Vector3(0, -s/2+dpml),
      size=mp.Vector3(s, 0),
      beam_x0=beam_x0, beam_kdir=beam_kdir,
      beam_w0=beam_w0, beam_E0=beam_E0
  )
  ```
- `matplotlib.use("agg")`: 헤드리스 환경에서 렌더링 백엔드

### 결과 해석
이미지는 가우시안 빔의 전기장 강도 |Ex|² 분포를 보여줍니다. 소스 평면에서 출발한 빔이 y=+3μm 위치에서 최소 빔 사이즈(포커스)를 형성하고, 그 이후 회절에 의해 발산합니다. 포커스 전후의 위상 곡률 변화(Gouy 위상)도 필드 패턴에서 확인됩니다.

### 연구 활용
광섬유-칩 수직 커플링 효율 계산, 대물렌즈 NA와 집광 스팟 크기 관계 시뮬레이션, VCSEL 빔 품질 분석, 격자 커플러의 자유공간 모드 매칭 최적화에 활용됩니다.
"""

# ── 578: faraday-rotation.py (NanoComp) ─────────────────────────────────────
descriptions[578] = """## 패러데이 회전 (NanoComp 업데이트 버전)

### 물리적 배경
smartalecH 버전의 개선판으로 동일한 자기광학 패러데이 회전 물리를 현대적 코드 스타일로 구현합니다. 자이로트로픽 로렌츠 매질에서 선형 편광 Ex 성분이 전파 중 Ey 성분을 생성하여 편광면이 회전합니다. 회전각 θ_F = VBd (V: Verdet 상수, B: 자기장 강도, d: 전파 거리)로 외부 자기장에 비례합니다.

### 시뮬레이션 세팅
- **매질**: epsn=1.5, f0=1.0, gamma=1e-6, sn=0.1, b0=0.15
- **1D 전파**: z방향, 단순하고 빠른 계산
- **소스**: Ex 편광 CW 평면파 (fcen=0.5, 로렌츠 공진 f0=1.0 아래 주파수)
- **모니터**: 전파 거리에 따른 Ex, Ey 필드 값 기록

### 핵심 MEEP API
- `mp.GyrotropicLorentzianSusceptibility(omega=2*pi*f0, gamma=2*pi*gamma, sigma=sn, bias=mp.Vector3(0, 0, b0))`: 자이로트로픽 분산 정의
- `mp.Medium(epsilon=epsn, mu=1, E_susceptibilities=[gyrotopic_sus])`: 자이로트로픽 매질 생성
- `sim.get_array(component=mp.Ex, ...)` + `sim.get_array(component=mp.Ey, ...)`: 공간 필드 추출
- `np.arctan2(Ey_amp, Ex_amp) * 180 / pi`: 편광 회전각(도) 계산

### 결과 해석
두 이미지: (1) Ex, Ey 공간 분포 — 순수 Ex로 시작한 빔이 Ey를 점차 생성, (2) 위치에 따른 편광각 — 선형 증가가 패러데이 회전의 증거. 기울기가 Verdet 상수 V에 해당하며, MEEP 매개변수(b0, sn)와의 관계로 실제 재료 파라미터를 역산할 수 있습니다.

### 연구 활용
자기광학 아이솔레이터(optical isolator) — SOI PIC에서 역방향 반사 차단의 핵심 소자, 자기광학 변조기 설계, 비가역 포토닉 소자의 삽입 손실과 격리도(isolation) 트레이드오프 최적화에 활용됩니다.
"""

# ── 586: absorbed_power_density.py (NanoComp) ───────────────────────────────
descriptions[586] = """## 흡수 파워 밀도 (NanoComp 업데이트 버전)

### 물리적 배경
smartalecH 버전의 개선판으로 SiO₂ 실린더에서의 흡수 파워 밀도 계산을 현대적 코드로 구현합니다. `matplotlib.use("agg")`를 분리하여 헤드리스 환경(Docker, HPC)에서도 안정적으로 동작합니다. 손실 매질에서 국소 흡수 파워 밀도 P(r) = (ω/2)Im(ε(ω))|E(r)|²는 열 발생, 광자-전자 변환 효율 계산의 핵심입니다.

### 시뮬레이션 세팅
- **해상도**: 100 pixels/μm (SiO₂ 분산 재료의 세밀한 공간 구조 포착)
- **PML**: 1μm 두께
- **SiO₂**: `meep.materials.SiO2` — 실제 Sellmeier 분산 모델 (가시광 + 근적외선 유효)
- **실린더**: r=1μm, 공기 패딩 2μm
- **DFT 주파수**: 단일 주파수 또는 광대역 스펙트럼

### 핵심 MEEP API
- `from meep.materials import SiO2`: 내장 분산 재료 임포트
- `sim.add_dft_fields([mp.Ex, mp.Ey, mp.Ez], fcen, fcen, 1)`: 단일 주파수 DFT 필드
- `eps_array = sim.get_array(component=mp.Dielectric, ...)`: 공간 유전율 분포
- `P_abs = 0.5 * omega * np.imag(eps_r) * np.abs(Ez)**2`: 흡수 파워 밀도 계산

### 결과 해석
두 이미지: (1) |Ez|² 필드 강도 분포 — 실린더 표면과 내부 Mie 공진 패턴, (2) 흡수 파워 밀도 P(r) — SiO₂의 허수 유전율이 큰 파장에서 실린더 내부 흡수가 증가. 공진 파장에서 내부 필드 증강으로 흡수 파워가 입사광 강도의 수배가 될 수 있습니다.

### 연구 활용
SOI 칩에서 SiO₂ 클래딩의 광학 손실 분석, 나노포토닉 광열 소자(plasmonic heater) 설계, 고출력 레이저에서 재료 손상 임계값 계산, 광기계 소자(optomechanical device)의 열-광-기계 결합 시뮬레이션에 활용됩니다.
"""

# ── 587: finite_grating.py (NanoComp) ───────────────────────────────────────
descriptions[587] = """## 유한 격자 산란 (NanoComp 업데이트 버전)

### 물리적 배경
smartalecH 버전의 업데이트판으로 유한 격자에서 평면파 산란을 계산합니다. 격자 주기 Λ, 격자 높이 gh, 채움비 gdc, 기판 두께 dsub의 4가지 핵심 파라미터로 회절 패턴이 결정됩니다. 유한 격자에서는 무한 격자 이론(RCWA) 대비 가장자리 회절, 격자 모드 간 결합, 유한 조명 빔 효과가 추가됩니다.

### 시뮬레이션 세팅
- **해상도**: 50 pixels/μm
- **field_profile=True**: 산란 필드 공간 분포 계산
- **field_profile=False**: 회절 스펙트럼 (1D 횡단면 기반)
- **격자**: gp=10μm, gh=0.5μm, gdc=0.5
- **기판 + 패딩**: dsub=3μm + dpad=3μm
- **소스**: 가우시안 펄스 또는 CW, 수직 입사

### 핵심 MEEP API
- `mp.Block` 반복 배치로 유한 격자 구성 (N주기)
- `sim.add_flux()`: 격자 위아래 여러 플럭스 모니터
- `field_profile=True` 시: `sim.get_array(component=mp.Ez)` → 2D 필드 맵
- `field_profile=False` 시: 1D 횡단면 DFT → 공간 주파수 FFT → 회절 각도

### 결과 해석
이미지는 격자 위 공기 영역의 산란 Ez 필드를 보여줍니다. 격자의 각 주기에서 산란된 파가 간섭하여 특정 각도에서 보강간섭(회절 피크)이 나타납니다. 유한 격자이므로 피크 폭이 주기 수 N에 반비례하며(N 클수록 날카로운 회절 피크), 가장자리 효과로 인한 스패클(speckle) 패턴도 관찰됩니다.

### 연구 활용
격자 커플러 설계 검증, 회절 광학 소자(DOE) 패턴 분석, 포토닉 집적 회로의 수직 I/O 커플러 최적화, 유한 크기 효과가 중요한 소자(MEMS 포토닉스, 마이크로 광학) 시뮬레이션에 활용됩니다.
"""

# ── 589: refl-quartz.py (NanoComp) ──────────────────────────────────────────
descriptions[589] = """## 석영 유리 반사 스펙트럼 (NanoComp 업데이트 버전)

### 물리적 배경
smartalecH 버전의 개선판으로 융합 석영의 가시광 반사 스펙트럼을 계산합니다. `from meep.materials import fused_quartz`를 이용한 깔끔한 임포트와 타입 힌트 추가로 코드 가독성이 향상되었습니다. 물리: 가시광 400-800nm에서 SiO₂의 Sellmeier 분산: n²(λ) = 1 + A₁λ²/(λ²-B₁) + A₂λ²/(λ²-B₂) + A₃λ²/(λ²-B₃). 실제 굴절률 데이터를 내장한 재료 모델로 정밀한 반사율 스펙트럼 계산이 가능합니다.

### 시뮬레이션 세팅
- **셀**: 1D z방향, sz=10+2×1μm
- **해상도**: 200 pixels/μm (λ/200 → 400nm/200 = 2nm 픽셀 크기)
- **주파수**: fmin=1/0.8 ~ fmax=1/0.4 (400-800nm)
- **소스**: 광대역 가우시안 펄스 (단일 시뮬레이션으로 전체 스펙트럼)
- **재료**: `from meep.materials import fused_quartz`

### 핵심 MEEP API
- `mp.FluxRegion`: z방향 1D에서 단일 점 또는 작은 영역으로 플럭스 모니터
- **2단계 계산**:
  1. 기준 시뮬레이션 (공기만): 입사광 DFT 플럭스 저장 (`sim.save_flux()`)
  2. 실제 시뮬레이션 (SiO₂): `sim.load_minus_flux_data()` → 반사 플럭스 = 입사 - 투과(기준)
- `R = -refl_flux / incident_flux`: 반사율 (부호 주의: 반사는 반대 방향)
- `wvl = 1/np.array(freqs)`: 주파수 → 파장 변환

### 결과 해석
파장 400-800nm에서 SiO₂ 반사율 R(λ) 그래프. 굴절률이 400nm에서 약 1.47, 800nm에서 약 1.44로 감소하므로, 프레넬 공식 R=(n-1)²/(n+1)²에 의해 단파장에서 반사율이 약간 높습니다. 계산값이 이론값 3.4-3.7%와 일치하면 시뮬레이션 정확도 확인.

### 연구 활용
SOI 플랫폼의 SiO₂ BOX(Buried Oxide) 층 반사율 분석, 반사 방지 코팅(AR coating) 두께 최적화, 광학 패키징에서 SiO₂-공기 계면 반사 손실 계산, 분산성 재료의 광대역 시뮬레이션 워크플로우 표준 예제로 활용됩니다.
"""

# ── DB 저장 ──────────────────────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
saved = 0
for example_id, desc in descriptions.items():
    result = conn.execute("SELECT id FROM examples WHERE id=?", (example_id,)).fetchone()
    if result:
        conn.execute("UPDATE examples SET description_ko=? WHERE id=?", (desc.strip(), example_id))
        saved += 1
        print(f"Saved: id={example_id}")
    else:
        print(f"WARNING: id={example_id} not found in DB")
conn.commit()
conn.close()
print(f"\nDone! Saved {saved}/{len(descriptions)} descriptions.")
