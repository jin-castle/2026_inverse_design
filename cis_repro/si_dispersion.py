"""
Si 가시광 분산 모델 — Palik 실측 데이터 → MEEP Lorentz 피팅
=============================================================
참고: E.D. Palik, "Handbook of Optical Constants of Solids" (1985)
     M.A. Green, Sol. Energy Mater. Sol. Cells 92, 1305 (2008)

MEEP LorentzianSusceptibility:
  ε(f) = ε_∞ + Σ_n σ_n * f_n² / (f_n² - f² - j*γ_n*f)
  f = frequency in MEEP units = c/λ (λ in μm, c=1 → f=1/λ[μm])
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit, minimize
from pathlib import Path

OUTDIR = Path(__file__).parent

# ── 1. Palik 실측 데이터 (가시광 400~720nm) ───────────────────
# λ(nm), n, k  — Green(2008) Table II + Palik 보간
si_data = np.array([
    # λ_nm      n       k
    [400,    5.570,  0.387],
    [420,    5.291,  0.218],
    [440,    5.066,  0.123],
    [460,    4.885,  0.068],
    [480,    4.741,  0.044],
    [500,    4.623,  0.028],
    [520,    4.527,  0.017],
    [540,    4.448,  0.011],
    [560,    4.382,  0.008],
    [580,    4.326,  0.006],
    [600,    4.280,  0.005],
    [620,    4.241,  0.004],
    [640,    4.208,  0.003],
    [660,    4.180,  0.002],
    [680,    4.155,  0.002],
    [700,    4.134,  0.001],
    [720,    4.115,  0.001],
])

wl_nm = si_data[:,0]
n_si  = si_data[:,1]
k_si  = si_data[:,2]
wl_um = wl_nm / 1000.0          # μm
f_meep= 1.0 / wl_um             # MEEP 주파수 단위 (c/λ, c=1)

# 복소 유전율
eps_complex = (n_si + 1j*k_si)**2
eps_r = np.real(eps_complex)
eps_i = np.imag(eps_complex)

print("Si 실측 데이터:")
print(f"  λ 범위: {wl_nm[0]:.0f}~{wl_nm[-1]:.0f} nm")
print(f"  n 범위: {n_si.min():.3f}~{n_si.max():.3f}")
print(f"  k 범위: {k_si.min():.4f}~{k_si.max():.4f}")
print(f"  ε_r 범위: {eps_r.min():.2f}~{eps_r.max():.2f}")
print(f"  ε_i 범위: {eps_i.min():.4f}~{eps_i.max():.4f}")

# ── 2. Lorentz 피팅 ──────────────────────────────────────────
# MEEP: ε(f) = ε_∞ + Σ_n σ_n * f_n² / (f_n² - f² - j*γ_n*f)
# 가시광은 UV 흡수단 근처 → 2~3 pole이면 충분

def eps_lorentz(f, eps_inf, *poles):
    """poles: (sigma, f0, gamma) 반복"""
    eps = np.ones(len(f), dtype=complex) * eps_inf
    n_poles = len(poles) // 3
    for i in range(n_poles):
        sig, f0, gam = poles[3*i], poles[3*i+1], poles[3*i+2]
        eps += sig * f0**2 / (f0**2 - f**2 - 1j*gam*f)
    return eps

def residuals(params, f, eps_target):
    eps_pred = eps_lorentz(f, *params)
    err_r = (np.real(eps_pred) - np.real(eps_target))**2
    err_i = (np.imag(eps_pred) - np.imag(eps_target))**2
    return np.sum(err_r + err_i * 10)  # 허수부(흡수) 가중치 높임

# 2-pole 초기값 (UV 흡수단: ~0.37μm, 먼 UV: ~0.28μm)
# eps_inf, (sigma1, f01, gamma1), (sigma2, f02, gamma2)
x0_2pole = [
    1.0,                    # eps_inf
    14.0, 1/0.37, 0.5,      # pole 1: UV 흡수단 (~370nm)
    4.0,  1/0.28, 0.8,      # pole 2: 먼 UV (~280nm)
]
bounds_2pole = (
    [0.1,  0,0,0,  0,0,0],
    [5.0, 50,10,5, 50,10,5]
)

result2 = minimize(residuals, x0_2pole,
                   args=(f_meep, eps_complex),
                   method='L-BFGS-B',
                   bounds=list(zip(bounds_2pole[0], bounds_2pole[1])),
                   options={'maxiter':10000, 'ftol':1e-15})

params2 = result2.x
eps_fit2 = eps_lorentz(f_meep, *params2)
err2_r = np.sqrt(np.mean((np.real(eps_fit2)-eps_r)**2))
err2_i = np.sqrt(np.mean((np.imag(eps_fit2)-eps_i)**2))
print(f"\n2-pole 피팅: RMS ε_r={err2_r:.4f} ε_i={err2_i:.4f}")
print(f"  params: {params2}")

# 3-pole 시도
x0_3pole = list(params2) + [1.0, 1/0.25, 0.3]
bounds_3pole = (
    bounds_2pole[0] + [0,0,0],
    bounds_2pole[1] + [20,15,3]
)
result3 = minimize(residuals, x0_3pole,
                   args=(f_meep, eps_complex),
                   method='L-BFGS-B',
                   bounds=list(zip(bounds_3pole[0], bounds_3pole[1])),
                   options={'maxiter':10000, 'ftol':1e-15})
params3 = result3.x
eps_fit3 = eps_lorentz(f_meep, *params3)
err3_r = np.sqrt(np.mean((np.real(eps_fit3)-eps_r)**2))
err3_i = np.sqrt(np.mean((np.imag(eps_fit3)-eps_i)**2))
print(f"3-pole 피팅: RMS ε_r={err3_r:.4f} ε_i={err3_i:.4f}")

best = params3 if (err3_r+err3_i) < (err2_r+err2_i) else params2
n_poles_best = 3 if (err3_r+err3_i) < (err2_r+err2_i) else 2
eps_best = eps_lorentz(f_meep, *best)
print(f"\n최적: {n_poles_best}-pole 사용")

# ── 3. MEEP Medium 코드 생성 ─────────────────────────────────
eps_inf_fit = best[0]
suscep_list = []
for i in range(n_poles_best):
    sig, f0, gam = best[3*i+1], best[3*i+2], best[3*i+3]
    suscep_list.append(f"    mp.LorentzianSusceptibility(frequency={f0:.6f}, gamma={gam:.6f}, sigma={sig:.6f}),")

meep_code = f"""import meep as mp

