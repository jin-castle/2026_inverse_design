# -*- coding: utf-8 -*-
"""Fix TypeE scripts that have truncated code (ends mid-statement)"""
import os
import sys
import ast

WORKDIR = r"C:\Users\user\projects\meep-kb"

# IDs with SyntaxError due to truncation
TRUNCATED_IDS = [336, 368, 395, 403, 533, 588]

def find_last_valid_line(code):
    """Binary search for last valid Python parse point"""
    lines = code.split('\n')
    
    # Try removing lines from the end until it parses
    for cutoff in range(len(lines), 0, -1):
        candidate = '\n'.join(lines[:cutoff])
        try:
            ast.parse(candidate)
            return cutoff, candidate
        except SyntaxError:
            continue
    
    return 0, ""

for eid in TRUNCATED_IDS:
    path = os.path.join(WORKDIR, f"typee_fixed_{eid}.py")
    with open(path, "r", encoding="utf-8") as f:
        full_code = f.read()
    
    # Split header from user code (header ends after plt.show = _patched_show)
    marker = "plt.show = _patched_show\n\n"
    marker_pos = full_code.find(marker)
    if marker_pos == -1:
        print(f"ID {eid}: Cannot find header marker, skipping")
        continue
    
    header = full_code[:marker_pos + len(marker)]
    user_code = full_code[marker_pos + len(marker):]
    
    # Find last valid line
    cutoff, valid_code = find_last_valid_line(user_code)
    
    if cutoff == 0:
        print(f"ID {eid}: No valid code found!")
        continue
    
    total_lines = len(user_code.split('\n'))
    print(f"ID {eid}: {total_lines} lines -> cut to {cutoff} valid lines")
    
    fixed = header + valid_code.rstrip() + "\n"
    
    out_path = os.path.join(WORKDIR, f"typee_fixed_{eid}.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(fixed)
    print(f"  Written: {len(fixed)} chars")
