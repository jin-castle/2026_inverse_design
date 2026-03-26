#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nlopt fix v6: transmission-based R=1-T (avoids load_minus issues)
"""
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt
import nlopt

# 2D quasi-1D Fabry-Perot
# T 측정 후 R = 1 - T로 반사율 계산 (lossless slab)

resolution = 15
fcen = 0.5
df = 0.5
sx = 12.0
sy = 4.0
dpml = 1.0
Si = mp.Medium(epsilon=12.0)

cell = mp.Vector3(sx, sy, 0)
pml = [mp.PML(dpml, direction=mp.X)]

def make_sources():
    return [mp.Source(
        mp.GaussianSource(fcen, fwidth=df),
        component=mp.Ez,
        center=mp.Vector3(-sx/2 + dpml + 0.5, 0),
        size=mp.Vector3(0, sy, 0)
    )]

# Normalization: T through open space
print("Computing normalization (no slab)...", flush=True)
sim_norm = mp.Simulation(
    cell_size=cell, geometry=[], sources=make_sources(),
    boundary_layers=pml, resolution=resolution
)
norm_mon = sim_norm.add_flux(fcen, df, 1,
    mp.FluxRegion(center=mp.Vector3(sx/2 - dpml - 0.5, 0),
                  size=mp.Vector3(0, sy, 0)))
sim_norm.run(until_after_sources=60)
P_norm = mp.get_fluxes(norm_mon)[0]
print(f"  P_norm = {P_norm:.4f}", flush=True)
sim_norm.reset_meep()

def simulate_fp_transmission(thickness):
    geometry = [
        mp.Block(size=mp.Vector3(float(thickness), sy, 0),
                 center=mp.Vector3(0, 0, 0), material=Si)
    ]
    sim = mp.Simulation(
        cell_size=cell, geometry=geometry, sources=make_sources(),
        boundary_layers=pml, resolution=resolution
    )
    trans_mon = sim.add_flux(fcen, df, 1,
        mp.FluxRegion(center=mp.Vector3(sx/2 - dpml - 0.5, 0),
                      size=mp.Vector3(0, sy, 0)))
    sim.run(until_after_sources=60)
    P_trans = mp.get_fluxes(trans_mon)[0]
    sim.reset_meep()
    T = float(np.clip(P_trans / P_norm, 0, 1)) if P_norm > 0 else 0.5
    R = 1.0 - T  # lossless: R = 1 - T
    return R, T

history_t, history_R = [], []

def objective(x, grad):
    t = float(x[0])
    R, T = simulate_fp_transmission(t)
    history_t.append(t)
    history_R.append(R)
    print(f"  t={t:.3f} → R={R:.4f} T={T:.4f}", flush=True)
    return R  # maximize R

opt = nlopt.opt(nlopt.LN_COBYLA, 1)
opt.set_max_objective(objective)
opt.set_lower_bounds([0.1])
opt.set_upper_bounds([1.5])
opt.set_xtol_rel(1e-2)
opt.set_maxeval(12)
x_opt = opt.optimize([0.5])
R_opt = opt.last_optimum_value()
print(f"\nOptimal: t={x_opt[0]:.4f}, R={R_opt:.4f}", flush=True)

# Dense sweep for visualization
print("\nDense sweep...", flush=True)
t_sweep = np.linspace(0.1, 1.5, 20)
R_sweep, T_sweep = [], []
for t in t_sweep:
    R, T = simulate_fp_transmission(t)
    R_sweep.append(R)
    T_sweep.append(T)
    print(f"  t={t:.3f} R={R:.4f}", flush=True)

print(f"Max R in sweep: {max(R_sweep):.3f} at t={t_sweep[np.argmax(R_sweep)]:.3f}")
print(f"NLopt optimal: t={x_opt[0]:.3f}, R={R_opt:.3f}")

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

# Panel 1: Optimization history
ax0.plot(range(1, len(history_R)+1), history_R, 'o-',
         color='#4FC3F7', markersize=7, lw=2, label='R(t) evaluated')
ax0.fill_between(range(1, len(history_R)+1), history_R, alpha=0.2, color='#4FC3F7')
ax0.axhline(R_opt, color='#FF6B6B', ls='--', lw=2,
            label=f'R_opt={R_opt:.3f}')
ax0.set_xlabel('NLopt Iteration', fontsize=11)
ax0.set_ylabel('Reflection R = 1 − T', fontsize=11)
ax0.set_title('NLopt COBYLA: Fabry-Perot\nMax-R Optimization', fontsize=10)
ax0.legend(fontsize=9, facecolor='#16213e', labelcolor='white')
ax0.set_ylim(0, 1.05)

# Panel 2: R and T vs thickness sweep
ax1.fill_between(t_sweep, R_sweep, alpha=0.25, color='#FF6B6B')
ax1.plot(t_sweep, R_sweep, 's-', color='#FF6B6B', markersize=5, lw=2, label='R = 1−T')
ax1.fill_between(t_sweep, T_sweep, alpha=0.2, color='#4FC3F7')
ax1.plot(t_sweep, T_sweep, '^-', color='#4FC3F7', markersize=5, lw=2, label='T')
ax1.axvline(x_opt[0], color='#FFD700', ls='--', lw=2,
            label=f'opt t={x_opt[0]:.3f}')
ax1.set_xlabel('Slab Thickness (a)', fontsize=11)
ax1.set_ylabel('R or T', fontsize=11)
ax1.set_title('Fabry-Perot: R & T vs Thickness\n(Si, ε=12, fcen=0.5)', fontsize=10)
ax1.legend(fontsize=9, facecolor='#16213e', labelcolor='white')
ax1.set_ylim(0, 1.05)

# Fresnel reference
n_si = np.sqrt(12.0)
R_fresnel = ((n_si - 1) / (n_si + 1))**2
ax1.axhline(R_fresnel, color='#69F0AE', ls=':', lw=1.5,
            label=f'Fresnel R={R_fresnel:.2f}')
ax1.legend(fontsize=8, facecolor='#16213e', labelcolor='white')

plt.tight_layout()
plt.savefig('/tmp/concept_nlopt.png', dpi=100, bbox_inches='tight',
            facecolor=fig.get_facecolor())
print("Saved /tmp/concept_nlopt.png")
