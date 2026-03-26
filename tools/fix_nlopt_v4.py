#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nlopt fix v4: 2D quasi-1D simulation (works with Ez)"""

import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt
import nlopt

# 1D Fabry-Perot 공진기: NLopt로 최대 반사율 두께 탐색
# 2D quasi-1D (sy=2) → Ez 가능, 평면파 소스

resolution = 20
fcen = 0.5
df = 0.4
sx = 12.0
sy = 2.0   # quasi-1D: small sy, periodic-like
dpml = 1.0
Si = mp.Medium(epsilon=12.0)

cell = mp.Vector3(sx, sy, 0)
pml = [mp.PML(dpml)]

def make_sources():
    return [mp.Source(
        mp.GaussianSource(fcen, fwidth=df),
        component=mp.Ez,
        center=mp.Vector3(-sx/2 + dpml + 0.5, 0),
        size=mp.Vector3(0, sy, 0)   # full height = plane wave
    )]

def simulate_fp_reflection(thickness):
    geometry = [
        mp.Block(size=mp.Vector3(float(thickness), sy, 0),
                 center=mp.Vector3(0, 0, 0), material=Si)
    ]
    sources = make_sources()

    # Normalization run (no slab)
    sim_ref = mp.Simulation(
        cell_size=cell, geometry=[], sources=sources,
        boundary_layers=pml, resolution=resolution
    )
    refl_ref = sim_ref.add_flux(fcen, df, 1,
        mp.FluxRegion(center=mp.Vector3(-sx/2 + dpml + 0.25, 0),
                      size=mp.Vector3(0, sy, 0), weight=-1))
    inc_ref = sim_ref.add_flux(fcen, df, 1,
        mp.FluxRegion(center=mp.Vector3(-sx/2 + dpml + 0.25, 0),
                      size=mp.Vector3(0, sy, 0)))
    sim_ref.run(until_after_sources=60)
    inc_val = mp.get_fluxes(inc_ref)[0]
    refl_data = sim_ref.get_flux_data(refl_ref)
    sim_ref.reset_meep()

    # Slab run
    sim = mp.Simulation(
        cell_size=cell, geometry=geometry, sources=sources,
        boundary_layers=pml, resolution=resolution
    )
    refl_mon = sim.add_flux(fcen, df, 1,
        mp.FluxRegion(center=mp.Vector3(-sx/2 + dpml + 0.25, 0),
                      size=mp.Vector3(0, sy, 0), weight=-1))
    sim.load_minus_flux_data(refl_mon, refl_data)
    sim.run(until_after_sources=60)
    refl_val = -mp.get_fluxes(refl_mon)[0]
    sim.reset_meep()

    R = float(np.clip(refl_val / inc_val, 0, 1)) if inc_val > 0 else 0.0
    return R

history_t, history_R = [], []

def objective(x, grad):
    t = float(x[0])
    R = simulate_fp_reflection(t)
    history_t.append(t)
    history_R.append(R)
    print(f"  t={t:.3f} → R={R:.4f}", flush=True)
    return R

opt = nlopt.opt(nlopt.LN_COBYLA, 1)
opt.set_max_objective(objective)
opt.set_lower_bounds([0.2])
opt.set_upper_bounds([2.0])
opt.set_xtol_rel(1e-2)
opt.set_maxeval(15)
x_opt = opt.optimize([0.7])
R_opt = opt.last_optimum_value()
print(f"Optimal t={x_opt[0]:.4f}, R={R_opt:.4f}")

# Dense sweep for visualization
t_sweep = np.linspace(0.2, 2.0, 30)
R_sweep = [simulate_fp_reflection(t) for t in t_sweep]

fig = plt.figure(figsize=(12, 5), facecolor='#1a1a2e')
ax0 = fig.add_subplot(1, 2, 1)
ax1 = fig.add_subplot(1, 2, 2)

for ax in [ax0, ax1]:
    ax.set_facecolor('#16213e')
    for sp in ax.spines.values():
        sp.set_color('#444')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    ax.grid(True, alpha=0.2, color='gray')

# Panel 1: 최적화 수렴 곡선
ax0.plot(range(1, len(history_R)+1), history_R, 'o-',
         color='#4FC3F7', markersize=7, linewidth=2, label='R(t) evaluated')
ax0.fill_between(range(1, len(history_R)+1), history_R, alpha=0.2, color='#4FC3F7')
ax0.axhline(R_opt, color='#FF6B6B', ls='--', lw=2, label=f'R_opt={R_opt:.3f}')
ax0.set_xlabel('Iteration', fontsize=11)
ax0.set_ylabel('Reflection R', fontsize=11)
ax0.set_title('NLopt COBYLA: Fabry-Perot\nOptimization Convergence', fontsize=10)
ax0.legend(fontsize=9, facecolor='#16213e', labelcolor='white')
ax0.set_ylim(0, 1.1)

# Panel 2: R vs 두께 (공진 패턴)
ax1.fill_between(t_sweep, R_sweep, alpha=0.25, color='#69F0AE')
ax1.plot(t_sweep, R_sweep, 's-', color='#00E676', markersize=5, lw=2, label='R(t)')
ax1.axvline(x_opt[0], color='#FF6B6B', ls='--', lw=2,
            label=f'NLopt opt: t={x_opt[0]:.3f}')
ax1.set_xlabel('Slab Thickness (a)', fontsize=11)
ax1.set_ylabel('Reflection R', fontsize=11)
ax1.set_title('Fabry-Perot: R vs Slab Thickness\n(Si slab ε=12, resonances at λ/2n)', fontsize=10)
ax1.legend(fontsize=9, facecolor='#16213e', labelcolor='white')
ax1.set_ylim(0, 1.1)
# 이론적 공진 두께 표시
n_si = np.sqrt(12.0)
for m in range(1, 5):
    t_res = m / (2 * n_si * fcen)
    if 0.2 <= t_res <= 2.0:
        ax1.axvline(t_res, color='#FFF176', ls=':', lw=1.2, alpha=0.5)
ax1.text(0.98, 0.95, 'dotted: λ/2n resonances', transform=ax1.transAxes,
         ha='right', va='top', fontsize=8, color='#FFF176')

plt.tight_layout()
plt.savefig('/tmp/concept_nlopt.png', dpi=100, bbox_inches='tight',
            facecolor=fig.get_facecolor())
print("Saved /tmp/concept_nlopt.png")
