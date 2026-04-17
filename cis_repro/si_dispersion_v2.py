"""
Si 분산 모델 v2 — MEEP 안정성 확보
====================================
pole이 소스 주파수(가시광 1.4~2.2)에 너무 가까우면 NaN 발생.
→ pole을 f > 3.5 (λ < 285nm, 딥 UV)에만 허용해서 안전 거리 확보.

또는 Drude-Lorentz 대신 단순 다항식 피팅 → epsilon_diag 사용.
"""
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from pathlib import Path

OUTDIR = Path(__file__).parent

# ── Palik 데이터 ─────────────────────────────────────────────
si_data = np.array([
    [400, 5.570, 0.387], [420, 5.291, 0.218], [440, 5.066, 0.123],
    [460, 4.885, 0.068], [480, 4.741, 0.044], [500, 4.623, 0.028],
    [520, 4.527, 0.017], [540, 4.448, 0.011], [560, 4.382, 0.008],
    [580, 4.326, 0.006], [600, 4.280, 0.005], [620, 4.241, 0.004],
    [640, 4.208, 0.003], [660, 4.180, 0.002], [680, 4.155, 0.002],
    [700, 4.134, 0.001], [720, 4.115, 0.001],
])
wl_nm = si_data[:,0]; n_si = si_data[:,1]; k_si = si_data[:,2]
wl_um = wl_nm / 1000.0
f_vis = 1.0 / wl_um
eps_complex = (n_si + 1j*k_si)**2
eps_r = np.real(eps_complex); eps_i = np.imag(eps_complex)

print("가시광 주파수 범위:", f_vis[-1], "~", f_vis[0], "(MEEP 단위)")
print("→ pole은 f > 3.5 이상에만 배치 (λ < 285nm)")

