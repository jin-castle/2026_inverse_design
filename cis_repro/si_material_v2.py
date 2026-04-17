import meep as mp

# Si 분산 모델 v2 — Palik 3-pole Lorentz (딥UV pole만)
# MEEP 안전: 모든 pole이 가시광 주파수(1.4~2.2)보다 훨씬 높음
# 유효 범위: 400~720nm
Si_dispersive = mp.Medium(
    epsilon=0.500000,
    E_susceptibilities=[
        mp.LorentzianSusceptibility(frequency=3.500000, gamma=0.179399, sigma=7.826863),
        mp.LorentzianSusceptibility(frequency=3.500000, gamma=0.179399, sigma=2.043324),
        mp.LorentzianSusceptibility(frequency=3.500000, gamma=0.179399, sigma=4.336282),
    ]
)

Si_simple = mp.Medium(epsilon=19.8)
