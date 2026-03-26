import matplotlib
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
    ax.set_title(f'\u03b2 = {beta}\n({("Smooth" if beta<=4 else "Binarized")})')
    ax.set_xlabel('x'); ax.set_ylabel('y')
    plt.colorbar(im, ax=ax, label='\u03c1_proj')
plt.suptitle('beta_projection: Heaviside Projection P_\u03b2(\u03c1)\n'
             '\u03b2\u2191: Gray\u2192Binary (0/1) binarization', fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/concept_beta_projection.png', dpi=100, bbox_inches='tight')
print("Done")
