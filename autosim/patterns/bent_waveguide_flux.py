#!/usr/bin/env python3
"""
Pattern: bent_waveguide_flux
Curved waveguide flux comparison: transmission efficiency of straight vs. curved waveguide. Normalized flux pattern.
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "bent_waveguide_flux"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # -*- coding: utf-8 -*-

    # From the Meep tutorial: plotting permittivity and fields of a bent waveguide

    cell = mp.Vector3(16,16,0)
    geometry = [mp.Block(mp.Vector3(12,1,mp.inf),
                         center=mp.Vector3(-2.5,-3.5),
                         material=mp.Medium(epsilon=12)),
                mp.Block(mp.Vector3(1,12,mp.inf),
                         center=mp.Vector3(3.5,2),
                         material=mp.Medium(epsilon=12))]
    pml_layers = [mp.PML(1.0)]
    resolution = 10

    sources = [mp.Source(mp.ContinuousSource(wavelength=2*(11**0.5), width=20),
                         component=mp.Ez,
                         center=mp.Vector3(-7,-3.5),
                         size=mp.Vector3(0,1))]

    sim = mp.Simulation(cell_size=cell,
                        boundary_layers=pml_layers,
                        geometry=geometry,
                        sources=sources,
                        resolution=resolution)

    sim.run(mp.at_beginning(mp.output_epsilon),
            mp.to_appended("ez", mp.at_every(0.6, mp.output_efield_z)),
            until=200)
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
