import sqlite3
conn = sqlite3.connect('db/knowledge.db')
rows = conn.execute("""SELECT id, error_class, error_type, error_message, symptom, 
    run_mode, device_type, resolution, pml_thickness, wavelength_um, dim,
    uses_adjoint, physics_cause, code_cause, root_cause_chain, original_code
FROM sim_errors_v2 ORDER BY id""").fetchall()
print(f'Total: {len(rows)}')
for row in rows:
    print(f'[{row[0]}] error_class={row[1]}, error_type={row[2]}')
    print(f'  error_message={str(row[3])[:120]}')
    print(f'  symptom={str(row[4])[:80]}')
    print(f'  run_mode={row[5]}, device_type={row[6]}, resolution={row[7]}')
    print(f'  pml_thickness={row[8]}, wavelength_um={row[9]}, dim={row[10]}')
    print(f'  uses_adjoint={row[11]}')
    has_orig = 'yes' if row[15] else 'no'
    print(f'  physics_cause={str(row[12])[:50] if row[12] else None}, code_cause={str(row[13])[:30] if row[13] else None}')
    print(f'  original_code: {has_orig}')
    print()
conn.close()
