#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json, os

HEADER_TEMPLATE = '''# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os, types

if '__file__' not in dir():
    __file__ = '/tmp/fixed_SCRIPT_ID.py'

_script_id = SCRIPT_ID
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

def write_fixed(id_, code):
    header = HEADER_TEMPLATE.replace('SCRIPT_ID', str(id_))
    content = header + code
    path = os.path.join(OUT_DIR, f'fixed_{id_}.py')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Written fixed_{id_}.py ({len(content)} chars)")

# 406: reduce resolution 128 -> 32 for MPB
code406 = full_data['406']['code']
code406 = code406.replace('resolution = 128', 'resolution = 32  # reduced from 128 for speed')
write_fixed(406, code406)

# 591: reduce resolution 128 -> 32 for MPB (same code as 406 but newer style)
code591 = full_data['591']['code']
code591 = code591.replace('resolution = 128', 'resolution = 32  # reduced from 128 for speed')
write_fixed(591, code591)

print("Done.")
