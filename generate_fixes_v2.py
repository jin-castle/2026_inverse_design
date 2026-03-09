#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate fixed scripts for failed MEEP examples - V2 with correct f-string."""

import json, os, sys

# Fix: use _script_id variable instead of direct f-string id interpolation
HEADER_TEMPLATE = '''# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os, types

# Fix __file__ issue
if '__file__' not in dir():
    __file__ = '/tmp/fixed_SCRIPT_ID.py'

_script_id = SCRIPT_ID

# Hook plt.show() to save
_fig_count = [0]
_orig_show = plt.show
def _patched_show(*args, **kwargs):
    os.makedirs('/tmp/kb_results', exist_ok=True)
    plt.savefig(f'/tmp/kb_results/fixed_{_script_id}_{_fig_count[0]:02d}.png', dpi=80, bbox_inches='tight')
    _fig_count[0] += 1
plt.show = _patched_show

'''

OUT_DIR = r'C:\Users\user\projects\meep-kb'

with open(os.path.join(OUT_DIR, 'full_codes.json'), encoding='utf-8') as f:
    full_data = json.load(f)

def get_code(id_):
    return full_data.get(str(id_), {}).get('code', '')

def write_fixed(id_, code):
    header = HEADER_TEMPLATE.replace('SCRIPT_ID', str(id_))
    content = header + code
    path = os.path.join(OUT_DIR, f'fixed_{id_}.py')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Written fixed_{id_}.py ({len(content)} chars)")

# ===== Type B: np.complex_ fixes =====

# ID 382
code382 = get_code(382)
code382_fixed = code382.replace('dtype=np.complex_)', 'dtype=np.complex128)')
code382_fixed = code382_fixed.replace('dtype=np.complex_,', 'dtype=np.complex128,')
write_fixed(382, code382_fixed)

# ===== Type B: argparse bypass - ID 521 =====
code521 = get_code(521)
main_idx = code521.find('if __name__ == "__main__":')
if main_idx >= 0:
    code521_body = code521[:main_idx]
else:
    code521_body = code521

main_block = '''
if __name__ == "__main__":
    # Fixed: bypass argparse with defaults
    dipole_pol = "x"
    dipole_pos_r = 0.1

    # For x-polarized dipole, use m = -1 and m = +1
    radial_flux = np.zeros(NUM_FARFIELD_PTS)
    for m in [-1, 1]:
        e_plus, h_plus, e_minus, h_minus = dipole_in_vacuum(dipole_pol, dipole_pos_r, m)
        radial_flux += radiation_pattern(e_plus, h_plus)
        radial_flux += radiation_pattern(e_minus, h_minus)

    plot_radiation_pattern(dipole_pol, radial_flux)
    plt.show()
    print("Done: dipole radiation pattern computed successfully.")
'''

code521_fixed = code521_body + main_block
write_fixed(521, code521_fixed)

# ===== Type C: Timeout -> MPI rerun (just add header) =====
type_c_ids = [
    333, 341, 353, 374, 378, 381, 389, 391, 400, 406,
    410, 505, 513, 526, 528, 539, 548, 554, 559, 562,
    573, 575, 591, 592, 595,
]

for id_ in type_c_ids:
    code = get_code(id_)
    if not code:
        print(f"ID {id_}: no code found, skipping")
        continue
    # Remove from __future__ imports (Python 2 compat, not needed in Python 3)
    # and remove duplicate matplotlib.use() calls
    lines = code.split('\n')
    clean_lines = []
    for line in lines:
        if line.strip().startswith('from __future__'):
            continue  # skip, Python 3 doesn't need this
        clean_lines.append(line)
    code_clean = '\n'.join(clean_lines)
    write_fixed(id_, code_clean)

# ID 563 is special - uses plt.savefig directly, not plt.show
# But we still need to wrap and copy the files
code563 = get_code(563)
code563_fixed = code563.replace('dtype=np.complex_,', 'dtype=np.complex128,')
code563_fixed = code563_fixed.replace('dtype=np.complex_)', 'dtype=np.complex128)')
# Add code to copy savefig outputs to kb_results
code563_fixed += '''
# Copy saved files to kb_results
import shutil, glob
os.makedirs('/tmp/kb_results', exist_ok=True)
for i, src in enumerate(['ring_err.png', 'ring_ez.png', 'ring_ez_dft.png']):
    if os.path.exists(src):
        dst = f'/tmp/kb_results/fixed_563_{i:02d}.png'
        shutil.copy2(src, dst)
        print(f"Copied {src} -> {dst}")
'''
write_fixed(563, code563_fixed)

print(f"\nDone! Generated fixed scripts.")
print("Type B (direct run): 382, 563, 521")
print(f"Type C (MPI): {type_c_ids}")
