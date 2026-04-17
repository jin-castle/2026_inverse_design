import meep as mp
import numpy as np

# 의도적 오류: resolution 너무 낮음 + PML 너무 얇음
resolution = 3
pml = mp.PML(0.1)
cell = mp.Vector3(10, 0, 0)
src = mp.Source(mp.GaussianSource(frequency=1/1.55, fwidth=0.2),
                component=mp.Ez, center=mp.Vector3(-4))
sim = mp.Simulation(cell_size=cell, resolution=resolution,
                    boundary_layers=[pml], sources=[src])
sim.run(until=300)
t = sim.get_field_point(mp.Ez, mp.Vector3(4))
print(f"Ez at output: {t}")
