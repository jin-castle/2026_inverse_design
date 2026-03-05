# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('db/knowledge.db')

# WarmRestarter - Tuple 사용 확인
for pname in ['WarmRestarter', 'BacktrackingLineSearch', 'material_grid_adjoint']:
    code = conn.execute('SELECT code_snippet FROM patterns WHERE pattern_name=?', (pname,)).fetchone()[0]
    print(f'\n=== {pname} (first 30 lines) ===')
    for i, line in enumerate(code.split('\n')[:30], 1):
        print(f'{i:3d}: {line}')

conn.close()
