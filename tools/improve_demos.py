#!/usr/bin/env python3
"""
tools/improve_demos.py - Improve concept demo images for meep-kb
Groups:
  A: DFT 2-panel add (17 concepts)
  B: Snippet regenration - full sim from scratch (9 concepts)
  C: Single plot 2-panel expansion (4 concepts)
"""
import sys, os, re, sqlite3, subprocess, argparse, json

DB_PATH = 'db/knowledge.db'
RESULTS_DIR = 'db/results'

def safe_name(name):
    return re.sub(r'[^a-zA-Z0-9_]', '_', name)

def run_in_docker(code, name, timeout=150):
    fname = safe_name(name)
    script_path = f'/tmp/concept_{fname}_script.py'
    image_path  = f'/tmp/concept_{fname}.png'
    local_script = f'tools/tmp_concept_{fname}.py'
    
    with open(local_script, 'w', encoding='utf-8') as f:
        f.write(code)
    
    r = subprocess.run(['docker', 'cp', local_script, f'meep-pilot-worker:{script_path}'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return False, f"docker cp failed: {r.stderr}"
    
    r = subprocess.run(
        ['docker', 'exec', 'meep-pilot-worker', 'python3', '-u', '-X', 'utf8', script_path],
        capture_output=True, text=True, timeout=timeout
    )
    stdout, stderr = r.stdout, r.stderr
    if r.returncode != 0:
        return False, f"EXIT={r.returncode}\nSTDOUT={stdout[-1000:]}\nSTDERR={stderr[-1000:]}"
    
    chk = subprocess.run(
        ['docker', 'exec', 'meep-pilot-worker', 'ls', '-la', image_path],
        capture_output=True, text=True
    )
    if chk.returncode != 0:
        return False, f"Image not found in docker. stdout={stdout[-500:]}"
    
    os.makedirs(RESULTS_DIR, exist_ok=True)
    local_img = f'{RESULTS_DIR}/concept_{fname}.png'
    r2 = subprocess.run(['docker', 'cp', f'meep-pilot-worker:{image_path}', local_img],
                        capture_output=True, text=True)
    if r2.returncode != 0:
        return False, f"copy back failed: {r2.stderr}"
    
    size = os.path.getsize(local_img)
    if size < 5000:
        return False, f"Image too small: {size} bytes (probably blank)"
    
    return True, f"OK ({size} bytes)"

def update_db(name, code, image_path):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""UPDATE concepts SET demo_code=?, result_images=?, result_status='success',
                 result_executed_at=datetime('now'), updated_at=datetime('now')
                 WHERE name=?""", (code, image_path, name))
    conn.commit()
    conn.close()

# ============================================================
# CONCEPT CODES
# ============================================================

CONCEPTS = {}

# -------- GROUP A: DFT 2-panel --------

CONCEPTS['mode_decomposition'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 14.0, 4.0
dpml = 1.0
w = 0.5
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, w), material=Si)],
    sources=[mp.EigenModeSource(
        mp.GaussianSource(fcen, fwidth=df),
        center=mp.Vector3(-sx/2+dpml+1), size=mp.Vector3(0, sy),
        eig_band=1, eig_parity=mp.ODD_Z
    )],
    resolution=resolution
)

mon_trans = sim.add_flux(fcen, 0, 1, mp.FluxRegion(center=mp.Vector3(sx/2-dpml-0.5), size=mp.Vector3(0, sy)))
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))

sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

res1 = sim.get_eigenmode_coefficients(mon_trans, [1], eig_parity=mp.ODD_Z)
res2 = sim.get_eigenmode_coefficients(mon_trans, [2], eig_parity=mp.ODD_Z)
p1 = abs(res1.alpha[0,0,0])**2
p2 = abs(res2.alpha[0,0,0])**2
total = p1+p2+1e-30

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[0].set_title('Ez Time Domain')
axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[1].set_title('|Ez|\\u00b2 DFT')
axes[2].bar(['Mode 1\\n(fundamental)', 'Mode 2\\n(higher)'], [p1/total, p2/total], color=['steelblue','tomato'])
axes[2].set_ylim(0,1.1); axes[2].set_title('Mode Power Decomposition')
axes[2].set_ylabel('Power Fraction')
plt.suptitle('Mode Decomposition Demo', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_mode_decomposition.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['PML'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.5
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
im0 = axes[0].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
axes[0].set_title('Ez Time Domain'); plt.colorbar(im0, ax=axes[0])
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
axes[1].set_title('|Ez|\\u00b2 DFT (Frequency Domain)'); plt.colorbar(im1, ax=axes[1])
plt.suptitle(f'PML Demo: dpml={dpml}, waveguide simulation', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_PML.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['taper'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 20
sx, sy = 12.0, 4.0
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
w_in = 0.4; w_out = 1.5; L = 5.0
eps_wg = 12

vertices = [mp.Vector3(-L/2, -w_in/2), mp.Vector3(-L/2, w_in/2),
            mp.Vector3(L/2, w_out/2), mp.Vector3(L/2, -w_out/2)]
taper = mp.Prism(vertices=vertices, height=mp.inf, material=mp.Medium(epsilon=eps_wg))
wg_in  = mp.Block(center=mp.Vector3(-sx/2+dpml+(sx/2-L/2-dpml)/2, 0),
                  size=mp.Vector3(sx/2-L/2-dpml, w_in, mp.inf), material=mp.Medium(epsilon=eps_wg))
wg_out = mp.Block(center=mp.Vector3(L/2+(sx/2-dpml-L/2)/2, 0),
                  size=mp.Vector3(sx/2-dpml-L/2, w_out, mp.inf), material=mp.Medium(epsilon=eps_wg))

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[wg_in, taper, wg_out],
    sources=[mp.EigenModeSource(mp.GaussianSource(fcen, fwidth=df),
                                center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
                                eig_band=1, eig_parity=mp.ODD_Z)],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
eps    = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].imshow(eps.T, cmap='Greys', origin='lower', aspect='auto')
axes[0].set_title(f'Taper Geometry (w_in={w_in}, w_out={w_out})')
im1 = axes[1].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[1].set_title('Ez Time Domain'); plt.colorbar(im1, ax=axes[1])
im2 = axes[2].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[2].set_title('|Ez|\\u00b2 DFT'); plt.colorbar(im2, ax=axes[2])
plt.suptitle('Linear Taper Waveguide: Mode Expansion', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_taper.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['Prism'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 15
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
w = 0.5; eps_wg = 12

# Prism as tapered waveguide
vertices = [mp.Vector3(-2, -0.3), mp.Vector3(-2, 0.3),
            mp.Vector3(2, 0.8), mp.Vector3(2, -0.8)]
prism = mp.Prism(vertices=vertices, height=mp.inf, material=mp.Medium(epsilon=eps_wg))
wg_in = mp.Block(center=mp.Vector3(-sx/2+dpml+1.5, 0), size=mp.Vector3(3, w, mp.inf),
                 material=mp.Medium(epsilon=eps_wg))

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[wg_in, prism],
    sources=[mp.EigenModeSource(mp.GaussianSource(fcen, fwidth=df),
                                center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
                                eig_band=1, eig_parity=mp.ODD_Z)],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

eps   = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_td = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].imshow(eps.T, cmap='Blues', origin='lower', aspect='auto')
axes[0].set_title('Prism Geometry (dielectric structure)')
im1 = axes[1].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[1].set_title('Ez Time Domain'); plt.colorbar(im1, ax=axes[1])
im2 = axes[2].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[2].set_title('|Ez|\\u00b2 DFT'); plt.colorbar(im2, ax=axes[2])
plt.suptitle('mp.Prism: Polygon Geometry Demo', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_Prism.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['FluxRegion'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
nfreq = 50; fmin = fcen-df; fmax = fcen+df
mon_trans = sim.add_flux(fcen, df*2, nfreq, mp.FluxRegion(center=mp.Vector3(sx/2-dpml-0.5), size=mp.Vector3(0, sy)))
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))

sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

freqs  = mp.get_flux_freqs(mon_trans)
fluxes = mp.get_fluxes(mon_trans)
ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
im0 = axes[0].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[0].set_title('Ez Time Domain'); plt.colorbar(im0, ax=axes[0])
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[1].set_title('|Ez|\\u00b2 DFT'); plt.colorbar(im1, ax=axes[1])
axes[2].plot(freqs, fluxes, 'b-o', markersize=3)
axes[2].set_xlabel('Frequency'); axes[2].set_ylabel('Flux')
axes[2].set_title('Transmitted Flux Spectrum (FluxRegion)')
axes[2].grid(True, alpha=0.4)
plt.suptitle('FluxRegion: Waveguide Transmission Monitoring', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_FluxRegion.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['get_array'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
eps    = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))

# Cross-section profile
mid_x = ez_td.shape[0]//2
y_vals = np.linspace(-(sy-2*dpml)/2, (sy-2*dpml)/2, ez_td.shape[1])

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
im0 = axes[0].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[0].set_title('get_array(Ez) - Time Domain'); plt.colorbar(im0, ax=axes[0])
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[1].set_title('|Ez|\\u00b2 DFT'); plt.colorbar(im1, ax=axes[1])
axes[2].plot(y_vals, ez_td[mid_x,:], 'b-', label='Ez (time domain)')
axes[2].plot(y_vals, np.abs(ez_dft[ez_dft.shape[0]//2,:]), 'r--', label='|Ez| DFT')
axes[2].set_xlabel('y'); axes[2].set_ylabel('Ez')
axes[2].set_title('Cross-section at x=0')
axes[2].legend(); axes[2].grid(True, alpha=0.4)
plt.suptitle('sim.get_array() - Field Data Extraction', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_get_array.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['plot2D'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si),
              mp.Cylinder(radius=0.3, material=mp.Medium(epsilon=8), center=mp.Vector3(1, 0))],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
sim.plot2D(ax=axes[0], fields=mp.Ez)
axes[0].set_title('sim.plot2D(fields=Ez) - Built-in Visualization')
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[1].set_title('|Ez|\\u00b2 DFT (Frequency Domain)')
plt.colorbar(im1, ax=axes[1])
plt.suptitle('plot2D: MEEP Built-in Visualization + DFT', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_plot2D.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['Simulation'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

eps   = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_td = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].imshow(eps.T, cmap='Greys', origin='lower', aspect='auto')
axes[0].set_title('Dielectric Structure (mp.Simulation)')
im1 = axes[1].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[1].set_title('Ez Time Domain'); plt.colorbar(im1, ax=axes[1])
im2 = axes[2].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[2].set_title('|Ez|\\u00b2 DFT'); plt.colorbar(im2, ax=axes[2])
plt.suptitle(f'mp.Simulation: resolution={resolution}, cell={sx}x{sy} \\u03bcm', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_Simulation.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['cell_size'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

results = {}
for (sx, sy) in [(8, 3), (12, 4)]:
    sim = mp.Simulation(
        cell_size=mp.Vector3(sx, sy),
        boundary_layers=[mp.PML(dpml)],
        geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
        sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                           center=mp.Vector3(-sx/2+dpml+0.5))],
        resolution=resolution
    )
    dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
        where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
    sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
    ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
    results[(sx, sy)] = ez_dft

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
for i, ((sx, sy), ez_dft) in enumerate(results.items()):
    im = axes[i].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
    axes[i].set_title(f'|Ez|\\u00b2 DFT\\ncell_size={sx}x{sy} \\u03bcm')
    plt.colorbar(im, ax=axes[i])
plt.suptitle('cell_size Effect on DFT Fields', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_cell_size.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['chunk'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
# Show chunk info
chunk_info = sim.get_array_metadata(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
im0 = axes[0].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[0].set_title('Ez Time Domain\\n(chunk = sub-domain processed by MPI rank)')
plt.colorbar(im0, ax=axes[0])
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[1].set_title('|Ez|\\u00b2 DFT\\n(aggregated across all chunks)')
plt.colorbar(im1, ax=axes[1])
plt.suptitle('chunk: MPI Domain Decomposition in MEEP', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_chunk.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['courant'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

# Compare two Courant numbers
results = {}
for courant in [0.4, 0.5]:
    sim = mp.Simulation(
        cell_size=mp.Vector3(sx, sy),
        boundary_layers=[mp.PML(dpml)],
        geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
        sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                           center=mp.Vector3(-sx/2+dpml+0.5))],
        resolution=resolution,
        Courant=courant
    )
    dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
        where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
    sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
    ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
    ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
    results[courant] = (ez_td, ez_dft)

fig, axes = plt.subplots(2, 2, figsize=(12, 7))
for i, (c, (ez_td, ez_dft)) in enumerate(results.items()):
    im0 = axes[i][0].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
    axes[i][0].set_title(f'Ez Time Domain (Courant={c})')
    plt.colorbar(im0, ax=axes[i][0])
    im1 = axes[i][1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
    axes[i][1].set_title(f'|Ez|\\u00b2 DFT (Courant={c})')
    plt.colorbar(im1, ax=axes[i][1])
plt.suptitle('Courant Number Stability Comparison', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_courant.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['mpi'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
im0 = axes[0].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[0].set_title('Ez Time Domain\\n(single process result)')
plt.colorbar(im0, ax=axes[0])
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[1].set_title('|Ez|\\u00b2 DFT\\n(mpirun -np N: identical result with parallelism)')
plt.colorbar(im1, ax=axes[1])
axes[1].text(0.02, 0.98, 'mpirun -np 4 python3 sim.py\\n=> same output, 4x faster', 
             transform=axes[1].transAxes, va='top', fontsize=8, color='white',
             bbox=dict(boxstyle='round', facecolor='navy', alpha=0.7))
plt.suptitle('MPI Parallel MEEP: mpirun -np N', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_mpi.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['stop_when_fields_decayed'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

# Track field values over time
times_list = []
ez_max_list = []

def record_field(sim):
    ez = sim.get_array(component=mp.Ez, center=mp.Vector3(sx/2-dpml-1), size=mp.Vector3(0.1, 0.1))
    times_list.append(sim.meep_time())
    ez_max_list.append(float(np.max(np.abs(ez))))

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))

sim.run(
    mp.at_every(1, record_field),
    until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6)
)

ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].semilogy(times_list, ez_max_list, 'b-')
axes[0].axhline(max(ez_max_list)*1e-6, color='r', ls='--', label='decay threshold 1e-6')
axes[0].set_xlabel('MEEP time'); axes[0].set_ylabel('|Ez| max')
axes[0].set_title('Field Decay at Monitor Point\\n(stop_when_fields_decayed)')
axes[0].legend(); axes[0].grid(True, alpha=0.4)
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[1].set_title('|Ez|\\u00b2 DFT at Convergence')
plt.colorbar(im1, ax=axes[1])
plt.suptitle('stop_when_fields_decayed: Automatic Termination', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_stop_when_fields_decayed.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['ContinuousSource'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.ContinuousSource(fcen), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until=100)

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
eps    = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].imshow(eps.T, cmap='Greys', origin='lower', aspect='auto')
axes[0].set_title('Waveguide Structure')
t = np.linspace(0, 4/fcen, 500)
axes[0].text(0.5, -0.18, f'ContinuousSource(freq={fcen:.3f}): sin(2\\u03c0ft)', 
             ha='center', transform=axes[0].transAxes, fontsize=8, style='italic')
im1 = axes[1].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[1].set_title('Ez Steady-State (CW)'); plt.colorbar(im1, ax=axes[1])
im2 = axes[2].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[2].set_title('|Ez|\\u00b2 DFT (CW steady state)'); plt.colorbar(im2, ax=axes[2])
plt.suptitle('ContinuousSource: CW Excitation Demo', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_ContinuousSource.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['CustomSource'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

# Custom source: modulated Gaussian
def custom_src_func(t):
    return np.exp(-((t-20)**2)/(2*5**2)) * np.cos(2*np.pi*fcen*t)

src = mp.CustomSource(src_func=custom_src_func, center_frequency=fcen, fwidth=df)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(src, component=mp.Ez, center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until=150)

ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

t_arr = np.linspace(0, 150, 1000)
src_arr = [custom_src_func(t) for t in t_arr]

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].plot(t_arr, src_arr, 'b-', lw=1)
axes[0].set_title('CustomSource Time Profile'); axes[0].set_xlabel('Time'); axes[0].set_ylabel('Amplitude')
axes[0].grid(True, alpha=0.4)
im1 = axes[1].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[1].set_title('Ez Time Domain'); plt.colorbar(im1, ax=axes[1])
im2 = axes[2].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[2].set_title('|Ez|\\u00b2 DFT'); plt.colorbar(im2, ax=axes[2])
plt.suptitle('CustomSource: User-Defined Source Function', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_CustomSource.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['eig_band'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 12, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

results = {}
for band in [1, 2]:
    sim = mp.Simulation(
        cell_size=mp.Vector3(sx, sy),
        boundary_layers=[mp.PML(dpml)],
        geometry=[mp.Block(size=mp.Vector3(mp.inf, 1.0), material=Si)],
        sources=[mp.EigenModeSource(
            mp.GaussianSource(fcen, fwidth=df),
            center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
            eig_band=band, eig_parity=mp.ODD_Z
        )],
        resolution=resolution
    )
    dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
        where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
    sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
    ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
    results[band] = ez_dft

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
for i, (band, ez_dft) in enumerate(results.items()):
    im = axes[i].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
    axes[i].set_title(f'|Ez|\\u00b2 DFT: eig_band={band}\\n({"Fundamental" if band==1 else "2nd order"} mode)')
    plt.colorbar(im, ax=axes[i])
plt.suptitle('EigenModeSource eig_band: Mode Selection', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_eig_band.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['eig_parity'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 12, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

# TE mode: ODD_Z parity for Ez (Ez != 0)
# TM mode: EVEN_Y (Hz field dominant, use Hz component)
results = {}

# TE mode (ODD_Z, Ez)
sim_te = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 1.0), material=Si)],
    sources=[mp.EigenModeSource(
        mp.GaussianSource(fcen, fwidth=df),
        center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
        eig_band=1, eig_parity=mp.ODD_Z
    )],
    resolution=resolution
)
dft_te = sim_te.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim_te.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
ez_te = sim_te.get_dft_array(dft_te, mp.Ez, 0)

# eig_band=2 mode (higher order, still ODD_Z)
sim_ho = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 1.0), material=Si)],
    sources=[mp.EigenModeSource(
        mp.GaussianSource(fcen, fwidth=df),
        center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
        eig_band=2, eig_parity=mp.ODD_Z
    )],
    resolution=resolution
)
dft_ho = sim_ho.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim_ho.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
ez_ho = sim_ho.get_dft_array(dft_ho, mp.Ez, 0)

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
im0 = axes[0].imshow(np.abs(ez_te).T**2, cmap='hot', origin='lower', aspect='auto')
axes[0].set_title('|Ez|\\u00b2 DFT: eig_parity=ODD_Z, eig_band=1\\n(Fundamental TE mode)')
plt.colorbar(im0, ax=axes[0])
im1 = axes[1].imshow(np.abs(ez_ho).T**2, cmap='hot', origin='lower', aspect='auto')
axes[1].set_title('|Ez|\\u00b2 DFT: eig_parity=ODD_Z, eig_band=2\\n(Higher-order TE mode)')
plt.colorbar(im1, ax=axes[1])
plt.suptitle('eig_parity: Parity Selection for EigenModeSource', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_eig_parity.png', dpi=100, bbox_inches='tight')
print("Done")
'''

# -------- GROUP B: Snippet regenration --------

CONCEPTS['epsilon_r'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

eps   = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_td = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
im0 = axes[0].imshow(eps.T, cmap='viridis', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im0, ax=axes[0], label='\\u03b5_r (relative permittivity)')
axes[0].set_title('Dielectric Map: \\u03b5_r = get_array(mp.Dielectric)\\nSi (\\u03b5=12) / Air (\\u03b5=1)')
axes[0].set_xlabel('x (\\u03bcm)'); axes[0].set_ylabel('y (\\u03bcm)')
im1 = axes[1].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im1, ax=axes[1], label='Ez')
axes[1].set_title('Ez Field Distribution')
axes[1].set_xlabel('x (\\u03bcm)'); axes[1].set_ylabel('y (\\u03bcm)')
plt.suptitle('epsilon_r: Relative Permittivity Distribution', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_epsilon_r.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['Block'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)    # n~3.46
SiO2 = mp.Medium(epsilon=2.25) # n~1.5

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[
        mp.Block(size=mp.Vector3(mp.inf, sy), material=SiO2),  # substrate
        mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si),   # waveguide core
    ],
    sources=[mp.EigenModeSource(
        mp.GaussianSource(fcen, fwidth=df),
        center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
        eig_band=1, eig_parity=mp.ODD_Z
    )],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

eps   = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
im0 = axes[0].imshow(eps.T, cmap='Blues', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im0, ax=axes[0], label='\\u03b5_r')
axes[0].set_title('mp.Block SOI Waveguide Structure\\nSi core + SiO\\u2082 substrate')
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im1, ax=axes[1], label='|Ez|\\u00b2')
axes[1].set_title('|Ez|\\u00b2 DFT: Guided Mode Intensity')
plt.suptitle('mp.Block: Rectangular Geometry for SOI Waveguide', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_Block.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['Cylinder'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 12, 12
dpml = 1.0
fcen = 0.3; df = 0.2
n_rod = 3.5
a = 1.0  # lattice constant

# Photonic crystal: 3x3 array of cylinders
cylinders = []
for ix in range(-1, 2):
    for iy in range(-1, 2):
        cylinders.append(mp.Cylinder(
            radius=0.2*a, height=mp.inf,
            material=mp.Medium(index=n_rod),
            center=mp.Vector3(ix*a, iy*a)
        ))

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=cylinders,
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+1))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

eps   = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
im0 = axes[0].imshow(eps.T, cmap='hot', origin='lower', aspect='equal',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im0, ax=axes[0], label='\\u03b5_r')
axes[0].set_title('mp.Cylinder Array\\nPhotonic Crystal (3x3 rods)')
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='inferno', origin='lower', aspect='equal',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im1, ax=axes[1], label='|Ez|\\u00b2')
axes[1].set_title('|Ez|\\u00b2 DFT: Scattering through PhC')
plt.suptitle('mp.Cylinder: Photonic Crystal Rod Array', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_Cylinder.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['Medium'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 12, 4
dpml = 1.0
fcen = 1/1.55; df = 0.8*fcen
nfreq = 60
Si   = mp.Medium(epsilon=12)
SiO2 = mp.Medium(epsilon=2.25)
Air  = mp.Medium(epsilon=1)

results = {}
for mat, name in [(Si, 'Si (\\u03b5=12)'), (SiO2, 'SiO\\u2082 (\\u03b5=2.25)'), (Air, 'Air (\\u03b5=1)')]:
    sim = mp.Simulation(
        cell_size=mp.Vector3(sx, sy),
        boundary_layers=[mp.PML(dpml)],
        geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=mat)],
        sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                           center=mp.Vector3(-sx/2+dpml+0.5))],
        resolution=resolution
    )
    flux_mon = sim.add_flux(fcen, df*2, nfreq,
                            mp.FluxRegion(center=mp.Vector3(sx/2-dpml-0.5), size=mp.Vector3(0, sy)))
    sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
    freqs  = mp.get_flux_freqs(flux_mon)
    fluxes = mp.get_fluxes(flux_mon)
    results[name] = (freqs, fluxes)

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
colors = ['steelblue', 'tomato', 'green']
for i, (name, (freqs, fluxes)) in enumerate(results.items()):
    axes[0].plot(freqs, np.array(fluxes)/max(max(f) for _,(_,f) in results.items()), 
                 color=colors[i], label=name, lw=2)
axes[0].set_xlabel('Frequency (c/\\u03bcm)'); axes[0].set_ylabel('Normalized Flux')
axes[0].set_title('Waveguide Transmission vs Frequency\\n(Different mp.Medium materials)')
axes[0].legend(); axes[0].grid(True, alpha=0.4)
wavelengths = [1e3/f for f in results['Si (\\u03b5=12)'][0]]  # nm
for i, (name, (freqs, fluxes)) in enumerate(results.items()):
    axes[1].plot(wavelengths, np.array(fluxes)/max(max(f) for _,(_,f) in results.items()),
                 color=colors[i], label=name, lw=2)
axes[1].set_xlabel('Wavelength (\\u03bcm)'); axes[1].set_ylabel('Normalized Flux')
axes[1].set_title('Transmission vs Wavelength')
axes[1].legend(); axes[1].grid(True, alpha=0.4)
plt.suptitle('mp.Medium: Material Definition (Si, SiO\\u2082, Air)', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_Medium.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['OptimizationProblem'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import meep.adjoint as mpa
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 8.0, 4.0
dpml = 1.0
w = 0.5
fcen = 1/1.55; df = 0.3
Si   = mp.Medium(epsilon=12)
SiO2 = mp.Medium(epsilon=2.25)

Nx, Ny = 20, 10
rho_init = np.ones((Nx, Ny)) * 0.5

design_region = mpa.DesignRegion(
    mp.MaterialGrid(mp.Vector3(Nx, Ny), SiO2, Si, weights=rho_init.flatten()),
    volume=mp.Volume(center=mp.Vector3(), size=mp.Vector3(2.0, 1.0))
)

geometry = [
    mp.Block(mp.Vector3(mp.inf, w), material=Si),
    mp.Block(mp.Vector3(2.0, 1.0), material=mp.MaterialGrid(
        mp.Vector3(Nx, Ny), SiO2, Si, weights=rho_init.flatten()
    )),
]

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=geometry,
    resolution=resolution
)
sim.init_sim()

eps = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
design_eps = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(2.0, 1.0))

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
im0 = axes[0].imshow(eps.T, cmap='Blues', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im0, ax=axes[0], label='\\u03b5_r')
axes[0].set_title('Full Structure: SOI + Design Region\\nBlue=Si, White=SiO\\u2082')
# Mark design region boundary
from matplotlib.patches import Rectangle
rect = Rectangle((-1, -0.5), 2, 1, linewidth=2, edgecolor='red', facecolor='none')
axes[0].add_patch(rect)
axes[0].set_xlabel('x (\\u03bcm)'); axes[0].set_ylabel('y (\\u03bcm)')

im1 = axes[1].imshow(rho_init.T, cmap='RdBu_r', origin='lower', aspect='auto',
                     vmin=0, vmax=1, extent=[-1, 1, -0.5, 0.5])
plt.colorbar(im1, ax=axes[1], label='\\u03c1 (design var)')
axes[1].set_title('Design Variable \\u03c1 (Initial: 0.5)\\nmpa.OptimizationProblem')
axes[1].text(0, 0, 'Adjoint optimization:\\nFOM gradient via \\u2202T/\\u2202\\u03c1', 
             ha='center', va='center', fontsize=9, color='white',
             bbox=dict(boxstyle='round', facecolor='navy', alpha=0.7))
plt.suptitle('mpa.OptimizationProblem: Inverse Design Setup', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_OptimizationProblem.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['beta_projection'] = '''import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt

# Heaviside projection: rho -> rho_proj
# P_beta(rho) = tanh(beta*eta) + tanh(beta*(rho-eta)) / (tanh(beta*eta) + tanh(beta*(1-eta)))
def heaviside_proj(rho, beta, eta=0.5):
    num = np.tanh(beta*eta) + np.tanh(beta*(rho - eta))
    den = np.tanh(beta*eta) + np.tanh(beta*(1 - eta))
    return num / den

# 2D design field (gradient)
x = np.linspace(0, 1, 100)
y = np.linspace(0, 1, 100)
XX, YY = np.meshgrid(x, y)
rho = 0.5 + 0.4*np.sin(2*np.pi*XX)*np.cos(2*np.pi*YY)

betas = [1, 4, 16, 64]
fig, axes = plt.subplots(1, 4, figsize=(16, 4))
for ax, beta in zip(axes, betas):
    rho_proj = heaviside_proj(rho, beta)
    im = ax.imshow(rho_proj, cmap='Greys_r', origin='lower', vmin=0, vmax=1)
    ax.set_title(f'\\u03b2 = {beta}\\n({("Smooth" if beta<=4 else "Binarized")})')
    ax.set_xlabel('x'); ax.set_ylabel('y')
    plt.colorbar(im, ax=ax, label='\\u03c1_proj')
plt.suptitle('beta_projection: Heaviside Projection P_\\u03b2(\\u03c1)\\n'
             '\\u03b2\\u2191: Gray\\u2192Binary (0/1) binarization', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_beta_projection.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['filter_and_project'] = '''import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import uniform_filter, gaussian_filter

# Create a random design field
np.random.seed(42)
rho_raw = np.random.rand(80, 80)

# Step 1: Gaussian filter (feature size control)
r_filter = 3  # filter radius (pixels)
rho_filt = gaussian_filter(rho_raw, sigma=r_filter)
rho_filt = (rho_filt - rho_filt.min()) / (rho_filt.max() - rho_filt.min())

# Step 2: Heaviside projection
def proj(rho, beta=16, eta=0.5):
    num = np.tanh(beta*eta) + np.tanh(beta*(rho - eta))
    den = np.tanh(beta*eta) + np.tanh(beta*(1-eta))
    return num / den

rho_proj = proj(rho_filt, beta=16)

fig, axes = plt.subplots(1, 3, figsize=(14, 4))
im0 = axes[0].imshow(rho_raw, cmap='Greys_r', origin='lower', vmin=0, vmax=1)
axes[0].set_title('1. Raw Design \\u03c1\\n(random initial)')
plt.colorbar(im0, ax=axes[0], label='\\u03c1')
im1 = axes[1].imshow(rho_filt, cmap='Greys_r', origin='lower', vmin=0, vmax=1)
axes[1].set_title(f'2. Gaussian Filter (r={r_filter}px)\\nFeature size control')
plt.colorbar(im1, ax=axes[1], label='\\u03c1_filt')
im2 = axes[2].imshow(rho_proj, cmap='Greys_r', origin='lower', vmin=0, vmax=1)
axes[2].set_title('3. Heaviside Projection (\\u03b2=16)\\nBinarized structure')
plt.colorbar(im2, ax=axes[2], label='\\u03c1_proj')
# Stats
for ax, d in zip(axes, [rho_raw, rho_filt, rho_proj]):
    ax.set_xlabel(f'mean={d.mean():.2f}, std={d.std():.2f}')
plt.suptitle('filter_and_project: Design Field Pipeline\\nFilter \\u2192 Project (Heaviside)', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_filter_and_project.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['resolution'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

results = {}
for res in [5, 10, 20]:
    sim = mp.Simulation(
        cell_size=mp.Vector3(sx, sy),
        boundary_layers=[mp.PML(dpml)],
        geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
        sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                           center=mp.Vector3(-sx/2+dpml+0.5))],
        resolution=res
    )
    dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
        where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
    sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
    ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)
    results[res] = ez_dft

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
for i, (res, ez_dft) in enumerate(results.items()):
    im = axes[i].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
    axes[i].set_title(f'resolution={res}\\n({ez_dft.shape[0]}x{ez_dft.shape[1]} grid points)')
    plt.colorbar(im, ax=axes[i])
plt.suptitle('resolution: Grid Density Effect on DFT Field Quality', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_resolution.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['GaussianSource'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

# Time profile of GaussianSource
t_arr = np.linspace(0, 60, 2000)
# GaussianSource envelope: Gaussian * cos(2pi*fcen*t)
t0 = 1.0/df  # peak time
width = t0
src_envelope = np.exp(-((t_arr - t0)**2) / (2*width**2))
src_signal = src_envelope * np.cos(2*np.pi*fcen*t_arr)

# Frequency spectrum via FFT
dt = t_arr[1]-t_arr[0]
freqs_fft = np.fft.rfftfreq(len(t_arr), d=dt)
spectrum = np.abs(np.fft.rfft(src_signal))**2
spectrum /= spectrum.max()

# Run simulation
sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
# Time profile
axes[0].plot(t_arr, src_signal, 'b-', lw=1, alpha=0.7, label='Signal')
axes[0].plot(t_arr, src_envelope, 'r--', lw=2, label='Envelope')
axes[0].set_xlabel('Time'); axes[0].set_ylabel('Amplitude')
axes[0].set_title(f'GaussianSource Time Profile\\nfcen={fcen:.3f}, df={df:.3f}')
axes[0].legend(); axes[0].grid(True, alpha=0.4)
# Spectrum
mask = (freqs_fft > fcen-df*1.5) & (freqs_fft < fcen+df*1.5)
axes[1].plot(freqs_fft[mask], spectrum[mask], 'g-', lw=2)
axes[1].axvline(fcen, color='r', ls='--', label=f'fcen={fcen:.3f}')
axes[1].axvline(fcen-df/2, color='orange', ls=':', label='FWHM')
axes[1].axvline(fcen+df/2, color='orange', ls=':')
axes[1].set_xlabel('Frequency'); axes[1].set_ylabel('Power (normalized)')
axes[1].set_title('Frequency Spectrum'); axes[1].legend(fontsize=8)
axes[1].grid(True, alpha=0.4)
# DFT field
im = axes[2].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[2].set_title('|Ez|\\u00b2 DFT at fcen')
plt.colorbar(im, ax=axes[2])
plt.suptitle('GaussianSource: Broadband Pulse Source', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_GaussianSource.png', dpi=100, bbox_inches='tight')
print("Done")
'''

# -------- GROUP C: 2-panel expansion --------

CONCEPTS['Harminv'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 14, 4
dpml = 1.0
w = 1.0
fcen = 0.25; df = 0.2
Si = mp.Medium(epsilon=12)

# Ring-like resonator: use a Cylinder to create resonance
# Simpler: use a block waveguide with reflections
geometry = [
    mp.Block(size=mp.Vector3(mp.inf, w), material=Si),
    mp.Block(size=mp.Vector3(0.1, w*2), material=mp.Medium(epsilon=1),
             center=mp.Vector3(3, 0)),  # partial gap to create reflection
]

# Record time series at a point
t_data, ez_data = [], []
def record(sim):
    t_data.append(sim.meep_time())
    arr = sim.get_array(component=mp.Ez, center=mp.Vector3(2, 0), size=mp.Vector3(0.1, 0.1))
    ez_data.append(float(np.real(arr.flat[0])))

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=geometry,
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
harminv_obj = mp.Harminv(mp.Ez, mp.Vector3(2, 0), fcen, df)

sim.run(
    mp.at_every(0.5, record),
    mp.after_sources(harminv_obj),
    until_after_sources=300
)

modes = harminv_obj.modes
freqs = [m.freq for m in modes]
Qs    = [abs(m.Q) for m in modes]
amps  = [abs(m.amp) for m in modes]

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].plot(t_data, ez_data, 'b-', lw=0.8)
axes[0].set_xlabel('Time (MEEP units)'); axes[0].set_ylabel('Ez')
axes[0].set_title('Time-Domain Signal at Monitor\\n(Harminv input)')
axes[0].grid(True, alpha=0.4)
# Spectrum panel
f_range = np.linspace(fcen-df, fcen+df, 400)
gaussian = np.exp(-((f_range-fcen)**2)/(2*(df/3)**2))
axes[1].plot(f_range, gaussian/gaussian.max(), 'b--', alpha=0.5, label='Source spectrum')
if freqs:
    for fi, qi, ai in zip(freqs, Qs, amps):
        axes[1].axvline(fi, color='red', alpha=0.8, lw=2,
                        label=f'f={fi:.3f}, Q={qi:.0f}')
    idx = np.argmax(amps)
    axes[1].scatter(freqs, amps/max(amps), c='red', s=80, zorder=5)
axes[1].set_xlabel('Frequency'); axes[1].set_ylabel('Amplitude (normalized)')
axes[1].set_title(f'Harminv: {len(freqs)} resonance(s) detected')
axes[1].legend(fontsize=7); axes[1].grid(True, alpha=0.4)
plt.suptitle('Harminv: Time-Domain \\u2192 Resonance Frequency Extraction', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_Harminv.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['MPB'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

# MPB: mode profile via MEEP eigenmode solver
resolution = 20
sx, sy = 6, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si   = mp.Medium(epsilon=12)
w = 0.5

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, w), material=Si)],
    sources=[mp.EigenModeSource(
        mp.GaussianSource(fcen, fwidth=df),
        center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
        eig_band=1, eig_parity=mp.ODD_Z
    )],
    resolution=resolution
)

dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

eps   = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

# Cross-section profile at center
mid_x = ez_dft.shape[0]//2
y_vals = np.linspace(-(sy-2*dpml)/2, (sy-2*dpml)/2, ez_dft.shape[1])
mode_profile = np.abs(ez_dft[mid_x, :])

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
im0 = axes[0].imshow(eps.T, cmap='Blues', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im0, ax=axes[0], label='\\u03b5_r')
axes[0].set_title('SOI Waveguide Structure\\n(MPB-like geometry)')
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im1, ax=axes[1], label='|Ez|\\u00b2')
axes[1].set_title('Guided Mode |Ez|\\u00b2 (DFT)\\nFundamental TE mode')
axes[2].plot(y_vals, mode_profile/mode_profile.max(), 'b-', lw=2, label='|Ez| DFT')
axes[2].axvspan(-w/2, w/2, alpha=0.2, color='orange', label=f'Core (w={w}\\u03bcm)')
axes[2].set_xlabel('y (\\u03bcm)'); axes[2].set_ylabel('|Ez| normalized')
axes[2].set_title('Mode Profile Cross-section\\n(MPB-equivalent)')
axes[2].legend(); axes[2].grid(True, alpha=0.4)
plt.suptitle('MPB: Waveguide Mode Profile Analysis', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_MPB.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['bend'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 14, 14
dpml = 1.5
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)
w = 0.5; R = 4.0  # bend radius

# L-shaped waveguide: horizontal + 90-deg bend + vertical
geometry = [
    # Horizontal section (left)
    mp.Block(size=mp.Vector3(sx/2+R, w), center=mp.Vector3(-(sx/2-R)/2, 0), material=Si),
    # Vertical section (top)
    mp.Block(size=mp.Vector3(w, sy/2-R), center=mp.Vector3(R, (sy/2+R)/2), material=Si),
    # Corner fill (approximate quarter circle with blocks)
]
# Add quarter-circle corner
n_seg = 12
for i in range(n_seg):
    th0 = np.pi * i / (2*n_seg)
    th1 = np.pi * (i+1) / (2*n_seg)
    th_mid = (th0+th1)/2
    # Center of segment on arc
    xc = R * (1 - np.cos(th_mid))
    yc = R * np.sin(th_mid)
    seg_w = R * (th1-th0) * 1.3  # overlap
    geometry.append(mp.Block(
        size=mp.Vector3(seg_w, w),
        center=mp.Vector3(xc - R + 0, yc),
        e1=mp.Vector3(np.cos(th_mid), np.sin(th_mid)),
        e2=mp.Vector3(-np.sin(th_mid), np.cos(th_mid)),
        material=Si
    ))

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=geometry,
    sources=[mp.EigenModeSource(
        mp.GaussianSource(fcen, fwidth=df),
        center=mp.Vector3(-sx/2+dpml+0.5), size=mp.Vector3(0, sy),
        eig_band=1, eig_parity=mp.ODD_Z
    )],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(R, sy/2-dpml-1), 1e-6))

eps    = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
im0 = axes[0].imshow(eps.T, cmap='Blues', origin='lower', aspect='equal',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im0, ax=axes[0], label='\\u03b5_r')
axes[0].set_title('90\\u00b0 Bend Waveguide Geometry\\n(R={} \\u03bcm)'.format(R))
im1 = axes[1].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='equal',
                     extent=[-(sx-2*dpml)/2,(sx-2*dpml)/2,-(sy-2*dpml)/2,(sy-2*dpml)/2])
plt.colorbar(im1, ax=axes[1], label='|Ez|\\u00b2')
axes[1].set_title('|Ez|\\u00b2 DFT: Guided Mode through Bend')
plt.suptitle('bend: 90\\u00b0 Waveguide Bend (R={} \\u03bcm)'.format(R), fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_bend.png', dpi=100, bbox_inches='tight')
print("Done")
'''

CONCEPTS['output_efield'] = '''import matplotlib
matplotlib.use('Agg')
import meep as mp
import numpy as np
import matplotlib.pyplot as plt

resolution = 10
sx, sy = 10, 4
dpml = 1.0
fcen = 1/1.55; df = 0.5*fcen
Si = mp.Medium(epsilon=12)

sim = mp.Simulation(
    cell_size=mp.Vector3(sx, sy),
    boundary_layers=[mp.PML(dpml)],
    geometry=[mp.Block(size=mp.Vector3(mp.inf, 0.5), material=Si)],
    sources=[mp.Source(mp.GaussianSource(fcen, fwidth=df), component=mp.Ez,
                       center=mp.Vector3(-sx/2+dpml+0.5))],
    resolution=resolution
)
dft_obj = sim.add_dft_fields([mp.Ez], fcen, fcen, 1,
    where=mp.Volume(center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml)))
sim.run(until_after_sources=mp.stop_when_fields_decayed(20, mp.Ez, mp.Vector3(sx/2-dpml-1), 1e-6))

eps    = sim.get_array(component=mp.Dielectric, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_td  = sim.get_array(component=mp.Ez, center=mp.Vector3(), size=mp.Vector3(sx-2*dpml, sy-2*dpml))
ez_dft = sim.get_dft_array(dft_obj, mp.Ez, 0)

fig, axes = plt.subplots(1, 3, figsize=(15, 4))
axes[0].imshow(eps.T, cmap='Greys', origin='lower', aspect='auto')
axes[0].set_title('Dielectric \\u03b5_r\\n(output_epsilon)')
im1 = axes[1].imshow(ez_td.T, cmap='RdBu', origin='lower', aspect='auto')
axes[1].set_title('Ez Time Domain\\n(output_efield_z)')
plt.colorbar(im1, ax=axes[1])
im2 = axes[2].imshow(np.abs(ez_dft).T**2, cmap='hot', origin='lower', aspect='auto')
axes[2].set_title('|Ez|\\u00b2 DFT\\n(frequency domain)')
plt.colorbar(im2, ax=axes[2])
plt.suptitle('output_efield: Field Data Output Methods', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_output_efield.png', dpi=100, bbox_inches='tight')
print("Done")
'''

# ============================================================
# MAIN
# ============================================================

GROUP_A = ['mode_decomposition', 'PML', 'taper', 'Prism', 'FluxRegion', 'get_array',
           'plot2D', 'Simulation', 'cell_size', 'chunk', 'courant', 'mpi',
           'stop_when_fields_decayed', 'ContinuousSource', 'CustomSource', 'eig_band', 'eig_parity']
GROUP_B = ['epsilon_r', 'Block', 'Cylinder', 'Medium', 'OptimizationProblem',
           'beta_projection', 'filter_and_project', 'resolution', 'GaussianSource']
GROUP_C = ['Harminv', 'MPB', 'bend', 'output_efield']

def process_concept(name):
    code = CONCEPTS.get(name)
    if not code:
        return False, f"No code defined for {name}"
    
    fname = safe_name(name)
    image_path = f'/static/results/concept_{fname}.png'
    
    print(f"\n[{name}] Running in Docker...")
    ok, msg = run_in_docker(code, name)
    if ok:
        update_db(name, code, image_path)
        print(f"  [OK] {msg}")
    else:
        print(f"  [FAIL] {msg}")
    return ok, msg

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', choices=['A', 'B', 'C', 'all'], default='all')
    parser.add_argument('--name', help='Single concept name')
    args = parser.parse_args()
    
    if args.name:
        names = [args.name]
    elif args.group == 'A':
        names = GROUP_A
    elif args.group == 'B':
        names = GROUP_B
    elif args.group == 'C':
        names = GROUP_C
    else:
        names = GROUP_A + GROUP_B + GROUP_C
    
    results = {}
    for name in names:
        ok, msg = process_concept(name)
        results[name] = ('OK' if ok else 'FAIL', msg)
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    ok_count = sum(1 for v in results.values() if v[0]=='OK')
    print(f"Total: {len(results)}, OK: {ok_count}, FAIL: {len(results)-ok_count}")
    print("\nFailed concepts:")
    for name, (status, msg) in results.items():
        if status == 'FAIL':
            print(f"  {name}: {msg[:200]}")
    
    return results

if __name__ == '__main__':
    main()
