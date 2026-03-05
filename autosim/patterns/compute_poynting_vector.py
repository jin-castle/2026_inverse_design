#!/usr/bin/env python3
"""
Pattern: compute_poynting_vector
Compute time-averaged Poynting vector from DFT field arrays. 3D formula: Px = 0.5*Re(Ey·Hz* - Ez·Hy*), Py = 0.5*Re(Ez·Hx
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "compute_poynting_vector"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # ── 3D Poynting vector from DFT complex field arrays ──────────────────────
    def compute_poynting_3d(Ex, Ey, Ez, Hx, Hy, Hz):
        """Time-averaged Poynting vector from 3D DFT fields.
    
        P = 0.5 * Re(E × H*)
        """
        Px = 0.5 * np.real(Ey * np.conj(Hz) - Ez * np.conj(Hy))
        Py = 0.5 * np.real(Ez * np.conj(Hx) - Ex * np.conj(Hz))
        Pz = 0.5 * np.real(Ex * np.conj(Hy) - Ey * np.conj(Hx))
        return Px, Py, Pz

    # ── 2D TE Poynting vector (Ez, Hx, Hy only) ──────────────────────────────
    def compute_poynting_2d_te(Ez, Hx, Hy):
        """Time-averaged Poynting vector for 2D TE polarization.
    
        TE: Ez dominant; Hx, Hy present; Ex=Ey=Hz=0
        """
        Px =  0.5 * np.real(Ez * np.conj(Hy))
        Py = -0.5 * np.real(Ez * np.conj(Hx))
        Pz = np.zeros_like(Px)  # No z-propagation in 2D
        return Px, Py, Pz

    # ── Usage with MEEP DFT arrays ────────────────────────────────────────────
    # After sim.run():
    # Ex = sim.get_dft_array(dft_mon, mp.Ex, 0)  # freq index 0
    # Ey = sim.get_dft_array(dft_mon, mp.Ey, 0)
    # ...
    # Px, Py, Pz = compute_poynting_3d(Ex, Ey, Ez, Hx, Hy, Hz)
    # # Plot |Px| to see power flow in x-direction
    # plt.imshow(np.abs(Px), cmap='hot')
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
