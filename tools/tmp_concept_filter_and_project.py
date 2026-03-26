import matplotlib
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
axes[0].set_title('1. Raw Design \u03c1\n(random initial)')
plt.colorbar(im0, ax=axes[0], label='\u03c1')
im1 = axes[1].imshow(rho_filt, cmap='Greys_r', origin='lower', vmin=0, vmax=1)
axes[1].set_title(f'2. Gaussian Filter (r={r_filter}px)\nFeature size control')
plt.colorbar(im1, ax=axes[1], label='\u03c1_filt')
im2 = axes[2].imshow(rho_proj, cmap='Greys_r', origin='lower', vmin=0, vmax=1)
axes[2].set_title('3. Heaviside Projection (\u03b2=16)\nBinarized structure')
plt.colorbar(im2, ax=axes[2], label='\u03c1_proj')
# Stats
for ax, d in zip(axes, [rho_raw, rho_filt, rho_proj]):
    ax.set_xlabel(f'mean={d.mean():.2f}, std={d.std():.2f}')
plt.suptitle('filter_and_project: Design Field Pipeline\nFilter \u2192 Project (Heaviside)', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_filter_and_project.png', dpi=100, bbox_inches='tight')
print("Done")
