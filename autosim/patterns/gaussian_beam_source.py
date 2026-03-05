#!/usr/bin/env python3
"""
Pattern: gaussian_beam_source
Gaussian beam source: GaussianBeam, beam waist w0, focal position setting
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "gaussian_beam_source"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    ## launch a Gaussian beam

    import math

    matplotlib.use('agg')

    s = 14
    resolution = 50
    dpml = 2

    cell_size = mp.Vector3(s,s)

    boundary_layers = [mp.PML(thickness=dpml)]

    beam_x0 = mp.Vector3(0,3.0)    # beam focus (relative to source center)
    rot_angle = 0  # CCW rotation angle about z axis (0: +y axis)
    beam_kdir = mp.Vector3(0,1,0).rotate(mp.Vector3(0,0,1),math.radians(rot_angle))  # beam propagation direction
    beam_w0 = 0.8  # beam waist radius
    beam_E0 = mp.Vector3(0,0,1)
    fcen = 1
    sources = [mp.GaussianBeamSource(src=mp.ContinuousSource(fcen),
                                     center=mp.Vector3(0,-0.5*s+dpml+1.0),
                                     size=mp.Vector3(s),
                                     beam_x0=beam_x0,
                                     beam_kdir=beam_kdir,
                                     beam_w0=beam_w0,
                                     beam_E0=beam_E0)]

    sim = mp.Simulation(resolution=resolution,
                        cell_size=cell_size,
                        boundary_layers=boundary_layers,
                        sources=sources)

    sim.run(until=20)

    sim.plot2D(fields=mp.Ez,
               output_plane=mp.Volume(center=mp.Vector3(),
                                      size=mp.Vector3(s-2*dpml,s-2*dpml)))

    plt.savefig('Ez_angle{}.png'.format(rot_angle),bbox_inches='tight',pad_inches=0)
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