# ── 방법 1: pole 주파수를 딥 UV로 제한한 Lorentz ───────────────
def eps_lorentz(f, eps_inf, *poles):
    eps = np.ones(len(f), dtype=complex) * eps_inf
    for i in range(len(poles)//3):
        sig, f0, gam = poles[3*i], poles[3*i+1], poles[3*i+2]
        eps += sig * f0**2 / (f0**2 - f**2 - 1j*gam*f)
    return eps

def residuals(params, f, eps_target, weight_imag=5.0):
    eps_pred = eps_lorentz(f, *params)
    err = np.sum((np.real(eps_pred)-np.real(eps_target))**2
                 + weight_imag*(np.imag(eps_pred)-np.imag(eps_target))**2)
    return err

# 3-pole, 모두 f0 > 3.5 제약
# UV Si 흡수 구조: ~3.4eV(365nm), ~4.2eV(295nm), ~5.5eV(225nm)
# MEEP f: 1/0.365=2.74, 1/0.295=3.39, 1/0.225=4.44
# f0 > 3.5 제약을 위해 f0 ∈ [3.5, 8.0]
x0 = [
    1.5,           # eps_inf
    10.0, 4.0, 1.5,  # pole1: near UV 320nm (f=3.1)
    5.0,  5.0, 1.0,  # pole2: UV 200nm (f=5.0)
    8.0,  6.5, 0.5,  # pole3: VUV (f=6.5)
]
# 제약: f0_i ∈ [3.5, 10.0], gamma_i > 0
bounds = [
    (0.5, 5.0),         # eps_inf
    (0.0, 30.0), (3.5, 10.0), (0.1, 5.0),   # pole1
    (0.0, 30.0), (3.5, 10.0), (0.1, 5.0),   # pole2
    (0.0, 30.0), (3.5, 10.0), (0.1, 5.0),   # pole3
]
res = minimize(residuals, x0, args=(f_vis, eps_complex),
               method='L-BFGS-B', bounds=bounds,
               options={'maxiter':20000, 'ftol':1e-16, 'gtol':1e-12})
p = res.x
eps_fit = eps_lorentz(f_vis, *p)
rms_r = np.sqrt(np.mean((np.real(eps_fit)-eps_r)**2))
rms_i = np.sqrt(np.mean((np.imag(eps_fit)-eps_i)**2))
print(f"\n3-pole (f0>3.5): RMS ε_r={rms_r:.4f} ε_i={rms_i:.4f}")
print(f"  eps_inf={p[0]:.4f}")
for i in range(3):
    print(f"  pole{i+1}: sigma={p[3*i+1]:.4f} f0={p[3*i+2]:.4f} gamma={p[3*i+3]:.4f}")

# ── MEEP 안전성 검증 ────────────────────────────────────────
pole_freqs = [p[3*i+2] for i in range(3)]
safety_margin = min(pole_freqs) / f_vis[0]
print(f"\n최소 pole 주파수: {min(pole_freqs):.3f}")
print(f"최대 소스 주파수 (400nm): {f_vis[0]:.3f}")
print(f"안전 마진 (비율): {safety_margin:.3f} {'✓ 안전' if safety_margin > 1.3 else '⚠️ 위험'}")

# ── 방법 2: 안전한 단순 모델 (eps_inf + 1-pole 높은 주파수) ───
# 가시광 대역 ε_r 변화가 주도적 → 흡수(ε_i)는 Drude 항으로 근사
print("\n=== 방법 2: 1-pole 안전 모델 ===")
x0_1 = [1.0, 25.0, 5.0, 2.0]  # eps_inf, sigma, f0(deep UV), gamma
bounds_1 = [(0.1,5.0), (0,100), (4.0,12.0), (0.1,10.0)]
res1 = minimize(residuals, x0_1, args=(f_vis, eps_complex, 3.0),
                method='L-BFGS-B', bounds=bounds_1,
                options={'maxiter':20000, 'ftol':1e-15})
p1 = res1.x
eps_fit1 = eps_lorentz(f_vis, *p1)
rms_r1 = np.sqrt(np.mean((np.real(eps_fit1)-eps_r)**2))
rms_i1 = np.sqrt(np.mean((np.imag(eps_fit1)-eps_i)**2))
print(f"1-pole (f0>4.0): RMS ε_r={rms_r1:.4f} ε_i={rms_i1:.4f}")
print(f"  eps_inf={p1[0]:.4f} sigma={p1[1]:.4f} f0={p1[2]:.4f} gamma={p1[3]:.4f}")

# ── 플롯 ─────────────────────────────────────────────────────
fig, axes = plt.subplots(1,2, figsize=(12,4), dpi=120)
for ax, (yr, yf1, yf3, ylabel) in zip(axes, [
    (eps_r,np.real(eps_fit1),np.real(eps_fit),"ε_r"),
    (eps_i,np.imag(eps_fit1),np.imag(eps_fit),"ε_i (absorption)"),
]):
    ax.plot(wl_nm, yr, 'ko-', ms=4, label="Palik")
    ax.plot(wl_nm, yf1, 'b--', lw=2, label=f"1-pole (f0>{bounds_1[2][0]})")
    ax.plot(wl_nm, yf3, 'r-', lw=2, label=f"3-pole (f0>3.5)")
    ax.set(xlabel="λ (nm)", ylabel=ylabel); ax.legend(); ax.tick_params(direction='in')
plt.suptitle("Si Lorentz Fitting v2 — Deep UV poles only", fontweight='bold')
plt.tight_layout(); plt.savefig(OUTDIR/"Si_dispersion_v2.png"); plt.close()

# 더 나은 쪽 선택
if (rms_r+rms_i) < (rms_r1+rms_i1):
    best = p; n_poles = 3
else:
    best = p1; n_poles = 1

eps_inf = best[0]
suscep = []
for i in range(n_poles):
    s,f0,g = best[3*i+1], best[3*i+2], best[3*i+3]
    suscep.append(f"        mp.LorentzianSusceptibility(frequency={f0:.6f}, gamma={g:.6f}, sigma={s:.6f}),")

code = f"""# Si 분산 모델 v2 — Palik {n_poles}-pole Lorentz (딥UV pole만)
# MEEP 안전: 모든 pole이 가시광 주파수(1.4~2.2)보다 훨씬 높음
# 유효 범위: 400~720nm
Si_dispersive = mp.Medium(
    epsilon={eps_inf:.6f},
    E_susceptibilities=[
{chr(10).join(suscep)}
    ]
)"""
print("\n=== 최종 MEEP 코드 ===")
print(code)

# 모듈 저장
Path(OUTDIR/"si_material_v2.py").write_text(
    f'import meep as mp\n\n{code}\n\nSi_simple = mp.Medium(epsilon=19.8)\n',
    encoding="utf-8"
)
print(f"\n저장: {OUTDIR}/si_material_v2.py")
print(f"플롯: {OUTDIR}/Si_dispersion_v2.png")
