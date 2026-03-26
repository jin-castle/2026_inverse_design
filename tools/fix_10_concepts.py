#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
10개 concepts 이미지 수정 스크립트
각 개념에 물리적으로 적합한 시나리오로 새 demo_code 작성 후 Docker 실행
"""

import sqlite3
import subprocess
import re
import os
import sys
from pathlib import Path
from PIL import Image
import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "knowledge.db"
RESULTS_DIR = PROJECT_ROOT / "db" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DOCKER_WORKER = "meep-pilot-worker"
TIMEOUT = 120

# ─────────────────────────────────────────────────────────────────────────────
# 10개 개념별 demo code 정의
# ─────────────────────────────────────────────────────────────────────────────

CONCEPT_CODES = {}

# 1. nlopt: 1D Fabry-Perot 공진기 반사율 최적화
CONCEPT_CODES["nlopt"] = r'''
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt
import nlopt

# 1D Fabry-Perot resonator: optimize slab thickness for max reflection at resonance
# Use NLopt (gradient-free COBYLA) to find optimal slab thickness

def simulate_fp_reflection(thickness):
    """1D Fabry-Perot: Si slab in air, measure reflection at fcen."""
    resolution = 40
    fcen = 0.5
    df = 0.4
    sx = 10.0
    dpml = 1.0
    Si = mp.Medium(epsilon=12.0)

    geometry = [
        mp.Block(
            size=mp.Vector3(thickness, mp.inf, mp.inf),
            center=mp.Vector3(0, 0, 0),
            material=Si
        )
    ]
    sources = [mp.Source(
        mp.GaussianSource(fcen, fwidth=df),
        component=mp.Ez,
        center=mp.Vector3(-sx/2 + dpml + 0.5)
    )]
    pml = [mp.PML(dpml, direction=mp.X)]
    sim = mp.Simulation(
        cell_size=mp.Vector3(sx, 0, 0),
        geometry=geometry,
        sources=sources,
        boundary_layers=pml,
        resolution=resolution,
        dimensions=1
    )
    refl_flux = sim.add_flux(fcen, df, 1,
        mp.FluxRegion(center=mp.Vector3(-sx/2 + dpml + 0.25), direction=mp.X))
    sim.run(until_after_sources=50)
    refl_data = sim.get_flux_data(refl_flux)
    sim.reset_meep()

    # Normalization run (no slab)
    sim2 = mp.Simulation(
        cell_size=mp.Vector3(sx, 0, 0),
        sources=sources,
        boundary_layers=pml,
        resolution=resolution,
        dimensions=1
    )
    norm_flux = sim2.add_flux(fcen, df, 1,
        mp.FluxRegion(center=mp.Vector3(-sx/2 + dpml + 0.25), direction=mp.X))
    sim2.run(until_after_sources=50)
    norm_val = mp.get_fluxes(norm_flux)[0]
    sim2.reset_meep()

    # load_minus for reflection
    sim3 = mp.Simulation(
        cell_size=mp.Vector3(sx, 0, 0),
        geometry=geometry,
        sources=sources,
        boundary_layers=pml,
        resolution=resolution,
        dimensions=1
    )
    refl3 = sim3.add_flux(fcen, df, 1,
        mp.FluxRegion(center=mp.Vector3(-sx/2 + dpml + 0.25), direction=mp.X))
    sim3.load_minus_flux_data(refl3, refl_data)
    sim3.run(until_after_sources=50)
    refl_val = -mp.get_fluxes(refl3)[0]
    sim3.reset_meep()

    R = refl_val / norm_val if norm_val > 0 else 0.0
    return float(np.clip(R, 0, 1))

# NLopt optimization
history_t = []
history_R = []

def objective(x, grad):
    t = float(x[0])
    R = simulate_fp_reflection(t)
    history_t.append(t)
    history_R.append(R)
    print(f"  t={t:.3f} → R={R:.4f}", flush=True)
    return R  # maximize reflection

opt = nlopt.opt(nlopt.LN_COBYLA, 1)
opt.set_max_objective(objective)
opt.set_lower_bounds([0.3])
opt.set_upper_bounds([2.0])
opt.set_xtol_rel(1e-2)
opt.set_maxeval(12)
x0 = [0.8]
x_opt = opt.optimize(x0)
R_opt = opt.last_optimum_value()

print(f"Optimal thickness: {x_opt[0]:.4f}, R={R_opt:.4f}")

# Plot
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: Convergence
axes[0].plot(range(1, len(history_R)+1), history_R, 'bo-', markersize=6)
axes[0].axhline(R_opt, color='r', linestyle='--', label=f'R_opt={R_opt:.3f}')
axes[0].set_xlabel('Iteration')
axes[0].set_ylabel('Reflection R')
axes[0].set_title('NLopt COBYLA: FP Resonator Optimization')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Panel 2: R vs thickness sweep (using history)
t_arr = np.array(history_t)
R_arr = np.array(history_R)
idx = np.argsort(t_arr)
axes[1].plot(t_arr[idx], R_arr[idx], 'g^-', markersize=6)
axes[1].axvline(x_opt[0], color='r', linestyle='--', label=f'opt t={x_opt[0]:.3f}')
axes[1].set_xlabel('Slab Thickness (μm units)')
axes[1].set_ylabel('Reflection R')
axes[1].set_title('Fabry-Perot: R vs Slab Thickness')
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('/tmp/concept_nlopt.png', dpi=100, bbox_inches='tight')
print("Saved /tmp/concept_nlopt.png")
'''

# 2. add_energy: 2D ring resonator 내부 에너지 축적 vs 시간
CONCEPT_CODES["add_energy"] = r'''
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# 2D ring resonator: accumulate energy inside ring vs time
# Monitor total electromagnetic energy with add_energy

resolution = 12
fcen = 0.3
df = 0.15
r_ring = 1.5
w_ring = 0.3
sx, sy = 10, 10
dpml = 1.0
Si = mp.Medium(epsilon=12.0)

cell = mp.Vector3(sx, sy, 0)
pml = [mp.PML(dpml)]

geometry = [
    mp.Cylinder(radius=r_ring + w_ring/2, material=Si),
    mp.Cylinder(radius=r_ring - w_ring/2, material=mp.air),
]

sources = [mp.Source(
    mp.GaussianSource(fcen, fwidth=df),
    component=mp.Ez,
    center=mp.Vector3(r_ring, 0),
    size=mp.Vector3()
)]

sim = mp.Simulation(
    cell_size=cell,
    geometry=geometry,
    sources=sources,
    boundary_layers=pml,
    resolution=resolution
)

# add_energy: monitor region inside ring (away from PML)
inner = sx/2 - dpml - 0.5
energy_mon = sim.add_energy(
    fcen, df, 1,
    mp.EnergyRegion(
        center=mp.Vector3(0, 0, 0),
        size=mp.Vector3(inner, inner, 0)  # z=0 for 2D
    )
)

# Record energy time series manually
energy_times = []
energy_vals = []

def record_energy(sim):
    t = sim.meep_time()
    # get_electric_energy + get_magnetic_energy = total energy (at fcen)
    try:
        e_e = mp.get_electric_energy(energy_mon)
        m_e = mp.get_magnetic_energy(energy_mon)
        total = e_e + m_e if (e_e is not None and m_e is not None) else 0.0
    except:
        total = 0.0
    energy_times.append(t)
    energy_vals.append(float(total))

sim.run(mp.at_every(2.0, record_energy), until=150)

# Final Ez field snapshot
ez_data = sim.get_array(center=mp.Vector3(), size=cell, component=mp.Ez)

# Plot
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: Energy vs time
axes[0].plot(energy_times, energy_vals, 'b-', linewidth=1.5)
axes[0].set_xlabel('MEEP Time')
axes[0].set_ylabel('Total EM Energy (arb.)')
axes[0].set_title('add_energy: Ring Resonator Energy Accumulation')
axes[0].grid(True, alpha=0.3)

# Panel 2: Ez field
im = axes[1].imshow(ez_data.T, origin='lower', cmap='RdBu',
                    extent=[-sx/2, sx/2, -sy/2, sy/2],
                    interpolation='bilinear', aspect='equal')
plt.colorbar(im, ax=axes[1], label='Ez')
axes[1].set_title('Ez Field: 2D Ring Resonator')
axes[1].set_xlabel('x (μm)')
axes[1].set_ylabel('y (μm)')

# Draw ring outline
theta = np.linspace(0, 2*np.pi, 200)
for rr in [r_ring - w_ring/2, r_ring + w_ring/2]:
    axes[1].plot(rr*np.cos(theta), rr*np.sin(theta), 'k-', linewidth=0.8, alpha=0.5)

plt.tight_layout()
plt.savefig('/tmp/concept_add_energy.png', dpi=100, bbox_inches='tight')
print("Saved /tmp/concept_add_energy.png")
'''

# 3. Harminv: 2D Si disk resonator → 시간 신호 + 공진 주파수/Q
CONCEPT_CODES["Harminv"] = r'''
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# 2D Si disk resonator: point source → time-domain Ez → Harminv extracts resonances

resolution = 20
r_disk = 0.6
fcen = 0.5
df = 0.4
sx, sy = 6, 6
dpml = 1.0
Si = mp.Medium(epsilon=12.0)

cell = mp.Vector3(sx, sy, 0)
pml = [mp.PML(dpml)]

geometry = [
    mp.Cylinder(radius=r_disk, material=Si)
]

pt = mp.Vector3(0.1*r_disk, 0)  # source/monitor inside disk

sources = [mp.Source(
    mp.GaussianSource(fcen, fwidth=df),
    component=mp.Ez,
    center=pt
)]

# Record Ez time series
ez_times = []
ez_vals = []
def record_ez(sim):
    t = sim.meep_time()
    ez = sim.get_array(component=mp.Ez, center=pt, size=mp.Vector3())
    ez_times.append(t)
    ez_vals.append(float(ez))

h = mp.Harminv(mp.Ez, pt, fcen, df)

sim = mp.Simulation(
    cell_size=cell,
    geometry=geometry,
    sources=sources,
    boundary_layers=pml,
    resolution=resolution
)

sim.run(
    mp.at_every(0.5, record_ez),
    mp.after_sources(h),
    until_after_sources=300
)

# Extract Harminv modes
modes = h.modes
print(f"Harminv found {len(modes)} modes")
for m in modes:
    print(f"  freq={m.freq:.4f}, Q={m.Q:.1f}, |amp|={abs(m.amplitude):.3f}")

# Ez field snapshot
ez_field = sim.get_array(center=mp.Vector3(), size=cell, component=mp.Ez)

# Plot
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: Time-domain signal + Harminv detected freqs
ax = axes[0]
ax.plot(ez_times, ez_vals, 'b-', linewidth=0.8, alpha=0.7, label='Ez(t)')
ax.set_xlabel('MEEP Time')
ax.set_ylabel('Ez amplitude')
ax.set_title('Harminv: Time-domain Signal (Si Disk)')
ax2 = ax.twinx()
if modes:
    freqs = [m.freq for m in modes]
    Qs = [m.Q for m in modes]
    amps = [abs(m.amplitude) for m in modes]
    ax2.bar(freqs, amps, width=0.01, color='red', alpha=0.6, label='|amplitude|')
    ax2.set_ylabel('|Amplitude|', color='red')
ax.legend(loc='upper right')
ax.grid(True, alpha=0.3)

# Panel 2: Resonance frequencies + Q values
if modes:
    freqs = [m.freq for m in modes]
    Qs = [m.Q for m in modes]
    amps = [abs(m.amplitude) for m in modes]
    scatter = axes[1].scatter(freqs, Qs, c=amps, cmap='hot',
                               s=100, zorder=5)
    plt.colorbar(scatter, ax=axes[1], label='|Amplitude|')
    axes[1].set_xlabel('Frequency (c/a)')
    axes[1].set_ylabel('Q factor')
    axes[1].set_title(f'Harminv: {len(modes)} Resonances Found')
    axes[1].grid(True, alpha=0.3)
    for m in modes:
        axes[1].annotate(f'f={m.freq:.3f}', (m.freq, m.Q),
                         textcoords='offset points', xytext=(5, 5), fontsize=8)
else:
    axes[1].text(0.5, 0.5, 'No modes found\n(try longer run)',
                 ha='center', va='center', transform=axes[1].transAxes)
    axes[1].set_title('Harminv: No Resonances')

plt.tight_layout()
plt.savefig('/tmp/concept_Harminv.png', dpi=100, bbox_inches='tight')
print("Saved /tmp/concept_Harminv.png")
'''

# 4. LDOS: 금속 평판 근처 점 소스 vs 자유공간 에너지 방출 비교
CONCEPT_CODES["LDOS"] = r'''
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# LDOS: Compare power emitted by point source near metal vs free space
# Purcell factor = flux_metal / flux_vacuum

resolution = 20
fcen = 0.5
df = 0.3
nfreq = 30
sx, sy = 8, 8
dpml = 1.0

# Metal plate parameters
plate_y = -1.0   # metal plate at y = -1.0
plate_t = 0.2    # thickness
src_y = 0.0      # source at y=0 (distance 1.0 from plate)

metal = mp.Medium(epsilon=-100)  # approximately perfect metal at fcen

cell = mp.Vector3(sx, sy, 0)
pml = [mp.PML(dpml)]
src_pt = mp.Vector3(0, src_y)

sources = [mp.Source(
    mp.GaussianSource(fcen, fwidth=df),
    component=mp.Ez,
    center=src_pt
)]

def run_flux(with_metal):
    geometry = []
    if with_metal:
        geometry = [
            mp.Block(
                size=mp.Vector3(sx, plate_t, mp.inf),
                center=mp.Vector3(0, plate_y - plate_t/2),
                material=metal
            )
        ]
    sim = mp.Simulation(
        cell_size=cell,
        geometry=geometry,
        sources=sources,
        boundary_layers=pml,
        resolution=resolution
    )
    # Total radiated power: flux box around source
    box_r = 0.5
    fluxes = [
        sim.add_flux(fcen, df, nfreq,
            mp.FluxRegion(center=mp.Vector3(0, box_r), size=mp.Vector3(2*box_r, 0))),
        sim.add_flux(fcen, df, nfreq,
            mp.FluxRegion(center=mp.Vector3(0, -box_r), size=mp.Vector3(2*box_r, 0),
                         weight=-1)),
        sim.add_flux(fcen, df, nfreq,
            mp.FluxRegion(center=mp.Vector3(box_r, 0), size=mp.Vector3(0, 2*box_r))),
        sim.add_flux(fcen, df, nfreq,
            mp.FluxRegion(center=mp.Vector3(-box_r, 0), size=mp.Vector3(0, 2*box_r),
                         weight=-1)),
    ]
    sim.run(until_after_sources=100)
    # Total flux = sum of 4 faces
    freqs = mp.get_flux_freqs(fluxes[0])
    total_flux = np.zeros(nfreq)
    for fl in fluxes:
        total_flux += np.array(mp.get_fluxes(fl))

    ez_field = sim.get_array(center=mp.Vector3(), size=cell, component=mp.Ez)
    sim.reset_meep()
    return freqs, total_flux, ez_field

print("Running free-space simulation...")
freqs_vac, flux_vac, ez_vac = run_flux(with_metal=False)
print("Running metal-plate simulation...")
freqs_met, flux_met, ez_met = run_flux(with_metal=True)

# Purcell factor
with np.errstate(divide='ignore', invalid='ignore'):
    purcell = np.where(flux_vac > 0, flux_met / flux_vac, 0.0)

# Plot
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: Purcell factor spectrum
axes[0].plot(freqs_vac, flux_vac, 'b-', linewidth=1.5, label='Free space')
axes[0].plot(freqs_met, flux_met, 'r-', linewidth=1.5, label='Near metal plate')
axes[0].set_xlabel('Frequency (c/a)')
axes[0].set_ylabel('Radiated Power (arb.)')
axes[0].set_title('LDOS: Power Emission Comparison')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

ax2 = axes[0].twinx()
ax2.plot(freqs_vac, purcell, 'g--', linewidth=1.5, label='Purcell factor')
ax2.set_ylabel('Purcell Factor', color='green')
ax2.tick_params(axis='y', labelcolor='green')
ax2.legend(loc='lower right')

# Panel 2: Ez field (metal case)
im = axes[1].imshow(ez_met.T, origin='lower', cmap='RdBu',
                    extent=[-sx/2, sx/2, -sy/2, sy/2],
                    vmin=-np.max(np.abs(ez_met))*0.3,
                    vmax=np.max(np.abs(ez_met))*0.3,
                    interpolation='bilinear', aspect='equal')
plt.colorbar(im, ax=axes[1], label='Ez')
axes[1].axhline(plate_y, color='k', linewidth=2, label='Metal plate')
axes[1].plot(0, src_y, 'r*', markersize=12, label='Source')
axes[1].set_xlabel('x (a)')
axes[1].set_ylabel('y (a)')
axes[1].set_title('LDOS: Ez Field Near Metal Plate')
axes[1].legend(fontsize=8)

plt.tight_layout()
plt.savefig('/tmp/concept_LDOS.png', dpi=100, bbox_inches='tight')
print("Saved /tmp/concept_LDOS.png")
'''

# 5. ring_resonator: 버스 도파관 + 링 공진기 → Ez + 투과/낙하 스펙트럼
CONCEPT_CODES["ring_resonator"] = r'''
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# Bus waveguide + ring resonator: Ez field + transmission & drop spectrum

resolution = 10
n_Si = 3.45
Si = mp.Medium(index=n_Si)

w = 0.4        # waveguide width
r = 1.5        # ring radius
gap = 0.15     # coupling gap
sx = 16.0
sy = 10.0
dpml = 1.0

fcen = 0.15
df = 0.1
nfreq = 200

# Waveguide y = -(r + gap + w/2)
wg_y = -(r + gap + w/2)

cell = mp.Vector3(sx, sy, 0)
pml_layers = [mp.PML(dpml)]

geometry = [
    # Bus waveguide
    mp.Block(size=mp.Vector3(sx, w, 0),
             center=mp.Vector3(0, wg_y, 0), material=Si),
    # Ring: outer - inner cylinder
    mp.Cylinder(radius=r + w/2, material=Si),
    mp.Cylinder(radius=r - w/2, material=mp.air),
]

sources = [mp.Source(
    mp.EigenModeSource(
        mp.GaussianSource(fcen, fwidth=df),
        eig_band=1, direction=mp.X, eig_parity=mp.ODD_Z,
        center=mp.Vector3(-sx/2 + dpml + 1.0, wg_y, 0),
        size=mp.Vector3(0, 3*w, 0)
    ),
    component=mp.ALL_COMPONENTS,
    center=mp.Vector3(-sx/2 + dpml + 1.0, wg_y, 0),
    size=mp.Vector3(0, 3*w, 0)
)]

sim = mp.Simulation(
    cell_size=cell,
    geometry=geometry,
    sources=sources,
    boundary_layers=pml_layers,
    resolution=resolution
)

# Flux monitors
trans_mon = sim.add_flux(fcen, df, nfreq,
    mp.FluxRegion(center=mp.Vector3(sx/2 - dpml - 0.5, wg_y, 0),
                  size=mp.Vector3(0, 3*w, 0)))

sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez,
    mp.Vector3(sx/2 - dpml - 0.5, wg_y, 0), 1e-5))

freqs = np.array(mp.get_flux_freqs(trans_mon))
trans = np.array(mp.get_fluxes(trans_mon))

ez_field = sim.get_array(center=mp.Vector3(), size=cell, component=mp.Ez)
sim.reset_meep()

# Normalization run
sim2 = mp.Simulation(
    cell_size=cell,
    geometry=[mp.Block(size=mp.Vector3(sx, w, 0),
                       center=mp.Vector3(0, wg_y, 0), material=Si)],
    sources=sources,
    boundary_layers=pml_layers,
    resolution=resolution
)
norm_mon = sim2.add_flux(fcen, df, nfreq,
    mp.FluxRegion(center=mp.Vector3(sx/2 - dpml - 0.5, wg_y, 0),
                  size=mp.Vector3(0, 3*w, 0)))
sim2.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez,
    mp.Vector3(sx/2 - dpml - 0.5, wg_y, 0), 1e-5))
norm = np.array(mp.get_fluxes(norm_mon))
sim2.reset_meep()

T = trans / norm

# Plot
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: Ez field
im = axes[0].imshow(ez_field.T, origin='lower', cmap='RdBu',
                    extent=[-sx/2, sx/2, -sy/2, sy/2],
                    vmin=-np.max(np.abs(ez_field))*0.5,
                    vmax=np.max(np.abs(ez_field))*0.5,
                    interpolation='bilinear', aspect='equal')
plt.colorbar(im, ax=axes[0], label='Ez')
axes[0].set_xlabel('x (μm)')
axes[0].set_ylabel('y (μm)')
axes[0].set_title('Ring Resonator: Ez Field')

# Draw ring
theta = np.linspace(0, 2*np.pi, 300)
for rr in [r - w/2, r + w/2]:
    axes[0].plot(rr*np.cos(theta), rr*np.sin(theta), 'k-', lw=0.8, alpha=0.4)

# Panel 2: Transmission spectrum
axes[1].plot(freqs, T, 'b-', linewidth=1.5)
axes[1].axhline(1.0, color='gray', linestyle='--', alpha=0.5)
axes[1].set_xlabel('Frequency (c/μm)')
axes[1].set_ylabel('Transmission T')
axes[1].set_title('Ring Resonator: Transmission Spectrum')
axes[1].set_ylim(-0.1, 1.2)
axes[1].grid(True, alpha=0.3)
# Find dips
if len(T) > 0:
    min_idx = np.argmin(T)
    axes[1].annotate(f'dip @ f={freqs[min_idx]:.4f}',
                     (freqs[min_idx], T[min_idx]),
                     textcoords='offset points', xytext=(10, 10),
                     arrowprops=dict(arrowstyle='->', color='red'),
                     color='red', fontsize=9)

plt.tight_layout()
plt.savefig('/tmp/concept_ring_resonator.png', dpi=100, bbox_inches='tight')
print("Saved /tmp/concept_ring_resonator.png")
'''

# 6. at_every: 자유공간 Gaussian pulse → 시계열 Ez + FFT
CONCEPT_CODES["at_every"] = r'''
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# Free-space Gaussian pulse propagation: record Ez every timestep → time series + FFT

resolution = 20
fcen = 0.5
df = 0.3
sx, sy = 12, 6
dpml = 1.0

cell = mp.Vector3(sx, sy, 0)
pml = [mp.PML(dpml)]

sources = [mp.Source(
    mp.GaussianSource(fcen, fwidth=df),
    component=mp.Ez,
    center=mp.Vector3(-sx/2 + dpml + 1.0, 0)
)]

sim = mp.Simulation(
    cell_size=cell,
    sources=sources,
    boundary_layers=pml,
    resolution=resolution
)

# Monitor point: midway between source and right boundary
mon_pt = mp.Vector3(sx/4, 0)

ez_times = []
ez_vals = []

def record_ez(sim):
    t = sim.meep_time()
    ez = sim.get_array(component=mp.Ez, center=mon_pt, size=mp.Vector3())
    ez_times.append(t)
    ez_vals.append(float(ez))

# at_every: record every 0.2 MEEP time units
sim.run(mp.at_every(0.2, record_ez), until=100)

ez_arr = np.array(ez_vals)
t_arr = np.array(ez_times)
dt = t_arr[1] - t_arr[0] if len(t_arr) > 1 else 0.2

# FFT
fft_vals = np.abs(np.fft.rfft(ez_arr))
fft_freqs = np.fft.rfftfreq(len(ez_arr), d=dt)

# Find peak frequency
peak_idx = np.argmax(fft_vals[1:]) + 1
peak_freq = fft_freqs[peak_idx]
print(f"Peak frequency: {peak_freq:.4f} (expected ~{fcen})")

# Plot
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: Time series
axes[0].plot(t_arr, ez_arr, 'b-', linewidth=0.8)
axes[0].set_xlabel('MEEP Time')
axes[0].set_ylabel('Ez amplitude')
axes[0].set_title('at_every: Gaussian Pulse - Time Domain\n(Free Space)')
axes[0].grid(True, alpha=0.3)
# Mark pulse peak region
axes[0].axvspan(0, 20, alpha=0.1, color='yellow', label='Source active')
axes[0].legend(fontsize=8)

# Panel 2: FFT spectrum
axes[1].plot(fft_freqs[:len(fft_freqs)//3], fft_vals[:len(fft_freqs)//3],
             'r-', linewidth=1.5)
axes[1].axvline(peak_freq, color='navy', linestyle='--',
                label=f'Peak f={peak_freq:.3f}')
axes[1].axvline(fcen, color='green', linestyle=':', alpha=0.7,
                label=f'fcen={fcen}')
axes[1].set_xlabel('Frequency (c/a)')
axes[1].set_ylabel('|FFT(Ez)|')
axes[1].set_title('at_every: Frequency Spectrum (FFT)')
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('/tmp/concept_at_every.png', dpi=100, bbox_inches='tight')
print("Saved /tmp/concept_at_every.png")
'''

# 7. get_eigenmode_coefficients: MMI 1x2 splitter TE0/TE1 모드 파워
CONCEPT_CODES["get_eigenmode_coefficients"] = r'''
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# MMI 1x2 splitter: get_eigenmode_coefficients to decompose TE0/TE1 modes

resolution = 20
Si = mp.Medium(epsilon=12.0)

w_in = 0.5      # input waveguide width
w_mmi = 2.0     # MMI width
L_mmi = 3.0     # MMI length
w_out = 0.5     # output waveguide width
out_sep = 0.8   # output separation

dpml = 1.0
sx = 12.0
sy = 6.0
fcen = 0.15
df = 0.1
nfreq = 1

cell = mp.Vector3(sx, sy, 0)
pml = [mp.PML(dpml)]

geometry = [
    # Input waveguide
    mp.Block(size=mp.Vector3(sx/2 - L_mmi/2, w_in, 0),
             center=mp.Vector3(-(sx/2 - L_mmi/2)/2 - L_mmi/2, 0, 0), material=Si),
    # MMI region
    mp.Block(size=mp.Vector3(L_mmi, w_mmi, 0),
             center=mp.Vector3(0, 0, 0), material=Si),
    # Output waveguides
    mp.Block(size=mp.Vector3(sx/2 - L_mmi/2, w_out, 0),
             center=mp.Vector3((sx/2 - L_mmi/2)/2 + L_mmi/2, out_sep/2, 0), material=Si),
    mp.Block(size=mp.Vector3(sx/2 - L_mmi/2, w_out, 0),
             center=mp.Vector3((sx/2 - L_mmi/2)/2 + L_mmi/2, -out_sep/2, 0), material=Si),
]

src_x = -sx/2 + dpml + 1.0
sources = [mp.Source(
    mp.GaussianSource(fcen, fwidth=df),
    component=mp.Ez,
    center=mp.Vector3(src_x, 0, 0),
    size=mp.Vector3(0, 3*w_in, 0)
)]

sim = mp.Simulation(
    cell_size=cell,
    geometry=geometry,
    sources=sources,
    boundary_layers=pml,
    resolution=resolution
)

# Flux monitor at output
mon_x = sx/2 - dpml - 0.5
flux_mon = sim.add_flux(fcen, df, nfreq,
    mp.FluxRegion(center=mp.Vector3(mon_x, 0, 0),
                  size=mp.Vector3(0, sy - 2*dpml, 0)))

sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez,
    mp.Vector3(mon_x, 0), 1e-4))

ez_field = sim.get_array(center=mp.Vector3(), size=cell, component=mp.Ez)

# get_eigenmode_coefficients: bands 1, 2 (TE0, TE1)
res = sim.get_eigenmode_coefficients(
    flux_mon, [1, 2],
    eig_parity=mp.ODD_Z
)
# res.alpha[band_idx-1, freq_idx, direction]  direction: 0=forward, 1=backward
alpha_TE0 = res.alpha[0, 0, 0]
alpha_TE1 = res.alpha[1, 0, 0]
P_TE0 = abs(alpha_TE0)**2
P_TE1 = abs(alpha_TE1)**2
P_total = P_TE0 + P_TE1

print(f"TE0 power: {P_TE0:.4f}")
print(f"TE1 power: {P_TE1:.4f}")
print(f"Total: {P_total:.4f}")

# Plot
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: Ez field
im = axes[0].imshow(ez_field.T, origin='lower', cmap='RdBu',
                    extent=[-sx/2, sx/2, -sy/2, sy/2],
                    vmin=-np.max(np.abs(ez_field))*0.5,
                    vmax=np.max(np.abs(ez_field))*0.5,
                    interpolation='bilinear', aspect='equal')
plt.colorbar(im, ax=axes[0], label='Ez')
axes[0].set_xlabel('x (a)')
axes[0].set_ylabel('y (a)')
axes[0].set_title('MMI 1×2 Splitter: Ez Field')

# Panel 2: Mode power bar chart
bars = axes[1].bar(['TE0', 'TE1'], [P_TE0, P_TE1],
                   color=['royalblue', 'tomato'], width=0.4, edgecolor='k')
axes[1].set_ylabel('Power (arb.)')
axes[1].set_title('get_eigenmode_coefficients:\nMMI Output Mode Decomposition')
axes[1].set_ylim(0, max(P_TE0, P_TE1) * 1.4 + 1e-6)
for bar, val in zip(bars, [P_TE0, P_TE1]):
    axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001*max(P_TE0,P_TE1+1e-9),
                 f'{val:.4f}', ha='center', va='bottom', fontsize=11)
if P_total > 0:
    axes[1].text(0.5, 0.95, f'TE0 fraction: {P_TE0/P_total*100:.1f}%',
                 ha='center', transform=axes[1].transAxes, fontsize=11)
axes[1].grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('/tmp/concept_get_eigenmode_coefficients.png', dpi=100, bbox_inches='tight')
print("Saved /tmp/concept_get_eigenmode_coefficients.png")
'''

# 8. phase_velocity: free-space 1D 파동 k(ω) 분산 관계
CONCEPT_CODES["phase_velocity"] = r'''
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# Free-space 1D: k(omega) dispersion relation
# Phase velocity v_ph = omega/k = c (should be 1 in MEEP units)

resolution = 40
dpml = 2.0
sx = 20.0
nfreq = 50
fcen = 0.5
df = 0.8

cell = mp.Vector3(sx, 0, 0)
pml = [mp.PML(dpml, direction=mp.X)]

sources = [mp.Source(
    mp.GaussianSource(fcen, fwidth=df),
    component=mp.Ez,
    center=mp.Vector3(-sx/2 + dpml + 0.5)
)]

sim = mp.Simulation(
    cell_size=cell,
    sources=sources,
    boundary_layers=pml,
    resolution=resolution,
    dimensions=1
)

# Two monitor points separated by L
x1 = -2.0
x2 = 2.0
L = x2 - x1

mon1 = sim.add_dft_fields([mp.Ez], fcen - df/2, fcen + df/2, nfreq,
                           center=mp.Vector3(x1), size=mp.Vector3())
mon2 = sim.add_dft_fields([mp.Ez], fcen - df/2, fcen + df/2, nfreq,
                           center=mp.Vector3(x2), size=mp.Vector3())

sim.run(until_after_sources=200)

# Extract phase at each frequency
freqs = np.linspace(fcen - df/2, fcen + df/2, nfreq)
phase1 = np.zeros(nfreq)
phase2 = np.zeros(nfreq)
for i in range(nfreq):
    E1 = sim.get_dft_array(mon1, mp.Ez, i)
    E2 = sim.get_dft_array(mon2, mp.Ez, i)
    if hasattr(E1, '__len__'):
        E1 = E1.flat[0]
    if hasattr(E2, '__len__'):
        E2 = E2.flat[0]
    phase1[i] = np.angle(complex(E1))
    phase2[i] = np.angle(complex(E2))

# k = (phi2 - phi1) / L (may need unwrap)
dphi = np.unwrap(phase2 - phase1)
k_vals = dphi / L  # wavenumber
omega_vals = 2 * np.pi * freqs

# Phase velocity: v_ph = omega / k
with np.errstate(divide='ignore', invalid='ignore'):
    v_ph = np.where(np.abs(k_vals) > 0.01, omega_vals / k_vals, np.nan)

# Group velocity: d(omega)/dk
# Effective index n_eff = c*k/f = k/(2pi*f) * lambda_0 in normalized units
n_eff = np.abs(k_vals) / (2 * np.pi * freqs)

print(f"Freqs: {freqs[0]:.3f} – {freqs[-1]:.3f}")
print(f"Mean n_eff: {np.nanmean(n_eff):.3f} (expected ~1 for free space)")

# Plot
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: Dispersion relation k(omega) = linear → v_ph = c
omega_theory = 2 * np.pi * freqs
axes[0].plot(k_vals, omega_vals, 'bo-', markersize=5, label='MEEP (measured)')
k_theory = np.linspace(k_vals.min(), k_vals.max(), 100)
axes[0].plot(k_theory, k_theory, 'r--', linewidth=2, label='Light line (v=c)')
axes[0].set_xlabel('k (2π/a)')
axes[0].set_ylabel('ω (2πc/a)')
axes[0].set_title('Phase Velocity: k(ω) Dispersion\n(Free Space, 1D)')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Panel 2: Phase velocity vs frequency
axes[1].plot(freqs, np.abs(v_ph) / (2*np.pi), 'g^-', markersize=5, label='v_ph / c')
axes[1].axhline(1.0, color='r', linestyle='--', label='c = 1')
axes[1].set_xlabel('Frequency (c/a)')
axes[1].set_ylabel('Phase Velocity (v_ph / c)')
axes[1].set_title('Phase Velocity vs Frequency')
axes[1].legend()
axes[1].grid(True, alpha=0.3)
axes[1].set_ylim(0, 3)

plt.tight_layout()
plt.savefig('/tmp/concept_phase_velocity.png', dpi=100, bbox_inches='tight')
print("Saved /tmp/concept_phase_velocity.png")
'''

# 9. LorentzianSusceptibility: 분산 매질 평판 → 공진 흡수 스펙트럼
CONCEPT_CODES["LorentzianSusceptibility"] = r'''
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# Lorentzian dispersive slab: plane wave → resonance absorption spectrum
# Also plot epsilon(f) showing dispersion

resolution = 40
fcen = 0.5
df = 0.6
nfreq = 80
dpml = 1.0
sx = 10.0
slab_t = 0.5

# Lorentzian susceptibility: resonance at f0=0.5
f0 = 0.5
gamma = 0.05
sigma = 2.0

lorentz_mat = mp.Medium(
    epsilon=2.25,
    E_susceptibilities=[
        mp.LorentzianSusceptibility(frequency=f0, gamma=gamma, sigma=sigma)
    ]
)

cell = mp.Vector3(sx, 0, 0)
pml = [mp.PML(dpml, direction=mp.X)]

geometry = [
    mp.Block(size=mp.Vector3(slab_t, mp.inf, mp.inf),
             center=mp.Vector3(0, 0, 0),
             material=lorentz_mat)
]

sources = [mp.Source(
    mp.GaussianSource(fcen, fwidth=df),
    component=mp.Ez,
    center=mp.Vector3(-sx/2 + dpml + 0.5)
)]

def run(with_slab):
    sim = mp.Simulation(
        cell_size=cell,
        geometry=geometry if with_slab else [],
        sources=sources,
        boundary_layers=pml,
        resolution=resolution,
        dimensions=1
    )
    trans = sim.add_flux(fcen, df, nfreq,
        mp.FluxRegion(center=mp.Vector3(sx/2 - dpml - 0.5)))
    refl_mon = sim.add_flux(fcen, df, nfreq,
        mp.FluxRegion(center=mp.Vector3(-sx/2 + dpml + 0.25), weight=-1))
    if not with_slab:
        sim.run(until_after_sources=100)
        return (mp.get_flux_freqs(trans),
                np.array(mp.get_fluxes(trans)),
                np.array(mp.get_fluxes(refl_mon)),
                sim.get_flux_data(refl_mon),
                sim.get_flux_data(trans))
    else:
        sim.run(until_after_sources=100)
        return (mp.get_flux_freqs(trans),
                np.array(mp.get_fluxes(trans)),
                np.array(mp.get_fluxes(refl_mon)))

freqs0, t_vac, r_vac, refl_data0, trans_data0 = run(with_slab=False)

sim2 = mp.Simulation(
    cell_size=cell,
    geometry=geometry,
    sources=sources,
    boundary_layers=pml,
    resolution=resolution,
    dimensions=1
)
trans2 = sim2.add_flux(fcen, df, nfreq,
    mp.FluxRegion(center=mp.Vector3(sx/2 - dpml - 0.5)))
refl2 = sim2.add_flux(fcen, df, nfreq,
    mp.FluxRegion(center=mp.Vector3(-sx/2 + dpml + 0.25), weight=-1))
sim2.load_minus_flux_data(refl2, refl_data0)
sim2.run(until_after_sources=100)
freqs = np.array(mp.get_flux_freqs(trans2))
t_slab = np.array(mp.get_fluxes(trans2))
r_slab = -np.array(mp.get_fluxes(refl2))

T = np.where(t_vac > 0, t_slab / t_vac, 0.0)
R = np.where(t_vac > 0, r_slab / t_vac, 0.0)
A = 1 - T - R

# Lorentzian epsilon(f)
omega = 2 * np.pi * freqs
omega_0 = 2 * np.pi * f0
gamma_ang = 2 * np.pi * gamma
eps_lorentz = 2.25 + sigma * omega_0**2 / (omega_0**2 - omega**2 - 1j*gamma_ang*omega)
eps_real = eps_lorentz.real
eps_imag = eps_lorentz.imag

# Plot
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: T, R, A spectrum
axes[0].plot(freqs, np.clip(T, 0, 1.2), 'b-', lw=1.5, label='Transmission T')
axes[0].plot(freqs, np.clip(R, 0, 1.2), 'r-', lw=1.5, label='Reflection R')
axes[0].plot(freqs, np.clip(A, 0, 1.2), 'g-', lw=1.5, label='Absorption A')
axes[0].axvline(f0, color='k', linestyle='--', alpha=0.5, label=f'f0={f0}')
axes[0].set_xlabel('Frequency (c/a)')
axes[0].set_ylabel('Fraction')
axes[0].set_title('LorentzianSusceptibility:\nDispersive Slab T/R/A Spectrum')
axes[0].legend()
axes[0].grid(True, alpha=0.3)
axes[0].set_ylim(-0.1, 1.3)

# Panel 2: epsilon(f)
ax = axes[1]
ax.plot(freqs, eps_real, 'b-', lw=1.5, label="ε'(f) real")
ax.plot(freqs, eps_imag, 'r-', lw=1.5, label='ε"(f) imag')
ax.axvline(f0, color='k', linestyle='--', alpha=0.5, label=f'f0={f0}')
ax.axhline(0, color='k', lw=0.5)
ax.set_xlabel('Frequency (c/a)')
ax.set_ylabel('ε(f)')
ax.set_title('Lorentzian Dispersion: ε(f)')
ax.legend()
ax.grid(True, alpha=0.3)
ax.set_ylim(-5, 10)

plt.tight_layout()
plt.savefig('/tmp/concept_LorentzianSusceptibility.png', dpi=100, bbox_inches='tight')
print("Saved /tmp/concept_LorentzianSusceptibility.png")
'''

# 10. Medium: 3가지 재질 평판 반사율 비교 (Fresnel reflection)
CONCEPT_CODES["Medium"] = r'''
import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# Medium: 3 materials (Air, SiO2, Si) slab reflection spectra
# Compare measured R vs Fresnel formula

resolution = 30
fcen = 0.5
df = 0.6
nfreq = 60
dpml = 1.0
sx = 10.0
slab_t = 0.3

Air   = mp.Medium(epsilon=1.0)
SiO2  = mp.Medium(epsilon=2.25)   # n ≈ 1.5
Si    = mp.Medium(epsilon=12.25)  # n ≈ 3.5

materials = [
    ("Air",  Air,  1.0,   'lightblue'),
    ("SiO2", SiO2, 2.25,  'orange'),
    ("Si",   Si,   12.25, 'tomato'),
]

cell = mp.Vector3(sx, 0, 0)
pml = [mp.PML(dpml, direction=mp.X)]
sources = [mp.Source(
    mp.GaussianSource(fcen, fwidth=df),
    component=mp.Ez,
    center=mp.Vector3(-sx/2 + dpml + 0.5)
)]

def run_reflection(mat, get_norm=False):
    geometry = [] if get_norm else [
        mp.Block(size=mp.Vector3(slab_t, mp.inf, mp.inf),
                 center=mp.Vector3(0), material=mat)
    ]
    sim = mp.Simulation(
        cell_size=cell,
        geometry=geometry,
        sources=sources,
        boundary_layers=pml,
        resolution=resolution,
        dimensions=1
    )
    refl = sim.add_flux(fcen, df, nfreq,
        mp.FluxRegion(center=mp.Vector3(-sx/2 + dpml + 0.25), weight=-1))
    inc  = sim.add_flux(fcen, df, nfreq,
        mp.FluxRegion(center=mp.Vector3(-sx/2 + dpml + 0.25)))
    sim.run(until_after_sources=100)
    r_data = sim.get_flux_data(refl)
    r_vals = np.array(mp.get_fluxes(refl))
    i_vals = np.array(mp.get_fluxes(inc))
    freqs  = np.array(mp.get_flux_freqs(refl))
    sim.reset_meep()
    return freqs, r_vals, i_vals, r_data

# Normalization (no slab)
freqs_norm, _, inc_norm, _ = run_reflection(Air, get_norm=True)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

results = {}
for name, mat, eps, color in materials:
    print(f"Running {name} (eps={eps})...")
    sim_r = mp.Simulation(
        cell_size=cell,
        geometry=[mp.Block(size=mp.Vector3(slab_t, mp.inf, mp.inf),
                           center=mp.Vector3(0), material=mat)],
        sources=sources,
        boundary_layers=pml,
        resolution=resolution,
        dimensions=1
    )
    refl = sim_r.add_flux(fcen, df, nfreq,
        mp.FluxRegion(center=mp.Vector3(-sx/2 + dpml + 0.25), weight=-1))
    inc_mon = sim_r.add_flux(fcen, df, nfreq,
        mp.FluxRegion(center=mp.Vector3(-sx/2 + dpml + 0.25)))
    sim_r.run(until_after_sources=100)
    r_vals = -np.array(mp.get_fluxes(refl))
    i_vals = np.array(mp.get_fluxes(inc_mon))
    freqs = np.array(mp.get_flux_freqs(refl))
    sim_r.reset_meep()

    R = np.where(inc_norm > 0, r_vals / inc_norm, 0.0)
    results[name] = (freqs, R, color, eps)

# Panel 1: Reflection spectra
for name, (freqs, R, color, eps) in results.items():
    n = np.sqrt(eps)
    R_fresnel = ((n - 1)/(n + 1))**2
    axes[0].plot(freqs, np.clip(R, 0, 1), color=color, lw=2,
                 label=f'{name} (n={n:.2f})')
    axes[0].axhline(R_fresnel, color=color, lw=1.2, linestyle='--', alpha=0.6)

axes[0].set_xlabel('Frequency (c/a)')
axes[0].set_ylabel('Reflectance R')
axes[0].set_title('Medium Comparison:\nReflectance vs Frequency (solid=MEEP, dashed=Fresnel)')
axes[0].legend()
axes[0].grid(True, alpha=0.3)
axes[0].set_ylim(-0.05, 0.7)

# Panel 2: Bar chart at fcen - compare MEEP vs Fresnel
names = list(results.keys())
R_meep = []
R_fresnel_vals = []
colors_bar = []
for name in names:
    freqs, R, color, eps = results[name]
    # find closest freq to fcen
    idx = np.argmin(np.abs(freqs - fcen))
    R_meep.append(float(np.clip(R[idx], 0, 1)))
    n = np.sqrt(eps)
    R_fresnel_vals.append(((n - 1)/(n + 1))**2)
    colors_bar.append(color)

x = np.arange(len(names))
w = 0.35
axes[1].bar(x - w/2, R_meep, w, label='MEEP', color=colors_bar, edgecolor='k', alpha=0.8)
axes[1].bar(x + w/2, R_fresnel_vals, w, label='Fresnel', color=colors_bar, edgecolor='k',
            alpha=0.4, hatch='///')
axes[1].set_xticks(x)
axes[1].set_xticklabels(names)
axes[1].set_ylabel('Reflectance R')
axes[1].set_title(f'Reflectance at f={fcen}\n(MEEP vs Fresnel Formula)')
axes[1].legend()
axes[1].grid(axis='y', alpha=0.3)
for xi, (rm, rf) in zip(x, zip(R_meep, R_fresnel_vals)):
    axes[1].text(xi - w/2, rm + 0.01, f'{rm:.3f}', ha='center', fontsize=9)
    axes[1].text(xi + w/2, rf + 0.01, f'{rf:.3f}', ha='center', fontsize=9)

plt.tight_layout()
plt.savefig('/tmp/concept_Medium.png', dpi=100, bbox_inches='tight')
print("Saved /tmp/concept_Medium.png")
'''


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

import tempfile

def check_image_quality(local_path):
    """Returns (ok, mean_val, size_bytes)"""
    if not local_path.exists():
        return False, 0, 0
    size = local_path.stat().st_size
    try:
        img = Image.open(local_path).convert('L')
        mean_val = np.array(img).mean()
        ok = mean_val < 230 and size > 10000
        return ok, mean_val, size
    except Exception as e:
        return False, 0, size

def run_one(name, code):
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    tmp_fname = f"fix10_{safe_name}.py"
    tmp_local = Path(tempfile.gettempdir()) / tmp_fname
    tmp_local.write_text(code, encoding='utf-8')

    docker_path = f"/tmp/{tmp_fname}"
    out_path = f"/tmp/concept_{safe_name}.png"
    local_img = RESULTS_DIR / f"concept_{safe_name}.png"

    print(f"  Copying script to Docker...", flush=True)
    subprocess.run(["docker", "cp", str(tmp_local), f"{DOCKER_WORKER}:{docker_path}"],
                   capture_output=True, timeout=15)

    print(f"  Executing in Docker (timeout={TIMEOUT}s)...", flush=True)
    result = subprocess.run(
        ["docker", "exec", DOCKER_WORKER,
         "python3", "-u", docker_path],
        capture_output=True, text=True, timeout=TIMEOUT
    )

    stdout = result.stdout[-3000:] if result.stdout else ""
    stderr = result.stderr[-3000:] if result.stderr else ""

    print(f"  returncode={result.returncode}", flush=True)
    if result.returncode != 0:
        print(f"  STDERR: {stderr[-500:]}", flush=True)
        return "error", stderr[-500:], None

    print(f"  STDOUT: {stdout[-300:]}", flush=True)

    # Retrieve image
    cp_result = subprocess.run(
        ["docker", "cp", f"{DOCKER_WORKER}:{out_path}", str(local_img)],
        capture_output=True, timeout=15
    )
    if cp_result.returncode != 0:
        return "error", f"Image not found at {out_path}", None

    ok, mean_val, size = check_image_quality(local_img)
    print(f"  Image: size={size}B, mean={mean_val:.1f}, ok={ok}", flush=True)
    if not ok:
        return "error", f"Image quality fail: mean={mean_val:.1f}, size={size}", None

    return "success", stdout[-300:], str(local_img)


def update_db(name, status, notes, demo_code, image_path=None):
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    img_url = f"/static/results/concept_{safe_name}.png" if image_path else None
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "UPDATE concepts SET demo_code=?, result_status=?, result_stdout=?, "
        "result_images=?, result_executed_at=CURRENT_TIMESTAMP, "
        "updated_at=CURRENT_TIMESTAMP WHERE name=?",
        (demo_code, status, notes, img_url, name)
    )
    conn.commit()
    conn.close()


def main():
    targets = [
        "nlopt", "add_energy", "Harminv", "LDOS", "ring_resonator",
        "at_every", "get_eigenmode_coefficients", "phase_velocity",
        "LorentzianSusceptibility", "Medium"
    ]

    print(f"\n{'='*60}")
    print(f"🚀 Fix 10 Concepts: Scenario-specific demos")
    print(f"{'='*60}\n")

    # Check docker
    chk = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Status}}", DOCKER_WORKER],
        capture_output=True, text=True
    )
    if "running" not in chk.stdout:
        print(f"❌ {DOCKER_WORKER} not running!"); sys.exit(1)
    print(f"✅ {DOCKER_WORKER} is running\n")

    summary = {}
    for name in targets:
        code = CONCEPT_CODES.get(name)
        if not code:
            print(f"[{name}] ⚠️ No code defined, skipping")
            summary[name] = "skip"
            continue

        print(f"\n[{name}]")
        try:
            status, notes, img_path = run_one(name, code)
        except subprocess.TimeoutExpired:
            print(f"  ⏱️ TIMEOUT")
            status, notes, img_path = "timeout", "timeout", None
        except Exception as e:
            print(f"  💥 Exception: {e}")
            status, notes, img_path = "error", str(e), None

        update_db(name, status, notes, code, img_path)
        icon = "✅" if status == "success" else "❌"
        print(f"  {icon} {name}: {status}")
        summary[name] = status

    print(f"\n{'='*60}")
    print("📊 Summary:")
    for name, s in summary.items():
        icon = "✅" if s == "success" else ("⏱" if s == "timeout" else "❌")
        print(f"  {icon} {name}: {s}")
    success_count = sum(1 for s in summary.values() if s == "success")
    print(f"\nTotal: {success_count}/{len(targets)} success")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
