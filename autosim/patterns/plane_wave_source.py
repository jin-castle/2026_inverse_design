#!/usr/bin/env python3
"""
Pattern: plane_wave_source
Plane wave source setup: uniform excitation using PlaneWave, k_point, and amplitude functions
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "plane_wave_source"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # This example creates an approximate Ez-polarized planewave in vacuum
    # propagating at a 45-degree angle, by using a couple of current sources
    # with amplitude exp(ikx) corresponding to the desired planewave.

    import cmath
    import math

    s = 11  # the size of the computational cell, not including PML
    dpml = 1  # thickness of PML layers

    sxy = s + 2 * dpml  # cell size, including PML
    cell = mp.Vector3(sxy, sxy, 0)

    pml_layers = [mp.PML(dpml)]
    resolution = 10

    # pw-amp is a function that returns the amplitude exp(ik(x+x0)) at a
    # given point x.  (We need the x0 because current amplitude functions
    # in Meep are defined relative to the center of the current source,
    # whereas we want a fixed origin.)  Actually, it is a function of k
    # and x0 that returns a function of x ...
    def pw_amp(k, x0):
        def _pw_amp(x):
            return cmath.exp(1j * k.dot(x + x0))
        return _pw_amp

    fcen = 0.8  # pulse center frequency
    df = 0.02  # turn-on bandwidth
    kdir = mp.Vector3(1, 1)  # direction of k (length is irrelevant)
    n = 1 # refractive index of material containing the source
    k = kdir.unit().scale(2 * math.pi * fcen * n)  # k with correct length

    sources = [
        mp.Source(
            mp.ContinuousSource(fcen, fwidth=df),
            component=mp.Ez,
            center=mp.Vector3(-0.5 * s, 0),
            size=mp.Vector3(0, s),
            amp_func=pw_amp(k, mp.Vector3(x=-0.5 * s))
        ),
        mp.Source(
            mp.ContinuousSource(fcen, fwidth=df),
            component=mp.Ez,
            center=mp.Vector3(0, -0.5 * s),
            size=mp.Vector3(s, 0),
            amp_func=pw_amp(k, mp.Vector3(y=-0.5 * s))
        )
    ]

    sim = mp.Simulation(
        cell_size=cell,
        sources=sources,
        boundary_layers=pml_layers,
        resolution=resolution,
        default_material=mp.Medium(index=n),
    )

    t = 400  # run time
    sim.run(mp.at_end(mp.output_efield_z), until=t)
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
