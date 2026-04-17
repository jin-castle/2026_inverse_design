"""
MEEP vs 논문 차이 원인 체계적 진단
=====================================
역설계 + 재현 시뮬레이션에서 발생하는 문제들을 순서대로 분리·검증
"""
import meep as mp
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

mp.verbosity(0)

OUT = Path(r"C:\Users\user\projects\meep-kb\cis_repro\diagnose_output")
OUT.mkdir(exist_ok=True)

Air  = mp.Medium(index=1.0)
SiO2 = mp.Medium(index=1.449)
TiO2 = mp.Medium(index=2.646)
_f550 = 1.0/0.55; _eps_i550 = 2*4.448*0.010
Si   = mp.Medium(epsilon=19.8, D_conductivity=2*np.pi*_f550*_eps_i550)

SP = 0.5; Sx=Sy=1.0; Lt=1.5; Lp=0.5; sg=0.3; sb=0.5
Sz = Lp+sg+Lt+sb+Lp

z_src = Sz/2 - Lp - sg/2
z_rt  = Sz/2 - Lp - sg
z_rc  = z_rt - Lt/2
z_rb  = z_rt - Lt
z_mon = z_rb - 0.05

print(f"Cell: Sz={Sz:.2f}, z_src={z_src:.2f}, router=[{z_rt:.2f},{z_rb:.2f}], mon={z_mon:.2f}")

cell_size  = mp.Vector3(Sx, Sy, Sz)
pml_layers = [mp.PML(Lp, direction=mp.Z)]
resolution = 20

# ── 진단 1: 소스 주파수와 Si 흡수 상관관계 ───────────────────
print("\n[진단 1] 파장별 Si 흡수 + 소스 주파수 확인")

# 설계 파장 3개
WL_R, WL_G, WL_B = 0.698, 0.538, 0.450
freqs_3 = [1/WL_R, 1/WL_G, 1/WL_B]
print(f"  fR={freqs_3[0]:.4f} fG={freqs_3[1]:.4f} fB={freqs_3[2]:.4f}")

# 광대역 소스 중심 주파수 = mean(freqs_3)
fcen = np.mean(freqs_3)
df   = max(freqs_3) - min(freqs_3)
print(f"  소스 fcen={fcen:.4f} df={df:.4f}")
print(f"  fB/fcen={freqs_3[2]/fcen:.3f}  fR/fcen={freqs_3[0]/fcen:.3f}")
# GaussianSource 진폭 at fB and fR
# A(f) ∝ exp(-(f-fcen)^2 / (2*(df/2)^2)) [푸리에 변환]
sigma_f = df / (2*np.sqrt(2*np.log(2)))  # FWHM → sigma
def gauss_amp(f): return np.exp(-(f-fcen)**2 / (2*sigma_f**2))
print(f"  소스 진폭 @fB={gauss_amp(freqs_3[2]):.4f} @fG={gauss_amp(freqs_3[1]):.4f} @fR={gauss_amp(freqs_3[0]):.4f}")
print(f"  → R과 B가 소스 스펙트럼에서 멀어서 flux 거의 0!!")
print(f"  해결: fcen을 3파장 중심으로, df를 충분히 넓게")

# 올바른 광대역 소스
fcen_new = (1/0.400 + 1/0.720)/2
df_new   = 1/0.400 - 1/0.720
print(f"\n  올바른 광대역: fcen={fcen_new:.4f} df={df_new:.4f}")
print(f"  새 소스 진폭 @fB={np.exp(-(freqs_3[2]-fcen_new)**2/(2*(df_new/2.355)**2)):.4f}")
print(f"  새 소스 진폭 @fG={np.exp(-(freqs_3[1]-fcen_new)**2/(2*(df_new/2.355)**2)):.4f}")
print(f"  새 소스 진폭 @fR={np.exp(-(freqs_3[0]-fcen_new)**2/(2*(df_new/2.355)**2)):.4f}")

# ── 진단 2: 올바른 소스로 tot_flux 비교 ─────────────────────
print("\n[진단 2] 올바른 광대역 소스로 참조 시뮬")

si_geo = [mp.Block(center=mp.Vector3(0,0,(z_rb-Sz/2)/2),
                   size=mp.Vector3(Sx,Sy,z_rb+Sz/2), material=Si)]

