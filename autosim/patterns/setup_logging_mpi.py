#!/usr/bin/env python3
"""
Pattern: setup_logging_mpi
MPI-safe logging: FileHandler+StreamHandler only for master process via mp.am_master(), NullHandler for others
"""
import sys, os, time as _time
sys.path.insert(0, "/root/autosim")
from common import *  # silicon, oxide, resolution, RESULT_DIR, etc.

_PATTERN = "setup_logging_mpi"
_t0 = _time.time()

try:
    # ─────────────────────────────────────────────────────────
    # 패턴 코드 (자동 생성)
    # ─────────────────────────────────────────────────────────
    import logging

    def setup_logging(output_dir: Path, stage_name: str) -> logging.Logger:
        """Setup logging to both file and console (master process only)."""
        logger = logging.getLogger(stage_name)
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        # Only add handlers on master process to avoid duplicate output in MPI
        if mp.am_master():
            fh = logging.FileHandler(output_dir / "run.log")
            fh.setLevel(logging.INFO)
            fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(fh)

            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(logging.INFO)
            ch.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(ch)
        else:
            # Non-master processes: add null handler to suppress output
            logger.addHandler(logging.NullHandler())

        return logger
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
