"""Si 분산 모델 — MEEP용 Lorentz 피팅 (가시광 400~720nm)"""
import meep as mp

# Palik/Green 데이터 기반 3-pole Lorentz 피팅
# RMS: eps_r=0.0590, eps_i=0.0333
Si_dispersive = mp.Medium(
    epsilon=5.000000,
    E_susceptibilities=[
    mp.LorentzianSusceptibility(frequency=2.541523, gamma=0.116865, sigma=0.222663),
    mp.LorentzianSusceptibility(frequency=2.392808, gamma=0.278399, sigma=0.202027),
    mp.LorentzianSusceptibility(frequency=3.156116, gamma=0.000000, sigma=9.069662),
    ]
)

# 파장별 참고값 (Palik)
SI_NK = {
    0.400: (5.570, 0.387),
    0.450: (4.885, 0.068),
    0.500: (4.623, 0.028),
    0.538: (4.460, 0.010),  # G 채널
    0.550: (4.448, 0.011),
    0.600: (4.280, 0.005),
    0.650: (4.208, 0.003),  # R 채널
    0.698: (4.147, 0.001),  # R peak
    0.700: (4.134, 0.001),
    0.720: (4.115, 0.001),
}

def get_si_eps(wl_um):
    """wl_um: 파장 μm → 복소 유전율 반환 (선형 보간)"""
    import numpy as np
    wls = sorted(SI_NK.keys())
    ns  = [SI_NK[w][0] for w in wls]
    ks  = [SI_NK[w][1] for w in wls]
    n   = np.interp(wl_um, wls, ns)
    k   = np.interp(wl_um, wls, ks)
    return (n + 1j*k)**2
