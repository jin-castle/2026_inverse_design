# -*- coding: utf-8 -*-
"""Analyze TypeB truncated code endings"""
import json
import ast

with open(r"C:\Users\user\projects\meep-kb\typeb_truncated_codes.json", "r", encoding="utf-8") as f:
    codes = json.load(f)

for eid_str, val in codes.items():
    eid = int(eid_str)
    if not val:
        print(f"ID {eid}: Not found")
        continue
    
    code = val["code"]
    lines = code.split('\n')
    total_lines = len(lines)
    total_chars = len(code)
    
    # Show last 5 lines
    last_lines = lines[-5:]
    print(f"\n=== ID {eid} ({total_chars} chars, {total_lines} lines) ===")
    print(f"Title: {val['title'][:80]}")
    print(f"Last 5 lines:")
    for i, ln in enumerate(last_lines):
        print(f"  {total_lines - 4 + i}: {repr(ln)[:100]}")
    
    # Try to parse
    try:
        ast.parse(code)
        print(f"  Parse: OK")
    except SyntaxError as e:
        print(f"  Parse: SyntaxError at line {e.lineno}: {e.msg}")
    
    # Find last valid line
    valid_cutoff = 0
    for cutoff in range(total_lines, 0, -1):
        candidate = '\n'.join(lines[:cutoff])
        try:
            ast.parse(candidate)
            valid_cutoff = cutoff
            break
        except SyntaxError:
            pass
    print(f"  Last valid line: {valid_cutoff} / {total_lines}")
