#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate fixed scripts for failed MEEP examples."""

import json, os, sys

HEADER_TEMPLATE = '''# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os, types

# Fix __file__ issue
if '__file__' not in dir():
    __file__ = '/tmp/fixed_{id}.py'

# Hook plt.show() to save
_fig_count = [0]
_orig_show = plt.show
def _patched_show(*args, **kwargs):
    os.makedirs('/tmp/kb_results', exist_ok=True)
    plt.savefig(f'/tmp/kb_results/fixed_{id}_{{_fig_count[0]:02d}}.png', dpi=80, bbox_inches='tight')
    _fig_count[0] += 1
plt.show = _patched_show

'''

OUT_DIR = r'C:\Users\user\projects\meep-kb'

with open(os.path.join(OUT_DIR, 'full_codes.json'), encoding='utf-8') as f:
    full_data = json.load(f)

def get_code(id_):
    return full_data.get(str(id_), {}).get('code', '')

def write_fixed(id_, code):
    header = HEADER_TEMPLATE.replace('{id}', str(id_))
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

# ID 563
code563 = get_code(563)
code563_fixed = code563.replace('dtype=np.complex_,', 'dtype=np.complex128,')
code563_fixed = code563_fixed.replace('dtype=np.complex_)', 'dtype=np.complex128)')
write_fixed(563, code563_fixed)

# ===== Type B: argparse bypass - ID 521 =====
# Truncated code ends at "args = parser.parse_"
# We construct a fixed main block

code521 = get_code(521)
# Find the if __name__ == "__main__": block
main_idx = code521.find('if __name__ == "__main__":')
if main_idx >= 0:
    code521_body = code521[:main_idx]
else:
    # The argparse block starts before - cut at "parser = argparse.ArgumentParser()"
    parser_idx = code521.find('if __name__ == "__main__":')
    code521_body = code521[:parser_idx] if parser_idx >= 0 else code521

# Append fixed main block
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
# These have correct code, just need MPI speedup

type_c_ids = [
    333, 341, 353, 374, 378, 381, 389, 391, 400, 406,
    410, 505, 513, 526, 528, 539, 548, 554, 559, 562,
    573, 575, 591, 592, 595,
]

# Detect and fix common issues:
# - matplotlib.use('Agg') might be set after import
# - savefig calls to local paths

for id_ in type_c_ids:
    code = get_code(id_)
    if not code:
        print(f"ID {id_}: no code found, skipping")
        continue
    
    # Remove existing matplotlib backend setting if any (we add it in header)
    # and existing matplotlib imports (header handles them)
    lines = code.split('\n')
    filtered = []
    for line in lines:
        # Keep all lines - the header will take care of backend and plt.show hooking
        filtered.append(line)
    code_clean = '\n'.join(filtered)
    
    write_fixed(id_, code_clean)

print(f"\nDone! Generated fixed scripts.")
print("Type B (direct run): 382, 563, 521")
print(f"Type C (MPI): {type_c_ids}")
