#!/usr/bin/env python3
"""
Pattern: plot_dft_mode_profiles
Visualize DFT mode profiles from 3D simulation: (left) 2D |Ey|² heatmap on YZ plane, (right) 1D cross-section profile ov
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "plot_dft_mode_profiles"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    def plot_dft_mode_profiles(results: dict, output_dir: Path):
        """
        Plot DFT time-averaged mode profiles with theoretical comparison.

        Creates two figures:
        - dft_input_mode_profile.png: Input waveguide (should show TE0)
        - dft_output_mode_profile.png: Output waveguide (should show TE1)
        """
        mode_dir = output_dir / "mode_profiles"
        mode_dir.mkdir(exist_ok=True)

        for location in ['input', 'output']:
            dft_key = f'dft_{location}'
            if dft_key not in results:
                continue

            dft_data = results[dft_key]
            Ey_field = dft_data['Ey']  # Complex 2D array (ny, nz)
            y_coords = dft_data['y']
            z_coords = dft_data['z']

            # Extract intensity
            intensity = np.abs(Ey_field) ** 2

            # 1D profile: integrate over z (or take slice at slab center)
            z_center_idx = len(z_coords) // 2
            profile_1d = np.abs(Ey_field[:, z_center_idx])
            if np.max(profile_1d) > 0:
                profile_1d = profile_1d / np.max(profile_1d)

            # Theoretical profiles
            te0_theory = theoretical_te0_profile(y_coords, WAVEGUIDE_WIDTH)
            te1_theory = theoretical_te1_profile(y_coords, WAVEGUIDE_WIDTH)

            # Compute overlaps
            overlap_te0 = compute_overlap(profile_1d, te0_theory, y_coords)
            overlap_te1 = compute_overlap(profile_1d, te1_theory, y_coords)

            # Create figure
            fig, axes = plt.subplots(1, 2, figsize=(14, 5))

            # Left: 2D heatmap (YZ plane)
            ax = axes[0]
            extent = [y_coords[0], y_coords[-1], z_coords[0], z_coords[-1]]
            im = ax.imshow(
                intensity.T,
                origin='lower',
                aspect='auto',
                extent=extent,
                cmap='hot'
            )
            ax.set_xlabel('Y (µm)')
            ax.set_ylabel('Z (µm)')
            ax.set_title(f'{location.capitalize()} DFT |Ey|² (YZ plane)')
            plt.colorbar(im, ax=ax, label='Intensity')

            # Waveguide boundary lines
            ax.axvline(-WAVEGUIDE_WIDTH/2, color='white', linestyle='--', alpha=0.7)
            ax.axvline(WAVEGUIDE_WIDTH/2, color='white', linestyle='--', alpha=0.7)

            # Right: 1D profile comparison
            ax = axes[1]
            ax.plot(y_coords, profile_1d, 'b-', linewidth=2, label='Simulated')
            ax.plot(y_coords, te0_theory, 'g--', linewidth=1.5,
                    label=f'TE0 theory (overlap={overlap_te0:.3f})')
            ax.plot(y_coords, te1_theory, 'r--', linewidth=1.5,
                    label=f'TE1 theory (overlap={overlap_te1:.3f})')
            ax.axvline(-WAVEGUIDE_WIDTH/2, color='gray', linestyle=':', alpha=0.5)
            ax.axvline(WAVEGUIDE_WIDTH/2, color='gray', linestyle=':', alpha=0.5)
            ax.set_xlabel('Y (µm)')
            ax.set_ylabel('Normalized |Ey|')
            ax.set_title(f'{location.capitalize()} Mode Profile (z=slab center)')
            ax.legend(loc='upper right')
            ax.grid(True, alpha=0.3)
            ax.set_xlim([y_coords[0], y_coords[-1]])
            ax.set_ylim([0, 1.1])

            plt.tight_layout()
            plt.savefig(mode_dir / f'dft_{location}_mode_profile.png',
                        dpi=150, bbox_inches='tight')
            plt.close()
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