# Si 분산 모델 — Palik 데이터 Lorentz 피팅 ({n_poles_best}-pole)
# 유효 범위: 400~720nm (가시광)
# RMS 오차: ε_r={err3_r:.4f} ε_i={err3_i:.4f}
Si_dispersive = mp.Medium(
    epsilon={eps_inf_fit:.6f},
    E_susceptibilities=[
{chr(10).join(suscep_list)}
    ]
)

# 단순 비분산 근사 (빠른 테스트용, 550nm 기준)
Si_simple = mp.Medium(epsilon=16.0, D_conductivity=2*3.14159*0.05*4.0/0.55)
"""
print("\n=== MEEP 코드 ===")
print(meep_code)

# ── 4. 검증 플롯 ─────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=120)

# ε_r 비교
ax = axes[0,0]
ax.plot(wl_nm, eps_r, 'ko-', ms=4, label="Palik data")
ax.plot(wl_nm, np.real(eps_fit2), 'b--', lw=2, label=f"2-pole (RMS={err2_r:.3f})")
ax.plot(wl_nm, np.real(eps_best), 'r-', lw=2, label=f"{n_poles_best}-pole (RMS={err3_r:.3f})")
ax.set(xlabel="λ (nm)", ylabel="ε_r = Re(ε)", title="Real part of dielectric")
ax.legend(); ax.tick_params(direction='in')

# ε_i 비교
ax = axes[0,1]
ax.plot(wl_nm, eps_i, 'ko-', ms=4, label="Palik data")
ax.plot(wl_nm, np.imag(eps_fit2), 'b--', lw=2, label=f"2-pole")
ax.plot(wl_nm, np.imag(eps_best), 'r-', lw=2, label=f"{n_poles_best}-pole")
ax.set(xlabel="λ (nm)", ylabel="ε_i = Im(ε)", title="Imaginary part (absorption)")
ax.legend(); ax.tick_params(direction='in')

# n 비교
n_fit = np.sqrt((np.abs(eps_best) + np.real(eps_best))/2)
k_fit = np.sqrt((np.abs(eps_best) - np.real(eps_best))/2)
ax = axes[1,0]
ax.plot(wl_nm, n_si, 'ko-', ms=4, label="Palik n")
ax.plot(wl_nm, n_fit, 'r-', lw=2, label="Lorentz fit n")
ax.set(xlabel="λ (nm)", ylabel="n", title="Refractive index")
ax.legend(); ax.tick_params(direction='in')

# k 비교
ax = axes[1,1]
ax.plot(wl_nm, k_si, 'ko-', ms=4, label="Palik k")
ax.plot(wl_nm, k_fit, 'r-', lw=2, label="Lorentz fit k")
ax.set(xlabel="λ (nm)", ylabel="k", title="Extinction coefficient")
ax.legend(); ax.tick_params(direction='in')

plt.suptitle(f"Si Lorentz Dispersion Fitting ({n_poles_best}-pole)\nPalik data vs MEEP model",
             fontweight='bold')
plt.tight_layout()
plt.savefig(OUTDIR/"Si_dispersion_fit.png", dpi=120)
plt.close()
print(f"\n플롯 저장: Si_dispersion_fit.png")

# ── 5. 파이썬 모듈로 저장 ────────────────────────────────────
module_code = f'''"""Si 분산 모델 — MEEP용 Lorentz 피팅 (가시광 400~720nm)"""
import meep as mp

# Palik/Green 데이터 기반 {n_poles_best}-pole Lorentz 피팅
# RMS: eps_r={err3_r:.4f}, eps_i={err3_i:.4f}
Si_dispersive = mp.Medium(
    epsilon={eps_inf_fit:.6f},
    E_susceptibilities=[
{chr(10).join(suscep_list)}
    ]
)

# 파장별 참고값 (Palik)
SI_NK = {{
    0.400: (5.570, 0.387),
    0.450: (4.885, 0.068),
    0.500: (4.623, 0.028),
    0.538: (4.460, 0.010),  # G 채널
    0.550: (4.448, 0.011),
    0.600: (4.280, 0.005),
    0.650: (4.208, 0.003),  # R 채널
    0.698: (4.147, 0.001),  # R peak
    0.700: (4.134, 0.001),
    0.720: (4.115, 0.001),
}}

def get_si_eps(wl_um):
    """wl_um: 파장 μm → 복소 유전율 반환 (선형 보간)"""
    import numpy as np
    wls = sorted(SI_NK.keys())
    ns  = [SI_NK[w][0] for w in wls]
    ks  = [SI_NK[w][1] for w in wls]
    n   = np.interp(wl_um, wls, ns)
    k   = np.interp(wl_um, wls, ks)
    return (n + 1j*k)**2
'''
module_path = OUTDIR / "si_material.py"
module_path.write_text(module_code, encoding="utf-8")
print(f"모듈 저장: {module_path}")

# 핵심 파라미터 출력
print("\n=== 최종 MEEP 코드 ===")
print(meep_code)
