# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('db/knowledge.db')
code = conn.execute("SELECT code_snippet FROM patterns WHERE pattern_name='material_grid_adjoint'").fetchone()[0]

for i, line in enumerate(code.split('\n'), 1):
    if 'MaterialGrid' in line or 'design_param' in line or 'weight' in line or 'filtered' in line:
        print(f'{i}: {line}')

# weights로 교체 시도
fixed = code.replace('design_parameters=filtered_design_params', 'weights=filtered_design_params')
if fixed != code:
    conn.execute("UPDATE patterns SET code_snippet=? WHERE pattern_name='material_grid_adjoint'", (fixed,))
    conn.commit()
    print('\n[FIXED] design_parameters -> weights')
else:
    print('\n[NO CHANGE] design_parameters not found (already removed?)')
    # filtered_design_params 확인
    if 'filtered_design_params' in code:
        idx = code.find('filtered_design_params')
        print(f'  filtered_design_params context: {repr(code[max(0,idx-30):idx+50])}')
conn.close()
