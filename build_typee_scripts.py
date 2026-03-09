# -*- coding: utf-8 -*-
"""Build fixed TypeE scripts from fetched codes JSON"""
import json
import os
import sys

WORKDIR = r"C:\Users\user\projects\meep-kb"
codes_path = os.path.join(WORKDIR, "typee_codes.json")

with open(codes_path, "r", encoding="utf-8") as f:
    codes = json.load(f)


def strip_markdown(code):
    """
    Strip markdown sections from notebook-derived code.
    Structure uses:
      # [MD]   -> switch to markdown mode (skip until # [CODE])
      # [CODE] -> switch to code mode (include lines)
    Also strips Jupyter magic commands (%matplotlib inline, etc.)
    and IPython imports.
    """
    lines = code.split('\n')
    result = []
    in_markdown = False

    for line in lines:
        stripped = line.strip()
        
        if stripped == '# [MD]':
            in_markdown = True
            continue
        
        if stripped == '# [CODE]':
            in_markdown = False
            continue  # Don't include the marker itself
        
        if in_markdown:
            # Skip all markdown prose lines
            continue
        
        # Strip Jupyter magic commands
        if stripped.startswith('%') or stripped.startswith('!'):
            continue
        
        # Strip IPython display imports (not available in plain Python)
        if 'from IPython' in stripped or 'import IPython' in stripped:
            continue
        
        result.append(line)
    
    return '\n'.join(result)


def test_strip():
    """Test the strip function with sample data"""
    sample = """# [MD]
## Title

Some markdown text here.

Another paragraph.

# [CODE]
import meep as mp
import numpy as np

sim = mp.Simulation()

# [MD]
More markdown description.

# [CODE]
sim.run()
"""
    result = strip_markdown(sample)
    print("TEST RESULT:")
    print(result)
    print("---")
    assert "import meep" in result
    assert "sim.run()" in result
    assert "Some markdown" not in result
    assert "More markdown" not in result
    print("Test passed!")


test_strip()


HEADER_TEMPLATE = '''# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os
os.makedirs('/tmp/kb_results', exist_ok=True)

if '__file__' not in dir():
    __file__ = '/tmp/typee_XIDX.py'

_fig_count = [0]
_orig_show = plt.show
def _patched_show(*a, **kw):
    _n = _fig_count[0]
    plt.savefig('/tmp/kb_results/typee_XIDX_%02d.png' % _n, dpi=80, bbox_inches='tight')
    _fig_count[0] += 1
    plt.close('all')
plt.show = _patched_show

'''

built = []
for eid_str, val in codes.items():
    eid = int(eid_str)
    if not val or not val.get("code"):
        print(f"SKIP {eid}: no code")
        continue
    
    code = val["code"]
    cleaned = strip_markdown(code)
    
    # Remove leading blank lines
    cleaned = cleaned.strip()
    
    header = HEADER_TEMPLATE.replace('XIDX', str(eid))
    full_script = header + cleaned + '\n'
    
    out_path = os.path.join(WORKDIR, f"typee_fixed_{eid}.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_script)
    built.append(eid)
    
    # Show first few lines of code to verify
    code_preview = cleaned[:200].replace('\n', '\\n')
    print(f"Built: typee_fixed_{eid}.py ({len(full_script)} chars) | preview: {code_preview[:80]}")

print(f"\nTotal built: {len(built)}")
