#!/usr/bin/env python3
"""
Pattern: adjoint_optimization_problem
Complete structure of meep.adjoint.OptimizationProblem: forward simulation pass, adjoint simulation pass, objective func
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "adjoint_optimization_problem"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    from collections import namedtuple

    Grid = namedtuple('Grid', ['x', 'y', 'z', 'w'])
    YeeDims = namedtuple('YeeDims', ['Ex','Ey','Ez'])

    class DesignRegion(object):
        def __init__(self,design_parameters,volume=None, size=None, center=mp.Vector3(), MaterialGrid=None):
            self.volume = volume if volume else mp.Volume(center=center,size=size)
            self.size=self.volume.size
            self.center=self.volume.center
            self.design_parameters=design_parameters
            self.num_design_params=design_parameters.num_params
            self.MaterialGrid=MaterialGrid
        def update_design_parameters(self,design_parameters):
            self.design_parameters.update_parameters(design_parameters)
        def get_gradient(self,sim,fields_a,fields_f,frequencies):
            for c in range(3):
                fields_a[c] = fields_a[c].flatten(order='C')
                fields_f[c] = fields_f[c].flatten(order='C')
            fields_a = np.concatenate(fields_a)
            fields_f = np.concatenate(fields_f)
            num_freqs = np.array(frequencies).size

            grad = np.zeros((num_freqs,self.num_design_params)) # preallocate

            geom_list = sim.geometry
            f = sim.fields
            vol = sim._fit_volume_to_simulation(self.volume)
            # compute the gradient
            mp._get_gradient(grad,fields_a,fields_f,vol,np.array(frequencies),geom_list,f)

            return np.squeeze(grad).T

    class OptimizationProblem(object):
        """Top-level class in the MEEP adjoint module.

        Intended to be instantiated from user scripts with mandatory constructor
        input arguments specifying the data required to define an adjoint-based
        optimization.

        The class knows how to do one basic thing: Given an input vector
        of design variables, compute the objective function value (forward
        calculation) and optionally its gradient (adjoint calculation).
        This is done by the __call__ method.

        """

        def __init__(self,
                    simulation,
                    objective_functions,
                    objective_arguments,
                    design_regions,
                    frequencies=None,
                    fcen=None,
                    df=None,
                    nf=None,
                    decay_dt=50,
                    decay_fields=[mp.Ez],
                    decay_by=1e-6,
                    minimum_run_time=0,
                    maximum_run_time=None
                     ):

            self.sim = simulation

            if isinstance(objective_functions, list):
                self.objective_functions = objective_functions
            else:
                self.objective_functions = [objective_functions]
            self.objective_arguments = objective_arguments
            self.f_bank = [] # objective function evaluation history

            if isinstance(design_regions, list):
                self.design_regions = design_regions
            else:
                self.design_regions = [design_regions]

            self.num_design_params = [ni.num_design_params for ni in self.design_regions]
            self.num_design_regions = len(self.design_regions)

            # TODO typecheck frequency choices
            if frequencies is not None:
                self.frequencies = frequencies
                self.nf = np.array(frequencies).size
            else:
                if nf == 1:
                    self.nf = nf
                    self.frequencies = [fcen]
                else:
                    fmax = fcen+0.5*df
                    fmin = fcen-0.5*df
                    dfreq = (fmax-fmin)/(nf-1)
                    self.frequencies = np.linspace(fmin, fmin+dfreq*nf, num=nf, endpoint=False)
                    self.nf = nf

            if self.nf == 1:
                self.fcen_idx = 0
            else:
                self.fcen_idx = int(np.argmin(np.abs(np.asarray(self.frequencies)-np.mean(np.asarray(self.frequencies)))**2)) # index of center frequency

            self.decay_by=decay_by
            self.decay_fields=decay_fields
            self.decay_dt=decay_dt
            self.minimum_run_time=minimum_run_time
            self.maximum_run_time=maximum_run_time

            # store sources for finite difference estimations
            self.forward_sources = self.sim.sources

            # The optimizer has three allowable states : "INIT", "FWD", and "ADJ".
            #    INIT - The optimizer is initialized and ready to run a forward simulation
            #    FWD  - The optimizer has already run a forward simulation
            #    ADJ  - The optimizer has already run an adjoint simulation (but not yet calculated the gradient)
            self.current_state = "INIT"

            self.gradient = []

        def __call__(self, rho_vector=None, need_value=True, need_gradient=True):
            """Evaluate value and/or gradient of objective function.
            """
            if rho_vector:
                self.update_design(rho_vector=rho_vector)

            # Run forward run if requested
            if need_value and self.current_state == "INIT":
                print("Starting forward run...")
                self.forward_run()

            # Run adjoint simulation and calculate gradient if requested
            if need_gradient:
                if self.current_state == "INIT":
                    # we need to run a forward run before an adjoint run
                    print("Starting forward run...")
                    self.forward_run()
                    print("Starting adjoint run...")
                    self.a_E = []
                    self.adjoint_run()
                    print("Calculating gradient...")
                    self.calculate_gradient()
                elif self.current_state == "FWD":
                    print("Starting adjoint run...")
                    self.a_E = []
                    self.adjoint_run()
                    print("Calculating gradient...")
                    self.calculate_gradient()
                else:
                    raise ValueError("Incorrect solver state detected: {}".format(self.current_state))

            return self.f0, self.gradient
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
