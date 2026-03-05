#!/usr/bin/env python3
"""
Pattern: history_json_format
Standard history dictionary format for adjoint optimization logging. Tracks: fom list, gradient_norm list, beta schedule
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "history_json_format"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    # Initialize history dictionary
    history = {
        'fom':            [],    # FOM value per iteration
        'gradient_norm':  [],    # Gradient norm per iteration
        'beta':           [],    # Beta value per iteration
        'binarization':   [],    # Binarization metric per iteration
        'best_fom':       0.0,   # Best FOM achieved so far
        'best_iteration': 0,     # Iteration index of best FOM
    }

    # Update after each iteration
    def update_history(history, fom, grad_norm, beta, binarization, iteration):
        history['fom'].append(float(fom))
        history['gradient_norm'].append(float(grad_norm))
        history['beta'].append(float(beta))
        history['binarization'].append(float(binarization))
        if fom > history['best_fom']:
            history['best_fom'] = float(fom)
            history['best_iteration'] = iteration

    # Save history to files
    def save_history(history, output_dir: Path):
        # JSON (human readable, for analysis/plotting)
        with open(output_dir / "history.json", "w") as f:
            json.dump(history, f, indent=2)
        # NPY (backward compatibility with older scripts)
        np.save(output_dir / "history.npy", history)

    # Load history (for resume or analysis)
    def load_history(output_dir: Path) -> dict:
        json_path = output_dir / "history.json"
        if json_path.exists():
            with open(json_path) as f:
                return json.load(f)
        return None
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
