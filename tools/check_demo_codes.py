import sqlite3
import re

targets_A = ['mode_decomposition', 'PML', 'taper', 'Prism', 'FluxRegion', 'get_array', 'plot2D', 
             'Simulation', 'cell_size', 'chunk', 'courant', 'mpi', 'stop_when_fields_decayed', 
             'ContinuousSource', 'CustomSource', 'eig_band', 'eig_parity']
targets_B = ['epsilon_r', 'Block', 'Cylinder', 'Medium', 'OptimizationProblem', 'beta_projection', 
             'filter_and_project', 'resolution', 'GaussianSource']
targets_C = ['Harminv', 'MPB', 'bend', 'output_efield']

all_targets = targets_A + targets_B + targets_C

conn = sqlite3.connect('db/knowledge.db')
c = conn.cursor()

for name in all_targets:
    c.execute("SELECT name, result_images, result_status FROM concepts WHERE name=?", (name,))
    row = c.fetchone()
    if row:
        print(f"  {row[0]}: status={row[2]}, images={row[1]}")
    else:
        print(f"  {name}: NOT FOUND")

conn.close()
