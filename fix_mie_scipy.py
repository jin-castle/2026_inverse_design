# -*- coding: utf-8 -*-
"""Fix PyMieScatt scipy trapz issue by adding monkey-patch to scripts"""
import os

WORKDIR = r"C:\Users\user\projects\meep-kb"
MIE_IDS = [368, 544]

SCIPY_PATCH = """
# Scipy compatibility patch for PyMieScatt (trapz removed in scipy>=1.12)
import scipy.integrate as _si
if not hasattr(_si, 'trapz'):
    import numpy as np
    _si.trapz = np.trapz

"""

for eid in MIE_IDS:
    path = os.path.join(WORKDIR, f"typee_fixed_{eid}.py")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Insert patch after the header (after plt.show = _patched_show)
    marker = "plt.show = _patched_show\n\n"
    insert_pos = content.find(marker) + len(marker)
    
    new_content = content[:insert_pos] + SCIPY_PATCH + content[insert_pos:]
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print(f"Patched ID {eid}: added scipy trapz patch")
