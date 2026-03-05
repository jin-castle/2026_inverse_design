import sqlite3
conn = sqlite3.connect('/app/db/knowledge.db')
rows = conn.execute('SELECT id, pattern_name, length(description), length(code_snippet), author_repo FROM patterns ORDER BY id').fetchall()
missing_desc = [r for r in rows if r[2] is None or r[2] < 80]
missing_code = [r for r in rows if r[3] is None or r[3] < 200]
print(f'Total: {len(rows)}')
print(f'Short description (<80): {len(missing_desc)}')
print(f'Short code (<200): {len(missing_code)}')
print()
key_names = ('dft_fields_extraction','adjoint_solver_basics','adjoint_optimization_problem','dft_field_monitor_3d','plot_dft_mode_profiles','adjoint_waveguide_bend_optimization')
for name in key_names:
    r = conn.execute("SELECT id, pattern_name, description, length(code_snippet) FROM patterns WHERE pattern_name=?", (name,)).fetchone()
    if r:
        print(f'[{r[0]}] {r[1]}')
        print(f'  desc: {r[2][:120]}')
        print(f'  code_len: {r[3]}')
        print()