for fcen_t, df_t, label in [
    (np.mean(freqs_3), max(freqs_3)-min(freqs_3), "OLD (narrow)"),
    (fcen_new, df_new, "NEW (broadband 400-720nm)"),
]:
    src  = mp.GaussianSource(fcen_t, fwidth=df_t)
    sp   = mp.Vector3(0,0,z_src); ss = mp.Vector3(Sx,Sy,0)
    srcs = [mp.Source(src,mp.Ex,center=sp,size=ss),
            mp.Source(src,mp.Ey,center=sp,size=ss)]

    sim = mp.Simulation(
        cell_size=cell_size, boundary_layers=pml_layers,
        geometry=si_geo, sources=srcs,
        default_material=Air, resolution=resolution,
        k_point=mp.Vector3(0,0,0), extra_materials=[Si],
    )
    fr = mp.FluxRegion(center=mp.Vector3(0,0,z_mon), size=mp.Vector3(Sx,Sy,0))
    fl = sim.add_flux(fcen_t, df_t, 3, fr, frequencies=freqs_3)
    sim.run(until_after_sources=mp.stop_when_dft_decayed(1e-3, 0))
    tot = np.abs(np.array(mp.get_fluxes(fl)))
    print(f"  {label}: tot_flux = R:{tot[0]:.4e} G:{tot[1]:.4e} B:{tot[2]:.4e}")
    sim.reset_meep()

# ── 진단 3: FDTD vs RCWA 근본 차이 분석 ────────────────────
print("\n[진단 3] FDTD vs RCWA 방법론 차이")
print("""
  논문 방법: RCWA (S4)
  ├─ 주파수 도메인 → 각 파장 독립 계산
  ├─ 평면파 분해 → Fourier order N개 합산
  ├─ 경계 조건: 완벽한 주기 (무한 주기 구조)
  └─ 효율 정의: 포토디텍터 평면 Poynting flux

  우리 방법: MEEP FDTD
  ├─ 시간 도메인 → 광대역 소스 + DFT
  ├─ 실공간 격자 → resolution 제한 (50nm→res=20)
  ├─ 경계 조건: Bloch periodic (k_point=0)
  └─ 효율 정의: DFT flux (포함된 Fourier mode 모두)
""")

print("[진단 4] 논문 구조 불확실성")
print("""
  ① Layer thickness: "~1-2μm" (정확한 값 미상)
     → 1.0, 1.5, 2.0μm 스캔 필요
  
  ② Si 모델: 비분산(D_cond@550nm) vs 분산(파장별 n+ik)
     → Lorentz 불안정, 파장별 k 차이가 크므로 오차 발생
     → 해결: 멀티-wavelength Si 모델 or 파장별 개별 시뮬
  
  ③ 최소 feature 50nm → resolution=20 (50px/μm = 20nm격자)
     → 50nm feature를 2~3 voxel로 표현 → 불충분
     → 정확한 재현: resolution=100 (10nm 격자) 필요
  
  ④ near-field (evanescent) contribution:
     논문: B=13%, G=12% of total from non-propagating orders
     FDTD: 자동 포함 (장점!) — 단, resolution이 충분해야 함
  
  ⑤ binary pattern: 논문 것 없음 → 역설계로 다른 패턴 사용
     → 논문 효율 달성 불가 (다른 local optimum)
""")

print("[진단 5] flux 정규화 방향 문제")
print("""
  APL2026 구조: 빛이 -Z (위→아래)
  FluxRegion: 기본 +Z 방향 = 소스에서 오는 빛은 양수
              -Z 방향으로 내려가는 빛(Si 흡수) = 음수 측정
  
  현재 코드: abs(flux) 취함 → 부호 문제 가림
  올바른 방법: 
    소스 위쪽에서 총 입사 파워 측정 (참조 시뮬 불필요)
    또는 참조 시뮬에서 router 없이 같은 모니터로 측정
""")

print("\n[결론] 우선순위 수정 사항")
print("""
  P1 (즉시): 소스 fcen/df 수정 → 400-720nm 광대역
  P2 (즉시): flux 정규화 — 소스 바로 아래 반사 모니터로 입사 파워 측정
  P3 (단기): Layer thickness 스캔 (1.0, 1.5, 2.0μm)
  P4 (단기): Si 분산 개선 — 파장별 개별 시뮬 합산 방식
  P5 (중기): resolution 100+ (SimServer 필요)
  P6 (중기): 저자에게 binary pattern 요청 (이메일)
""")
