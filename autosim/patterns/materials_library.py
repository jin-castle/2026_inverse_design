#!/usr/bin/env python3
"""
Pattern: materials_library
MEEP material library: dispersive materials including Si, SiO2, Al, Au, etc. Drude-Lorentz parameters
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "materials_library"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # -*- coding: utf-8 -*-
    # Materials Library

    # default unit length is 1 um
    um_scale = 1.0

    # conversion factor for eV to 1/um [=1/hc]
    eV_um_scale = um_scale/1.23984193

    #------------------------------------------------------------------
    # crystalline silicon (c-Si) from A. Deinega et al., J. Optical Society of America A, Vol. 28, No. 5, pp. 770-77, 2011
    # based on experimental data for intrinsic silicon at T=300K from M.A. Green and M. Keevers, Progress in Photovoltaics, Vol. 3, pp. 189-92, 1995
    # wavelength range: 0.4 - 1.0 um

    cSi_range = mp.FreqRange(min=um_scale, max=um_scale/0.4)

    cSi_frq1 = 3.64/um_scale
    cSi_gam1 = 0
    cSi_sig1 = 8
    cSi_frq2 = 2.76/um_scale
    cSi_gam2 = 2*0.063/um_scale
    cSi_sig2 = 2.85
    cSi_frq3 = 1.73/um_scale
    cSi_gam3 = 2*2.5/um_scale
    cSi_sig3 = -0.107

    cSi_susc = [mp.LorentzianSusceptibility(frequency=cSi_frq1, gamma=cSi_gam1, sigma=cSi_sig1),
                mp.LorentzianSusceptibility(frequency=cSi_frq2, gamma=cSi_gam2, sigma=cSi_sig2),
                mp.LorentzianSusceptibility(frequency=cSi_frq3, gamma=cSi_gam3, sigma=cSi_sig3)]

    cSi = mp.Medium(epsilon=1.0, E_susceptibilities=cSi_susc, valid_freq_range=cSi_range)

    #------------------------------------------------------------------
    # amorphous silicon (a-Si) from Horiba Technical Note 08: Lorentz Dispersion Model
    # ref: http://www.horiba.com/fileadmin/uploads/Scientific/Downloads/OpticalSchool_CN/TN/ellipsometer/Lorentz_Dispersion_Model.pdf
    # wavelength range: 0.21 - 0.83 um

    aSi_range = mp.FreqRange(min=um_scale/0.83, max=um_scale/0.21)

    aSi_frq1 = 1/(0.315481407124682*um_scale)
    aSi_gam1 = 1/(0.645751005208333*um_scale)
    aSi_sig1 = 14.571

    aSi_susc = [mp.LorentzianSusceptibility(frequency=aSi_frq1, gamma=aSi_gam1, sigma=aSi_sig1)]

    aSi = mp.Medium(epsilon=3.109, E_susceptibilities=aSi_susc, valid_freq_range=aSi_range)

    #------------------------------------------------------------------
    # hydrogenated amorphous silicon (a-Si:H) from Horiba Technical Note 08: Lorentz Dispersion Model
    # ref: http://www.horiba.com/fileadmin/uploads/Scientific/Downloads/OpticalSchool_CN/TN/ellipsometer/Lorentz_Dispersion_Model.pdf
    # wavelength range: 0.21 - 0.83 um

    aSi_H_range = mp.FreqRange(min=um_scale/0.83, max=um_scale/0.21)

    aSi_H_frq1 = 1/(0.334189199460916*um_scale)
    aSi_H_gam1 = 1/(0.579365387850467*um_scale)
    aSi_H_sig1 = 12.31

    aSi_H_susc = [mp.LorentzianSusceptibility(frequency=aSi_H_frq1, gamma=aSi_H_gam1, sigma=aSi_H_sig1)]

    aSi_H = mp.Medium(epsilon=3.22, E_susceptibilities=aSi_H_susc, valid_freq_range=aSi_H_range)

    #------------------------------------------------------------------
    # indium tin oxide (ITO) from Horiba Technical Note 08: Lorentz Dispersion Model
    # ref: http://www.horiba.com/fileadmin/uploads/Scientific/Downloads/OpticalSchool_CN/TN/ellipsometer/Lorentz_Dispersion_Model.pdf
    # wavelength range: 0.21 - 0.83 um

    ITO_range = mp.FreqRange(min=um_scale/0.83, max=um_scale/0.21)

    ITO_frq1 = 1/(0.182329695588235*um_scale)
    ITO_gam1 = 1/(1.94637665620094*um_scale)
    ITO_sig1 = 2.5

    ITO_susc = [mp.LorentzianSusceptibility(frequency=ITO_frq1, gamma=ITO_gam1, sigma=ITO_sig1)]

    ITO = mp.Medium(epsilon=1.0, E_susceptibilities=ITO_susc, valid_freq_range=ITO_range)

    #------------------------------------------------------------------
    # alumina (Al2O3) from Horiba Technical Note 08: Lorentz Dispersion Model
    # ref: http://www.horiba.com/fileadmin/uploads/Scientific/Downloads/OpticalSchool_CN/TN/ellipsometer/Lorentz_Dispersion_Model.pdf
    # wavelength range: 0.21 - 2.07 um

    Al2O3_range = mp.FreqRange(min=um_scale/2.07, max=um_scale/0.21)

    Al2O3_frq1 = 1/(0.101476668030774*um_scale)
    Al2O3_gam1 = 0
    Al2O3_sig1 = 1.52

    Al2O3_susc = [mp.LorentzianSusceptibility(frequency=Al2O3_frq1, gamma=Al2O3_gam1, sigma=Al2O3_sig1)]

    Al2O3 = mp.Medium(epsilon=1.0, E_susceptibilities=Al2O3_susc, valid_freq_range=Al2O3_range)

    #------------------------------------------------------------------
    # aluminum nitride (AlN) from Horiba Technical Note 08: Lorentz Dispersion Model
    # ref: http://www.horiba.com/fileadmin/uploads/Scientific/Downloads/OpticalSchool_CN/TN/ellipsometer/Lorentz_Dispersion_Model.pdf
    # wavelength range: 0.26 - 1.65 um

    AlN_range = mp.FreqRange(min=um_scale/1.65, max=um_scale/0.26)

    AlN_frq1 = 1/(0.139058089950651*um_scale)
    AlN_gam1 = 0
    AlN_sig1 = 3.306

    AlN_susc = [mp.LorentzianSusceptibility(frequency=AlN_frq1, gamma=AlN_gam1, sigma=AlN_sig1)]

    AlN = mp.Medium(epsilon=1.0, E_susceptibilities=AlN_susc, valid_freq_range=AlN_range)

    #------------------------------------------------------------------
    # aluminum arsenide (AlAs) from R.E. Fern and A. Onton, J. Applied Physics, Vol. 42, pp. 3499-500, 1971
    # ref: https://refractiveindex.info/?shelf=main&book=AlAs&page=Fern
    # wavelength range: 0.56 - 2.2 um

    AlAs_range = mp.FreqRange(min=um_scale/2.2, max=um_scale/0.56)

    AlAs_frq1 = 1/(0.2822*um_scale)
    AlAs_gam1 = 0
    AlAs_sig1 = 6.0840
    AlAs_frq2 = 1/(27.62*um_scale)
    AlAs_gam2 = 0
    AlAs_sig2 = 1.900

    AlAs_susc = [mp.LorentzianSusceptibility(frequency=AlAs_frq1, gamma=AlAs_gam1, sigma=AlAs_sig1),
                 mp.LorentzianSusceptibility(frequency=AlAs_frq2, gamma=AlAs_gam2, sigma=AlAs_sig2)]

    AlAs = mp.Medium(epsilon=2.0792, E_susceptibilities=AlAs_susc, valid_freq_range=AlAs_range)

    #------------------------------------------------------------------
    # borosilicate glass (BK7) from SCHOTT Zemax catalog 2017-01-20b
    # ref: https://refractiveindex.info/?shelf=glass&book=BK7&page=SCHOTT
    # wavelength range: 0.3 - 2.5 um

    BK7_range = mp.FreqRange(min=um_scale/2.5, max=um_scale/0.3)

    BK7_frq1 = 1/(0.07746417668832478*um_scale)
    BK7_gam1 = 0
    BK7_sig1 = 1.03961212
    BK7_frq2 = 1/(0.14148467902921502*um_scale)
    BK7_gam2 = 0
    BK7_sig2 = 0.231792344
    BK7_frq3 = 1/(10.176475470417055*um_scale)
    BK7_gam3 = 0
    BK7_sig3 = 1.01046945
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
