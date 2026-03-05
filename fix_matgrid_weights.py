# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('db/knowledge.db')
code = conn.execute("SELECT code_snippet FROM patterns WHERE pattern_name='material_grid_adjoint'").fetchone()[0]

OLD = '''        matgrid = mp.MaterialGrid(mp.Vector3(Nx,Ny),
                                  mp.air,
                                  mp.Medium(index=3.5),
                                  do_averaging=True,
                                  beta=1000,
                                  eta=0.5)'''

NEW = '''        matgrid = mp.MaterialGrid(mp.Vector3(Nx,Ny),
                                  mp.air,
                                  mp.Medium(index=3.5),
                                  weights=filtered_design_params,
                                  do_averaging=True,
                                  beta=1000,
                                  eta=0.5)'''

if OLD in code:
    fixed = code.replace(OLD, NEW)
    conn.execute("UPDATE patterns SET code_snippet=? WHERE pattern_name='material_grid_adjoint'", (fixed,))
    conn.commit()
    print("[FIXED] weights=filtered_design_params 추가")
else:
    print("[WARN] 패턴 매칭 실패")
    for i, line in enumerate(code.split('\n')[30:40], start=31):
        print(f"  {i}: {repr(line)}")
conn.close()
