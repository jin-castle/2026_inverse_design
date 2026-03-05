#!/usr/bin/env python3
"""
Pattern: adjoint_objective_functions
Define objective functions (FOM) for MEEP adjoint optimization. EigenmodeCoefficient: maximize |α|² for target mode at o
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "adjoint_objective_functions"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    """Handling of objective functions and objective quantities."""

    from abc import ABC, abstractmethod

    from .filter_source import FilteredSource
    from .optimization_problem import Grid
    from meep.simulation import py_v3_to_vec

    class ObjectiveQuantitiy(ABC):
        @abstractmethod
        def __init__(self):
            return
        @abstractmethod
        def register_monitors(self):
            return
        @abstractmethod
        def place_adjoint_source(self):
            return
        @abstractmethod
        def __call__(self):
            return
        @abstractmethod
        def get_evaluation(self):
            return

    class EigenmodeCoefficient(ObjectiveQuantitiy):
        def __init__(self,sim,volume,mode,forward=True,kpoint_func=None,**kwargs):
            '''
            '''
            self.sim = sim
            self.volume=volume
            self.mode=mode
            self.forward = 0 if forward else 1
            self.normal_direction = None
            self.kpoint_func = kpoint_func
            self.eval = None
            self.EigenMode_kwargs = kwargs
            return

        def register_monitors(self,frequencies):
            self.frequencies = np.asarray(frequencies)
            self.monitor = self.sim.add_mode_monitor(frequencies,mp.ModeRegion(center=self.volume.center,size=self.volume.size),yee_grid=True)
            self.normal_direction = self.monitor.normal_direction
            return self.monitor

        def place_adjoint_source(self,dJ):
            '''Places an equivalent eigenmode monitor facing the opposite direction. Calculates the
            correct scaling/time profile.
            dJ ........ the user needs to pass the dJ/dMonitor evaluation
            '''
            dJ = np.atleast_1d(dJ)
            dt = self.sim.fields.dt # the timestep size from sim.fields.dt of the forward sim
            # determine starting kpoint for reverse mode eigenmode source
            direction_scalar = 1 if self.forward else -1
            if self.kpoint_func is None:
                if self.normal_direction == 0:
                    k0 = direction_scalar * mp.Vector3(x=1)
                elif self.normal_direction == 1:
                    k0 = direction_scalar * mp.Vector3(y=1)
                elif self.normal_direction == 2:
                    k0 == direction_scalar * mp.Vector3(z=1)
            else:
                k0 = direction_scalar * self.kpoint_func(self.time_src.frequency,1)
            if dJ.ndim == 2:
                dJ = np.sum(dJ,axis=1)
            da_dE = 0.5 * self.cscale # scalar popping out of derivative

            scale = adj_src_scale(self, dt)

            if self.frequencies.size == 1:
                # Single frequency simulations. We need to drive it with a time profile.
                amp = da_dE * dJ * scale # final scale factor
                src=self.time_src
            else:
                # multi frequency simulations
                scale = da_dE * dJ * scale
                src = FilteredSource(self.time_src.frequency,self.frequencies,scale,dt) # generate source from broadband response
                amp = 1

            # generate source object
            self.source = [mp.EigenModeSource(src,
                        eig_band=self.mode,
                        direction=mp.NO_DIRECTION,
                        eig_kpoint=k0,
                        amplitude=amp,
                        eig_match_freq=True,
                        size=self.volume.size,
                        center=self.volume.center,
                        **self.EigenMode_kwargs)]

            return self.source

        def __call__(self):
            # Eigenmode data
            self.time_src = create_time_profile(self)
            direction = mp.NO_DIRECTION if self.kpoint_func else mp.AUTOMATIC
            ob = self.sim.get_eigenmode_coefficients(self.monitor,[self.mode],direction=direction,kpoint_func=self.kpoint_func,**self.EigenMode_kwargs)
            self.eval = np.squeeze(ob.alpha[:,:,self.forward]) # record eigenmode coefficients for scaling
            self.cscale = ob.cscale # pull scaling factor

            return self.eval
        def get_evaluation(self):
            '''Returns the requested eigenmode coefficient.
            '''
            try:
                return self.eval
            except AttributeError:
                raise RuntimeError("You must first run a forward simulation before resquesting an eigenmode coefficient.")

    class FourierFields(ObjectiveQuantitiy):
        def __init__(self,sim,volume, component):
            self.sim = sim
            self.volume=volume
            self.eval = None
            self.component = component
            return

        def register_monitors(self,frequencies):
            self.frequencies = np.asarray(frequencies)
            self.num_freq = len(self.frequencies)
            self.monitor = self.sim.add_dft_fields([self.component], self.frequencies, where=self.volume, yee_grid=False)
            return self.monitor

        def place_adjoint_source(self,dJ):
            dt = self.sim.fields.dt # the timestep size from sim.fields.dt of the forward sim
            self.sources = []
            scale = adj_src_scale(self, dt)

            x_dim, y_dim, z_dim = len(self.dg.x), len(self.dg.y), len(self.dg.z)

            if self.num_freq == 1:
                amp = -dJ[0].copy().reshape(x_dim, y_dim, z_dim) * scale
                src = self.time_src
                if self.component in [mp.Hx, mp.Hy, mp.Hz]:
                    amp = -amp
                for zi in range(z_dim):
                    for yi in range(y_dim):
                        for xi in range(x_dim):
                            if amp[xi, yi, zi] != 0:
                                self.sources += [mp.Source(src, component=self.component, amplitude=amp[xi, yi, zi],
                                center=mp.Vector3(self.dg.x[xi], self.dg.y[yi], self.dg.z[zi]))]
    # ... (truncated)
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
