# -*- coding: utf-8 -*-
"""Build TypeB_truncated fixed scripts"""
import json
import os
import ast

WORKDIR = r"C:\Users\user\projects\meep-kb"

with open(os.path.join(WORKDIR, "typeb_truncated_codes.json"), "r", encoding="utf-8") as f:
    codes = json.load(f)

def strip_markdown(code):
    """Strip # [MD] sections"""
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
            continue
        if in_markdown:
            continue
        if stripped.startswith('%') or stripped.startswith('!'):
            continue
        if 'from IPython' in stripped or 'import IPython' in stripped:
            continue
        result.append(line)
    return '\n'.join(result)

def find_last_valid_line(code):
    """Find last line where code parses successfully"""
    lines = code.split('\n')
    for cutoff in range(len(lines), 0, -1):
        candidate = '\n'.join(lines[:cutoff])
        try:
            ast.parse(candidate)
            return cutoff, candidate
        except SyntaxError:
            pass
    return 0, ""

HEADER = """# -*- coding: utf-8 -*-
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os
os.makedirs('/tmp/kb_results', exist_ok=True)

if '__file__' not in dir():
    __file__ = '/tmp/typeb_XIDX.py'

_fig_count = [0]
_orig_show = plt.show
def _patched_show(*a, **kw):
    _n = _fig_count[0]
    plt.savefig('/tmp/kb_results/typeb_XIDX_%02d.png' % _n, dpi=80, bbox_inches='tight')
    _fig_count[0] += 1
    plt.close('all')
plt.show = _patched_show

"""

results = {"built": [], "skipped": []}

for eid_str, val in codes.items():
    eid = int(eid_str)
    if not val or not val["code"]:
        print(f"ID {eid}: No code, skipping")
        results["skipped"].append({"id": eid, "reason": "no code"})
        continue
    
    code = val["code"]
    title = val.get("title", "")
    
    print(f"\n=== ID {eid}: {title[:60]} ===")
    
    # ID 269 is a library file - not standalone runnable
    if eid == 269:
        print(f"  SKIP: library file (visualization.py), not a standalone script")
        results["skipped"].append({"id": eid, "reason": "library file, not a standalone simulation script"})
        continue
    
    # Strip markdown if TypeE-like structure
    has_md = '# [MD]' in code or '# [CODE]' in code
    if has_md:
        print(f"  Stripping markdown sections...")
        code = strip_markdown(code)
    
    # Truncate to last valid parse point
    lines = code.split('\n')
    cutoff, valid_code = find_last_valid_line(code)
    total_lines = len(lines)
    
    if cutoff == 0:
        print(f"  SKIP: no valid Python code found")
        results["skipped"].append({"id": eid, "reason": "no valid Python code"})
        continue
    
    print(f"  Lines: {total_lines} -> truncated to {cutoff} valid lines")
    
    # Build script
    header = HEADER.replace("XIDX", str(eid))
    
    # Special handling for test files (428)
    if eid == 428:
        # Add unittest runner
        script = header + valid_code.rstrip() + "\n\n# Run tests\nimport unittest\nif __name__ == '__main__':\n    unittest.main(verbosity=2, exit=False)\n"
    else:
        script = header + valid_code.rstrip() + "\n"
    
    out_path = os.path.join(WORKDIR, f"typeb_fixed_{eid}.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(script)
    
    results["built"].append(eid)
    print(f"  Written: {len(script)} chars -> {out_path}")

print(f"\nBuilt: {results['built']}")
print(f"Skipped: {results['skipped']}")
