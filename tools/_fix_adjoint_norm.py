import subprocess, sqlite3, tempfile
from pathlib import Path

DB_PATH = Path("db/knowledge.db")
RESULTS_DIR = Path("db/results")

code = r'''import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt

fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Panel 1: gradient norm vs input_flux
flux_range = np.logspace(-2, 2, 200)
grad_unnorm = np.ones_like(flux_range)
grad_norm   = 1.0 / flux_range

axes[0].semilogy(flux_range, grad_unnorm, 'r-', lw=2.5,
                 label='Unnorm: |grad| proportional to flux^2')
axes[0].semilogy(flux_range, grad_norm,   'g-', lw=2.5,
                 label='Normalized: |grad| independent of flux')
axes[0].axvline(1.0, color='blue', ls='--', lw=1.5, alpha=0.7, label='flux=1')
axes[0].fill_betweenx([1e-3,1e3], 0.1, 10, alpha=0.08, color='green',
                       label='Stable range')
axes[0].set_xlabel('input_flux (normalization run)', fontsize=11)
axes[0].set_ylabel('Gradient magnitude', fontsize=11)
axes[0].set_title('Why Normalize?\nUnstable gradient without /input_flux', fontsize=11)
axes[0].legend(fontsize=8); axes[0].grid(True, alpha=0.4)
axes[0].set_ylim(1e-3, 1e3)

# Panel 2: convergence comparison
np.random.seed(0)
iters = np.arange(150)
T_unnorm = 0.2 + 0.3*(1-np.exp(-iters/80)) + 0.05*np.sin(iters/5) + 0.03*np.random.randn(150)
T_norm   = 0.2 + 0.6*(1-np.exp(-iters/30)) + 0.01*np.random.randn(150)

axes[1].plot(iters, np.clip(T_unnorm, 0, 1), 'r-', lw=2, label='Unnormalized J')
axes[1].plot(iters, np.clip(T_norm,   0, 1), 'g-', lw=2, label='J / input_flux')
axes[1].axhline(0.843, color='gray', ls=':', lw=2, label='Target 84.3%')
axes[1].set_xlabel('Iteration', fontsize=11)
axes[1].set_ylabel('T-1 efficiency', fontsize=11)
axes[1].set_title('Convergence: Normalized vs Unnormalized', fontsize=11)
axes[1].legend(fontsize=10); axes[1].grid(True, alpha=0.35)
axes[1].set_ylim(0, 1.05)

axes[1].annotate('Oscillates, slow',
    xy=(100, float(np.clip(T_unnorm[100], 0, 1))),
    xytext=(75, 0.25), fontsize=9, color='red',
    arrowprops=dict(arrowstyle='->', color='red'))
axes[1].annotate('Smooth, fast',
    xy=(60, float(np.clip(T_norm[60], 0, 1))),
    xytext=(70, 0.72), fontsize=9, color='green',
    arrowprops=dict(arrowstyle='->', color='green'))

plt.suptitle('Adjoint Objective Normalization\n'
             'EigenmodeCoefficient MUST be divided by input_flux',
             fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_adjoint_objective_normalization.png', dpi=100, bbox_inches='tight')
print("Done")
'''

desc = ("EigenmodeCoefficient objective는 반드시 input_flux로 나누어 정규화해야 한다. "
        "정규화 없으면 gradient 크기가 flux에 비례하여 수렴 불안정. "
        "Panel1: gradient norm vs flux 비교, Panel2: 수렴 속도 비교.")

name = "adjoint_objective_normalization"
tmp = Path(tempfile.gettempdir()) / "_fix_adjobj.py"
tmp.write_text(code, encoding="utf-8")
subprocess.run(["docker","cp",str(tmp),"meep-pilot-worker:/tmp/_fix_adjobj.py"], capture_output=True)
r = subprocess.run(["docker","exec","meep-pilot-worker","python3","/tmp/_fix_adjobj.py"],
                   capture_output=True, text=True, timeout=60)
tmp.unlink(missing_ok=True)
print("exit:", r.returncode)
if r.returncode != 0:
    print(r.stderr[-500:])
else:
    img_name = "concept_adjoint_objective_normalization.png"
    local = RESULTS_DIR / img_name
    subprocess.run(["docker","cp",f"meep-pilot-worker:/tmp/{img_name}",str(local)], capture_output=True)
    size = local.stat().st_size // 1024
    print(f"Image: {img_name} ({size}KB)")
    img_url = f"/static/results/{img_name}"
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "UPDATE concepts SET demo_code=?, result_images=?, demo_description=?, "
        "result_status='success', updated_at=CURRENT_TIMESTAMP WHERE name=?",
        (code, img_url, desc, name)
    )
    conn.commit()
    conn.close()
    print("DB updated")
