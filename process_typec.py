#!/usr/bin/env python3
"""Apply standard fixes to TypeC scripts and write fixed versions."""
import json
import re
import os

with open(r"C:\Users\user\projects\meep-kb\typec_codes.json", "r", encoding="utf-8") as f:
    data = json.load(f)

OUTPUT_DIR = r"C:\Users\user\projects\meep-kb"

def fix_script(eid, code):
    """Apply all standard fixes to a script."""
    
    # 1. Replace np.complex_ with np.complex128
    code = code.replace("np.complex_", "np.complex128")
    code = code.replace("numpy.complex_", "np.complex128")
    
    # 2. Fix get_array(vol, component=X) -> get_array(component=X, vol=vol)
    # Pattern: get_array(vol_var, component=X) or get_array(some_vol, component=...)
    code = re.sub(
        r'get_array\(([^,\)]+),\s*(component\s*=\s*[^,\)]+)\)',
        r'get_array(\2, vol=\1)',
        code
    )
    # Also handle: get_array(vol_var, component=X, ...) with more args
    code = re.sub(
        r'get_array\(([^,\)]+),\s*(component\s*=\s*[^,\)]+),\s*',
        r'get_array(\2, vol=\1, ',
        code
    )
    
    # 3. Remove "from __future__ import division"
    code = re.sub(r'^\s*from\s+__future__\s+import\s+division\s*\n', '', code, flags=re.MULTILINE)
    
    # 4. Strip # [MD] markdown sections
    # Remove lines that start with # [MD] and the content between them
    code = re.sub(r'#\s*\[MD\].*?(?=#\s*\[MD\]|$)', '', code, flags=re.DOTALL)
    code = re.sub(r'#\s*\[MD\][^\n]*\n', '', code)
    
    # 5. Replace plt.show() with plt.savefig(...)
    # We need a counter for multiple saves per script
    # Use a regex with a function to add counter
    fig_counter = [0]
    def replace_show(m):
        fig_counter[0] += 1
        return f"plt.savefig(f'/tmp/kb_results/typec_{eid}_{fig_counter[0]}.png'); plt.close()"
    code = re.sub(r'plt\.show\(\)', replace_show, code)
    
    # 6. Add matplotlib.use('Agg') before any matplotlib import
    # Find first matplotlib import line
    lines = code.split('\n')
    new_lines = []
    agg_inserted = False
    import_os_found = False
    
    for i, line in enumerate(lines):
        # Check if we need to insert matplotlib.use('Agg') before matplotlib imports
        if not agg_inserted and re.match(r'\s*import\s+matplotlib|import\s+pylab', line):
            new_lines.append("import matplotlib")
            new_lines.append("matplotlib.use('Agg')")
            agg_inserted = True
        elif not agg_inserted and re.match(r'\s*from\s+matplotlib', line):
            new_lines.append("import matplotlib")
            new_lines.append("matplotlib.use('Agg')")
            agg_inserted = True
        
        if re.match(r'\s*import\s+os', line):
            import_os_found = True
        
        new_lines.append(line)
    
    code = '\n'.join(new_lines)
    
    # 7. Add os.makedirs('/tmp/kb_results', exist_ok=True) at top
    # Add after imports section - find first non-import, non-comment line
    lines = code.split('\n')
    header_lines = []
    body_lines = []
    in_header = True
    makedirs_added = False
    import_os_added = False
    
    for line in lines:
        stripped = line.strip()
        if in_header and (
            stripped == '' or
            stripped.startswith('#') or
            stripped.startswith('import ') or
            stripped.startswith('from ') or
            stripped.startswith('matplotlib.use')
        ):
            header_lines.append(line)
        else:
            if in_header:
                in_header = False
                # Add os import if not already present
                if not import_os_found:
                    header_lines.append("import os")
                header_lines.append("os.makedirs('/tmp/kb_results', exist_ok=True)")
                makedirs_added = True
            body_lines.append(line)
    
    if not makedirs_added:
        # If script is all header, add at end of header
        if not import_os_found:
            header_lines.append("import os")
        header_lines.append("os.makedirs('/tmp/kb_results', exist_ok=True)")
    
    code = '\n'.join(header_lines + body_lines)
    
    return code


for eid_str, info in data.items():
    eid = int(eid_str)
    title = info['title']
    code = info['code']
    
    fixed = fix_script(eid, code)
    
    out_path = os.path.join(OUTPUT_DIR, f"typec_fixed_{eid}.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(fixed)
    
    print(f"  ID {eid}: {title} -> {out_path}")

print(f"\nDone! Wrote {len(data)} fixed scripts.")
