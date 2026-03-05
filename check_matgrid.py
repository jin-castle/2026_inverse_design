# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('db/knowledge.db')
code = conn.execute("SELECT code_snippet FROM patterns WHERE pattern_name='material_grid_adjoint'").fetchone()[0]
# MaterialGrid 호출 부분 출력
lines = code.split('\n')
for i, line in enumerate(lines, 1):
    if 30 <= i <= 50:
        print(f'{i:3d}: {line}')
conn.close()
