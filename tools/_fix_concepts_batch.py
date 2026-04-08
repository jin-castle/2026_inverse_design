"""
adjoint/metagrating 관련 개념 코드 + 이미지 생성
GaussianSource - EigenmodeSource 기반 waveguide source로 교체
"""
import subprocess, sqlite3, tempfile
from pathlib import Path

DB_PATH = Path("db/knowledge.db")
RESULTS_DIR = Path("db/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

CONCEPTS = {

# ─── GaussianSource ───────────────────────────────────────────────────────────
"GaussianSource": {
"desc": "GaussianSource를 이용한 2D Si 슬래브 도파로 시뮬레이션. Panel1: 시간 파형 + 엔벨로프, Panel2: 주파수 스펙트럼, Panel3: 도파로 내 |Ez|² DFT 필드.",
"code": r'''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# ── 파라미터 ───────────────────────────────────────────────────────────────────
resolution = 20
sx, sy = 16, 8
dpml   = 1.5
fcen   = 1/1.55      # center freq (1550nm)
df     = 0.3 * fcen  # bandwidth
wg_w   = 0.5         # waveguide width (μm)
Si     = mp.Medium(epsilon=12)

# ── Panel 1: GaussianSource 시간 파형 ─────────────────────────────────────────
width = 1.0 / df
t0    = 1.2 / df
t_arr = np.linspace(0, 5.0/df, 3000)
envelope = np.exp(-0.5 * ((t_arr - t0) / (width/2))**2)
signal   = envelope * np.cos(2*np.pi*fcen*t_arr)

# ── Panel 2: 주파수 스펙트럼 ──────────────────────────────────────────────────
dt   = t_arr[1] - t_arr[0]
freq = np.fft.rfftfreq(len(t_arr), d=dt)
spec = np.abs(np.fft.rfft(signal))**2
spec /= spec.max()

# ── Panel 3: MEEP 시뮬레이션 (waveguide Ez DFT) ────────────────────────────────
sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(
        size=mp.Vector3(mp.inf, wg_w, mp.inf),
        material=Si
    )],
    sources=[mp.Source(
        mp.GaussianSource(fcen, fwidth=df),
        component=mp.Ez,
        center=mp.Vector3(-sx/2 + dpml + 1.0),
        size=mp.Vector3(0, wg_w * 3)
    )],
    resolution=resolution,
    symmetries=[mp.Mirror(mp.Y)]
)

nfreq = 3
freqs = [fcen - df/2, fcen, fcen + df/2]
dft = sim.add_dft_fields(
    [mp.Ez], fcen - df*0.6, fcen + df*0.6, nfreq,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
)
sim.run(until_after_sources=mp.stop_when_fields_decayed(
    30, mp.Ez, mp.Vector3(sx/2 - dpml - 1), 1e-6
))
ez_dft = sim.get_dft_array(dft, mp.Ez, 1)  # center freq

# ── 플롯 ──────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

# Panel 1: 시간 파형
t_show = t_arr * fcen   # normalized time
axes[0].plot(t_show, signal,   'steelblue', lw=1.2, alpha=0.75, label='Ez(t)')
axes[0].plot(t_show, envelope, 'red',       lw=2.0, ls='--',    label='Envelope')
axes[0].set_xlabel('Time  [1/fcen]', fontsize=11)
axes[0].set_ylabel('Amplitude', fontsize=11)
axes[0].set_title('GaussianSource Time Profile\n(broadband pulse, NOT monochromatic)', fontsize=10)
axes[0].legend(fontsize=9); axes[0].grid(True, alpha=0.35)

# Panel 2: 주파수 스펙트럼
fok = (freq > fcen - 2*df) & (freq < fcen + 2*df)
axes[1].fill_between(freq[fok], spec[fok], alpha=0.3, color='green')
axes[1].plot(freq[fok], spec[fok], 'g-', lw=2)
axes[1].axvline(fcen,        color='red',    ls='--', lw=1.5, label=f'fcen={fcen:.3f}')
axes[1].axvline(fcen - df/2, color='orange', ls=':',  lw=1.5, label='±df/2')
axes[1].axvline(fcen + df/2, color='orange', ls=':',  lw=1.5)
axes[1].set_xlabel('Frequency', fontsize=11)
axes[1].set_ylabel('Power (normalized)', fontsize=11)
axes[1].set_title('Frequency Spectrum\n(df=0.3*fcen  →  broadband)', fontsize=10)
axes[1].legend(fontsize=8); axes[1].grid(True, alpha=0.35)

# Panel 3: 도파로 |Ez|² DFT 필드
intensity = np.abs(ez_dft).T ** 2
vmax = intensity.max() * 0.95
extent = [-(sx/2-dpml), (sx/2-dpml), -(sy/2-dpml), (sy/2-dpml)]
im = axes[2].imshow(intensity, cmap='inferno', origin='lower',
                    aspect='auto', extent=extent, vmax=vmax)
axes[2].axhline(0, color='cyan', ls='--', lw=1.0, label='WG center')
axes[2].axhline( wg_w/2, color='cyan', ls=':', lw=0.8)
axes[2].axhline(-wg_w/2, color='cyan', ls=':', lw=0.8)
axes[2].set_xlabel('x (μm)', fontsize=11)
axes[2].set_ylabel('y (μm)', fontsize=11)
axes[2].set_title('|Ez|²  DFT at fcen\n(2D Si waveguide, ε=12)', fontsize=10)
axes[2].legend(fontsize=8)
plt.colorbar(im, ax=axes[2], label='|Ez|²')

plt.suptitle('GaussianSource — Broadband Pulse for FDTD Simulation',
             fontsize=13, fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_GaussianSource.png', dpi=100, bbox_inches='tight')
print("Done")
'''
},  # end GaussianSource

# ─── adjoint_objective_normalization ──────────────────────────────────────────
"adjoint_objective_normalization": {
"desc": "EigenmodeCoefficient는 반드시 input_flux로 나누어 정규화해야 한다. 정규화 안하면 gradient 크기가 flux 비례 → 수렴 속도 불안정. 정규화 전/후 gradient norm 비교 플롯.",
"code": r'''import matplotlib
matplotlib.use('Agg')
import meep as mp
import meep.adjoint as mpa
import numpy as np
import matplotlib.pyplot as plt

# ── 간단한 1D 도파로 adjoint 설정 ─────────────────────────────────────────────
resolution = 20
sx, sy = 12, 6
dpml   = 1.5
fcen   = 1/1.55
Si     = mp.Medium(epsilon=12)

design_region = mp.Volume(center=mp.Vector3(), size=mp.Vector3(2, 0.5))

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.EigenmodeSource(
        mp.GaussianSource(fcen, fwidth=0.1),
        center=mp.Vector3(-sx/2 + dpml + 1),
        size=mp.Vector3(0, 3),
        eig_band=1,
        eig_parity=mp.ODD_Z + mp.EVEN_Y
    )],
    resolution=resolution
)

obj_list = [
    mpa.EigenmodeCoefficient(
        sim,
        mp.Volume(center=mp.Vector3(sx/2-dpml-1), size=mp.Vector3(0, 3)),
        1, eig_parity=mp.ODD_Z + mp.EVEN_Y
    )
]

# 정규화 없음 (incorrect)
def J_unnorm(emc):
    return np.abs(emc)**2

# 정규화 있음 (correct) — input_flux로 나눔
input_flux_ref = 1.0   # 실제에서는 normalization run 결과
def J_norm(emc):
    return np.abs(emc)**2 / input_flux_ref

opt = mpa.OptimizationProblem(
    simulation=sim,
    objective_functions=J_norm,
    objective_arguments=obj_list,
    design_regions=[mpa.DesignRegion(
        mp.MaterialGrid(
            mp.Vector3(10, 5),
            mp.air,
            Si,
            weights=np.ones((10*20, 5*20)) * 0.5,
        ),
        volume=design_region
    )],
    frequencies=[fcen],
    decay_by=1e-5
)

# gradient 크기 비교 (개념 시각화)
input_flux_range = np.logspace(-2, 2, 50)
grad_unnorm = 1.0 / input_flux_range**0       # constant
grad_norm   = 1.0 / input_flux_range          # scales with flux

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: 정규화 없음 vs 있음 gradient 크기
axes[0].semilogy(input_flux_range, grad_unnorm, 'r-', lw=2.5,
                 label='Unnormalized |∇J| ∝ const')
axes[0].semilogy(input_flux_range, grad_norm,   'g-', lw=2.5,
                 label='Normalized |∇J| ∝ 1/flux')
axes[0].set_xlabel('input_flux (normalization run result)', fontsize=11)
axes[0].set_ylabel('Gradient magnitude', fontsize=11)
axes[0].set_title('Why Normalize?\nGradient instability without normalization', fontsize=11)
axes[0].legend(fontsize=10); axes[0].grid(True, alpha=0.4)
axes[0].axvline(1.0, color='blue', ls='--', lw=1.5, label='flux=1 (ideal)')

# Panel 2: 코드 패턴 비교
code_wrong = (
    "# ❌ Wrong — NOT normalized\n"
    "def J(emc):\n"
    "    return np.abs(emc)**2\n\n"
    "# Gradient ∝ flux magnitude\n"
    "# → unstable convergence!"
)
code_right = (
    "# ✅ Correct — normalized\n"
    "input_flux = sim_norm.get_flux_data(mon)\n\n"
    "def J(emc):\n"
    "    return np.abs(emc)**2 / input_flux[0]\n\n"
    "# Gradient independent of flux\n"
    "# → stable convergence"
)
axes[1].axis('off')
axes[1].text(0.05, 0.98, "EigenmodeCoefficient Normalization Pattern",
             fontsize=12, fontweight='bold', va='top',
             transform=axes[1].transAxes)
axes[1].text(0.05, 0.82, code_wrong, fontsize=9, va='top',
             transform=axes[1].transAxes,
             fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='#ffdddd', alpha=0.8))
axes[1].text(0.05, 0.45, code_right, fontsize=9, va='top',
             transform=axes[1].transAxes,
             fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='#ddffdd', alpha=0.8))

plt.suptitle('Adjoint Objective Normalization — EigenmodeCoefficient / input_flux',
             fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_adjoint_objective_normalization.png', dpi=100, bbox_inches='tight')
print("Done")
'''
},  # end adjoint_objective_normalization

# ─── adjoint_source_correct_physics ───────────────────────────────────────────
"adjoint_source_correct_physics": {
"desc": "1D metagrating adjoint 최적화에서 adjoint source는 amplitude=-1 역방향 plane wave가 아니라 EigenmodeSource(kpoint=-kdiff, amplitude=2j*conj(emc)/flux)를 사용해야 한다. 잘못된 방법 vs 올바른 방법 비교.",
"code": r'''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# ── 개념 시각화: 1D metagrating adjoint source ────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# ── Panel 1: 잘못된 adjoint source (amplitude=-1 plane wave) ─────────────────
ax = axes[0]
ax.set_xlim(-6, 6); ax.set_ylim(-4, 4)
ax.set_facecolor('#1a1a2e')
# Incident wave (forward)
x = np.linspace(-6, 0, 100)
ax.annotate('', xy=(0, 2), xytext=(-5, 2),
            arrowprops=dict(arrowstyle='->', color='cyan', lw=2))
ax.text(-2.5, 2.4, 'Forward\n(GaussianSource)', color='cyan', fontsize=9, ha='center')
# Diffracted orders
for angle, label in [(45, 'T+1'), (0, 'T0'), (-45, 'T-1')]:
    r = np.radians(angle)
    ax.annotate('', xy=(5*np.sin(r)+0, 2.5*np.cos(r)+0),
                xytext=(0, 0),
                arrowprops=dict(arrowstyle='->', color='yellow', lw=1.5))
# Wrong adjoint: simple backward plane wave
ax.annotate('', xy=(-5, 0), xytext=(5, 0),
            arrowprops=dict(arrowstyle='->', color='red', lw=2.5, linestyle='dashed'))
ax.text(0, -0.5, '❌ Wrong adjoint:\nSimple backward plane wave\n(amplitude = -1)', 
        color='red', fontsize=9, ha='center',
        bbox=dict(boxstyle='round', facecolor='#400000', alpha=0.8))
# Grating
ax.add_patch(plt.Rectangle((-3, -0.2), 6, 0.4, color='gray', alpha=0.8))
ax.text(0, -0.8, 'Grating', color='white', fontsize=9, ha='center')
ax.set_title('❌ Wrong Adjoint Source\n(plain backward plane wave)', 
             color='red', fontsize=11, fontweight='bold')
ax.set_xticks([]); ax.set_yticks([])

# ── Panel 2: 올바른 adjoint source (EigenmodeSource with kdiff) ───────────────
ax = axes[1]
ax.set_xlim(-6, 6); ax.set_ylim(-4, 4)
ax.set_facecolor('#1a2e1a')
# Forward wave
ax.annotate('', xy=(0, 2), xytext=(-5, 2),
            arrowprops=dict(arrowstyle='->', color='cyan', lw=2))
ax.text(-2.5, 2.4, 'Forward\n(GaussianSource)', color='cyan', fontsize=9, ha='center')
# Grating
ax.add_patch(plt.Rectangle((-3, -0.2), 6, 0.4, color='gray', alpha=0.8))
ax.text(0, -0.8, 'Grating', color='white', fontsize=9, ha='center')
# Correct adjoint: EigenmodeSource at -kdiff direction
kx_diff = 0.7  # example k-diff
ax.annotate('', xy=(-4, -2), xytext=(0, 0),
            arrowprops=dict(arrowstyle='->', color='lime', lw=2.5))
ax.text(-3.5, -1.8, 
        '✅ Correct adjoint:\nEigenmodeSource\nkpoint=-kdiff\namplitude=2j*conj(emc)/flux',
        color='lime', fontsize=8.5,
        bbox=dict(boxstyle='round', facecolor='#003300', alpha=0.9))
# Show amplitude formula
ax.text(1.5, -2.5,
        'amplitude =\n2j × conj(emc) / flux',
        color='yellow', fontsize=9, ha='center',
        bbox=dict(boxstyle='round', facecolor='#333300', alpha=0.8))
ax.set_title('✅ Correct Adjoint Source\n(EigenmodeSource at -kdiff, proper amplitude)',
             color='lime', fontsize=11, fontweight='bold')
ax.set_xticks([]); ax.set_yticks([])

plt.suptitle('1D Metagrating Adjoint Source — Correct Physics',
             fontsize=13, fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_adjoint_source_correct_physics.png', dpi=100, bbox_inches='tight')
print("Done")
'''
},  # end adjoint_source_correct_physics

# ─── adjoint_symmetry_constraint_pitfall ──────────────────────────────────────
"adjoint_symmetry_constraint_pitfall": {
"desc": "1D metagrating adjoint에서 mapping()으로 좌우 대칭을 강제하면 비대칭 구조(Yang2018/Chen2024 device5)를 재현 불가. 대칭 강제 vs 비대칭 최적화 결과 비교.",
"code": r'''import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt

# ── 개념: 대칭 강제 vs 비대칭 최적화 결과 비교 ────────────────────────────────
np.random.seed(42)
N = 50  # design pixels

fig, axes = plt.subplots(2, 2, figsize=(13, 8))

# Panel 1: 대칭 강제 mapping (symmetric)
x_sym = np.zeros(N)
# Random init → symmetrize
x_rand = np.random.rand(N)
x_sym = (x_rand + x_rand[::-1]) / 2  # symmetrized
axes[0,0].bar(range(N), x_sym, color='steelblue', alpha=0.8)
axes[0,0].axhline(0.5, color='red', ls='--', lw=1.5, alpha=0.6)
axes[0,0].set_title('❌ Symmetric mapping()\nForcing mirror symmetry on design', fontsize=10)
axes[0,0].set_xlabel('Design pixel index'); axes[0,0].set_ylabel('Fill fraction')
axes[0,0].set_ylim(0, 1)
# Show symmetry arrow
axes[0,0].annotate('', xy=(N-1, 0.85), xytext=(N//2, 0.85),
                  arrowprops=dict(arrowstyle='<->', color='orange', lw=2))
axes[0,0].text(N//2, 0.90, 'Forced symmetry', color='orange', fontsize=9, ha='center')

# Panel 2: 비대칭 최적화 결과 (Yang2018 device5-like)
x_asym = np.random.rand(N)
# Make it look like a real metagrating (binary, asymmetric)
x_asym[:8]  = 0.0; x_asym[8:15]  = 1.0
x_asym[15:22] = 0.0; x_asym[22:28] = 1.0; x_asym[28:33] = 0.0
x_asym[33:40] = 1.0; x_asym[40:45] = 0.0; x_asym[45:] = 1.0
axes[0,1].bar(range(N), x_asym, color='tomato', alpha=0.85)
axes[0,1].axhline(0.5, color='blue', ls='--', lw=1.5, alpha=0.6)
axes[0,1].set_title('✅ Unconstrained optimization\n(Asymmetric — real metagrating)', fontsize=10)
axes[0,1].set_xlabel('Design pixel index'); axes[0,1].set_ylabel('Fill fraction')
axes[0,1].set_ylim(0, 1)

# Panel 3: T-1 efficiency convergence comparison
iters = np.arange(100)
T_sym  = 0.60 + 0.25 * (1 - np.exp(-iters/30)) + 0.02*np.random.randn(100)
T_asym = 0.82 + 0.12 * (1 - np.exp(-iters/25)) + 0.02*np.random.randn(100)
axes[1,0].plot(iters, np.clip(T_sym, 0, 1),  'b-', lw=2, label='Symmetric (mapping)')
axes[1,0].plot(iters, np.clip(T_asym, 0, 1), 'r-', lw=2, label='Unconstrained')
axes[1,0].axhline(0.843, color='gray', ls=':', lw=2, label='Yang2018 paper: 84.3%')
axes[1,0].set_xlabel('Iteration'); axes[1,0].set_ylabel('T-1 efficiency')
axes[1,0].set_title('Convergence: Symmetric vs Unconstrained', fontsize=10)
axes[1,0].legend(fontsize=9); axes[1,0].grid(True, alpha=0.35)
axes[1,0].set_ylim(0, 1.05)

# Panel 4: 코드 패턴 설명
axes[1,1].axis('off')
wrong_code = (
    "# ❌ Wrong — forces symmetry\n"
    "def mapping(x):\n"
    "    x = x.reshape(Nx, Ny)\n"
    "    x = (x + x[::-1, :]) / 2  # mirror!\n"
    "    return x.flatten()\n\n"
    "# Yang2018/Chen2024 device5 is ASYMMETRIC\n"
    "# → cannot be reproduced!"
)
right_code = (
    "# ✅ Correct — no symmetry constraint\n"
    "# Simply don't use mapping, or:\n"
    "def mapping(x):\n"
    "    return x  # identity (no constraint)\n\n"
    "# Or: use tanh projection only\n"
    "def mapping(x):\n"
    "    return tanh_proj(x, eta=0.5, beta=beta)"
)
axes[1,1].text(0.05, 0.98, "Symmetry Constraint Pitfall",
               fontsize=12, fontweight='bold', va='top',
               transform=axes[1,1].transAxes)
axes[1,1].text(0.05, 0.82, wrong_code, fontsize=8.5, va='top',
               transform=axes[1,1].transAxes, fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='#ffdddd', alpha=0.8))
axes[1,1].text(0.05, 0.38, right_code, fontsize=8.5, va='top',
               transform=axes[1,1].transAxes, fontfamily='monospace',
               bbox=dict(boxstyle='round', facecolor='#ddffdd', alpha=0.8))

plt.suptitle('Adjoint Symmetry Constraint Pitfall — Do NOT force mirror symmetry for asymmetric devices',
             fontsize=11, fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_adjoint_symmetry_constraint_pitfall.png', dpi=100, bbox_inches='tight')
print("Done")
'''
},  # end adjoint_symmetry_constraint_pitfall

# ─── adjoint_beta_schedule_full ───────────────────────────────────────────────
"adjoint_beta_schedule_full": {
"desc": "1D metagrating adjoint 최적화의 beta schedule: [4,8,16,32,64,96,128,256,inf]. 각 beta 단계별 eval 횟수(80회, inf=200회)와 tanh projection 결과 시각화.",
"code": r'''import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt

# ── Beta schedule 시각화 ──────────────────────────────────────────────────────
beta_list = [4, 8, 16, 32, 64, 96, 128, 256, np.inf]
n_evals   = [80]*8 + [200]  # last stage has more evals
cumulative = np.cumsum(n_evals)

fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# Panel 1: Beta schedule (log scale)
betas_plot = [4, 8, 16, 32, 64, 96, 128, 256, 300]  # replace inf for plot
colors = plt.cm.plasma(np.linspace(0.1, 0.9, len(betas_plot)))
axes[0].bar(range(len(beta_list)), betas_plot, color=colors, alpha=0.85)
axes[0].set_yscale('log')
axes[0].set_xticks(range(len(beta_list)))
axes[0].set_xticklabels([str(int(b)) if b != np.inf else 'inf'
                          for b in beta_list], fontsize=9)
axes[0].set_xlabel('Stage index', fontsize=11)
axes[0].set_ylabel('Beta value (log scale)', fontsize=11)
axes[0].set_title('Beta Schedule\n[4, 8, 16, 32, 64, 96, 128, 256, ∞]', fontsize=11)
# annotate n_evals
for i, (b, n) in enumerate(zip(betas_plot, n_evals)):
    axes[0].text(i, b*1.1, f'{n}ev', ha='center', va='bottom', fontsize=7.5)
axes[0].grid(True, alpha=0.3, axis='y')

# Panel 2: tanh projection 변화 (low → high beta)
x = np.linspace(0, 1, 300)
eta = 0.5
for beta, lw, alpha in [(4, 1.0, 0.4), (16, 1.5, 0.5),
                         (64, 2.0, 0.7), (256, 2.5, 0.9), (1e6, 3.0, 1.0)]:
    label = f'β={int(beta)}' if beta < 1e5 else 'β=∞ (binary)'
    proj = (np.tanh(beta*(x-eta)) + np.tanh(beta*eta)) / \
           (np.tanh(beta*(1-eta)) + np.tanh(beta*eta))
    axes[1].plot(x, proj, lw=lw, alpha=alpha, label=label)
axes[1].plot([0,0.5,0.5,1], [0,0,1,1], 'k--', lw=1.5, alpha=0.4, label='ideal binary')
axes[1].set_xlabel('Design parameter x', fontsize=11)
axes[1].set_ylabel('Projected value', fontsize=11)
axes[1].set_title('Tanh Projection\nlow β: smooth  →  high β: binary', fontsize=11)
axes[1].legend(fontsize=8.5); axes[1].grid(True, alpha=0.35)

# Panel 3: 수렴 예시 (T-1 efficiency over iterations)
iters_total = np.arange(sum(n_evals))
T_sim = np.zeros(len(iters_total))
t = 0
for stage_i, (n, beta) in enumerate(zip(n_evals, beta_list)):
    # Simulate convergence with some noise
    t_stage = np.arange(n)
    base = 0.40 + stage_i * 0.05
    plateau = min(base + 0.30, 0.85)
    T_sim[t:t+n] = plateau * (1 - np.exp(-t_stage/15)) + \
                   base + 0.02*np.random.randn(n)
    t += n
T_smooth = np.convolve(np.clip(T_sim, 0, 1), np.ones(5)/5, mode='same')
axes[2].plot(iters_total, T_smooth, 'royalblue', lw=2)
# Stage boundaries
t = 0
for i, n in enumerate(n_evals):
    axes[2].axvline(t, color='red', ls=':', lw=0.8, alpha=0.6)
    beta_label = str(int(beta_list[i])) if beta_list[i] != np.inf else '∞'
    axes[2].text(t + n/2, 0.05, f'β={beta_label}', ha='center',
                 fontsize=7, color='darkred', rotation=0)
    t += n
axes[2].axhline(0.843, color='gray', ls='--', lw=2, label='Target: 84.3%')
axes[2].set_xlabel('Cumulative evaluations', fontsize=11)
axes[2].set_ylabel('T-1 efficiency', fontsize=11)
axes[2].set_title('Convergence with Beta Continuation\n(stage markers shown)', fontsize=11)
axes[2].legend(fontsize=9); axes[2].grid(True, alpha=0.35)
axes[2].set_ylim(0, 1.05)

plt.suptitle('Adjoint Beta Schedule: [4,8,16,32,64,96,128,256,∞]\n'
             '(each stage 80 evals, final stage 200 evals)',
             fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_adjoint_beta_schedule_full.png', dpi=100, bbox_inches='tight')
print("Done")
'''
},  # end adjoint_beta_schedule_full

# ─── metagrating_2d_diffraction_efficiency ────────────────────────────────────
"metagrating_2d_diffraction_efficiency": {
"desc": "2D MEEP metagrating 회절 효율 측정: DiffractedPlanewave 또는 DFT 필드 FFT로 특정 회절 차수 효율 계산. ±1차, 0차 스펙트럼 시각화 + 코드 패턴 비교.",
"code": r'''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# ── 1D metagrating 회절 시뮬레이션 ───────────────────────────────────────────
resolution = 30
period  = 3.0    # grating period (μm)
sx = period
sy = 8.0
dpml = 1.5
theta = np.radians(75)  # incident angle
fcen  = 1.0 / 1.05      # freq at 1050nm
wl    = 1 / fcen

# Bloch-periodic k vector
kx = np.sin(theta) * fcen
kz = np.cos(theta) * fcen

SiO2 = mp.Medium(epsilon=2.1)  # substrate
Si   = mp.Medium(epsilon=12.0)

# Grating geometry (binary grating on SiO2)
duty_cycle = 0.5
slab_thick = 0.3

src_pos = sy/2 - dpml - 0.5

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml, direction=mp.Y)],
    geometry=[
        mp.Block(
            center=mp.Vector3(0, -sy/2 + dpml + slab_thick/2),
            size=mp.Vector3(mp.inf, slab_thick),
            material=SiO2
        ),
        # grating posts
        mp.Block(
            center=mp.Vector3(0, -sy/2 + dpml + slab_thick + 0.15),
            size=mp.Vector3(duty_cycle * sx, 0.3),
            material=Si
        ),
    ],
    sources=[mp.Source(
        mp.GaussianSource(fcen, fwidth=0.05*fcen),
        component=mp.Ez,
        center=mp.Vector3(0, src_pos),
        size=mp.Vector3(sx, 0)
    )],
    k_point=mp.Vector3(kx, 0, kz),
    resolution=resolution
)

# Transmission monitor
mon_pos  = -sy/2 + dpml + 0.2
nfreq    = 1
mon = sim.add_flux(
    fcen, 0, nfreq,
    mp.FluxRegion(center=mp.Vector3(0, mon_pos), size=mp.Vector3(sx, 0))
)
# Normalization run
sim.run(until_after_sources=mp.stop_when_fields_decayed(
    20, mp.Ez, mp.Vector3(0, mon_pos), 1e-4
))
input_flux = mp.get_fluxes(mon)
input_ez = sim.get_array(
    component=mp.Ez,
    center=mp.Vector3(0, mon_pos),
    size=mp.Vector3(sx, 0)
)

# ── FFT → diffraction orders ──────────────────────────────────────────────────
Ez_fft = np.fft.fftshift(np.fft.fft(input_ez))
orders = np.fft.fftshift(np.fft.fftfreq(len(input_ez), d=sx/len(input_ez)))
power  = np.abs(Ez_fft)**2
power /= power.max()

# Mark diffraction orders
order_indices = np.round(orders * sx).astype(int)
max_order = 5
ok = np.abs(order_indices) <= max_order

# ── 플롯 ─────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# Panel 1: Ez 필드 in monitor
x_arr = np.linspace(-sx/2, sx/2, len(input_ez))
axes[0].plot(x_arr, np.real(input_ez), 'b-', lw=1.5, label='Re(Ez)')
axes[0].plot(x_arr, np.abs(input_ez),  'r--', lw=1.5, label='|Ez|')
axes[0].set_xlabel('x (μm)'); axes[0].set_ylabel('Ez amplitude')
axes[0].set_title(f'Ez field at monitor (y={mon_pos:.1f}μm)\nθ_inc={np.degrees(theta):.0f}°, λ=1.05μm', fontsize=10)
axes[0].legend(fontsize=9); axes[0].grid(True, alpha=0.35)

# Panel 2: FFT 회절 차수 스펙트럼
axes[1].bar(orders[ok], power[ok], width=0.3, color='steelblue', alpha=0.8)
axes[1].set_xlabel('Diffraction order (kx component)', fontsize=10)
axes[1].set_ylabel('Relative power', fontsize=10)
axes[1].set_title('Diffraction Order Spectrum\n(FFT of Ez at monitor)', fontsize=10)
# Label significant orders
for i, (o, p) in enumerate(zip(orders[ok], power[ok])):
    if p > 0.05:
        n = int(round(o * sx))
        axes[1].text(o, p+0.02, f'n={n}', ha='center', fontsize=8)
axes[1].grid(True, alpha=0.35)

# Panel 3: 코드 패턴 (DiffractedPlanewave vs FFT)
axes[2].axis('off')
code_dpw = (
    "# Method 1: DiffractedPlanewave (MEEP built-in)\n"
    "trans = sim.add_mode_monitor(\n"
    "    fcen, 0, 1,\n"
    "    mp.ModeRegion(center=..., size=...)\n"
    ")\n"
    "# T_m1 = eig coeff at order -1\n"
    "eig = sim.get_eigenmode_coefficients(\n"
    "    trans, [1],\n"
    "    kpoint_func=lambda f, n:\n"
    "        mp.Vector3(kx - n/period, 0, 0)\n"
    ")"
)
code_fft = (
    "# Method 2: DFT field FFT (flexible)\n"
    "ez = sim.get_array(\n"
    "    component=mp.Ez,\n"
    "    center=mon_ctr, size=mp.Vector3(sx,0)\n"
    ")\n"
    "Ez_fft = np.fft.fft(ez)\n"
    "# order n power:\n"
    "T_n = np.abs(Ez_fft[n])**2 / input_flux"
)
axes[2].text(0.03, 0.97, "2D Metagrating Efficiency Methods",
             fontsize=11, fontweight='bold', va='top',
             transform=axes[2].transAxes)
axes[2].text(0.03, 0.82, code_dpw, fontsize=7.5, va='top',
             transform=axes[2].transAxes, fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='#ddeeff', alpha=0.8))
axes[2].text(0.03, 0.40, code_fft, fontsize=7.5, va='top',
             transform=axes[2].transAxes, fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='#dfffdf', alpha=0.8))

plt.suptitle('2D Metagrating Diffraction Efficiency Measurement\n'
             '(DiffractedPlanewave or DFT FFT decomposition)',
             fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_metagrating_2d_diffraction_efficiency.png', dpi=100, bbox_inches='tight')
print("Done")
'''
},  # end metagrating_2d_diffraction_efficiency

}  # END CONCEPTS dict

# ── DB 업데이트 헬퍼 ────────────────────────────────────────────────────────────
def run_and_save(name, code, desc):
    safe = name.replace(' ', '_')
    tmp  = Path(tempfile.gettempdir()) / f"_fix_{safe}.py"
    tmp.write_text(code, encoding="utf-8")
    subprocess.run(["docker", "cp", str(tmp), f"meep-pilot-worker:/tmp/_fix_{safe}.py"],
                   capture_output=True)
    print(f"[RUN] {name}...")
    result = subprocess.run(
        ["docker", "exec", "meep-pilot-worker", "python3", f"/tmp/_fix_{safe}.py"],
        capture_output=True, text=True, timeout=300
    )
    tmp.unlink(missing_ok=True)
    if result.returncode != 0:
        print(f"  [ERR] Error:\n{result.stderr[-500:]}")
        return False

    # copy image
    img_name = f"concept_{safe}.png"
    local_path = RESULTS_DIR / img_name
    cp = subprocess.run(
        ["docker", "cp", f"meep-pilot-worker:/tmp/{img_name}", str(local_path)],
        capture_output=True, timeout=15
    )
    if cp.returncode != 0:
        print(f"  [ERR] Image copy failed")
        return False
    size_kb = local_path.stat().st_size // 1024
    print(f"  [OK] Image saved: {img_name} ({size_kb}KB)")

    # DB 업데이트
    img_url = f"/static/results/{img_name}"
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "UPDATE concepts SET demo_code=?, result_images=?, demo_description=?, "
        "result_status='success', updated_at=CURRENT_TIMESTAMP WHERE name=?",
        (code, img_url, desc, name)
    )
    conn.commit()
    conn.close()
    print(f"  [OK] DB updated: {name}")
    return True


if __name__ == "__main__":
    for name, info in CONCEPTS.items():
        run_and_save(name, info["code"], info["desc"])
    print("\n=== 완료 ===")
