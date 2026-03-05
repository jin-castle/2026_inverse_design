#!/usr/bin/env python3
"""
Pattern: faraday_rotation
Faraday Rotation: gyromagnetic materials, applied magnetic field, polarization rotation measurement
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "faraday_rotation"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # From the Meep tutorial: plotting Faraday rotation of a linearly polarized plane wave

    ## Parameters for a gyrotropic Lorentzian medium
    epsn  = 1.5    # background permittivity
    f0    = 1.0    # natural frequency
    gamma = 1e-6   # damping rate
    sn    = 0.1    # sigma parameter
    b0    = 0.15   # magnitude of bias vector

    susc = [mp.GyrotropicLorentzianSusceptibility(frequency=f0, gamma=gamma, sigma=sn,
                                                  bias=mp.Vector3(0, 0, b0))]
    mat = mp.Medium(epsilon=epsn, mu=1, E_susceptibilities=susc)

    ## Set up and run the Meep simulation:
    tmax = 100
    L = 20.0
    cell = mp.Vector3(0, 0, L)
    fsrc, src_z = 0.8, -8.5
    pml_layers = [mp.PML(thickness=1.0, direction=mp.Z)]

    sources = [mp.Source(mp.ContinuousSource(frequency=fsrc),
                         component=mp.Ex, center=mp.Vector3(0, 0, src_z))]

    sim = mp.Simulation(cell_size=cell, geometry=[], sources=sources,
                        boundary_layers=pml_layers,
                        default_material=mat, resolution=50)
    sim.run(until=tmax)

    ## Plot results:

    ex_data = sim.get_efield_x().real
    ey_data = sim.get_efield_y().real

    z = np.linspace(-L/2, L/2, len(ex_data))
    plt.figure(1)
    plt.plot(z, ex_data, label='Ex')
    plt.plot(z, ey_data, label='Ey')
    plt.xlim(-L/2, L/2); plt.xlabel('z')
    plt.legend()

    ## Comparison with analytic result:
    dfsq = (f0**2 - 1j*fsrc*gamma - fsrc**2)
    eperp = epsn + sn * f0**2 * dfsq / (dfsq**2 - (fsrc*b0)**2)
    eta = sn * f0**2 * fsrc * b0 / (dfsq**2 - (fsrc*b0)**2)

    k_gyro = 2*np.pi*fsrc * np.sqrt(0.5*(eperp - np.sqrt(eperp**2 - eta**2)))
    Ex_theory = 0.37 * np.cos(k_gyro * (z - src_z)).real
    Ey_theory = 0.37 * np.sin(k_gyro * (z - src_z)).real

    plt.figure(2)
    plt.subplot(2,1,1)
    plt.plot(z, ex_data, label='Ex (MEEP)')
    plt.plot(z, Ex_theory, 'k--')
    plt.plot(z, -Ex_theory, 'k--', label='Ex envelope (theory)')
    plt.xlim(-L/2, L/2); plt.xlabel('z')
    plt.legend(loc='lower right')

    plt.subplot(2,1,2)
    plt.plot(z, ey_data, label='Ey (MEEP)')
    plt.plot(z, Ey_theory, 'k--')
    plt.plot(z, -Ey_theory, 'k--', label='Ey envelope (theory)')
    plt.xlim(-L/2, L/2); plt.xlabel('z')
    plt.legend(loc='lower right')
    plt.tight_layout()
    # plt.show() suppressed
    # ─────────────────────────────────────────────────────────

    # figure 자동 저장
    _outputs = []
    if plt.get_fignums():
        _out = savefig_safe(_PATTERN)
        if _out:
            _outputs.append("output.png")

    _elapsed = round(_time.time() - _t0, 2)
    save_result(_PATTERN, outputs=_outputs, elapsed=_elapsed)
    if mp.am_master():
        print(f"[OK] {_PATTERN} ({_elapsed}s) outputs={_outputs}")

except Exception as _e:
    _elapsed = round(_time.time() - _t0, 2)
    save_result(_PATTERN, error=_e, elapsed=_elapsed)
    import traceback
    traceback.print_exc()
    sys.exit(1)
